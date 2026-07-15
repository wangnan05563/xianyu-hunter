"""应用启动与关闭钩子

将 app.py 中的调度器启动、DB 迁移、优雅关闭逻辑抽离，
使 app.py 仅保留路由注册和核心端点定义。
"""
from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any

from fastapi import FastAPI


# 调度器后台任务引用（用于 shutdown 时优雅停止）
_scheduler_task: asyncio.Task | None = None

# Cookie 定时同步调度器引用（用于 shutdown 时优雅停止）
_cookie_sync_scheduler = None

# 批量采集调度器引用（用于 shutdown 时优雅停止 + API 端点访问）
_batch_refresh_scheduler = None

# 智能客服知识库定时刷新调度器引用（用于 shutdown 时优雅停止）
# 为什么单独持有：KBRefreshScheduler 内部用 BackgroundScheduler，
# 必须在应用关闭时显式 shutdown(wait=True) 避免知识库构建被中断导致状态不一致
_kb_refresh_scheduler = None

# 接管超时清理调度器引用（用于 shutdown 时优雅停止）
# 为什么独立于 with_browser 模式：本调度器只读/写 DB，不依赖浏览器实例，
# 即使 Web 进程（with_browser=False）也需启动，避免订单永久卡在 takeover_pending
_takeover_timeout_scheduler = None

# EventBus 主循环后台任务引用（用于 shutdown 时优雅停止）
# 为什么独立于 _scheduler_task：EventBus 是事件分发基础设施，
# 不应与"是否有 RUNNING 任务"耦合。原实现把 run_forever() 放在
# _scheduler_loop 内部，导致 collector=None 或启动时无 RUNNING 任务时
# EventBus 永不启动，后续 API resume/restart 任务时 worker.publish_nowait
# 事件入队但无消费者，NotifierHub 收不到 EVAL_PASSED，钉钉等通知失效
_event_bus_task: asyncio.Task | None = None


def get_batch_refresh_scheduler():
    """供 api_batch_refresh 路由获取调度器实例"""
    return _batch_refresh_scheduler


async def _call_official_collect(
    container: Any, item_id: str, task_id: str | None = None
) -> dict[str, Any]:
    """P1: 官方采集回调包装，延迟导入避免循环依赖

    worker 通过此回调对通过评估的商品做官方采集深度验证，
    实际逻辑委托给 api_evaluations._collect_official_and_evaluate。
    """
    from xianyu_hunter.web.routes.api_evaluations import _collect_official_and_evaluate
    return await _collect_official_and_evaluate(container, item_id, task_id)


def start_cookie_sync_scheduler(container: Any) -> None:
    """启动 Cookie 定时同步调度器（如果配置启用）

    独立于项目主任务调度器，使用 APScheduler BackgroundScheduler 运行。
    仅当 browser.auto_sync=true 时启动。
    """
    global _cookie_sync_scheduler
    from loguru import logger
    from xianyu_hunter.infra.yaml_config import get_config
    from xianyu_hunter.modules.cookie_sync_scheduler import CookieSyncScheduler

    cfg = get_config()
    if not cfg.browser.auto_sync:
        logger.info("Cookie 自动同步未启用（browser.auto_sync=false）")
        return

    _cookie_sync_scheduler = CookieSyncScheduler(
        cookie_store=container.cookie_store,
        auto_sync_interval=cfg.browser.auto_sync_interval,
        expiry_threshold=cfg.browser.auto_sync_expiry_threshold,
        cdp_port=cfg.browser.cdp_port,
    )
    _cookie_sync_scheduler.start()


def start_batch_refresh_scheduler(container: Any) -> None:
    """启动批量采集调度器（如果配置启用且 collector 可用）

    仅当 XH_WITH_SCHEDULER=1（collector 非 None）且 batch_refresh.enabled=true 时启动。
    为什么需要 collector：调度器调用 collector.detail() 采集商品详情，
    Web 进程 with_browser=False 时 collector 为 None，无法采集。
    """
    global _batch_refresh_scheduler
    from loguru import logger
    from xianyu_hunter.infra.yaml_config import get_config
    from xianyu_hunter.modules.batch_refresh_scheduler import BatchRefreshScheduler

    cfg = get_config()
    if not cfg.batch_refresh.enabled:
        logger.info("批量采集调度器未启用（batch_refresh.enabled=false）")
        return

    # 关键约束：collector 为 None 时不启动（Web 进程 with_browser=False）
    if container.collector is None:
        logger.info("批量采集调度器未启动（collector 未初始化，需 XH_WITH_SCHEDULER=1）")
        return

    _batch_refresh_scheduler = BatchRefreshScheduler(
        container=container,
        config=cfg.batch_refresh,
    )
    # 传入主事件循环：调度器在 BackgroundScheduler 线程中通过
    # run_coroutine_threadsafe 提交 async 采集任务到主循环执行
    # get_running_loop：startup 事件中事件循环一定在运行，比 get_event_loop 更明确
    _batch_refresh_scheduler.start(asyncio.get_running_loop())


