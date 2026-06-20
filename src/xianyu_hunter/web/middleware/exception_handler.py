"""全局异常处理器

为 FastAPI 应用提供统一的异常兜底：
- Exception：未捕获的异常统一返回 500，避免堆栈信息泄露给前端
- RequestValidationError：422 参数校验失败，保留 FastAPI 原有 detail 结构
- HTTPException：保持原有 status_code 与 detail 格式

设计要点：
- 仅作为兜底，不替代各路由中已有的 try-except（路由层仍可自行处理业务异常）
- 日志记录时对敏感字段（Authorization、Cookie 等）做脱敏，防止 token 泄露到日志文件
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger

# 敏感请求头：记录日志时需脱敏，避免 token/cookie 写入持久化日志
_SENSITIVE_HEADERS = {"authorization", "cookie", "xh_token", "set-cookie"}


def _sanitize_headers(headers: Any) -> dict[str, str]:
    """脱敏请求头，敏感字段只保留键名，值替换为 ***

    之所以在日志层脱敏而非在异常层，是因为日志文件会持久化保留 14 天，
    一旦 token 明文落盘将无法回收。
    """
    safe: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in _SENSITIVE_HEADERS:
            safe[key] = "***"
        else:
            safe[key] = value
    return safe


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底处理所有未捕获的 Exception

    返回统一的 500 响应，不向前端暴露内部堆栈（防止信息泄露）。
    完整异常信息写入日志便于事后排查。
    """
    logger.exception(
        "未处理异常 path={path} method={method} headers={headers} | {exc}",
        path=request.url.path,
        method=request.method,
        headers=_sanitize_headers(request.headers),
        exc=exc,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "内部服务器错误", "code": "internal_error"},
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """处理请求参数校验失败（422）

    保留 FastAPI 默认的 errors 结构，前端依赖该结构展示字段级错误。
    """
    logger.warning(
        "参数校验失败 path={path} | errors={errors}",
        path=request.url.path,
        errors=exc.errors(),
    )
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """处理 HTTPException，保持原有 detail 格式

    各路由主动抛出的 HTTPException（如 404/400/401）走此通道，
    响应体保持 {"detail": ...} 结构，与现有前端契约一致。
    """
    if exc.status_code >= 500:
        logger.warning(
            "HTTPException path={path} status={status} | {detail}",
            path=request.url.path,
            status=exc.status_code,
            detail=exc.detail,
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


def register_exception_handlers(app: Any) -> None:
    """注册全局异常处理器到 FastAPI 应用

    使用 app.add_exception_handler 而非装饰器，便于在 create_app() 中集中管理。
    """
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
