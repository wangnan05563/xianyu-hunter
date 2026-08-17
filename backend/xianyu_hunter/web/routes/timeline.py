"""统一时间线 API - 聚合 orders + events 按时间倒序

端点：
- GET /api/timeline     统一时间线视图
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Request

from xianyu_hunter.container import Container
from xianyu_hunter.infra.db_models import _utcnow
from xianyu_hunter.web.deps import get_container

router = APIRouter(prefix="/api", tags=["timeline"])


def _to_utc_iso(val: Any) -> str:
    """把 created_at 统一转为带 UTC 标记的 ISO 字符串

    SQLite 不存储时区信息，但 _utcnow() 写入的是 UTC。
    如果不加 'Z' 后缀，前端 new Date() 会把 UTC 时间当作本地时间解析，
    导致 UTC+8 用户看到的事件全部"偏移 8 小时"。
    """
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.isoformat() + "Z"
        return val.astimezone(timezone.utc).isoformat()
    if isinstance(val, str) and val:
        if val.endswith("Z") or "+" in val[10:]:
            return val
        return val + "Z"
    return ""


@router.get("/timeline")
def timeline(
    request: Request,
    types: str = "orders,events",
    task_id: str | None = None,
    limit: int = 200,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """统一时间线：聚合 orders + events（事件已涵盖评估/日志子集）按时间倒序

    为什么合并 events 而不单列 evaluations/logs：
    - events 表本身就是"全量行为记录"
    - 单列评估/日志端点已存在（向后兼容），timeline 只做"视图聚合"
    - 避免 N 次查询 + Python 端 union 排序的开销
    """
    # 多用户隔离：仅查询当前账号的 orders/events
    user_id = getattr(request.state, "user_id", None)
    wanted = {t.strip() for t in types.split(",") if t.strip()}
    items: list[dict] = []
    if "orders" in wanted:
        for o in container.repo.list_orders(limit=limit, user_id=user_id) or []:
            o2 = dict(o)
            o2["_kind"] = "order"
            o2["_ts"] = _to_utc_iso(o2.get("created_at"))
            items.append(o2)
    if "events" in wanted:
        for e in container.repo.list_events(limit=limit, user_id=user_id) or []:
            if task_id and e.get("task_id") != task_id:
                continue
            e2 = dict(e)
            e2["_kind"] = "event"
            e2["_ts"] = _to_utc_iso(e2.get("created_at"))
            items.append(e2)
    # 过滤空时间戳
    items = [x for x in items if x.get("_ts")]
    # 按 _ts 倒序
    items.sort(key=lambda x: x["_ts"], reverse=True)
    return {
        "items": items[:limit],
        "count": min(len(items), limit),
        "types": list(wanted),
        "task_id": task_id,
        "ts": _utcnow().isoformat(timespec="seconds"),
    }
