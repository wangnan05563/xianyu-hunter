"""账号管理 API - 多账号列表 / 切换 / 退出 / 会话事件

设计文档 §3.5.1 账号管理 API 蓝图实现。

路由前缀 /api/auth，与现有 /api/auth/cookie、/api/auth/me 等保持一致，
所有端点需鉴权（中间件注入 request.state.user_id）。
敏感字段（token 原文、Cookie 值）不记录日志，detail 字段在写入时已脱敏。
"""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text as sa_text

from xianyu_hunter.web.routes.auth_helpers import make_auth_response
from xianyu_hunter.web.services.user_manager import get_user_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["accounts"])

# UserManager 已禁止删除 default 用户；这里仅作文档化常量，避免散落硬编码
_DEFAULT_USER_ID = "default"

# 防滥用：会话事件查询上限，避免前端误传 limit=100w 拖垮 SQLite
_MAX_EVENT_LIMIT = 1000


class SwitchAccountBody(BaseModel):
    """切换账号请求体

    字段名 target_user_id 与设计文档严格对齐：
    需求规格 L341 [POST /api/auth/switch {target_user_id}]、概要设计 L825 入参 {target_user_id}。
    语义明确"目标账号"，避免与请求体中其他 user_id 字段混淆。
    """
    target_user_id: str = Field(..., description="目标账号 user_id")


@router.get("/accounts")
def list_accounts(request: Request) -> dict[str, Any]:
    """列出所有已登录账号

    返回所有用户记录（含 disabled 状态），附加 is_current 标记当前登录账号。
    不过滤 disabled：由展示层负责过滤，保留历史记录便于审计。
    """
    user_manager = get_user_manager()
    current_user_id = getattr(request.state, "user_id", _DEFAULT_USER_ID)
    users = user_manager.list_users()
    items = [
        {
            "user_id": u.get("user_id", ""),
            "nickname": u.get("nickname", ""),
            "avatar_url": u.get("avatar_url", ""),
            "custom_alias": u.get("custom_alias", ""),
            "status": u.get("status", "active"),
            "is_current": u.get("user_id") == current_user_id,
            "last_active_at": u.get("last_active_at"),
            "last_login_at": u.get("last_login_at"),
            "created_at": u.get("created_at"),
        }
        for u in users
    ]
    return {"accounts": items, "items": items, "count": len(items)}


@router.post("/switch")
def switch_account(body: SwitchAccountBody, request: Request) -> Any:
    """切换账号：签发新 session_token + 写入 xh_token cookie

    关键字传参 session_token，与 unified_login.py 调用风格一致。
    UserManager.issue_session 已含会话固定防护（旧 session 标记 is_active=0）。

    多用户 Cookie 状态同步（C-08 修复）：
    切换账号时必须失效旧用户 + 新用户的 CookieStore 缓存，并重置 CookieRotator
    层状态。否则旧用户的层失效状态会"传染"给新用户，导致 /cookies/layers
    返回错误的 invalid 状态，前端显示"Cookie 异常"。
    为什么重置层状态而非同步：CookieRotator 是全局单例，不按 user_id 隔离，
    切换时无法确定旧层状态属于哪个用户，最安全的方式是清空让下次 /cookies/layers
    重新从 JSON 同步。
    """
    user_manager = get_user_manager()
    # 校验目标账号存在且非 disabled（disabled 不可恢复，需重新添加）
    target = user_manager.get_user(body.target_user_id)
    if not target:
        raise HTTPException(status_code=404, detail="目标账号不存在")
    if target.get("status") == "disabled":
        raise HTTPException(status_code=400, detail="目标账号已禁用，需重新添加")

    # C-08 修复：切换前失效旧用户的 CookieStore 缓存
    # 为什么失效旧用户：30s TTL 内可能读到旧缓存，切换后立即读应直接读 JSON
    old_user_id = getattr(request.state, "user_id", None)
    if old_user_id and old_user_id != body.target_user_id:
        try:
            from xianyu_hunter.web.services.cookie_store import get_cookie_store
            get_cookie_store().invalidate_cache(old_user_id)
        except Exception as e:
            # 不阻断主流程，但记录告警便于排查缓存同步异常
            logger.warning("切换账号时旧用户缓存失效失败 user_id=%s: %s", old_user_id, e)

    token = user_manager.issue_session(body.target_user_id)
    user_manager.update_last_active(body.target_user_id)

    # C-08 修复：切换后失效新用户缓存 + 重置 CookieRotator 层状态
    # 为什么重置而非同步：CookieRotator 全局单例不按 user_id 隔离，
    # 旧用户的失效状态不应保留到新用户。重置后 /cookies/layers 会从
    # 新用户的 cookies_{user_id}.json 重新同步层状态。
    try:
        from xianyu_hunter.web.services.cookie_store import get_cookie_store
        get_cookie_store().invalidate_cache(body.target_user_id)
    except Exception as e:
        logger.warning("切换账号时新用户缓存失效失败 user_id=%s: %s", body.target_user_id, e)
    try:
        from xianyu_hunter.modules.login_orchestrator import get_orchestrator
        get_orchestrator().cookie_rotator.invalidate_all()
    except Exception as e:
        logger.warning("切换账号时重置 CookieRotator 层状态失败: %s", e)

    result = {
        "ok": True,
        "user_id": body.target_user_id,
        "nickname": target.get("nickname", ""),
        "avatar_url": target.get("avatar_url", ""),
        "session_set": True,
    }
    return make_auth_response(result, session_token=token)


