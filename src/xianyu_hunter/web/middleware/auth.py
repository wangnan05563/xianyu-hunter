"""Bearer Token 认证中间件

本地个人工具场景：防止同网络其他设备随意访问。
- 浏览器首次访问 / 时，如果没带 token，重定向到 /api/auth/login/start
- API 请求缺少 token 返回 401
- 页面请求通过 cookie 中的 token 验证
"""
from __future__ import annotations

import hmac

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# 不需要认证的路径前缀
# SPA 页面本身免认证（API 调用仍需 token）；认证相关接口免认证（否则登录流程无法启动）；
# SSE 流免认证（未登录时返回空流）；通知接口免认证（供外部回调调用）
PUBLIC_PREFIXES = (
    "/static/", "/healthz",
    "/app/",                     # SPA 可视化控制台页面（API 调用仍需 token）
    "/api/auth/login", "/api/auth/verify",
    "/api/auth/cookie",          # 手动 Cookie 注入（未登录时也需要调用）
    "/api/auth/me",              # 登录状态检测（未登录时返回 logged_in=false）
    "/api/auth/verify-session",  # 会话有效性验证
    "/api/auth/import-from-browser",  # 从系统浏览器导入 Cookie（未登录时也需要调用）
    "/api/auth/browser-login",   # Playwright 浏览器登录（推荐方式）
    "/api/events/stream",        # Dashboard SSE（未登录时返回空事件流）
    "/api/logs/stream",          # 日志 SSE 实时流（未登录时返回空流）
    "/api/notifications",        # 通知相关（无尾部斜杠，匹配 /api/notifications 和 /api/notifications/...）
    "/api/notifier/",            # 通知器配置（免打扰等）
    "/api/docs", "/openapi.json",
    "/api/about",                # 关于菜单：系统元信息 + 检查更新
    "/api/tunnel",               # 内网穿透：未登录也需可查询/控制隧道（远程访问引导）
)


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Bearer Token 认证中间件

    从 Authorization header 或 xh_token cookie 中提取 token，
    与 .env 中配置的 WEB_TOKEN 做恒定时间比较。
    """

    async def dispatch(self, request: Request, call_next):
        # 公开路径直接放行
        for prefix in PUBLIC_PREFIXES:
            if request.url.path.startswith(prefix):
                return await call_next(request)

        # 根路径放行（前端会处理认证跳转）
        if request.url.path == "/":
            return await call_next(request)

        from xianyu_hunter.config import get_settings
        from loguru import logger

        # 从 Authorization header 或 cookie 中取 token
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            req_token = auth_header[7:]
        else:
            req_token = request.cookies.get("xh_token", "")

        if not req_token:
            if request.url.path.startswith("/api/"):
                return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
            return await call_next(request)

        web_token = get_settings().web_token

        # 路径 1：WEB_TOKEN 管理令牌直通（向后兼容单用户模式）
        if hmac.compare_digest(req_token.encode(), web_token.encode()):
            request.state.user_id = "default"
            return await call_next(request)

        # 路径 2：session_token 多用户会话校验
        try:
            from xianyu_hunter.web.services.user_manager import get_user_manager
            user_id = get_user_manager().verify_session(req_token)
        except Exception as e:
            logger.warning("[Auth] session 校验异常，降级到 401: %s", e)
            user_id = None

        if user_id:
            request.state.user_id = user_id
            return await call_next(request)

        # 路径 3：校验失败
        logger.debug(
            "[Auth] path=%s has_cookie=%s web_token_match=False session_invalid=True",
            request.url.path, 'xh_token' in request.cookies,
        )
        if request.url.path.startswith("/api/"):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        return await call_next(request)


def setup_auth_middleware(app: FastAPI) -> None:
    """注册认证中间件到 FastAPI 应用"""
    app.add_middleware(BearerAuthMiddleware)
