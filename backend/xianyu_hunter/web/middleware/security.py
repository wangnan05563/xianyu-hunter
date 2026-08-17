"""安全中间件：拦截恶意扫描请求

外部 IP 批量扫描敏感文件路径（.env、.git/、.ssh/、backup.sql 等），
直接返回 404 并跳过后续中间件/路由，减少日志噪声和资源消耗。
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# 敏感路径前缀：匹配则直接拦截（覆盖该前缀下所有子路径）
# 为什么用前缀而非精确匹配：扫描器常尝试 .git/HEAD、.git/config、.ssh/id_rsa 等变体
SENSITIVE_PREFIXES = (
    "/.git",
    "/.svn",
    "/.ssh",
    "/.aws",
    "/.env",
    "/.htaccess",
    "/.htpasswd",
    "/.DS_Store",
    "/wp-admin",
    "/wp-content",
    "/wp-includes",
    "/phpmyadmin",
)

# 敏感路径精确匹配：扫描器常尝试的具体文件名
SENSITIVE_EXACT = frozenset({
    "/config.xml",
    "/dump.sql",
    "/backup.sql",
    "/backup.zip",
    "/backup.tar.gz",
    "/database_backup.sql",
    "/db.sql",
    "/data.sql",
    "/wp-config.php",
    "/wp-login.php",
    "/xmlrpc.php",
    "/phpinfo.php",
    "/docker-compose.yml",
    "/docker-compose.yaml",
    "/composer.json",
    "/composer.lock",
    "/package.json",
    "/package-lock.json",
    "/credentials.json",
    "/service-account.json",
})


class SecurityMiddleware(BaseHTTPMiddleware):
    """安全中间件：拦截敏感文件扫描请求

    为什么独立于 auth 中间件：扫描请求不携带任何认证信息，
    且需在 request_id 分配之前拦截，避免分配无意义的流水号。
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 精确匹配
        if path in SENSITIVE_EXACT:
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

        # 前缀匹配
        for prefix in SENSITIVE_PREFIXES:
            if path.startswith(prefix):
                return JSONResponse(status_code=404, content={"detail": "Not Found"})

        return await call_next(request)


def setup_security_middleware(app: FastAPI) -> None:
    """注册安全中间件

    LIFO 栈后注册的先执行 → SecurityMiddleware 最先执行，
    在 auth/request_id 之前拦截敏感路径。
    """
    app.add_middleware(SecurityMiddleware)
