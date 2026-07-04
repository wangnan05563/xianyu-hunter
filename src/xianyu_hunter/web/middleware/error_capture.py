"""错误日志捕获与 AI 上下文生成

提供两类捕获入口：
1. capture_request_error：从 FastAPI Request 对象提取请求上下文，供 exception_handler 调用
2. capture_background_error：供后台任务（worker/scheduler）捕获异常

两类入口都会：
- 构建结构化错误日志（含堆栈、请求参数、服务器环境）
- 生成 AI 诊断上下文（JSON + Markdown 双格式）
- 写入 error_logs 表
"""
from __future__ import annotations

import json
import os
import platform
import sys
import traceback
from datetime import datetime, timezone
from typing import Any

from loguru import logger

# 敏感请求头：脱敏后才能入库，避免 token 落盘
_SENSITIVE_HEADERS = {"authorization", "cookie", "xh_token", "set-cookie"}


def _sanitize_headers(headers: Any) -> dict[str, str]:
    """脱敏请求头，敏感字段值替换为 ***"""
    safe: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in _SENSITIVE_HEADERS:
            safe[key] = "***"
        else:
            safe[key] = value
    return safe


def _collect_server_env() -> dict[str, str]:
    """收集服务器环境快照（仅技术诊断所需信息）"""
    return {
        "python_version": sys.version.split()[0],
        "os": f"{platform.system()} {platform.release()}",
        "platform": platform.machine(),
        "pid": str(os.getpid()),
    }


def _infer_possible_causes(error_message: str, prefix: str = "") -> list[str]:
    """基于错误消息关键词推断可能的原因

    为什么独立：_build_ai_context_json 和 _build_ai_context_md 中重复了相同的
    关键词匹配逻辑（5 组 if + or/and），集中维护避免两处不一致，
    同时降低两个构建函数的认知复杂度。
    """
    possible_causes: list[str] = []
    msg_lower = error_message.lower()
    if "connection" in msg_lower or "timeout" in msg_lower:
        possible_causes.append(f"{prefix}网络连接或超时问题")
    if "permission" in msg_lower or "denied" in msg_lower:
        possible_causes.append(f"{prefix}权限或文件系统访问问题")
    if "type" in msg_lower and ("convert" in msg_lower or "cast" in msg_lower):
        possible_causes.append(f"{prefix}数据类型转换错误")
    if "key" in msg_lower and ("not found" in msg_lower or "missing" in msg_lower):
        possible_causes.append(f"{prefix}字典/配置键缺失")
    if "index" in msg_lower and "out of range" in msg_lower:
        possible_causes.append(f"{prefix}数组索引越界")
    if not possible_causes:
        possible_causes.append(f"{prefix}需要根据堆栈信息进一步分析")
    return possible_causes


def _build_request_context_md_lines(request_info: dict) -> list[str]:
    """构建 Markdown 格式的请求上下文行（含方法/路径/流水号/参数）

    为什么独立：_build_ai_context_md 中请求上下文构建有嵌套 if (params)，
    拆分后主函数线性拼接各段落，便于增删字段。
    """
    lines = [
        "",
        "## 请求上下文",
        f"- **方法**: {request_info.get('method', 'N/A')}",
        f"- **路径**: {request_info.get('path', 'N/A')}",
        f"- **流水号**: `{request_info.get('request_id', 'N/A')}`",
        f"- **客户端 IP**: {request_info.get('client_ip', 'N/A')}",
        f"- **User-Agent**: {request_info.get('user_agent', 'N/A')}",
    ]
    params = request_info.get("params")
    if params:
        lines += ["", "### 请求参数", "```json", json.dumps(params, ensure_ascii=False, indent=2), "```"]
    return lines


def _build_ai_context_json(
    error_type: str,
    error_message: str,
    stack_trace: str,
    request_info: dict | None,
    server_env: dict,
) -> str:
    """构建结构化 JSON 上下文，可直接喂给 AI 诊断系统"""
    ctx: dict[str, Any] = {
        "error_type": error_type,
        "error_message": error_message,
        "stack_trace": stack_trace,
        "environment": server_env,
    }
    if request_info:
        ctx["request"] = request_info
    ctx["possible_causes"] = _infer_possible_causes(error_message)
    return json.dumps(ctx, ensure_ascii=False, indent=2)


def _build_ai_context_md(
    error_type: str,
    error_message: str,
    stack_trace: str,
    request_info: dict | None,
    server_env: dict,
    timestamp: str,
) -> str:
    """构建 Markdown 格式错误报告，可直接粘贴给 AI"""
    lines = [
        "# 错误报告",
        "",
        "## 基本信息",
        f"- **类型**: `{error_type}`",
        f"- **时间**: {timestamp}",
        f"- **消息**: {error_message}",
    ]
    if request_info:
        lines += _build_request_context_md_lines(request_info)
    lines += [
        "",
        "## 堆栈信息",
        "```",
        stack_trace or "(无堆栈信息)",
        "```",
        "",
        "## 服务器环境",
        f"- **Python**: {server_env.get('python_version', 'N/A')}",
        f"- **OS**: {server_env.get('os', 'N/A')}",
        f"- **PID**: {server_env.get('pid', 'N/A')}",
        "",
        "## 可能原因",
    ]
    # 复用 JSON 构建中的原因推断逻辑，加 "- " 前缀适配 Markdown 列表格式
    lines.extend(_infer_possible_causes(error_message, prefix="- "))
    return "\n".join(lines)


