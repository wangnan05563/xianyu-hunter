"""工具基类与结果类型定义

设计要点（详见 docs/chatbot-概要设计.md §3.2.9）：
- 每个工具继承 BaseTool，实现 get_openai_schema 与 execute
- permissions 控制运行时权限校验：['read'] 默认启用，['write'] 默认禁用（需求 FR-4.4.4）
- is_llm_tool 标识是否消耗 LLM 预算（如 search_help 走 embedding 计入预算）
- timeout_sec 单工具超时，由 ToolRegistry.call 通过 asyncio.timeout 强制
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ToolResult:
    """工具调用结果（统一返回类型）

    ToolRegistry 捕获所有异常后构造 success=False 的 ToolResult，
    确保工具异常不会击穿到 Agent 主循环。
    """
    success: bool
    data: dict | None = None
    error: str | None = None
    duration_ms: int = 0

    def to_dict(self) -> dict:
        """转换为 dict（用于序列化为 LLM messages 中 tool 角色的 content）"""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


class BaseTool:
    """工具基类

    子类需覆盖 name / description / permissions / timeout_sec / is_llm_tool 类属性，
    并实现 get_openai_schema 与 execute。
    """
    name: str = ""
    description: str = ""
    # ['read'] = 只读工具默认启用；['write'] = 写入工具默认 disabled（SR-8.4.2）
    permissions: list[str] = []  # noqa: B006 — 与项目约定一致的可变默认值占位
    timeout_sec: int = 5
    is_llm_tool: bool = False

    def get_openai_schema(self) -> dict:
        """返回 OpenAI function calling 格式的 schema"""
        raise NotImplementedError

    async def execute(self, **kwargs) -> ToolResult:
        raise NotImplementedError
