"""get_config_value 工具 — 查询闲鱼猎人系统配置项

权限：read
超时：5s

调用模式：
- 不传 key：返回所有配置段摘要
- 传 key：返回指定配置段或字段（支持点号路径，如 "eval.pass_score"）

安全：返回数据由 ToolRegistry._filter_sensitive 统一脱敏，
本工具不重复实现敏感字段过滤逻辑（DRY 原则）。
"""
from __future__ import annotations

from typing import Any

from xianyu_hunter.modules.chatbot.tools.base import BaseTool, ToolResult


class GetConfigValueTool(BaseTool):
    """查询系统配置工具

    从 yaml_config.get_config() 读取运行时配置（Pydantic 模型），
    转为 dict 返回。敏感字段（api_key / cookie / token 等）由
    ToolRegistry._filter_sensitive 递归替换为 <REDACTED>。
    """

    name: str = "get_config_value"
    description: str = "查询闲鱼猎人系统的配置项（如通知渠道、Cookie 状态、调度参数）"
    permissions: list[str] = ["read"]
    timeout_sec: int = 5
    is_llm_tool: bool = False

    def __init__(self, repo: Any | None = None) -> None:
        # repo 保留参数位置以与其他工具构造签名一致（ToolRegistry._register_defaults
        # 统一传 repo，本工具实际不依赖 repo）
        self._repo = repo

    def get_openai_schema(self) -> dict:
        # key 可选，支持点号路径访问嵌套字段
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": (
                                "配置项 key，支持点号路径，如 'eval.pass_score'、'notifier.default_channels'。"
                                "不传则返回所有配置段摘要。"
                            ),
                        },
                    },
                    "required": [],
                },
            },
        }

    async def execute(self, key: str | None = None, **_: Any) -> ToolResult:
        from xianyu_hunter.infra.yaml_config import get_config

        config = get_config()
        # Pydantic 模型 → dict（mode="json" 确保枚举/datetime 等可序列化）
        config_dict = config.model_dump(mode="json")

        if not key:
            return ToolResult(success=True, data={"config": config_dict})

        # 点号路径访问嵌套字段：避免 LLM 用 "eval.pass_score" 时无法定位
        current: Any = config_dict
        for part in key.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return ToolResult(
                    success=False,
                    error=f"配置项不存在: {key}",
                )

        return ToolResult(success=True, data={"key": key, "value": current})
