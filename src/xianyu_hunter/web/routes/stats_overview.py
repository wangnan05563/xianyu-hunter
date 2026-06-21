"""总览统计 API - Dashboard 核心统计卡片

端点：
- GET /api/stats              总览统计（4卡数据：任务/订单/事件）
- GET /api/events/recent      最近事件列表
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text as sa_text

from xianyu_hunter.container import Container
from xianyu_hunter.infra.db_models import EventRow, TaskRow, OrderRow, _utcnow
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


def _overview(container: Container) -> dict[str, Any]:
    """总览统计（S-01 修复：用 SQL COUNT 替代拉全量数据计数）

    性能优化：将原来 9 次 COUNT 查询合并为 3 次（tasks / orders / events 各一次），
    用 CASE WHEN 条件聚合替代逐状态单独查询。
    """
    engine = container.repo.engine
    with engine.connect() as conn:
        # 1. 任务统计：一次查询搞定 4 个状态计数
        task_row = conn.execute(sa_text("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) AS running,
                SUM(CASE WHEN status = 'paused' THEN 1 ELSE 0 END) AS paused,
                SUM(CASE WHEN status = 'stopped' THEN 1 ELSE 0 END) AS stopped
            FROM tasks
        """)).one()

        # 2. 订单统计：一次查询搞定 4 个状态计数
        order_row = conn.execute(sa_text("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'succeeded' THEN 1 ELSE 0 END) AS succeeded,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                SUM(CASE WHEN status IN ('pending', 'submitting', 'paying') THEN 1 ELSE 0 END) AS pending
            FROM orders
        """)).one()

        # 3. 事件总数
        event_total = int(conn.execute(select(func.count()).select_from(EventRow)).scalar() or 0)

        # 4. 评估记录总数
        from xianyu_hunter.infra.db_models import EvaluationRow as EvalRow
        eval_total = int(conn.execute(select(func.count()).select_from(EvalRow)).scalar() or 0)

    return {
        "tasks": {
            "total": int(task_row.total or 0),
            "running": int(task_row.running or 0),
            "paused": int(task_row.paused or 0),
            "stopped": int(task_row.stopped or 0),
        },
        "orders": {
            "total": int(order_row.total or 0),
            "succeeded": int(order_row.succeeded or 0),
            "failed": int(order_row.failed or 0),
            "pending": int(order_row.pending or 0),
        },
        "events": {
            "total": event_total,
        },
        "evaluation_count": eval_total,
        # 系统状态：数据库大小 + 浏览器数据目录 + 调度器状态
        "db_size": _calc_db_size(container),
        "browser_dir": _get_browser_dir(container),
        # 调度器状态：--with-scheduler 模式即视为运行中（即使无 RUNNING 任务）
        "scheduler_running": _should_start_scheduler(),
        "ts": _utcnow().isoformat(timespec="seconds"),
    }


@router.get("/stats")
def stats(container: Container = Depends(get_container)) -> dict[str, Any]:
    """Dashboard 统计（每次请求时实时计算）"""
    return _overview(container)


@router.get("/events/recent")
def events_recent(
    limit: int = 50,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """最近事件列表（用于初次加载）"""
    rows = container.repo.list_events(limit=limit) or []
    return {"items": rows, "count": len(rows)}