def start_kb_refresh_scheduler(container: Any) -> None:
    """启动智能客服知识库定时刷新调度器（如果 chatbot 启用且 kb.auto_update_enabled=true）

    独立于批量采集调度器：本调度器仅扫描 docs/ 和 src/ 目录构建知识库，
    不依赖浏览器/collector，因此 Web 进程（with_browser=False）也可启动。

    为什么不依赖 collector：KB 构建只读文件系统 + 调用 OpenAI Embedding API，
    不涉及闲鱼页面采集，无需浏览器实例。
    """
    global _kb_refresh_scheduler
    from loguru import logger

    # chatbot 子容器为 None：chromadb 未安装或 chatbot.enabled=false
    if container.chatbot is None:
        logger.info("智能客服未启用，知识库调度器不启动（container.chatbot=None）")
        return

    kb_scheduler = container.chatbot.get("kb_scheduler")
    if kb_scheduler is None:
        logger.warning("chatbot 子容器缺少 kb_scheduler 实例，跳过启动")
        return

    try:
        # get_running_loop：startup 事件中事件循环一定在运行
        kb_scheduler.start(asyncio.get_running_loop())
        _kb_refresh_scheduler = kb_scheduler
    except Exception:  # noqa: BLE001
        # 启动失败不阻断应用：用户仍可手动通过 POST /api/chatbot/kb/rebuild 触发构建
        logger.exception("知识库定时刷新调度器启动失败")


def start_takeover_timeout_scheduler(container: Any) -> None:
    """启动接管超时清理调度器

    独立于 with_browser 模式：本调度器只读/写 DB，不依赖浏览器实例，
    即使 Web 进程（with_browser=False）也需启动，避免订单永久卡在 takeover_pending。

    超时阈值复用 api_orders.TAKEOVER_TIMEOUT_MIN（30 分钟），
    与 list_orders 中 takeover_deadline 计算保持一致。
    扫描间隔默认 5 分钟，平衡时效性与 DB 开销。
    """
    global _takeover_timeout_scheduler
    from loguru import logger
    from xianyu_hunter.modules.takeover_timeout_scheduler import TakeoverTimeoutScheduler
    from xianyu_hunter.web.routes.api_orders import TAKEOVER_TIMEOUT_MIN

    try:
        _takeover_timeout_scheduler = TakeoverTimeoutScheduler(
            container=container,
            timeout_min=TAKEOVER_TIMEOUT_MIN,
        )
        _takeover_timeout_scheduler.start()
    except Exception:  # noqa: BLE001
        # 启动失败不阻断应用：用户仍可通过手动修改订单状态处理超时
        logger.exception("接管超时清理调度器启动失败")


def start_event_bus_in_background(container: Any) -> None:
    """独立启动 EventBus 主循环（与调度器解耦）

    为什么独立于 start_scheduler_in_background：原实现把 run_forever()
    放在 _scheduler_loop 内部，导致两个隐患：
    1. collector 为 None（with_browser=False）时直接 return，EventBus 不启动
    2. 启动时无 RUNNING 任务时直接 return，EventBus 不启动
    后续通过 API resume/restart 任务时 EventBus 仍不会启动，
    worker.publish_nowait(EVAL_PASSED) 事件入队但无消费者，NotifierHub
    永远收不到事件，钉钉等通知永远不触发。抽离后只要调度器模式开启
    即无条件启动 EventBus，根治此问题。
    """
    global _event_bus_task
    from loguru import logger

    # 幂等防护：已在运行则跳过，避免重复启动产生多个消费者竞争同一队列
    if _event_bus_task is not None and not _event_bus_task.done():
        logger.info("EventBus 已在运行，跳过重复启动")
        return

    async def _bus_loop() -> None:
        try:
            logger.info("EventBus 主循环启动")
            await container.event_bus.run_forever()
        except asyncio.CancelledError:
            logger.info("EventBus 正在停止...")
            raise
        except Exception:  # noqa: BLE001
            # run_forever 内部已隔离 handler 异常，此处兜底防止 task 静默退出
            logger.exception("EventBus 主循环异常退出")

    _event_bus_task = asyncio.create_task(_bus_loop())


