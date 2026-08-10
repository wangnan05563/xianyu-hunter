"""认证辅助函数 - 被多个 auth 子模块共享的工具函数
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from xianyu_hunter.config import get_settings

# 当前请求协议（"http"/"https"），由 RequestSchemeMiddleware 在每个请求进入时写入。
# 为什么用 ContextVar 而非给 make_auth_response 逐处传 request：
#   make_auth_response 被 13+ 处调用（含深层 helper），逐处传 request 改动面大且易遗漏；
#   ContextVar 由最外层【原始】ASGI 中间件统一写入，端点内（含 BaseHTTPMiddleware 派生的
#   子任务）读取即可，做到"定义一次、处处生效"。默认 https 保持旧行为（Secure cookie）。
_request_scheme_ctx: ContextVar[str] = ContextVar("xh_request_scheme", default="https")


def _resolve_secure_policy(request: Request | None = None) -> tuple[bool, str]:
    """根据请求协议决定 xh_token cookie 的 Secure / SameSite 属性

    - HTTPS：secure=True + samesite="none"（保留移动端跨域携带能力）
    - HTTP ：secure=False + samesite="lax"
      ⚠️ 关键：SameSite=None 强制要求 Secure，否则浏览器直接拒绝设置该 cookie。
      纯 HTTP（IP 访问，如 http://127.0.0.1:8001）若仍设 secure=True，
      浏览器会丢弃 xh_token，导致登录 / 切换账号后整页刷新，导航栏 / 反爬页
      解析不到 user_id，误读 cookies_default.json 而报 "Cookie 异常" /
      身份层 / 会话层 / 追踪层 "缺失"（与 bug #2/#3 同源根因）。

    优先级：显式传入的 request > ContextVar（由中间件写入）> 默认 https。
    兼容反向代理：若前置 TLS 终止且未改 scheme，可用 X-Forwarded-Proto 识别真实 https。
    """
    scheme = None
    if request is not None:
        scheme = request.url.scheme
    else:
        scheme = _request_scheme_ctx.get()
    # 反向代理场景：真实协议可能在 X-Forwarded-Proto
    if request is not None:
        fwd = request.headers.get("x-forwarded-proto", "").lower()
        if fwd in ("https", "http"):
            scheme = fwd
    is_https = (scheme or "https") == "https"
    if is_https:
        return True, "none"
    return False, "lax"


def make_auth_response(data: dict, session_token: str | None = None, request: Request | None = None) -> JSONResponse:
    """构建带 xh_token 认证 Cookie 的响应

    Cookie 注入成功后，用户需要同时获得 Web 会话认证，
    否则后续 /api/tasks 等 API 调用都会 401。

    Args:
        data: 响应 JSON 数据
        session_token: 多用户会话令牌。传入时写入 session_token；
                       不传时回退到全局 web_token（向后兼容单用户模式）
        request: 当前请求（用于按协议决定 Secure/SameSite）。不传时回退到
                 ContextVar（由 RequestSchemeMiddleware 写入）/ 默认 https。
    """
    resp = JSONResponse(content=data)
    token = session_token if session_token else get_settings().web_token
    secure, samesite = _resolve_secure_policy(request)
    # 设计说明：samesite="none" 允许移动端跨域携带 Cookie（PWA / 内网穿透访问场景必需）
    # CSRF 风险评估：本工具定位为本地个人工具，不对外公网开放；
    # 通过内网穿透暴露时，应在网络层（反向代理 / 防火墙）限制访问来源，
    # 而非在应用层校验 Origin（个人工具增加 Origin 校验会拖累开发体验且收益有限）。
    # 如未来需增强安全：可在 auth 中间件中对 POST/PUT/DELETE 校验 Origin header 白名单。
    # 注意：SameSite=None 必须与 Secure 同时出现，故 HTTPS 才用 none；HTTP 改用 lax
    # （否则浏览器拒绝设置 cookie，导致纯 HTTP 访问下登录 / 切换后导航栏报 "Cookie 异常"）。
    resp.set_cookie(
        key="xh_token",
        value=token,
        httponly=True,
        samesite=samesite,
        secure=secure,
        max_age=86400 * 30,  # 30 天
    )
    return resp


class RequestSchemeMiddleware:
    """最外层【原始】ASGI 中间件：在每个请求进入时把协议写入 ContextVar

    为什么是最外层原始（非 BaseHTTPMiddleware）中间件：
    - 原始 ASGI 中间件在【同一任务上下文】中 await 下游 app，不会像 BaseHTTPMiddleware
      那样把端点 spawn 到子任务而切断 contextvar 透传；
    - 注册为最外层（app.add_middleware 最后添加 → LIFO 最先执行），确保端点读取到 scheme。

    已通过最小复现验证：RawOuter 写入的 ContextVar 能穿透 BaseHTTPMiddleware 到达端点
    （http→'http'、https→'https' 均正确）。
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            _request_scheme_ctx.set(scope.get("scheme", "https"))
        await self.app(scope, receive, send)
