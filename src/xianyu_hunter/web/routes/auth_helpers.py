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
    # 设计说明：samesite="none" 允许移动端跨域携带 Cookie（PWA / 内网穿透访问场景必需）
    # CSRF 风险评估：本工具定位为本地个人工具，不对外公网开放；
    # 通过内网穿透暴露时，应在网络层（反向代理 / 防火墙）限制访问来源，
    # 而非在应用层校验 Origin（个人工具增加 Origin 校验会拖累开发体验且收益有限）。
    # 如未来需增强安全：可在 auth 中间件中对 POST/PUT/DELETE 校验 Origin header 白名单。
    resp.set_cookie(
        key="xh_token",
        value=token,
        httponly=True,
        # 与 verify_token 保持一致：SameSite=None 允许移动端跨域携带
        # Secure 是 SameSite=None 的强制要求，否则浏览器会拒绝设置 cookie
        samesite="none",
        secure=True,
        max_age=86400 * 30,  # 30 天
    )
    return resp