@router.post("/logout")
def logout_account(request: Request) -> JSONResponse:
    """退出当前账号：撤销 session + 清除 xh_token cookie

    default 用户也允许 logout（仅撤销当前会话，不删除用户记录），
    这是与 delete 端点的核心差异——default 不可删除但可退出。
    """
    user_manager = get_user_manager()
    user_id = getattr(request.state, "user_id", _DEFAULT_USER_ID)
    user_manager.revoke_session(user_id)

    # 清除 xh_token cookie，强制前端回到登录页
    resp = JSONResponse(content={"ok": True})
    resp.delete_cookie("xh_token")
    return resp


@router.get("/session-events")
def get_session_events(
    request: Request,
    limit: int = 100,
) -> dict[str, Any]:
    """查询当前登录用户的会话事件日志

    安全修复（mu-audit Critical）：移除 user_id 查询参数，强制只查当前登录用户事件。
    原实现接受 user_id 查询参数直接过滤 user_session_events 表，但未校验调用方权限，
    任何登录用户均可通过 ?user_id=other_user_id 越权查询其他用户的事件流
    （登录/退出/Cookie 过期等），泄露账号活跃状态画像。

    修复后从 request.state.user_id 读取中间件注入的当前用户身份，
    拒绝任何外部传入的 user_id 覆盖，确保用户只能查看自己的事件。
    按 created_at DESC 返回最近 limit 条事件。
    detail 字段在写入时已脱敏（不含 token 原文 / Cookie 值），可直接返回。
    """
    user_manager = get_user_manager()
    # 防滥用：limit 上限 1000，与 api_tasks.list_tasks 的限制风格一致
    effective_limit = max(1, min(limit, _MAX_EVENT_LIMIT))

    # 强制使用中间件注入的当前用户身份，忽略任何外部传入的 user_id
    # 为什么不读 query 参数：原 user_id 参数是越权根因，移除后从源头杜绝覆盖
    user_id = getattr(request.state, "user_id", _DEFAULT_USER_ID)

    # 直接通过 user_manager 的 engine 查询 user_session_events 表
    # 为什么不在 UserManager 中加 query_events 方法：会话事件查询是展示层需求，
    # 不属于用户身份管理核心职责，放在路由内保持 UserManager 接口精简
    engine = user_manager._engine
    with engine.connect() as conn:
        rows = conn.execute(
            sa_text(
                "SELECT id, user_id, event_type, detail, created_at "
                "FROM user_session_events WHERE user_id=:uid "
                "ORDER BY created_at DESC LIMIT :limit"
            ),
            {"uid": user_id, "limit": effective_limit},
        ).fetchall()

    items = [
        {
            "id": r[0],
            "user_id": r[1],
            "event_type": r[2],
            "detail": _safe_parse_json(r[3]),
            "created_at": r[4],
        }
        for r in rows
    ]
    return {"items": items, "count": len(items)}


def _safe_parse_json(value: str | None) -> dict:
    """安全解析 JSON 字符串，统一返回 dict

    为什么需要：user_session_events.detail 字段虽约定为 JSON，
    但历史数据或异常写入可能不是合法 JSON，避免解析失败导致整个响应 500。
    为什么统一返回 dict：原实现空值返回 {}、合法 JSON 返回原始类型、非法 JSON 返回 str，
    类型不一致让下游消费者需要多处 isinstance 判断；统一包装为 dict 后下游可直接 .get()。
    """
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
        # list/str/number 等非 dict 类型包装为 dict，保留原始值供下游消费
        return {"_raw": parsed}
    except (json.JSONDecodeError, TypeError):
        # 非法 JSON 包装为 dict，避免返回 str 让下游 isinstance 判断失效
        return {"_raw": value}
