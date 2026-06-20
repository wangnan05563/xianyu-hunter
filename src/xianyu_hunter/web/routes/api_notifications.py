"""业务通知 API（P1-4 Notification Center）

与 /api/events/* 的分工：
- /api/events/*：技术性事件流（SSE 推送 + 历史回溯），只读追加，不区分已读
- /api/notifications：业务性通知（订单超时、登录态失效等），持久化、可读/可删
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from xianyu_hunter.container import Container
from xianyu_hunter.web.deps import get_container

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


# 通知级别与"可创建"的业务场景白名单
# 为什么不开放 category/level 任意写入：内部 API 也加白名单，防止误调用造出垃圾
# （外部如果需要创建通知，调用 /api/notifications 即可，但需要带 dedup_key 表明业务意图）
_ALLOWED_LEVELS = {"info", "warn", "err"}
_ALLOWED_CATEGORIES = {"order", "auth", "system", "config", "task"}


@router.get("")
def list_notifications(
    status: str | None = Query(default=None, description="unread / read / None(全部)"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """列出通知（默认未读置顶）

    为什么不限制为只能看未读：用户可能想回看"我之前漏看什么"，
    走 status=read 即可；同时返回 total 字段，前端用于分页/计数展示。
    """
    rows = container.repo.list_notifications(status=status, limit=limit, offset=offset)
    total = container.repo.count_notifications(status=status)
    return {
        "items": rows,
        "count": len(rows),
        "total": total,
        "limit": limit,
        "offset": offset,
        "status": status or "all",
    }


@router.get("/unread_count")
def unread_count(
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """未读数（给顶栏铃铛 badge 单独拉取，避免列表里再算）"""
    return {"unread": container.repo.count_notifications(status="unread")}


@router.post("")
def create_notification(
    payload: dict[str, Any] = Body(...),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """创建/更新一条通知（业务模块内部调用 + 测试用）

    必填：level, category, title, message, dedup_key
    可选：link, reset_read
    """
    level = (payload.get("level") or "info").lower()
    category = (payload.get("category") or "").lower()
    title = (payload.get("title") or "").strip()
    message = (payload.get("message") or "").strip()
    dedup_key = (payload.get("dedup_key") or "").strip()
    link = payload.get("link")
    reset_read = bool(payload.get("reset_read", True))

    # 入参校验：白名单 + 必填 → 防止脏数据
    if level not in _ALLOWED_LEVELS:
        raise HTTPException(status_code=400, detail=f"level 必须是 {_ALLOWED_LEVELS} 之一")
    if category not in _ALLOWED_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"category 必须是 {_ALLOWED_CATEGORIES} 之一")
    if not title:
        raise HTTPException(status_code=400, detail="title 必填")
    if not message:
        raise HTTPException(status_code=400, detail="message 必填")
    if not dedup_key:
        raise HTTPException(status_code=400, detail="dedup_key 必填（用于业务去重）")
    # 防 dedup_key 过长撑爆数据库
    if len(dedup_key) > 200:
        raise HTTPException(status_code=400, detail="dedup_key 太长（≤200）")
    if link is not None and len(link) > 500:
        raise HTTPException(status_code=400, detail="link 太长（≤500）")

    row = container.repo.add_notification(
        level=level,
        category=category,
        title=title,
        message=message,
        link=link,
        dedup_key=dedup_key,
        reset_read=reset_read,
    )
    return {"ok": True, "item": row}


@router.post("/{notif_id}/read")
def mark_read(
    notif_id: int,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """标记单条已读（幂等：已读的不报错）"""
    existed = container.repo.get_notification(notif_id)
    if not existed:
        raise HTTPException(status_code=404, detail="通知不存在")
    updated = container.repo.mark_notification_read(notif_id)
    return {"ok": True, "id": notif_id, "newly_read": updated}


@router.post("/read_all")
def mark_all_read(
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """全部标记已读（"打开通知中心"行为时使用）"""
    updated = container.repo.mark_all_notifications_read()
    return {"ok": True, "updated": updated}


@router.delete("/{notif_id}")
def delete_notification(
    notif_id: int,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """删除单条"""
    existed = container.repo.get_notification(notif_id)
    if not existed:
        raise HTTPException(status_code=404, detail="通知不存在")
    deleted = container.repo.delete_notification(notif_id)
    return {"ok": True, "id": notif_id, "deleted": deleted}


@router.delete("")
def clear_notifications(
    status: str | None = Query(default=None, description="unread / read / None(全部)"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """清空通知（带 status 过滤）

    为什么不默认"清空 = 全清"：用户最常见操作是"清掉已读的腾出空间"，
    走 status=read 即可；status 留 None 仍然支持全清，但前端默认走 read。
    """
    if status is not None and status not in ("unread", "read"):
        raise HTTPException(status_code=400, detail="status 必须是 unread / read")
    deleted = container.repo.clear_notifications(status=status)
    return {"ok": True, "deleted": deleted, "status": status or "all"}
