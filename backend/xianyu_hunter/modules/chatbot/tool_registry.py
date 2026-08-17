"""ToolRegistry — AGENT 工具注册表

职责（详见 docs/chatbot-详细设计.md §5.3.3）：
- 集中管理工具声明（name / schema / handler / permissions / timeout）
- 统一调度工具调用，捕获所有异常转换为 ToolResult(success=False)
- 对工具返回数据递归脱敏（敏感字段替换为 <REDACTED>）

设计要点：
- 工具实例由 _register_defaults 创建并注入 repo / rag_engine
- call 方法的超时用 asyncio.timeout，与 tool.timeout_sec 解耦
- _filter_sensitive 用 sanitizer.redact_sensitive 处理 str，
  对 dict/list 递归遍历，键名匹配敏感模式时替换值为 <REDACTED>
"""
from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from xianyu_hunter.modules.chatbot.tools.base import BaseTool, ToolResult
from xianyu_hunter.modules.chatbot.sanitizer import redact_sensitive
from xianyu_hunter.infra.yaml_config import ChatbotAgentConfig


class ToolRegistry:
    """工具注册表：管理工具声明、调用、敏感字段过滤

    异常边界（概要设计 §3.13.2）：
    - 工具不存在 / 已禁用：返回 ToolResult(success=False)
    - 工具超时：返回 ToolResult(success=False, error="Tool timeout")
    - 工具内部 Exception：捕获并返回 ToolResult(success=False, error=str(e))
    - asyncio.CancelledError：向上传播触发资源清理
    """

    def __init__(
        self,
        repo: Any,
        rag_engine: Any | None = None,
        config: ChatbotAgentConfig | None = None,
    ) -> None:
        self._repo = repo
        self._rag_engine = rag_engine
        self._config = config or ChatbotAgentConfig()
        self._tools: dict[str, BaseTool] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """注册默认工具集

        5 个只读工具：task_status / eval_score / config_value / error_logs / help_page
        help_page 依赖 rag_engine（用于 embedding 检索），rag_engine=None 时跳过注册
        以避免在知识库未构建时调用失败。
        """
        # 延迟导入避免模块加载时循环依赖
        from xianyu_hunter.modules.chatbot.tools.task_status import GetTaskStatusTool
        from xianyu_hunter.modules.chatbot.tools.eval_score import GetEvalScoreTool
        from xianyu_hunter.modules.chatbot.tools.config_value import GetConfigValueTool
        from xianyu_hunter.modules.chatbot.tools.error_logs import GetErrorLogsTool

        # 本地工具（不消耗 LLM 预算）
        self.register(GetTaskStatusTool(self._repo))
        self.register(GetEvalScoreTool(self._repo))
        self.register(GetConfigValueTool(self._repo))
        self.register(GetErrorLogsTool(self._repo))

        # LLM 工具（消耗 embedding 预算）：仅当 rag_engine 可用时注册
        # 否则跳过——未构建知识库时 search_help 无意义，避免注册后调用失败
        if self._rag_engine is not None:
            from xianyu_hunter.modules.chatbot.tools.help_page import SearchHelpTool
            self.register(SearchHelpTool(self._rag_engine))

    def register(self, tool: BaseTool) -> None:
        """注册单个工具，重复注册同名工具会覆盖旧实例"""
        if not tool.name:
            raise ValueError("工具必须定义 name 属性")
        self._tools[tool.name] = tool

    def get_openai_schemas(self) -> list[dict]:
        """生成 OpenAI function calling 用的 tools 参数

        仅返回 permissions 含 'read' 的工具——AGENT 当前仅支持只读工具
        （写入工具 disabled=True，SR-8.4.2）。
        """
        return [
            tool.get_openai_schema()
            for tool in self._tools.values()
            if "read" in tool.permissions
        ]

    async def call(self, name: str, **kwargs: Any) -> ToolResult:
        """统一工具调用入口

        超时控制：用 asyncio.timeout(tool.timeout_sec) 强制单工具超时，
        超时返回 ToolResult(success=False, error="Tool timeout")。

        异常处理：
        - 工具不存在：返回失败结果（对应错误码 TOOL_NOT_FOUND）
        - 超时：返回失败结果（对应错误码 TOOL_TIMEOUT）
        - 内部异常：返回失败结果（对应错误码 TOOL_INTERNAL）
        """
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(success=False, error=f"Tool not found: {name}")

        try:
            # 用工具自身的 timeout_sec 控制单次调用上限
            async with asyncio.timeout(tool.timeout_sec):
                result = await tool.execute(**kwargs)
        except asyncio.TimeoutError:
            logger.warning(
                f"工具 {name} 执行超时（>{tool.timeout_sec}s）"
            )
            return ToolResult(
                success=False,
                error=f"Tool timeout: {name} (>{tool.timeout_sec}s)",
            )
        except asyncio.CancelledError:
            # 取消是协作式的，向上传播以触发上层资源清理
            raise
        except Exception as e:
            # 工具内部异常统一兜底，避免击穿 Agent 主循环
            logger.exception(f"工具 {name} 执行异常")
            return ToolResult(
                success=False,
                error=f"Tool {name} internal error: {type(e).__name__}: {str(e)[:200]}",
            )

        # 工具返回数据脱敏：保证不向 LLM 泄漏 api_key / cookie / token 等敏感字段
        if isinstance(result, ToolResult) and result.data is not None:
            result = ToolResult(
                success=result.success,
                data=self._filter_sensitive(result.data),
                error=result.error,
                duration_ms=result.duration_ms,
            )
        return result

    def _filter_sensitive(self, data: dict) -> dict:
        """递归过滤工具返回数据中的敏感字段

        策略（概要设计 §3.2.9 / SR-8.4.5）：
        - dict：键名匹配敏感模式时值替换为 <REDACTED>，否则递归处理值
        - list：对每个元素递归处理
        - str：调用 redact_sensitive 做正则替换（处理值中嵌套的敏感串）
        - 其他类型：原样返回
        """
        return self._redact_recursive(data)

    def _redact_recursive(self, obj: Any) -> Any:
        # dict：键名敏感直接脱敏值，否则递归处理
        if isinstance(obj, dict):
            return {
                k: ("<REDACTED>" if self._is_sensitive_key(k) else self._redact_recursive(v))
                for k, v in obj.items()
            }
        # list：递归处理每个元素
        if isinstance(obj, list):
            return [self._redact_recursive(item) for item in obj]
        # str：用 redact_sensitive 处理字符串中嵌套的敏感串（如 "api_key=sk-xxx"）
        if isinstance(obj, str):
            return redact_sensitive(obj)
        return obj

    @staticmethod
    def _is_sensitive_key(key: str) -> bool:
        """判断键名是否匹配敏感模式

        与详细设计 §5.3.3 中的 _SENSITIVE_KEY_PATTERNS 保持一致，
        覆盖 api_key / openai_key / cookie / token / password / secret /
        webhook_url / bearer 等常见命名。
        """
        key_lower = key.lower()
        # 用 lower + in 简化匹配，避免重复编译正则
        # 注意：需同时支持 snake_case（api_key）与 kebab-case（api-key）
        normalized = key_lower.replace("-", "_")
        sensitive_markers = (
            "api_key", "openai_key", "openai_api_key",
            "cookie", "token", "password", "secret",
            "webhook_url", "bearer",
        )
        return any(marker in normalized for marker in sensitive_markers)
