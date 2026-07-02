"""认证辅助函数 - 被多个 auth 子模块共享的工具函数
"""
from __future__ import annotations

from fastapi.responses import JSONResponse

from xianyu_hunter.config import get_settings


def make_auth_response(data: dict, session_token: str | None = None) -> JSONResponse:
    """构建带 xh_token 认证 Cookie 的响应

    Cookie 注入成功后，用户需要同时获得 Web 会话认证，
    否则后续 /api/tasks 等 API 调用都会 401。

    Args:
        data: 响应 JSON 数据
        session_token: 多用户会话令牌。传入时写入 session_token；
                       不传时回退到全局 web_token（向后兼容单用户模式）
    """
    resp = JSONResponse(content=data)
    token = session_token if session_token else get_settings().web_token
    resp.set_cookie(
        key="xh_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400 * 30,  # 30 天
    )
    return resp