async def start_scheduler_in_background(container: Any) -> None:
    """在 FastAPI 事件循环中启动调度器后台任务

    从 DB 加载 RUNNING 任务 → 注册到 Scheduler → 启动循环。

    注意：EventBus 主循环已解耦到 start_event_bus_in_background，
    本函数不再负责启动 EventBus，避免"无 RUNNING 任务 → EventBus 不启动"
    的链式失败。
    """
    from loguru import logger
    from xianyu_hunter.modules.worker import TaskWorker
    from xianyu_hunter.infra.yaml_config import get_config

    if not container.collector:
        logger.warning("调度器模式需要浏览器，但 collector 未初始化（请确认已登录闲鱼）")
        return

    # 启动浏览器实例（BrowserManager 已创建但未 start，必须在调度器和 live 端点使用前完成）
    if container.browser:
        try:
            await container.browser.start()
            logger.info("浏览器实例已就绪")
        except Exception as e:
            logger.error("浏览器启动失败: %s（实时搜索功能将不可用）", e)
            # 不 return——允许其他功能继续工作，只是实时搜索不可用

    # 读取全局配置作为基线（任务级覆盖会合并到此之上）
    app_cfg = get_config()
    search_cfg = app_cfg.search
    price_cfg = app_cfg.price_strategy
    logger.info(
        f"全局配置: search(page_size={search_cfg.page_size}, sort_type={search_cfg.sort_type}, "
        f"timeout={search_cfg.timeout}s), price(max={price_cfg.max_price}, min={price_cfg.min_price})"
    )

    raw_tasks = container.repo.list_tasks()
    workers: list[TaskWorker] = []
    for raw in raw_tasks:
        # Worker 构造逻辑统一委托给 container.build_worker_from_raw_task
        # 避免与 __main__.py 的 CLI 入口代码重复，保持任务级配置覆盖逻辑一致
        worker = container.build_worker_from_raw_task(raw)
        if worker is None:
            continue
        await container.scheduler.register(worker.task, worker)
        workers.append(worker)

    if not workers:
        logger.info("调度器: 无 RUNNING 任务，跳过启动")
        return

    async def _scheduler_loop() -> None:
        """调度器主循环：启动所有任务

        EventBus 消费已解耦到 start_event_bus_in_background，本循环只负责
        保持调度器运行；移除原 bus_task 状态检测，因为 EventBus 异常退出
        已在 _bus_loop 内部记录日志，无需此处重复告警。
        """
        try:
            container.scheduler.start_all()
            task_ids = [w.task.id for w in workers]
            logger.info(f"调度器已启动 {len(task_ids)} 个任务: {task_ids}")
            # 保持运行直到被取消
            stop_event = asyncio.Event()
            await stop_event.wait()
        except asyncio.CancelledError:
            logger.info("调度器正在停止...")
            await container.scheduler.stop_all()
            logger.info("调度器已停止")
            # 重新抛出以传播取消信号，符合 S7497
            raise

    global _scheduler_task
    _scheduler_task = asyncio.create_task(_scheduler_loop())


