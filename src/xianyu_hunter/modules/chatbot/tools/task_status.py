"""get_task_status 工具 — 查询闲鱼猎人任务的运行状态、配置和最近执行结果

权限：read（默认启用）
超时：5s（本地 SQLite 查询，远低于此阈值）

调用模式：
- 不传 task_id：返回所有任务摘要（按 created_at 降序，最多 20 条）
- 传 task_id：返回单个任务详情
"""
from __future__ import annotations

from typing import Any

from xianyu_hunter.modules.chatbot.tools.base import BaseTool, ToolResult


class GetTaskStatusTool(BaseTool):
    """查询任务状态工具

    通过主 Repository.list_tasks / get_task 查询 SQLite tasks 表，
    不消耗 LLM 预算（is_llm_tool=False）。
    """

    name: str = "get_task_status"
    description: str = "查询闲鱼猎人系统中任务的运行状态、配置和最近执行结果"
    permissions: list[str] = ["read"]
    timeout_sec: int = 5
    is_llm_tool: bool = False

    def __init__(self, repo: Any) -> None:
        # 主 Repository 由 ToolRegistry 注入，工具不持有其他依赖
        self._repo = repo

    def get_openai_schema(self) -> dict:
        # task_id 可选：未传时返回摘要列表，传入时返回单任务详情
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "任务 ID。不传则返回所有任务摘要列表",
                        },
                    },
                    "required": [],
                },
            },
        }

    async def execute(self, task_id: str | None = None, **_: Any) -> ToolResult:
        if task_id:
            task = self._repo.get_task(task_id)
            if not task:
                return ToolResult(
                    success=False,
                    error=f"任务不存在: {task_id}",
                )
            return ToolResult(success=True, data={"task": task})
        # 未指定 task_id：返回摘要列表（限制 20 条避免响应过大）
        tasks = self._repo.list_tasks(limit=20)
        return ToolResult(
            success=True,
            data={"tasks": tasks, "count": len(tasks)},
        )
