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
# SSE 流免认证（未登录时返回空流）；通知接口免认证（供外部回调调用）。
#
# ⚠️ 域名模式（/xianyu 子路径）：鉴权在 dispatch 中把 /xianyu 命名空间前缀归一化掉，
#    /xianyu/api/X -> /api/X、/xianyu/login -> /login，使本白名单与 401 逻辑对
#    /api 与 /xianyu/api 完全复用。因此此处【不再】保留 blanket "/xianyu/"，
#    否则会让 /xianyu/api/* 全部免认证而扩大暴露面（见 P1 安全观察）。
PUBLIC_PREFIXES = (
    "/static/", "/healthz",
    "/api/auth/login", "/api/auth/verify",
    "/api/auth/cookie",          # 手动 Cookie 注入（未登录时也需要调用）
    "/api/auth/me",              # 登录状态检测（未登录时返回 logged_in=false）
    "/api/auth/restore-session",  # 会话恢复（免登录即可触发首启动重建会话）
    "/api/auth/verify-session",  # 会话有效性验证
    "/api/auth/import-from-browser",  # 从系统浏览器导入 Cookie（未登录时也需要调用）
    "/api/auth/browser-login",   # Playwright 浏览器登录（推荐方式）
    "/api/events/stream",        # Dashboard SSE（未登录时返回空事件流）
    "/api/logs/stream",          # 日志 SSE 实时流（未登录时返回空流）
    "/api/notifications",        # 通知相关（无尾部斜杠，匹配 /api/notifications 和 /api/notifications/...）
    "/api/notifier/",            # 通知器配置（免打扰等）
    "/api/docs", "/openapi.json",
    "/api/about",                # 关于菜单：系统元信息 + 检查更新
    "/api/tunnel/status",        # 内网穿透：未登录也需可查询隧道状态（远程访问引导）
    "/api/tunnel/start",         # 启动隧道（远程访问引导：未登录时需先建隧道才能访问登录页）
    "/api/tunnel/stop",          # 停止隧道（与 start 对称）
    # /api/tunnel/config 不在白名单：修改 provider/authtoken 需认证，防止未授权篡改
    "/.well-known/",             # 浏览器/DevTools 自动探测路径（com.chrome.devtools.json 等），无需认证
    "/@vite/client",             # Vite HMR 客户端：浏览器缓存开发模式 HTML 后误请求生产后端，无需认证
)


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Bearer Token 认证中间件

    从 Authorization header 或 xh_token cookie 中提取 token，
    与 .env 中配置的 WEB_TOKEN 做恒定时间比较。
    """

    def _extract_candidate_tokens(self, request: Request) -> list[str]:
        """从 Authorization header 和 cookie 中提取候选 token

        Authorization 优先，但失败后继续尝试 cookie，避免前端 localStorage
        残留旧 token 覆盖刚登录写入的 HttpOnly xh_token cookie。
        """
        auth_header = request.headers.get("authorization", "")
        candidate_tokens: list[str] = []
        if auth_header.startswith("Bearer "):
            candidate_tokens.append(auth_header[7:])
        cookie_token = request.cookies.get("xh_token", "")
        if cookie_token and cookie_token not in candidate_tokens:
            candidate_tokens.append(cookie_token)
        return candidate_tokens

    def _verify_session_token(self, candidate_tokens: list[str], logger) -> str | None:
        """校验 session token，返回 user_id 或 None"""
        from xianyu_hunter.web.services.user_manager import get_user_manager
        for req_token in candidate_tokens:
            try:
                user_id = get_user_manager().verify_session(req_token)
            except Exception as e:
                logger.warning(f"[Auth] session 校验异常，降级尝试下一个 token: {e}")
                user_id = None
            if user_id:
                return user_id
        return None

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # 域名模式归一化：前端以 /xianyu/ 子路径部署，API 经 /xianyu/api/ 透传后端。
        # 剥离命名空间前缀后 /api/* 与 /xianyu/api/* 走同一套白名单与 401 逻辑，
        # 既避免双份维护，也防止 /xianyu/api/* 被 blanket 放行而免认证面扩大。
        #   /xianyu/        -> /          （SPA 根，按根路径放行）
        #   /xianyu/login   -> /login     （SPA 页面，非 API，无 token 也放行）
        #   /xianyu/api/me  -> /api/me    （API，沿用 /api 白名单与 401 逻辑）
        if path.startswith("/xianyu"):
            norm_path = path[7:] or "/"
        else:
            norm_path = path

        # 公开路径直接放行（已归一化）
        for prefix in PUBLIC_PREFIXES:
            if norm_path.startswith(prefix):
                return await call_next(request)

        # 根路径放行（前端会处理认证跳转）
        if norm_path == "/":
            return await call_next(request)

        from xianyu_hunter.config import get_settings
        from loguru import logger

        # 从 Authorization header 和 cookie 中取 token（提取到辅助方法降低认知复杂度）
        candidate_tokens = self._extract_candidate_tokens(request)

        if not candidate_tokens:
            if norm_path.startswith("/api/"):
                return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
            return await call_next(request)

        web_token = get_settings().web_token

        # 路径 1：WEB_TOKEN 管理令牌直通（向后兼容单用户模式）
        for req_token in candidate_tokens:
            if hmac.compare_digest(req_token.encode(), web_token.encode()):
                request.state.user_id = "default"
                return await call_next(request)

        # 路径 2：session_token 多用户会话校验（提取到辅助方法降低认知复杂度）
        user_id = self._verify_session_token(candidate_tokens, logger)
        if user_id:
            request.state.user_id = user_id
            return await call_next(request)

        # 路径 3：校验失败
        logger.debug(
            f"[Auth] path={norm_path} has_cookie={'xh_token' in request.cookies} web_token_match=False session_invalid=True",
        )
        if norm_path.startswith("/api/"):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        return await call_next(request)


def setup_auth_middleware(app: FastAPI) -> None:
    """注册认证中间件到 FastAPI 应用"""
    app.add_middleware(BearerAuthMiddleware)