def _migrate_task_links_table(container: Any, insp: Any) -> None:
    """C-01: task_links 表重建（含 UNIQUE 约束）+ 历史数据回填

    为什么独立：原 run_migrations 中 6 个迁移块的 try/except 链使主函数
    认知复杂度超过阈值，拆分后每个迁移块独立维护，主函数只负责顺序调用。
    """
    from loguru import logger
    from sqlalchemy import text as sa_text
    from xianyu_hunter.infra.db_models import TaskLinkRow

    try:
        needs_rebuild = False
        if not insp.has_table("task_links"):
            # 表不存在，create_all 会建
            needs_rebuild = False
        else:
            # 表存在，检查是否有 uq_task_link 唯一约束
            uq_names = {uq["name"] for uq in insp.get_unique_constraints("task_links")}
            if "uq_task_link" not in uq_names:
                needs_rebuild = True
                logger.info("task_links 缺少 UNIQUE 约束，将重建表")

        if needs_rebuild:
            # C-03 修复：DROP 前记录数据量，避免静默丢失
            with container.repo.engine.connect() as conn:
                count_result = conn.execute(sa_text("SELECT COUNT(*) FROM task_links")).scalar()
                logger.warning(
                    f"task_links 缺少 UNIQUE 约束，将重建表（当前 {count_result} 条数据将被清除）"
                )
            with container.repo.engine.begin() as conn:
                conn.exec_driver_sql("DROP TABLE IF EXISTS task_links")
            TaskLinkRow.__table__.create(container.repo.engine, checkfirst=True)
            logger.info("task_links 表已重建（含 UNIQUE 约束）")
        else:
            # 确保表存在（首次启动时）
            TaskLinkRow.__table__.create(container.repo.engine, checkfirst=True)

        inserted = container.repo.auto_migrate_task_links()
        logger.info(f"task_links auto-migrate: 新增 {inserted} 条")
    except Exception as e:  # noqa: BLE001
        # 为什么用 exc_info=True 而非 logger.exception：
        # 迁移失败是已知可降级场景，保持 WARNING 级别避免误触发告警，
        # 但必须保留完整 traceback 便于定位根因（违反 meta-rule #26 会丢失堆栈）
        logger.warning("C-01 task_links 迁移失败（忽略，不影响后续迁移）: {}", e, exc_info=True)


def _migrate_orders_task_id(container: Any, insp: Any) -> None:
    """C-02 迁移：确保 orders 表含 task_id 列"""
    from loguru import logger

    try:
        if insp.has_table("orders"):
            order_cols = {c["name"] for c in insp.get_columns("orders")}
            if "task_id" not in order_cols:
                with container.repo.engine.begin() as conn:
                    conn.exec_driver_sql(
                        "ALTER TABLE orders ADD COLUMN task_id TEXT DEFAULT NULL"
                    )
                logger.info("orders 表已新增 task_id 列（C-02 迁移）")
    except Exception as e:  # noqa: BLE001
        # 保留 WARNING 级别但附加 traceback，见 C-01 注释
        logger.warning("C-02 orders.task_id 迁移失败（忽略）: {}", e, exc_info=True)


def _migrate_tasks_search_filters(container: Any, insp: Any) -> None:
    """C-03 迁移：确保 tasks 表含 search_filters 列（闲鱼筛选标签）"""
    from loguru import logger

    try:
        if insp.has_table("tasks"):
            task_cols = {c["name"] for c in insp.get_columns("tasks")}
            if "search_filters" not in task_cols:
                with container.repo.engine.begin() as conn:
                    conn.exec_driver_sql(
                        "ALTER TABLE tasks ADD COLUMN search_filters TEXT DEFAULT NULL"
                    )
                logger.info("tasks 表已新增 search_filters 列（C-03 迁移）")
    except Exception as e:  # noqa: BLE001
        logger.warning("C-03 tasks.search_filters 迁移失败（忽略）: {}", e, exc_info=True)


def _migrate_notifications_read_at(container: Any, insp: Any) -> None:
    """C-04 迁移：确保 notifications 表含 read_at 列

    关键迁移：缺此列会导致 add_notification 的 UPSERT 完全失败，所有告警丢失
    """
    from loguru import logger

    try:
        if insp.has_table("notifications"):
            notif_cols = {c["name"] for c in insp.get_columns("notifications")}
            if "read_at" not in notif_cols:
                with container.repo.engine.begin() as conn:
                    conn.exec_driver_sql(
                        "ALTER TABLE notifications ADD COLUMN read_at DATETIME DEFAULT NULL"
                    )
                logger.info("notifications 表已新增 read_at 列（C-04 迁移）")
    except Exception as e:  # noqa: BLE001
        logger.warning("C-04 notifications.read_at 迁移失败（忽略）: {}", e, exc_info=True)


