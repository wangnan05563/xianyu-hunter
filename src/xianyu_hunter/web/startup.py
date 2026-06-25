"""应用启动与关闭钩子

将 app.py 中的调度器启动、DB 迁移、优雅关闭逻辑抽离，
使 app.py 仅保留路由注册和核心端点定义。
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI


# 调度器后台任务引用（用于 shutdown 时优雅停止）
_scheduler_task: asyncio.Task | None = None

# Cookie 定时同步调度器引用（用于 shutdown 时优雅停止）
_cookie_sync_scheduler = None


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


async def start_scheduler_in_background(container: Any) -> None:
    """在 FastAPI 事件循环中启动调度器后台任务

    从 DB 加载 RUNNING 任务 → 注册到 Scheduler → 启动循环。
    """
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

    # 读取用户在 /app/config/search 页面保存的搜索参数
    # 这些参数会注入到每个 TaskWorker 的 TaskConfig 中，控制 collector.search() 行为
    search_cfg = get_config().search
    logger.info(
        f"搜索参数配置: page_size={search_cfg.page_size}, sort_type={search_cfg.sort_type}, "
        f"timeout={search_cfg.timeout}s, regions='{search_cfg.regions}', "
        f"filter_tags={search_cfg.filter_tags}"
    )

    raw_tasks = container.repo.list_tasks()
    workers: list[TaskWorker] = []
    for raw in raw_tasks:
        if raw.get("status") != "running":
            continue
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
        )
        # 按任务维度设置价格策略
        if task.min_price is not None or task.max_price is not None:
            container.price_strategy = type(container.price_strategy)(
                PriceConfig(
                    min_price=task.min_price,
                    max_price=task.max_price,
                    market_ratio=getattr(container.price_strategy, "config", None).market_ratio
                    if getattr(container.price_strategy, "config", None) is not None
                    else 0.8,
                )
            )
        # 从 AppConfig.search 注入搜索参数到 TaskConfig
        # 这样 Worker.run_once() 调用 collector.search() 时会使用用户配置的参数
        task_config = TaskConfig(
            search_page_size=search_cfg.page_size,
            search_sort_type=search_cfg.sort_type,
            search_timeout=search_cfg.timeout,
            search_regions=search_cfg.regions,
            search_filter_tags=search_cfg.filter_tags,
        )
        worker = TaskWorker(
            task=task,
            collector=container.collector,
            dedup=container.dedup,
            price_strategy=container.price_strategy,
            evaluator=container.evaluator,
            buyer=container.buyer,
            config=task_config,
            repo=container.repo,
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
            # 保持运行直到被取消
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            logger.info("调度器正在停止...")
            await container.scheduler.stop_all()
            container.event_bus.stop()
            bus_task.cancel()
            try:
                await bus_task
            except asyncio.CancelledError:
                pass
            logger.info("调度器已停止")

    global _scheduler_task
    loop = asyncio.get_event_loop()
    _scheduler_task = loop.create_task(_scheduler_loop())


def run_migrations(container: Any) -> None:
    """执行数据库增量迁移

    包含 task_links 表重建、orders.task_id、tasks.search_filters、
    notifications.read_at 等历史迁移逻辑。
    """
    from loguru import logger
    from sqlalchemy import inspect as sa_inspect, text as sa_text
    from xianyu_hunter.infra.db_models import TaskLinkRow

    insp = sa_inspect(container.repo.engine)
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

    # C-02 迁移：确保 orders 表含 task_id 列
    if insp.has_table("orders"):
        order_cols = {c["name"] for c in insp.get_columns("orders")}
        if "task_id" not in order_cols:
            with container.repo.engine.begin() as conn:
                conn.exec_driver_sql(
                    "ALTER TABLE orders ADD COLUMN task_id TEXT DEFAULT NULL"
                )
            logger.info("orders 表已新增 task_id 列（C-02 迁移）")

    # C-03 迁移：确保 tasks 表含 search_filters 列（闲鱼筛选标签）
    if insp.has_table("tasks"):
        task_cols = {c["name"] for c in insp.get_columns("tasks")}
        if "search_filters" not in task_cols:
            with container.repo.engine.begin() as conn:
                conn.exec_driver_sql(
                    "ALTER TABLE tasks ADD COLUMN search_filters TEXT DEFAULT NULL"
                )
            logger.info("tasks 表已新增 search_filters 列（C-03 迁移）")

    # C-04 迁移：确保 notifications 表含 read_at 列
    if insp.has_table("notifications"):
        notif_cols = {c["name"] for c in insp.get_columns("notifications")}
        if "read_at" not in notif_cols:
            with container.repo.engine.begin() as conn:
                conn.exec_driver_sql(
                    "ALTER TABLE notifications ADD COLUMN read_at DATETIME DEFAULT NULL"
                )
            logger.info("notifications 表已新增 read_at 列（C-04 迁移）")

    # C-05 迁移：eval.scored 事件去重 + 添加部分唯一索引
    # 防止 live_links 多次触发或 recompute 多次调用产生重复评估记录
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

        try:
            container = get_container()
            run_migrations(container)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"启动迁移钩子失败（忽略）: {e}")

        # 一键启动模式：在 FastAPI 事件循环中启动调度器
        if _should_start_scheduler():
            await start_scheduler_in_background(container)

        # 启动 Cookie 定时同步（如果配置启用）
        start_cookie_sync_scheduler(container)

    @app.on_event("shutdown")
    async def _on_shutdown() -> None:
        """优雅停止调度器后台任务"""
        global _scheduler_task, _cookie_sync_scheduler
        if _cookie_sync_scheduler:
            _cookie_sync_scheduler.stop()
            _cookie_sync_scheduler = None
        if _scheduler_task and not _scheduler_task.done():
            _scheduler_task.cancel()
            try:
                await _scheduler_task
            except asyncio.CancelledError:
                pass
            _scheduler_task = None
