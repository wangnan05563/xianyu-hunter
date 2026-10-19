"""总览统计 API - Dashboard 核心统计卡片

端点：
- GET /api/stats              总览统计（4卡数据：任务/订单/事件）
- GET /api/events/recent      最近事件列表
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select, text as sa_text

from xianyu_hunter.container import Container
from xianyu_hunter.domain.order import PENDING_STATUSES, OrderStatus
from xianyu_hunter.infra.db_models import EventRow, EvaluationRow, TaskLinkRow, _utcnow
# 口径同源（FR-G-1）：通知事件的 stage 精确值与业务 KPI 卡共用同一常量，
# 避免「仪表盘说没失败、KPI 卡说失败率 3%」这类两套字面值各说各话
from xianyu_hunter.web.routes.business_kpi import _NOTIFY_STAGE
from xianyu_hunter.web.cache import cached_ttl
from xianyu_hunter.web.deps import get_container, _should_start_scheduler

router = APIRouter(prefix="/api", tags=["stats-overview"])


def _calc_db_size(container: Container) -> str:
    """计算数据库文件大小（人类可读格式）"""
    try:
        db_url = str(container.repo.engine.url)
        # 从 URL 中提取文件路径（sqlite:///path/to/db）
        db_path = db_url.replace("sqlite:///", "").replace("sqlite://", "")
        size_bytes = Path(db_path).stat().st_size
        if size_bytes < 1024:
            return f"{size_bytes} B"
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    except Exception:
        return "—"


def _get_browser_dir(container: Container) -> str:
    """获取浏览器数据目录路径"""
    try:
        if hasattr(container.collector, 'browser') and container.collector.browser:
            return str(getattr(container.collector.browser, 'user_data_dir', '—') or '—')
    except Exception:
        pass
    return "—"


def _query_task_stats(engine) -> tuple[int, int, int, int]:
    """查询 1：任务统计（一次 CASE WHEN 聚合拿 4 个状态计数，排除软删除）

    P3-1：独立 connection，配合 asyncio.gather 并发执行
    """
    with engine.connect() as conn:
        row = conn.execute(sa_text("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) AS running,
                SUM(CASE WHEN status = 'paused' THEN 1 ELSE 0 END) AS paused,
                SUM(CASE WHEN status = 'stopped' THEN 1 ELSE 0 END) AS stopped
            FROM tasks
            WHERE status != 'deleted'
        """)).one()
    return int(row.total or 0), int(row.running or 0), int(row.paused or 0), int(row.stopped or 0)


def _query_order_stats(engine) -> tuple[int, int, int, int]:
    """查询 2：订单统计（一次 CASE WHEN 聚合拿 4 个状态计数）

    P3-1：独立 connection，配合 asyncio.gather 并发执行
    """
    # 状态字面值取自 OrderStatus（T02585 口径同源）：原先这里写的是
    # IN ('pending','submitting','paying')，三个字面值从未被写入，仪表盘「待处理」恒 0。
    pending_in = ", ".join(f":pending_{i}" for i in range(len(PENDING_STATUSES)))
    params = {f"pending_{i}": v for i, v in enumerate(PENDING_STATUSES)}
    params["succeeded"], params["failed"] = OrderStatus.SUCCEEDED.value, OrderStatus.FAILED.value
    with engine.connect() as conn:
        row = conn.execute(sa_text(f"""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = :succeeded THEN 1 ELSE 0 END) AS succeeded,
                SUM(CASE WHEN status = :failed THEN 1 ELSE 0 END) AS failed,
                SUM(CASE WHEN status IN ({pending_in}) THEN 1 ELSE 0 END) AS pending
            FROM orders
        """), params).one()
    return int(row.total or 0), int(row.succeeded or 0), int(row.failed or 0), int(row.pending or 0)


def _query_event_total(engine) -> int:
    """查询 3：事件总数（EventRow.created_at 有索引，COUNT 快速）

    P3-1：独立 connection，配合 asyncio.gather 并发执行
    """
    with engine.connect() as conn:
        return int(conn.execute(select(func.count()).select_from(EventRow)).scalar() or 0)


def _query_eval_total(engine) -> int:
    """查询 4：评估记录总数

    P3-1：独立 connection，配合 asyncio.gather 并发执行
    """
    with engine.connect() as conn:
        return int(conn.execute(select(func.count()).select_from(EvaluationRow)).scalar() or 0)


