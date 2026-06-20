"""今日异常雷达 API - Dashboard 异常检测

端点：
- GET /api/stats/today     今日统计 + 异常项（超时/失败/低分）
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends

from xianyu_hunter.container import Container
from xianyu_hunter.infra.db_models import _utcnow
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.utils import to_datetime

router = APIRouter(prefix="/api", tags=["stats-today"])


@router.get("/stats/today")
def stats_today(container: Container = Depends(get_container)) -> dict[str, Any]:
    """Dashboard 异常雷达数据源

    之所以单列端点（不合并到 /stats）:
    - 计算密集（需扫全表过滤时间窗），与"实时 4 卡"分离避免互相影响缓存
    - 仅在 alert 模式才调用，正常模式零开销
    """
    orders = container.repo.list_orders(limit=2000) or []
    events = container.repo.list_events(limit=2000) or []

    today_start = _utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    def _is_today(s: str | None) -> bool:
        d = to_datetime(s)
        return d is not None and d >= today_start

    today_orders = [o for o in orders if _is_today(o.get("created_at"))]
    today_events = [e for e in events if _is_today(e.get("created_at"))]

    # 异常项：pending 超时（>5min）+ failed + 评估低分
    failed_orders = [o for o in today_orders if o.get("status") == "failed"]
    pending_orders = [o for o in today_orders if o.get("status") in ("pending", "submitting", "paying")]

    now = _utcnow()
    timeout_pending: list[dict] = []
    for o in pending_orders:
        d = to_datetime(o.get("created_at"))
        if d and (now - d) > timedelta(minutes=5):
            age_sec = (now - d).total_seconds()
            o2 = dict(o)
            o2["age_sec"] = int(age_sec)
            timeout_pending.append(o2)

    # 评估异常：score < 0.5（人工接管/拒绝）
    low_evals: list[dict] = []
    for e in today_events:
        score = e.get("score")
        try:
            if score is not None and float(score) < 0.5:
                low_evals.append(e)
        except (TypeError, ValueError):
            pass

    return {
        "today": {
            "orders": len(today_orders),
            "events": len(today_events),
            "succeeded": sum(1 for o in today_orders if o.get("status") == "succeeded"),
            "failed": len(failed_orders),
        },
        "alerts": {
            "failed_orders": failed_orders[:20],
            "timeout_pending": timeout_pending[:20],
            "low_evaluations": low_evals[:20],
            "counts": {
                "failed": len(failed_orders),
                "timeout": len(timeout_pending),
                "low_eval": len(low_evals),
            },
        },
        "ts": _utcnow().isoformat(timespec="seconds"),
    }
