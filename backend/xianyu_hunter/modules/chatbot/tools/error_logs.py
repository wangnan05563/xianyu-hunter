"""get_error_logs 工具 — 查询系统最近的错误日志

权限：read
超时：5s

调用模式：
- limit（默认 10）：返回最近 N 条错误日志
- task_id（可选）：按 request_path 中包含 task_id 的日志过滤（粗粒度，error_logs 表无 task_id 字段）

安全：返回数据由 ToolRegistry._filter_sensitive 统一脱敏，
stack_trace / request_headers 等可能含敏感信息的字段也会被处理。
"""
from __future__ import annotations

from typing import Any

from xianyu_hunter.modules.chatbot.tools.base import BaseTool, ToolResult


class GetErrorLogsTool(BaseTool):
    """查询错误日志工具

    通过 repo.list_error_logs 查询 error_logs 表，
    按 timestamp 降序返回。
    """

    name: str = "get_error_logs"
    description: str = "查询系统最近的错误日志，用于排查问题"
    permissions: list[str] = ["read"]
    timeout_sec: int = 5
    is_llm_tool: bool = False

    def __init__(self, repo: Any) -> None:
        self._repo = repo

    def get_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "返回的日志条数，默认 10，最大 50",
                        },
                        "task_id": {
                            "type": "string",
                            "description": "按任务 ID 过滤（匹配 request_path 包含该 ID 的日志）",
                        },
                    },
                    "required": [],
                },
            },
        }

    async def execute(
        self,
        limit: int = 10,
        task_id: str | None = None,
        **_: Any,
    ) -> ToolResult:
        # 限制 limit 上限避免响应过大；负数/0 兜底为默认值
        if not isinstance(limit, int) or limit <= 0:
            limit = 10
        limit = min(limit, 50)

        # error_logs 表无 task_id 字段，task_id 过滤通过 request_path 模糊匹配实现
        # 注意 list_error_logs 的 request_path 参数本身即做 LIKE 匹配
        request_path = task_id if task_id else None
        logs = self._repo.list_error_logs(
            request_path=request_path,
            limit=limit,
        )

        return ToolResult(
            success=True,
            data={
                "logs": logs,
                "count": len(logs),
                "task_id_filter": task_id,
            },
        )