def _migrate_eval_scored_dedup(container: Any, insp: Any) -> None:
    """C-05 迁移：eval.scored 事件去重 + 添加部分唯一索引

    防止 live_links 多次触发或 recompute 多次调用产生重复评估记录
    """
    from loguru import logger

    try:
        if insp.has_table("events"):
            with container.repo.engine.begin() as conn:
                # 1. 清理已有的重复 eval.scored 记录（每个 task_id+item_id 只保留最新一条）
                conn.exec_driver_sql("""
                    DELETE FROM events
                    WHERE id NOT IN (
                        SELECT MAX(id) FROM events
                        WHERE type = 'eval.scored'
                        GROUP BY task_id, item_id
                    )
                    AND type = 'eval.scored'
                """)
                # 2. 创建部分唯一索引（仅对 eval.scored 类型生效）
                conn.exec_driver_sql(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_eval_scored_unique "
                    "ON events (task_id, item_id) WHERE type = 'eval.scored'"
                )
            logger.info("eval.scored 事件去重 + 唯一索引已创建（C-05 迁移）")
    except Exception as e:  # noqa: BLE001
        logger.warning("C-05 eval.scored 去重迁移失败（忽略）: {}", e, exc_info=True)


def _cleanup_old_batch_history(container: Any) -> None:
    """C-06: 清理过期的批量采集执行历史

    为什么放这里：init_db 已通过 create_all 创建 batch_refresh_history 表，
    此处根据配置 history_retention_days 清理过期记录，避免磁盘无限增长。
    """
    from loguru import logger

    try:
        from xianyu_hunter.infra.yaml_config import get_config
        days = get_config().batch_refresh.history_retention_days
        if days > 0:
            deleted = container.repo.cleanup_old_batch_refresh_history(days)
            if deleted > 0:
                logger.info(f"已清理 {deleted} 条过期批量采集历史（>{days} 天）")
    except Exception as e:  # noqa: BLE001
        logger.warning("C-06 批量采集历史清理失败（忽略）: {}", e, exc_info=True)


def _migrate_to_multi_user(container: Any) -> None:
    """C-07: 单用户 → 多用户迁移（幂等）

    为什么独立：migrate_to_multi_user 自建 engine 而非复用 container.repo.engine，
    放在独立函数中避免与 container 的 session 生命周期耦合。
    """
    from loguru import logger

    try:
        from xianyu_hunter.web.services.user_manager import migrate_to_multi_user
        migrate_to_multi_user()
        logger.info("多用户迁移完成（C-07）")
    except Exception as e:  # noqa: BLE001
        logger.warning("C-07 多用户迁移失败（忽略）: {}", e, exc_info=True)


def run_migrations(container: Any) -> None:
    """执行数据库增量迁移

    包含 task_links 表重建、orders.task_id、tasks.search_filters、
    notifications.read_at 等历史迁移逻辑。

    每个迁移块独立 try/except：历史教训——auto_migrate_task_links 抛异常会让
    C-04 等后续迁移全部跳过，外层 try/except 又吞掉异常，最终数据库 schema 与
    ORM 不一致，运行时 INSERT 才报 "no such column"。
    """
    from sqlalchemy import inspect as sa_inspect

    insp = sa_inspect(container.repo.engine)

    _migrate_task_links_table(container, insp)
    _migrate_orders_task_id(container, insp)
    _migrate_tasks_search_filters(container, insp)
    _migrate_notifications_read_at(container, insp)
    _migrate_eval_scored_dedup(container, insp)
    _cleanup_old_batch_history(container)
    # 多用户迁移放最后：依赖 init_db 创建的多用户表已就绪
    _migrate_to_multi_user(container)


