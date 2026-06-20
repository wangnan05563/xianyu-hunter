"""趋势数据 API - Dashboard sparkline 趋势

端点：
- GET /api/stats/trend     多指标趋势数据（事件/订单/评分/成功率）
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends

from xianyu_hunter.container import Container
from xianyu_hunter.infra.db_models import _utcnow
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
    bucket_count = {24: 24, 72: 24, 168: 14, 720: 30, 2160: 90}.get(range_hours, 24)

    events = container.repo.list_events(limit=5000) or []
    orders = container.repo.list_orders(limit=5000) or []
    now = _utcnow()
    cutoff = now - timedelta(hours=range_hours)
    skipped_reason: str | None = None

    if task_id:
        if metric in ("orders", "success_rate"):
            skipped_reason = f"metric={metric} 暂不支持按 task_id 过滤（Order 模型无 task_id 字段）"
        else:
            events = [e for e in events if (e.get("payload") or {}).get("task_id") == task_id]

    if metric == "events":
        rows = [(e.get("created_at"), 1.0) for e in events if _ensure_aware(to_datetime(e.get("created_at"))) and _ensure_aware(to_datetime(e.get("created_at"))) >= cutoff]
    elif metric == "orders":
        rows = [(o.get("created_at"), 1.0) for o in orders if _ensure_aware(to_datetime(o.get("created_at"))) and _ensure_aware(to_datetime(o.get("created_at"))) >= cutoff]
    elif metric == "eval_score":
        rows = []
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
    elif metric == "success_rate":
        rows = []
        for o in orders:
            d = _ensure_aware(to_datetime(o.get("created_at")))
            if d is None or d < cutoff:
                continue
            v = 1.0 if o.get("status") == "succeeded" else 0.0
            rows.append((o.get("created_at"), v))
    else:
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
