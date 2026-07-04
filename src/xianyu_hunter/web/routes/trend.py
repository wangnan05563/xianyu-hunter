"""趋势数据 API - Dashboard sparkline 趋势

端点：
- GET /api/stats/trend     多指标趋势数据（事件/订单/评分/成功率）
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select

from xianyu_hunter.container import Container
from xianyu_hunter.infra.db_models import EventRow, OrderRow, _utcnow
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.utils import to_datetime

router = APIRouter(prefix="/api", tags=["stats-trend"])


def _ensure_aware(d: datetime | None) -> datetime | None:
    """SQLite 存 naive datetime，cutoff 是 aware，比较前统一转 aware"""
    if d is None:
        return None
    if d.tzinfo is None:
        return d.replace(tzinfo=timezone.utc)
    return d


def _build_trend_series(
    rows_with_ts: list[tuple[str, float]],
    range_hours: int,
    bucket_count: int = 24,
) -> list[dict[str, Any]]:
    """按时间桶聚合数据

    为什么不直接返回 raw rows：
    - dashboard 期望 "趋势" 视图（过去 24h 每小时一个点）
    - 用等宽时间桶聚合更适合 sparkline
    """
    now = _utcnow()
    bucket_sec = (range_hours * 3600) // bucket_count
    buckets: list[dict[str, Any]] = [{
        "ts": (now - timedelta(seconds=(bucket_count - 1 - i) * bucket_sec)).replace(microsecond=0).isoformat(timespec="seconds"),
        "value": 0.0,
        "count": 0,
    } for i in range(bucket_count)]

    for ts, val in rows_with_ts:
        d = _ensure_aware(to_datetime(ts))
        if d is None:
            continue
        delta_sec = (now - d).total_seconds()
        if delta_sec < 0 or delta_sec > range_hours * 3600:
            continue
        idx = (bucket_count - 1) - int(delta_sec // bucket_sec)
        if 0 <= idx < bucket_count:
            buckets[idx]["value"] += float(val)
            buckets[idx]["count"] += 1

    for b in buckets:
        if b["count"] > 0:
            b["value"] = round(b["value"] / b["count"], 2)
    return buckets


_RANGE_BUCKET_COUNT = {24: 24, 72: 24, 168: 14, 720: 30, 2160: 90}


def _load_trend_events(conn, container: Container, task_id: str | None, cutoff) -> list[dict]:
    """加载 events 表行：用 EventRow.task_id 列过滤（有索引），比解析 payload 更高效"""
    if task_id:
        event_stmt = (
            select(EventRow).where(EventRow.created_at >= cutoff)
            .where(EventRow.task_id == task_id)
        )
    else:
        event_stmt = select(EventRow).where(EventRow.created_at >= cutoff)
    event_stmt = event_stmt.order_by(EventRow.created_at.desc()).limit(5000)
    return [container.repo._row_to_dict(r) for r in conn.execute(event_stmt).all()]


def _load_trend_orders(conn, container: Container, cutoff) -> list[dict]:
    """加载 orders 表行：OrderRow 有 task_id 列，原注释"无 task_id 字段"过时"""
    order_stmt = select(OrderRow).where(OrderRow.created_at >= cutoff)
    order_stmt = order_stmt.order_by(OrderRow.created_at.desc()).limit(5000)
    return [container.repo._row_to_dict(r) for r in conn.execute(order_stmt).all()]


def _build_count_metric_rows(records: list[dict], cutoff) -> list[tuple]:
    """events/orders 计数指标：每条记录贡献 1.0，过滤掉 cutoff 之外的记录"""
    rows: list[tuple] = []
    for r in records:
        d = _ensure_aware(to_datetime(r.get("created_at")))
        if d is not None and d >= cutoff:
            rows.append((r.get("created_at"), 1.0))
    return rows


def _build_eval_score_rows(events: list[dict], cutoff) -> list[tuple]:
    """eval_score 指标：score>0 时放大 100 倍入库，便于与百分比指标同图展示"""
    rows: list[tuple] = []
    for e in events:
        d = _ensure_aware(to_datetime(e.get("created_at")))
        if d is None or d < cutoff:
            continue
        score = e.get("score")
        try:
            if score is not None and float(score) > 0:
                rows.append((e.get("created_at"), float(score) * 100))
        except (TypeError, ValueError):
            pass
    return rows


def _build_success_rate_rows(orders: list[dict], cutoff) -> list[tuple]:
    """success_rate 指标：succeeded=1.0，其它=0.0，聚合后即为成功率"""
    rows: list[tuple] = []
    for o in orders:
        d = _ensure_aware(to_datetime(o.get("created_at")))
        if d is None or d < cutoff:
            continue
        v = 1.0 if o.get("status") == "succeeded" else 0.0
        rows.append((o.get("created_at"), v))
    return rows


def _build_trend_metric_rows(
    metric: str, events: list[dict], orders: list[dict], cutoff
) -> list[tuple] | None:
    """按 metric 分发到对应行构建函数，未知 metric 返回 None 由调用方返回空响应"""
    if metric == "events":
        return _build_count_metric_rows(events, cutoff)
    if metric == "orders":
        return _build_count_metric_rows(orders, cutoff)
    if metric == "eval_score":
        return _build_eval_score_rows(events, cutoff)
    if metric == "success_rate":
        return _build_success_rate_rows(orders, cutoff)
    return None


@router.get("/stats/trend")
def stats_trend(
    metric: str = "events",
    range_hours: int = 24,
    task_id: str | None = None,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """P3-UX-07：Dashboard sparkline 趋势数据"""
    if range_hours not in (24, 72, 168, 720, 2160):
        range_hours = 24
    bucket_count = _RANGE_BUCKET_COUNT.get(range_hours, 24)

    now = _utcnow()
    cutoff = now - timedelta(hours=range_hours)
    skipped_reason: str | None = None

    # 性能优化：原实现拉取 list_events(5000) + list_orders(5000) 到内存再过滤，
    # 现改为 SQL WHERE created_at >= cutoff 直接在数据库端过滤时间窗，
    # 且仅查询当前 metric 需要的表，避免无谓的全量加载。
    events: list[dict] = []
    orders: list[dict] = []
    engine = container.repo.engine
    with engine.connect() as conn:
        if metric in ("events", "eval_score"):
            events = _load_trend_events(conn, container, task_id, cutoff)
        elif metric in ("orders", "success_rate"):
            if task_id:
                # OrderRow 有 task_id 列，原注释"无 task_id 字段"过时，但保留 skipped_reason 行为不变
                skipped_reason = f"metric={metric} 暂不支持按 task_id 过滤（Order 模型无 task_id 字段）"
            orders = _load_trend_orders(conn, container, cutoff)

    rows = _build_trend_metric_rows(metric, events, orders, cutoff)
    if rows is None:
        return {"metric": metric, "range_hours": range_hours, "task_id": task_id, "series": [],
                "summary": {"min": 0, "max": 0, "avg": 0, "current": 0}, "skipped_reason": None}

    series = _build_trend_series(rows, range_hours, bucket_count)
    values = [s["value"] for s in series]
    summary = {
        "min": round(min(values), 2) if values else 0,
        "max": round(max(values), 2) if values else 0,
        "avg": round(sum(values) / len(values), 2) if values else 0,
        "current": values[-1] if values else 0,
    }
    return {
        "metric": metric,
        "range_hours": range_hours,
        "task_id": task_id,
        "series": series,
        "summary": summary,
        "skipped_reason": skipped_reason,
    }
