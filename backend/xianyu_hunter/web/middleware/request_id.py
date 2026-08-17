"""全局流水号中间件

职责：
- 请求入口生成或透传 request_id（支持 X-Request-Id 头传入）
- 设置到 request.state 与 ContextVar，供后续中间件/路由/日志/数据库层读取
- 在响应头回传 X-Request-Id，便于前端/客户端关联排障

中间件执行顺序（FastAPI LIFO）：
    RequestIdMiddleware（最先执行，最外层）
      → BearerAuthMiddleware
        → 路由
      → BearerAuthMiddleware
    RequestIdMiddleware（最后执行，最外层）

为什么放在最外层：认证中间件、异常处理器、所有路由日志都依赖 request_id，
必须最先注入、最后清理。
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

from xianyu_hunter.infra.request_context import (
    clear_request_id,
    generate_request_id,
    is_valid_request_id,
    set_request_id,
)

# 客户端透传头名称
_REQUEST_ID_HEADER = "X-Request-Id"


class RequestIdMiddleware(BaseHTTPMiddleware):
    """全局流水号中间件

    从 X-Request-Id 头读取客户端传入的流水号（需通过格式校验防止伪造注入），
    否则服务端生成新的流水号。设置到 request.state 和 ContextVar，
    供认证中间件、路由、日志层、数据库层统一读取。
    """

    async def dispatch(self, request: Request, call_next):
        # 优先使用客户端透传的 request_id（需通过格式校验防止注入任意字符串）
        rid = request.headers.get(_REQUEST_ID_HEADER, "")
        if not is_valid_request_id(rid):
            rid = generate_request_id()

        # 双重存储：request.state 供同步代码读取，ContextVar 供异步任务和 loguru 读取
        request.state.request_id = rid
        set_request_id(rid)

        try:
            response = await call_next(request)
        finally:
            # 清理 ContextVar 防止跨请求泄漏（ContextVar 在协程栈中持久化）
            clear_request_id()

        # 响应头回传便于前端/客户端关联排障
        response.headers[_REQUEST_ID_HEADER] = rid
        return response


def setup_request_id_middleware(app: FastAPI) -> None:
    """注册流水号中间件到 FastAPI 应用

    必须在 setup_auth_middleware 之后调用：
    FastAPI 中间件按 LIFO 执行，后注册的先执行，
    因此 RequestIdMiddleware 后注册 → 最先执行 → 包裹认证中间件。
    """
    app.add_middleware(RequestIdMiddleware)
