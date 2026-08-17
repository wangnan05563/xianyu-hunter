"""get_eval_score 工具 — 查询商品评估分数及评估详情

权限：read
超时：5s

调用模式：
- item_id（必填）：返回该商品最新评估记录
- item_id + task_id：等价于只传 item_id（item_id 全局唯一）
- 仅 task_id：返回该任务下所有商品的最近评估列表（通过 items 表关联）

评估字段：score / risk_level / dimension_scores / reject_reasons / created_at
"""
from __future__ import annotations

from typing import Any

from xianyu_hunter.modules.chatbot.tools.base import BaseTool, ToolResult


class GetEvalScoreTool(BaseTool):
    """查询商品评估分数工具

    通过 repo.get_latest_evaluation(item_id) 查询 evaluations 表，
    评估记录无 task_id 字段，task_id 模式需先 list_items 再查评估。
    """

    name: str = "get_eval_score"
    description: str = "查询商品的人工评估/AI 评估分数及评估详情"
    permissions: list[str] = ["read"]
    timeout_sec: int = 5
    is_llm_tool: bool = False

    def __init__(self, repo: Any) -> None:
        self._repo = repo

    def get_openai_schema(self) -> dict:
        # item_id 与 task_id 都可选，但 execute 内部会校验至少传一个
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_id": {
                            "type": "string",
                            "description": "商品 ID（闲鱼商品 ID 全局唯一）",
                        },
                        "task_id": {
                            "type": "string",
                            "description": "任务 ID。仅传 task_id 时返回该任务下所有商品的最近评估列表",
                        },
                    },
                    "required": [],
                },
            },
        }

    async def execute(
        self,
        item_id: str | None = None,
        task_id: str | None = None,
        **_: Any,
    ) -> ToolResult:
        if not item_id and not task_id:
            return ToolResult(
                success=False,
                error="至少需要传 item_id 或 task_id 中的一个",
            )

        # item_id 模式：返回单商品最新评估
        if item_id:
            evaluation = self._repo.get_latest_evaluation(item_id)
            if not evaluation:
                return ToolResult(
                    success=False,
                    error=f"商品 {item_id} 暂无评估记录",
                )
            return ToolResult(success=True, data={"evaluation": evaluation})

        # task_id 模式：取任务下商品列表，聚合每件商品的最近评估
        # 限制 50 件避免大任务下查询时间过长
        items = self._repo.list_items(task_id=task_id, limit=50)
        evaluations: list[dict] = []
        for item in items:
            item_id = item.get("id")
            if not item_id:
                continue
            evaluation = self._repo.get_latest_evaluation(item_id)
            if evaluation:
                # 同时带上 item 的基础信息（title/price）便于 LLM 引用
                evaluation["item_title"] = item.get("title", "")
                evaluation["item_price"] = item.get("price")
                evaluations.append(evaluation)

        return ToolResult(
            success=True,
            data={
                "task_id": task_id,
                "evaluations": evaluations,
                "count": len(evaluations),
            },
        )