async def _start_all_schedulers(container: Any) -> None:
    """启动所有后台调度器（含 EventBus、调度器、Cookie 同步等）

    为什么独立：_on_startup 中调度器启动顺序有依赖关系（EventBus 必须先于调度器），
    集中维护避免遗漏顺序约束，同时降低 _on_startup 认知复杂度。
    """
    from loguru import logger
    from xianyu_hunter.web.deps import _should_start_scheduler

    # 一键启动模式：在 FastAPI 事件循环中启动调度器
    if _should_start_scheduler():
        # EventBus 必须先于调度器启动：worker.run_once 会在调度循环中
        # publish_nowait(EVAL_PASSED)，若无消费者事件会堆积在队列
        # 无消费者。EventBus 与"是否有 RUNNING 任务"解耦，无条件启动
        # start_event_bus_in_background 已改为同步（无 await 的 async 移除以避免 S7503）
        start_event_bus_in_background(container)
        await start_scheduler_in_background(container)

    # 启动 Cookie 定时同步（如果配置启用）
    start_cookie_sync_scheduler(container)

    # 启动批量采集调度器（如果配置启用且 collector 可用）
    start_batch_refresh_scheduler(container)

    # 启动智能客服知识库定时刷新调度器（如果 chatbot 启用）
    # 放在最后：chatbot 为可选模块，启动失败不影响主系统
    start_kb_refresh_scheduler(container)

    # 启动接管超时清理调度器（独立于 with_browser 模式）
    # 为什么放最后：本调度器只读写 DB，无外部依赖，启动失败不影响主业务
    start_takeover_timeout_scheduler(container)

    # 启动反爬会话管理（TokenRenewer 后台续期）
    # 无条件启动（不再依赖 _should_start_scheduler 门控）：
    # _default_renew_callback 已支持 httpx 兜底（with_browser=False 时
    # 通过 httpx 调用 MTOP getTimestamp API 续期），无浏览器也能续期。
    # 无有效 Cookie 时 start_session_default 内部会跳过，无副作用。
    try:
        from xianyu_hunter.web.services.session_starter import trigger_session_start
        trigger_session_start()
        logger.info("反爬会话管理已尝试自动启动（若无有效 Cookie 将跳过）")
    except Exception as e:  # noqa: BLE001
        logger.warning("反爬会话管理自动启动失败（忽略）: {}", e, exc_info=True)


def _stop_all_sync_schedulers() -> None:
    """停止所有同步调度器（非 async task 类型的调度器）

    为什么独立：_on_shutdown 中 4 个 if scheduler: stop + None 模式重复，
    集中维护停止顺序（知识库优先，避免主调度器停止时新任务被提交）。
    """
    global _kb_refresh_scheduler, _batch_refresh_scheduler, _cookie_sync_scheduler, _takeover_timeout_scheduler

    # 知识库调度器优先停止：避免停止主调度器时新任务仍被提交
    if _kb_refresh_scheduler:
        _kb_refresh_scheduler.stop()
        _kb_refresh_scheduler = None
    if _batch_refresh_scheduler:
        _batch_refresh_scheduler.stop()
        _batch_refresh_scheduler = None
    if _cookie_sync_scheduler:
        _cookie_sync_scheduler.stop()
        _cookie_sync_scheduler = None
    if _takeover_timeout_scheduler:
        _takeover_timeout_scheduler.stop()
        _takeover_timeout_scheduler = None


def _install_asyncio_exception_handler() -> None:
    """注册 asyncio 事件循环异常处理器，过滤 Windows 平台 ConnectionResetError 噪音

    背景：Windows ProactorEventLoop 在客户端关闭连接后，_call_connection_lost 回调
    调用 socket.shutdown(SHUT_RDWR) 会抛出 WinError 10054。该异常由 asyncio 内部
    回调触发，无法用 try/except 拦截，只能通过 loop.set_exception_handler 静默处理。
    """
    loop = asyncio.get_running_loop()

    def _exception_handler(loop, context):
        exception = context.get("exception")
        # ConnectionResetError: WinError 10054 客户端主动断开，属正常行为
        if isinstance(exception, ConnectionResetError):
            return
        # 其他异常走默认处理（输出到 stderr）
        loop.default_exception_handler(context)

    loop.set_exception_handler(_exception_handler)