def _save_error_log(
    error_type: str,
    error_message: str,
    stack_trace: str | None,
    request_info: dict | None,
    server_env: dict,
    timestamp: datetime,
    request_id: str | None = None,
) -> int | None:
    """构建完整错误日志记录并写入数据库

    返回 error_log id，写入失败时返回 None（不阻断主流程）

    request_id 由调用方显式传入（从 request.state 或后台 context 读取），
    未传入时 save_error_log 会自动从 ContextVar 读取作为兜底。
    """
    try:
        from xianyu_hunter.container import build_default_container
        # 复用 Web 进程的 Container 单例（如果已初始化），否则构建临时实例
        try:
            from xianyu_hunter.web.deps import get_container
            container = get_container()
        except Exception:
            container = build_default_container(with_browser=False)

        ts_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        # 将 request_id 注入 request_info，使 AI 诊断上下文报告中可见
        if request_id and request_info is not None:
            request_info["request_id"] = request_id
        ai_json = _build_ai_context_json(
            error_type, error_message, stack_trace or "", request_info, server_env
        )
        ai_md = _build_ai_context_md(
            error_type, error_message, stack_trace or "", request_info, server_env, ts_str
        )

        error_log = {
            "timestamp": timestamp,
            "error_type": error_type,
            "error_message": error_message,
            "stack_trace": stack_trace,
            "request_method": request_info.get("method") if request_info else None,
            "request_path": request_info.get("path") if request_info else None,
            "request_params": json.dumps(request_info.get("params"), ensure_ascii=False) if request_info and request_info.get("params") else None,
            "request_headers": json.dumps(request_info.get("headers"), ensure_ascii=False) if request_info and request_info.get("headers") else None,
            "client_ip": request_info.get("client_ip") if request_info else None,
            "user_agent": request_info.get("user_agent") if request_info else None,
            "server_env": json.dumps(server_env, ensure_ascii=False),
            "ai_context_json": ai_json,
            "ai_context_md": ai_md,
            "status": "new",
        }
        # 显式注入 request_id：覆盖 ContextVar 兜底值
        # 为什么显式传入：异常处理可能在 ContextVar 已被清理后触发（如中间件 finally 后），
        # 显式传参确保 request_id 不丢失
        if request_id:
            error_log["request_id"] = request_id
        return container.repo.save_error_log(error_log)
    except Exception as e:
        # 错误日志写入本身失败时，仅记录到 loguru，不抛出
        logger.error(f"写入 error_logs 表失败: {e}")
        return None


async def capture_request_error(request: Any, exc: Exception) -> int | None:
    """从 FastAPI Request 对象提取上下文并捕获异常

    供 exception_handler.py 的 unhandled_exception_handler 调用
    """
    timestamp = datetime.now(timezone.utc).replace(tzinfo=None)

    # 从 request.state 读取流水号（由 RequestIdMiddleware 注入）
    # 兜底从 ContextVar 读取，确保异常链路与请求日志关联
    request_id = getattr(request.state, "request_id", None)
    if not request_id:
        from xianyu_hunter.infra.request_context import get_request_id
        request_id = get_request_id()

    # 提取请求上下文
    request_info: dict[str, Any] = {
        "method": request.method,
        "path": request.url.path,
        "headers": _sanitize_headers(request.headers),
        "client_ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent", ""),
    }

    # 尝试提取 query params
    try:
        query_params = dict(request.query_params)
        if query_params:
            request_info["params"] = {"query": query_params}
    except Exception:
        pass

    server_env = _collect_server_env()
    stack_trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    return _save_error_log(
        error_type=type(exc).__name__,
        error_message=str(exc),
        stack_trace=stack_trace,
        request_info=request_info,
        server_env=server_env,
        timestamp=timestamp,
        request_id=request_id,
    )


def capture_background_error(exc: Exception, context: dict | None = None) -> int | None:
    """捕获后台任务异常（worker/scheduler 等）

    context 可选：传入任务相关的额外上下文信息，可包含 request_id
    用于关联 HTTP 请求触发的后台任务链路。
    """
    timestamp = datetime.now(timezone.utc).replace(tzinfo=None)
    server_env = _collect_server_env()
    stack_trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    # 优先从 context 读取 request_id，兜底从 ContextVar 读取
    request_id = None
    if context:
        request_id = context.get("request_id")
    if not request_id:
        from xianyu_hunter.infra.request_context import get_request_id
        request_id = get_request_id()

    request_info = None
    if context:
        request_info = {
            "method": "BACKGROUND",
            "path": context.get("source", "unknown"),
            "client_ip": None,
            "user_agent": None,
            "params": context,
        }

    return _save_error_log(
        error_type=type(exc).__name__,
        error_message=str(exc),
        stack_trace=stack_trace,
        request_info=request_info,
        server_env=server_env,
        timestamp=timestamp,
        request_id=request_id,
    )
