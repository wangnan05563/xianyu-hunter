"""账号管理 API - 多账号列表 / 切换 / 退出 / 会话事件

设计文档 §3.5.1 账号管理 API 蓝图实现。

路由前缀 /api/auth，与现有 /api/auth/cookie、/api/auth/me 等保持一致，
所有端点需鉴权（中间件注入 request.state.user_id）。
敏感字段（token 原文、Cookie 值）不记录日志，detail 字段在写入时已脱敏。
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text as sa_text

from xianyu_hunter.web.routes.auth_helpers import make_auth_response
from xianyu_hunter.web.services.user_manager import get_user_manager

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
    """
    user_manager = get_user_manager()
    # 校验目标账号存在且非 disabled（disabled 不可恢复，需重新添加）
    target = user_manager.get_user(body.target_user_id)
    if not target:
        raise HTTPException(status_code=404, detail="目标账号不存在")
    if target.get("status") == "disabled":
        raise HTTPException(status_code=400, detail="目标账号已禁用，需重新添加")

    token = user_manager.issue_session(body.target_user_id)
    user_manager.update_last_active(body.target_user_id)

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
    user_id: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """查询会话事件日志

    支持按 user_id 过滤；按 created_at 降序返回最近 limit 条事件。
    detail 字段在写入时已脱敏（不含 token 原文 / Cookie 值），可直接返回。
    """
    user_manager = get_user_manager()
    # 防滥用：limit 上限 1000，与 api_tasks.list_tasks 的限制风格一致
    effective_limit = max(1, min(limit, _MAX_EVENT_LIMIT))

    # 直接通过 user_manager 的 engine 查询 user_session_events 表
    # 为什么不在 UserManager 中加 query_events 方法：会话事件查询是展示层需求，
    # 不属于用户身份管理核心职责，放在路由内保持 UserManager 接口精简
    engine = user_manager._engine
    with engine.connect() as conn:
        if user_id:
            rows = conn.execute(
                sa_text(
                    "SELECT id, user_id, event_type, detail, created_at "
                    "FROM user_session_events WHERE user_id=:uid "
                    "ORDER BY created_at DESC LIMIT :limit"
                ),
                {"uid": user_id, "limit": effective_limit},
            ).fetchall()
        else:
            rows = conn.execute(
                sa_text(
                    "SELECT id, user_id, event_type, detail, created_at "
                    "FROM user_session_events ORDER BY created_at DESC LIMIT :limit"
                ),
                {"limit": effective_limit},
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


def _safe_parse_json(value: str | None) -> Any:
    """安全解析 JSON 字符串，失败时返回原始字符串或空 dict

    为什么需要：user_session_events.detail 字段虽约定为 JSON，
    但历史数据或异常写入可能不是合法 JSON，避免解析失败导致整个响应 500。
    """
    if not value:
        return {}
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value
