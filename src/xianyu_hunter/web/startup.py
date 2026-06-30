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
    import asyncio
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
    _batch_refresh_scheduler.start(asyncio.get_event_loop())


def start_kb_refresh_scheduler(container: Any) -> None:
    """启动智能客服知识库定时刷新调度器（如果 chatbot 启用且 kb.auto_update_enabled=true）

    独立于批量采集调度器：本调度器仅扫描 docs/ 和 src/ 目录构建知识库，
    不依赖浏览器/collector，因此 Web 进程（with_browser=False）也可启动。

    为什么不依赖 collector：KB 构建只读文件系统 + 调用 OpenAI Embedding API，
    不涉及闲鱼页面采集，无需浏览器实例。
    """
    global _kb_refresh_scheduler
    import asyncio
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
        kb_scheduler.start(asyncio.get_event_loop())
        _kb_refresh_scheduler = kb_scheduler
    except Exception as e:  # noqa: BLE001
        # 启动失败不阻断应用：用户仍可手动通过 POST /api/chatbot/kb/rebuild 触发构建
        logger.exception(f"知识库定时刷新调度器启动失败: {e}")


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
    except Exception as e:  # noqa: BLE001
        # 启动失败不阻断应用：用户仍可通过手动修改订单状态处理超时
        logger.exception(f"接管超时清理调度器启动失败: {e}")


