"""业务通知 API（P1-4 Notification Center）

与 /api/events/* 的分工：
- /api/events/*：技术性事件流（SSE 推送 + 历史回溯），只读追加，不区分已读
- /api/notifications：业务性通知（订单超时、登录态失效等），持久化、可读/可删

多用户归属口径（T02618）——本文件 8 个端点一律用 `web.utils.owner_user_id(request)`：
真实会话用户 → 该用户；WEB_TOKEN 直通与未过中间件的内部调用 → "default"。
读写同函数是两条硬约束的交集：
- 「看得见 = 改得动」：原先读侧兜 None（全量）、写侧兜 "default"（过滤），两套值
  错开时列表能看见、点了标记已读/删除却 404，前端表现即「点了没反应」。
- 「跨用户可见即越权」：tests/test_order_stats_and_notif_batch.py 的
  test_batch_delete_is_user_scoped 明确锁住「直通身份也删不掉 other 用户的行」，
  所以这里不能学日志侧（T02684 `reader_user_id`）放开为不过滤——
  日志是只读场景，通知有改侧，放开读侧就会连带放开改侧或制造 404。
通知行的 user_id 是 NOT NULL，owner_user_id 保证创建侧永远拿到非空值。

⚠ 尚未收口的结构性残留（已建派生单）：`notifications` 表上是
UNIQUE(dedup_key) 而非 UNIQUE(user_id, dedup_key)，跨用户的同名 dedup_key 会
互相抢占同一行（先写者持有归属），所以"按用户隔离"目前只在常规 key 形态下成立
（订单号/商品 ID 天然不撞）。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from xianyu_hunter.container import Container
from xianyu_hunter.domain.notification import (
    NOTIFICATION_CATEGORY_ORDER,
    NOTIFICATION_CATEGORY_VALUES,
    NOTIFICATION_LEVEL_ORDER,
    NOTIFICATION_LEVEL_VALUES,
)
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.utils import owner_user_id

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


# 通知级别与"可创建"的业务场景白名单
# 为什么不开放 category/level 任意写入：内部 API 也加白名单，防止误调用造出垃圾
# （外部如果需要创建通知，调用 /api/notifications 即可，但需要带 dedup_key 表明业务意图）
# 白名单不在此处手写枚举，而是取自 domain/notification（T02619）：
# 原先这里是硬编码 5 个分类，唯独漏了 price_watch 真实写入的 price，
# 导致「仓储能落库、API 会 400、前端标签渲染空白」三态不一致。
_ALLOWED_LEVELS: frozenset[str] = NOTIFICATION_LEVEL_VALUES
_ALLOWED_CATEGORIES: frozenset[str] = NOTIFICATION_CATEGORY_VALUES


@router.get("")
def list_notifications(
    request: Request,
    status: str | None = Query(default=None, description="unread / read / None(全部)"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """列出通知（默认未读置顶）

    为什么不限制为只能看未读：用户可能想回看"我之前漏看什么"，
    走 status=read 即可；同时返回 total 字段，前端用于分页/计数展示。
    """
    # 多用户隔离：读侧与创建侧同源，统一走 web.utils.owner_user_id（T02618）
    user_id = owner_user_id(request)
    rows = container.repo.list_notifications(status=status, limit=limit, offset=offset, user_id=user_id)
    total = container.repo.count_notifications(status=status, user_id=user_id)
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
    request: Request,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """通知全量计数（未读 / 已读 / 总数）

    为什么一个端点回三个数：铃铛 badge、告警抽屉、通知中心三处都要显示计数，
    而通知中心页的「已读」原先用 `列表 total − unread` 现算，total 随筛选变化导致恒 0 或错算
    （T02561 / 2.9-3）。三个数都由后端按"当前用户命名空间内的全量"算出，
    与任何列表筛选（status/分页）无关——命名空间仍走 owner_user_id（T02618），
    否则铃铛计数与列表页会各报一套。
    """
    # 多用户隔离：读侧与创建侧同源，统一走 web.utils.owner_user_id（T02618）
    user_id = owner_user_id(request)
    return {
        "unread": container.repo.count_notifications(status="unread", user_id=user_id),
        "read": container.repo.count_notifications(status="read", user_id=user_id),
        "total": container.repo.count_notifications(status=None, user_id=user_id),
    }


@router.post("")
def create_notification(
    request: Request,
    payload: dict[str, Any] = Body(...),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """创建/更新一条通知（业务模块内部调用 + 测试用）

    必填：level, category, title, message, dedup_key
    可选：link, reset_read
    """
    # 多用户隔离：创建侧需要一个非空归属值 → web.utils.owner_user_id（T02618）
    user_id = owner_user_id(request)
    level = (payload.get("level") or "info").lower()
    category = (payload.get("category") or "").lower()
    title = (payload.get("title") or "").strip()
    message = (payload.get("message") or "").strip()
    dedup_key = (payload.get("dedup_key") or "").strip()
    link = payload.get("link")
    reset_read = bool(payload.get("reset_read", True))

    # 入参校验：白名单 + 必填 → 防止脏数据
    # 报错文案取 domain 的声明序（NOTIFICATION_*_ORDER）而不是 sorted(frozenset)：
    # 字母序会把等级写成 "err/info/warn"，既不按严重度、每次看起来也像集合调试输出
    if level not in _ALLOWED_LEVELS:
        raise HTTPException(
            status_code=400,
            detail=f"level 必须是 {'/'.join(NOTIFICATION_LEVEL_ORDER)} 之一",
        )
    if category not in _ALLOWED_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"category 必须是 {'/'.join(NOTIFICATION_CATEGORY_ORDER)} 之一",
        )
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
        user_id=user_id,
    )
    return {"ok": True, "item": row}


@router.post("/{notif_id}/read")
def mark_read(
    notif_id: int,
    request: Request,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """标记单条已读（幂等：已读的不报错）"""
    # 多用户隔离：改侧与读侧必须同一口径（看得见 = 改得动），见 web.utils.owner_user_id
    user_id = owner_user_id(request)
    existed = container.repo.get_notification(notif_id, user_id=user_id)
    if not existed:
        raise HTTPException(status_code=404, detail="通知不存在")
    updated = container.repo.mark_notification_read(notif_id, user_id=user_id)
    return {"ok": True, "id": notif_id, "newly_read": updated}


@router.post("/read_all")
def mark_all_read(
    request: Request,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """全部标记已读（"打开通知中心"行为时使用）"""
    # 多用户隔离：改侧与读侧必须同一口径（看得见 = 改得动），见 web.utils.owner_user_id
    user_id = owner_user_id(request)
    updated = container.repo.mark_all_notifications_read(user_id=user_id)
    return {"ok": True, "updated": updated}


@router.delete("/{notif_id}")
def delete_notification(
    notif_id: int,
    request: Request,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """删除单条"""
    # 多用户隔离：改侧与读侧必须同一口径（看得见 = 改得动），见 web.utils.owner_user_id
    user_id = owner_user_id(request)
    existed = container.repo.get_notification(notif_id, user_id=user_id)
    if not existed:
        raise HTTPException(status_code=404, detail="通知不存在")
    deleted = container.repo.delete_notification(notif_id, user_id=user_id)
    return {"ok": True, "id": notif_id, "deleted": deleted}


# 批量删除的单次上限：前端勾选分页最大 200，这里与列表 limit 同口径，
# 避免一次 DELETE 传上万个 id 把 IN 子句撑爆（SQLite 变量上限默认 999）。
_BATCH_DELETE_MAX = 200


@router.post("/batch-delete")
def batch_delete_notifications(
    request: Request,
    payload: dict[str, Any] = Body(..., description='{"ids": [1, 2, 3]}'),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """批量删除通知（通知中心「勾选后删除」）

    为什么不复用 DELETE ""?（clear_notifications）：清空按 status 维度全量删除，
    无法表达"只删我勾的这几条"；且清空是不可逆的批量操作，语义应与勾选删除分开。
    deleted < requested 是正常的：勾中的 id 可能已被别人（其他标签页）删掉，
    这里如实返回两个数，由前端提示"实际删除 N 条"而不是假装全部成功。
    """
    user_id = owner_user_id(request)
    raw_ids = payload.get("ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        raise HTTPException(status_code=400, detail="ids 必须是非空数组")
    if len(raw_ids) > _BATCH_DELETE_MAX:
        raise HTTPException(
            status_code=400, detail=f"单次最多删除 {_BATCH_DELETE_MAX} 条"
        )
    ids: list[int] = []
    for item in raw_ids:
        try:
            ids.append(int(item))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="ids 必须是通知 id 数组")
    deleted = container.repo.delete_notifications(ids, user_id=user_id)
    return {"ok": True, "deleted": deleted, "requested": len(ids)}


@router.delete("")
def clear_notifications(
    request: Request,
    status: str | None = Query(default=None, description="unread / read / None(全部)"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """清空通知（带 status 过滤）

    为什么不默认"清空 = 全清"：用户最常见操作是"清掉已读的腾出空间"，
    走 status=read 即可；status 留 None 仍然支持全清，但前端默认走 read。
    """
    # 多用户隔离：改侧与读侧必须同一口径（看得见 = 改得动），见 web.utils.owner_user_id
    user_id = owner_user_id(request)
    if status is not None and status not in ("unread", "read"):
        raise HTTPException(status_code=400, detail="status 必须是 unread / read")
    deleted = container.repo.clear_notifications(status=status, user_id=user_id)
    return {"ok": True, "deleted": deleted, "status": status or "all"}