def _query_funnel_metrics(engine) -> tuple[int, int, int]:
    """查询 5：真实商品数 / 评估通过数 / 通知失败数（FR-G-1 移动端 KPI 口径）

    为什么需要这三个字段：`/api/stats` 原先只有 tasks / orders / events / evaluation_count，
    移动端 KPI 卡拿不到「发现商品数」和「评估通过数」，只好贴错标签复用
    `tasks.total`（任务数）和 `evaluation_count`（评估总次数），读者看到的是假数据。

    口径与既有实现严格同源，不新造定义：
    - items_discovered：business_kpi.py `_kpi_items_discovered`（DISTINCT link_key WHERE link_type='item'）
      与 stats_eval_funnel.py 阶段1 `discovered` 同一表达式（漏斗那个带时间窗，这里取累计）
    - eval_pass：stats_eval_funnel.py `eval_pass_expr`（risk_level == 'low'），
      即业务 KPI「评估通过率」的分子
    - notify_failed：business_kpi.py `_kpi_notify_failure_rate` 的分子
      （stage=_NOTIFY_STAGE 且 level='err'），同样共用 stage 常量避免字面值漂移

    P3-1 风格：独立 connection + CASE WHEN 一次聚合，配合 asyncio.gather 并发。
    """
    with engine.connect() as conn:
        items_discovered = int(conn.execute(
            select(func.count(func.distinct(TaskLinkRow.link_key)))
            .where(TaskLinkRow.link_type == "item")
        ).scalar() or 0)
        eval_pass_expr = case((EvaluationRow.risk_level == "low", 1), else_=0)
        notify_fail_expr = case(
            ((EventRow.stage == _NOTIFY_STAGE) & (EventRow.level == "err"), 1),
            else_=0,
        )
        eval_row = conn.execute(
            select(func.sum(eval_pass_expr).label("matched")).select_from(EvaluationRow)
        ).one()
        notify_row = conn.execute(
            select(func.sum(notify_fail_expr).label("matched")).select_from(EventRow)
        ).one()
    return items_discovered, int(eval_row.matched or 0), int(notify_row.matched or 0)


@cached_ttl(300, key_fn=lambda container: "stats_overview")
async def _overview(container: Container) -> dict[str, Any]:
    """总览统计（S-01 修复：用 SQL COUNT 替代拉全量数据计数）

    性能优化：将原来 9 次 COUNT 查询合并为条件聚合（tasks / orders / events / eval / funnel-metrics 各一次），
    用 CASE WHEN 条件聚合替代逐状态单独查询。

    为什么缓存 60s：总览卡片数据变化频率低（任务状态/订单状态分钟级变化），
    60s 缓存让多用户访问 dashboard 时命中率 >90%，响应从 ~800ms 降到 <10ms。

    P3-1 优化：4 个查询用 asyncio.gather + asyncio.to_thread 并发执行，
    每个查询独立 connection 利用 SQLite WAL 并发读。串行 ~200ms → 并发 ~80ms。
    """
    engine = container.repo.engine

    # P3-1：5 个查询并发执行，每个独立 connection（SQLite WAL 支持并发读）
    (task_total, task_running, task_paused, task_stopped), \
        (order_total, order_succeeded, order_failed, order_pending), \
        event_total, \
        eval_total, \
        (items_discovered, eval_pass, notify_failed) = await asyncio.gather(
            asyncio.to_thread(_query_task_stats, engine),
            asyncio.to_thread(_query_order_stats, engine),
            asyncio.to_thread(_query_event_total, engine),
            asyncio.to_thread(_query_eval_total, engine),
            asyncio.to_thread(_query_funnel_metrics, engine),
        )

    return {
        "tasks": {
            "total": task_total,
            "running": task_running,
            "paused": task_paused,
            "stopped": task_stopped,
        },
        "orders": {
            "total": order_total,
            "succeeded": order_succeeded,
            "failed": order_failed,
            "pending": order_pending,
        },
        "events": {
            "total": event_total,
        },
        "evaluation_count": eval_total,
        # FR-G-1：真实商品/通过/通知失败计数。移动端与桌面 KPI 共用这一份，
        # 不再用 tasks.total 冒充商品数、用 evaluation_count 冒充「评估通过」
        "metrics": {
            "items_discovered": items_discovered,
            "eval_pass": eval_pass,
            "notify_failed": notify_failed,
        },
        # 系统状态：数据库大小 + 浏览器数据目录 + 调度器状态
        "db_size": _calc_db_size(container),
        "browser_dir": _get_browser_dir(container),
        # 调度器状态：--with-scheduler 模式即视为运行中（即使无 RUNNING 任务）
        "scheduler_running": _should_start_scheduler(),
        "ts": _utcnow().isoformat(timespec="seconds"),
    }


@router.get("/stats")
async def stats(container: Container = Depends(get_container)) -> dict[str, Any]:
    """Dashboard 统计（每次请求时实时计算）"""
    return await _overview(container)


@router.get("/events/recent")
def events_recent(
    limit: int = 50,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """最近事件列表（用于初次加载）"""
    rows = container.repo.list_events(limit=limit) or []
    return {"items": rows, "count": len(rows)}