async def start_scheduler_in_background(container: Any) -> None:
    """在 FastAPI 事件循环中启动调度器后台任务

    从 DB 加载 RUNNING 任务 → 注册到 Scheduler → 启动循环。
    """
    import json
    from loguru import logger
    from xianyu_hunter.domain.task import Task, TaskMode, TaskConfig
    from xianyu_hunter.modules.worker import TaskWorker
    from xianyu_hunter.modules.price_strategy import PriceConfig
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

    def _parse_json_field(raw: Any, field_name: str) -> dict | None:
        """安全解析 DB 中的 JSON 配置覆盖字段

        返回 None 表示无覆盖（沿用全局），dict 表示有效覆盖
        """
        if not raw:
            return None
        if isinstance(raw, dict):
            return raw or None
        if isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
                return parsed if parsed else None
            except json.JSONDecodeError:
                logger.warning(f"任务 {field_name} JSON 解析失败，将沿用全局配置: {raw[:80]}")
                return None
        return None

    raw_tasks = container.repo.list_tasks()
    workers: list[TaskWorker] = []
    for raw in raw_tasks:
        if raw.get("status") != "running":
            continue
        # 解析任务级配置覆盖（JSON 字符串 → dict，None 表示沿用全局）
        task_search_override = _parse_json_field(raw.get("search_config"), "search_config")
        task_price_override = _parse_json_field(raw.get("price_config"), "price_config")
        # antidetect_config: 解析保留以兼容旧 DB 数据，但 TaskWorker 不消费此字段
        # AntiDetect 是 container 级共享单例（所有 worker 复用 collector.antidetect），
        # 任务级覆盖架构上不可行，前端已改为全局快捷入口 Modal（见 F4 修复）
        task_antidetect_override = _parse_json_field(raw.get("antidetect_config"), "antidetect_config")
        # eval_config: 任务级覆盖 AppConfig.eval（auto_collect_official/auto_collect_max_per_run 等）
        # 在 worker.run_once 中与全局 eval_cfg 深度合并，None 表示沿用全局
        task_eval_override = _parse_json_field(raw.get("eval_config"), "eval_config")

        task = Task(
            id=raw["id"],
            name=raw.get("name", raw["id"]),
            keyword=raw["keyword"],
            min_price=raw.get("min_price"),
            max_price=raw.get("max_price"),
            exclude_words=raw.get("exclude_words") or [],
            region=raw.get("region"),
            mode=TaskMode(raw.get("mode", "confirm")),
            search_filters=raw.get("search_filters") or [],
            # 调度配置：从 DB 读取，scheduler._run_loop 据此决定 cron 或 interval 模式
            # 用 or 防御 NULL：迁移后的旧行可能为 None，dict.get(key, default) 在 key 存在但值为 None 时返回 None
            cron=raw.get("cron") or "*/1 * * * *",
            use_cron=bool(raw.get("use_cron") or 0),
            interval_seconds=float(raw.get("interval_seconds") or 60.0),
            # AI 评估任务级配置：None 表示沿用全局 eval.pass_score，具体值表示任务级覆盖
            # 之前用 `if not None else 60` 导致无法区分"用户设 60"和"未设置"，现已修正
            eval_threshold=raw.get("eval_threshold"),
            ai_prompt=raw.get("ai_prompt"),
            # 任务级配置覆盖（dict 或 None）
            search_config=task_search_override,
            price_config=task_price_override,
            antidetect_config=task_antidetect_override,
            eval_config=task_eval_override,
        )
        # 合并任务级价格策略覆盖到 PriceConfig
        # 任务级覆盖优先于全局配置，任务字段 min_price/max_price 优先于 price_config
        # 使用局部变量避免污染 container.price_strategy 共享单例：
        # 之前直接改 container.price_strategy 会导致循环结束后指向最后一个任务的配置，
        # 影响 live 端点等共享 container 的代码
        effective_min = task.min_price
        effective_max = task.max_price
        # 任务级 price_config 覆盖全局 price_strategy 的 min/max_price
        # 注意：仅消费 min_price/max_price/market_ratio 三个字段
        # PriceStrategyConfig 的 enabled_* 开关和 top_n 未消费（UI 未暴露 price_config 编辑入口）
        # PriceConfig 用 None 表示禁用，与 enabled_*=False 语义等价
        if task_price_override:
            if effective_min is None and "min_price" in task_price_override:
                effective_min = task_price_override["min_price"]
            if effective_max is None and "max_price" in task_price_override:
                effective_max = task_price_override["max_price"]
        worker_price_strategy = container.price_strategy
        if effective_min is not None or effective_max is not None:
            worker_price_strategy = type(container.price_strategy)(
                PriceConfig(
                    min_price=effective_min,
                    max_price=effective_max,
                    market_ratio=task_price_override.get("market_ratio", price_cfg.market_ratio)
                    if task_price_override else price_cfg.market_ratio,
                )
            )
        # 合并任务级搜索参数覆盖到 TaskConfig
        # 任务级 search_config 覆盖全局 AppConfig.search 的对应字段
        effective_search = {
            "page_size": search_cfg.page_size,
            "sort_type": search_cfg.sort_type,
            "timeout": search_cfg.timeout,
            "regions": search_cfg.regions,
            "filter_tags": search_cfg.filter_tags,
        }
        if task_search_override:
            for k in effective_search:
                if k in task_search_override:
                    effective_search[k] = task_search_override[k]
        task_config = TaskConfig(
            search_page_size=effective_search["page_size"],
            search_sort_type=effective_search["sort_type"],
            search_timeout=effective_search["timeout"],
            search_regions=effective_search["regions"],
            search_filter_tags=effective_search["filter_tags"],
            use_cron=task.use_cron,
            interval_seconds=task.interval_seconds,
        )
        worker = TaskWorker(
            task=task,
            collector=container.collector,
            dedup=container.dedup,
            price_strategy=worker_price_strategy,
            evaluator=container.evaluator,
            buyer=container.buyer,
            config=task_config,
            repo=container.repo,
            # P1: 注入官方采集回调，延迟导入避免循环依赖
            # worker 调用此回调对通过评估的商品做深度验证
            official_collect_fn=(
                lambda iid, tid: _call_official_collect(container, iid, tid)
            ),
            # Task 9: 注入 notifier 用于自动采集暂停告警
            notifier=container.notifier_hub,
        )
        await container.scheduler.register(task, worker)
        workers.append(worker)

    if not workers:
        logger.info("调度器: 无 RUNNING 任务，跳过启动")
        return

    async def _scheduler_loop() -> None:
        """调度器主循环：启动所有任务 + EventBus 消费"""
        try:
            # 启动 EventBus 消费循环
            bus_task = asyncio.create_task(container.event_bus.run_forever())
            # 启动所有已注册任务
            await container.scheduler.start_all()
            task_ids = [w.task.id for w in workers]
            logger.info(f"调度器已启动 {len(task_ids)} 个任务: {task_ids}")
            # 保持运行直到被取消或 bus_task 异常退出
            # 为什么不用 asyncio.Event().wait()：EventBus 异常退出后事件推送静默失效，
            # 需要检测 bus_task 状态并告警
            stop_event = asyncio.Event()
            while not stop_event.is_set():
                if bus_task.done():
                    exc = bus_task.exception()
                    if exc:
                        logger.error(f"EventBus 异常退出，事件推送将不可用: {exc}")
                    else:
                        logger.warning("EventBus 已退出，事件推送不可用")
                    break
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=10.0)
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            logger.info("调度器正在停止...")
            await container.scheduler.stop_all()
            container.event_bus.stop()
            bus_task.cancel()
            # 子任务被取消是预期行为，使用 suppress 避免 CancelledError 上抛中断 cleanup
            with suppress(asyncio.CancelledError):
                await bus_task
            logger.info("调度器已停止")
            # 重新抛出以传播取消信号，符合 S7497
            raise

    global _scheduler_task
    loop = asyncio.get_event_loop()
    _scheduler_task = loop.create_task(_scheduler_loop())