def setup_startup_hooks(app: FastAPI) -> None:
    """注册启动和关闭钩子

    启动时：初始化日志 → 执行 DB 迁移 → 按需启动调度器
    关闭时：优雅停止调度器后台任务
    """
    from xianyu_hunter.infra.logger import setup_logging
    from xianyu_hunter.web.deps import get_container, _should_start_scheduler

    @app.on_event("startup")
    async def _on_startup() -> None:
        from loguru import logger

        # 初始化日志系统（含 run.stdout.log 文件 sink，供 SSE 日志流使用）
        setup_logging()

        # 注册 asyncio 异常处理器：过滤 Windows ProactorEventLoop 的 ConnectionResetError
        # 客户端关闭连接后，服务端 _call_connection_lost 调用 socket.shutdown(SHUT_RDWR) 抛 WinError 10054
        # 这是 Windows 平台已知行为，无需告警，避免日志噪音
        _install_asyncio_exception_handler()

        # container 必须先初始化，避免迁移失败时后续调度器启动引用未绑定变量
        container = get_container()
        try:
            run_migrations(container)
        except Exception as e:  # noqa: BLE001
            # 启动迁移钩子是关键路径（meta-rule #26），必须保留完整 traceback
            # 用 exception 而非 warning+exc_info：迁移失败影响面大，值得 ERROR 级告警
            logger.exception("启动迁移钩子失败（忽略，继续启动）: {}", e)

        # 启动所有后台调度器（EventBus 优先 → 调度器 → Cookie 同步等）
        await _start_all_schedulers(container)

        # 内网穿透：auto_start 为 True 时后台线程自动启动隧道
        # 用线程而非 asyncio：cloudflared/cpolar 是阻塞子进程，线程不占用事件循环
        # daemon=True 确保随主进程退出，shutdown hook 中会显式 stop
        try:
            from xianyu_hunter.infra.yaml_config import get_config
            if get_config().tunnel.auto_start:
                import threading
                from xianyu_hunter.web.routes.api_tunnel import get_tunnel_service

                def _auto_start_tunnel():
                    try:
                        svc = get_tunnel_service()
                        svc.start()
                        logger.info("内网穿透隧道已自动启动: {}", svc.public_url)
                    except Exception as e:
                        logger.exception("内网穿透自动启动失败: {}", e)
                        # 写入 DB 事件让前端能看到失败原因，而非只写日志
                        # 否则用户看不到自启动失败，以为"开关没生效"
                        try:
                            container.repo.save_event({
                                "type": "tunnel.autostart_failed",
                                "task_id": None,
                                "item_id": None,
                                "stage": "tunnel",
                                "level": "err",
                                "message": f"内网穿透自启动失败: {e}",
                                "payload": None,
                            })
                        except Exception:
                            pass  # DB 写入失败不二次报错
                        # 发送失败通知：用户不看 DB 事件也能通过通知渠道获知自启动失败
                        # 否则用户只看到隧道状态 stopped，不知道是自启动失败了还是没执行
                        # 复用 notify_tunnel_started 的子线程 + asyncio.run 模式，避免阻塞
                        try:
                            from xianyu_hunter.web.services.tunnel_notifications import (
                                _send_autostart_failed_notification,
                            )
                            _send_autostart_failed_notification(str(e))
                        except Exception:
                            logger.warning("发送自启动失败通知时出错")

                threading.Thread(
                    target=_auto_start_tunnel, daemon=True, name="tunnel-autostart"
                ).start()
                logger.info("检测到 tunnel.auto_start=True，已在后台线程启动隧道")
        except Exception as e:
            logger.exception("内网穿透 auto_start 检查失败: {}", e)

    @app.on_event("shutdown")
    async def _on_shutdown() -> None:
        """优雅停止调度器后台任务"""
        global _scheduler_task, _event_bus_task
        # 内网穿透隧道优先停止：避免调度器停止后隧道仍转发流量到已关闭的服务
        try:
            from xianyu_hunter.web.routes.api_tunnel import get_tunnel_service
            svc = get_tunnel_service()
            if svc.status == "running":
                svc.stop()
                logger.info("内网穿透隧道已随服务关闭而停止")
        except Exception:
            pass  # 隧道模块未初始化或已停止，忽略
        # 同步调度器优先停止（知识库 → 批量采集 → Cookie 同步 → 接管超时）
        _stop_all_sync_schedulers()
        if _scheduler_task and not _scheduler_task.done():
            _scheduler_task.cancel()
            # shutdown 中 await 已取消的子任务，使用 suppress 避免 CancelledError 中断 cleanup
            with suppress(asyncio.CancelledError):
                await _scheduler_task
            _scheduler_task = None
        # EventBus 在调度器之后停止：调度器 stop_all 时可能还会 publish
        # 事件（如任务停止事件），EventBus 需存活到调度器完全停止后才能关闭
        if _event_bus_task and not _event_bus_task.done():
            container.event_bus.stop()
            _event_bus_task.cancel()
            with suppress(asyncio.CancelledError):
                await _event_bus_task
            _event_bus_task = None