def run_migrations(container: Any) -> None:
    """执行数据库增量迁移

    包含 task_links 表重建、orders.task_id、tasks.search_filters、
    notifications.read_at 等历史迁移逻辑。

    每个迁移块独立 try/except：历史教训——auto_migrate_task_links 抛异常会让
    C-04 等后续迁移全部跳过，外层 try/except 又吞掉异常，最终数据库 schema 与
    ORM 不一致，运行时 INSERT 才报 "no such column"。
    """
    from loguru import logger
    from sqlalchemy import inspect as sa_inspect, text as sa_text
    from xianyu_hunter.infra.db_models import TaskLinkRow

    insp = sa_inspect(container.repo.engine)

    # C-01: task_links 表重建（含 UNIQUE 约束）+ 历史数据回填
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
        logger.warning(f"C-01 task_links 迁移失败（忽略，不影响后续迁移）: {e}")

    # C-02 迁移：确保 orders 表含 task_id 列
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
        logger.warning(f"C-02 orders.task_id 迁移失败（忽略）: {e}")

    # C-03 迁移：确保 tasks 表含 search_filters 列（闲鱼筛选标签）
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
        logger.warning(f"C-03 tasks.search_filters 迁移失败（忽略）: {e}")

    # C-04 迁移：确保 notifications 表含 read_at 列
    # 关键迁移：缺此列会导致 add_notification 的 UPSERT 完全失败，所有告警丢失
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
        logger.warning(f"C-04 notifications.read_at 迁移失败（忽略）: {e}")

    # C-05 迁移：eval.scored 事件去重 + 添加部分唯一索引
    # 防止 live_links 多次触发或 recompute 多次调用产生重复评估记录
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
        logger.warning(f"C-05 eval.scored 去重迁移失败（忽略）: {e}")

    # C-06: 清理过期的批量采集执行历史
    # 为什么放这里：init_db 已通过 create_all 创建 batch_refresh_history 表，
    # 此处根据配置 history_retention_days 清理过期记录，避免磁盘无限增长。
    try:
        from xianyu_hunter.infra.yaml_config import get_config
        days = get_config().batch_refresh.history_retention_days
        if days > 0:
            deleted = container.repo.cleanup_old_batch_refresh_history(days)
            if deleted > 0:
                logger.info(f"已清理 {deleted} 条过期批量采集历史（>{days} 天）")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"C-06 批量采集历史清理失败（忽略）: {e}")


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

        # container 必须先初始化，避免迁移失败时后续调度器启动引用未绑定变量
        container = get_container()
        try:
            run_migrations(container)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"启动迁移钩子失败（忽略）: {e}")

        # 一键启动模式：在 FastAPI 事件循环中启动调度器
        if _should_start_scheduler():
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
        # 仅在 with_browser=True 时启动：renew_callback 依赖 container.browser 进行 Cookie 续期
        # 无有效 Cookie 时 start_session_default 内部会失败并记录日志，无副作用
        # 放在调度器之后：确保浏览器实例已就绪，避免 renew_callback 因 browser=None 反复失效
        if _should_start_scheduler():
            try:
                from xianyu_hunter.web.services.session_starter import trigger_session_start
                trigger_session_start()
                logger.info("反爬会话管理已尝试自动启动（若无有效 Cookie 将跳过）")
            except Exception as e:  # noqa: BLE001
                logger.warning(f"反爬会话管理自动启动失败（忽略）: {e}")

    @app.on_event("shutdown")
    async def _on_shutdown() -> None:
        """优雅停止调度器后台任务"""
        global _scheduler_task, _cookie_sync_scheduler, _batch_refresh_scheduler, _kb_refresh_scheduler, _takeover_timeout_scheduler
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
        if _scheduler_task and not _scheduler_task.done():
            _scheduler_task.cancel()
            # shutdown 中 await 已取消的子任务，使用 suppress 避免 CancelledError 中断 cleanup
            with suppress(asyncio.CancelledError):
                await _scheduler_task
            _scheduler_task = None
