"""Agent — 基于 OpenAI function calling 的多步工具调用与推理

职责（详见 docs/chatbot-详细设计.md §5.3）：
- 多轮工具调用循环：LLM 决策 → 工具执行 → 结果回填 → 再决策
- 总超时控制：asyncio.timeout(tool_total_timeout_sec)
- 单轮 LLM 决策超时：tool_llm_timeout_sec
- 预算控制：每轮 LLM 调用前 check_budget，调用后 record_usage

事件流（AgentEvent）：
- tool_call: 工具调用开始（含工具名 + 参数）
- tool_result: 工具调用结束（含工具名 + 结果）
- thinking: LLM 思考中（可选，本实现未使用）
- done: 主循环结束（含最终回复内容）
- error: 异常结束（含错误消息）
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, AsyncIterator

import httpx
from loguru import logger

from xianyu_hunter.modules.chatbot.tool_registry import ToolRegistry
from xianyu_hunter.infra.yaml_config import ChatbotAgentConfig, ChatbotLLMConfig


@dataclass
class AgentEvent:
    """Agent 流程事件

    type 取值：tool_call / tool_result / thinking / done / error
    data 字段结构依 type 而异：
    - tool_call: {"tool": name, "args": dict}
    - tool_result: {"tool": name, "result": ToolResult.to_dict()}
    - done: {"content": str}
    - error: {"message": str}
    """
    type: str
    data: dict


class Agent:
    """AGENT：基于 OpenAI function_calling 的多步推理

    设计要点：
    - 单轮 LLM 决策（非流式），拿到 tool_calls 或 content 后立即处理
    - 工具结果以 tool role 消息回填，让 LLM 基于结果继续决策
    - 总超时由 asyncio.timeout 控制，单轮 LLM 超时由 _call_llm 内部控制
    - 异常统一转换为 AgentEvent("error")，由 Orchestrator 决定降级
    """

    # 系统提示词：定义 AGENT 角色 + 工具使用规则
    _SYSTEM_PROMPT = (
        "你是闲鱼猎人智能客服助手。你可以调用工具查询系统状态以回答用户问题。\n"
        "工具调用规则：\n"
        "1. 仅在需要实时数据（任务状态/评估分数/配置/错误日志/帮助文档）时调用工具\n"
        "2. 一次可以调用多个工具，但每个工具调用都要有必要\n"
        "3. 工具返回的敏感字段已被脱敏（<REDACTED>），不要尝试还原\n"
        "4. 基于工具结果回答时给出明确结论，避免重复调用相同工具\n"
        "5. 若工具调用失败，告知用户当前不可用并建议转人工\n"
        "6. 不回答与闲鱼猎人系统无关的问题\n"
    )

    def __init__(
        self,
        tool_registry: ToolRegistry,
        config: ChatbotAgentConfig,
        llm_config: ChatbotLLMConfig,
        ai_usage: Any = None,
    ) -> None:
        self._tools = tool_registry
        self._config = config
        self._llm_config = llm_config
        self._ai_usage = ai_usage

        # OpenAI base_url 与 api_key 从 settings 读取，与 RAGEngine 保持一致
        from xianyu_hunter.config import get_settings
        settings = get_settings()
        self._openai_base_url = settings.openai_base_url.rstrip("/")
        self._api_key = settings.openai_api_key

        # httpx 客户端复用：单轮 LLM 决策为非流式 POST，连接池复用减少握手开销
        self._http = httpx.AsyncClient(
            base_url=self._openai_base_url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=httpx.Timeout(
                connect=5.0,
                read=llm_config.http_timeout_sec,
                write=5.0,
                pool=2.0,
            ),
        )

    async def run(
        self,
        query: str,
        context: str,
        history: list[dict],
        images: list[str] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """AGENT 多步推理主循环

        用 asyncio.timeout 包裹整个循环，超时后 yield error 事件并结束。
        所有异常均转换为 error 事件，由 Orchestrator 决定降级链。
        """
        try:
            async with asyncio.timeout(self._config.tool_total_timeout_sec):
                async for event in self._run_loop(query, context, history, images):
                    yield event
        except asyncio.TimeoutError:
            # M-3 修复：提取消息变量复用，避免字符串重复构造且未来修改只需改一处
            msg = f"AGENT 总超时（>{self._config.tool_total_timeout_sec}s）"
            logger.warning(msg)
            yield AgentEvent(type="error", data={"message": msg})
        except asyncio.CancelledError:
            # 取消向上传播：触发上层资源清理
            raise
        except Exception as e:
            logger.exception(f"AGENT 异常: {e}")
            yield AgentEvent(
                type="error",
                data={"message": f"AGENT 内部错误: {type(e).__name__}: {e}"},
            )

    async def _run_loop(
        self,
        query: str,
        context: str,
        history: list[dict],
        images: list[str] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """单轮工具调用循环

        算法：
        1. 构造初始 messages（system + history + system(context) + user）
        2. 调用 LLM 决策（带 tools schema）
        3. 若 LLM 返回 tool_calls：执行所有工具 → 回填结果 → 回到步骤 2
        4. 若 LLM 返回 content：yield done 并结束
        5. 达到 max_tool_rounds 仍未回答：yield done "已达到最大工具调用轮数"
        """
        messages = self._build_initial_messages(query, context, history, images)
        tools_schema = self._tools.get_openai_schemas()

        for _ in range(self._config.max_tool_rounds):
            response = await self._call_llm(messages, tools_schema, images)

            tool_calls = response.get("tool_calls")
            if tool_calls:
                # 把 LLM 的 assistant 消息（含 tool_calls）追加到 messages，
                # 否则下一轮调用时 LLM 看不到自己上轮的 tool_calls 上下文
                messages.append({
                    "role": "assistant",
                    "content": response.get("content"),
                    "tool_calls": tool_calls,
                })

                # 串行执行所有 tool_calls：避免对 SQLite/ChromaDB 并发压力
                # （工具大多为本地查询，串行延迟可接受且更稳定）
                for tool_call in tool_calls:
                    tool_name = tool_call.get("function", {}).get("name", "")
                    raw_args = tool_call.get("function", {}).get("arguments", "{}")
                    try:
                        args = json.loads(raw_args) if raw_args else {}
                    except json.JSONDecodeError as e:
                        # LLM 偶尔会返回非合法 JSON 的 arguments，记录后用空 dict 兜底
                        logger.warning(
                            f"工具 {tool_name} arguments JSON 解析失败: {e}"
                        )
                        args = {}

                    yield AgentEvent(
                        type="tool_call",
                        data={"tool": tool_name, "args": args},
                    )

                    result = await self._tools.call(tool_name, **args)

                    yield AgentEvent(
                        type="tool_result",
                        data={"tool": tool_name, "result": result.to_dict()},
                    )

                    # 工具结果以 tool role 回填，tool_call_id 必须与 assistant.tool_calls 中的 id 对应
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", ""),
                        "content": json.dumps(result.to_dict(), ensure_ascii=False),
                    })

                # 继续下一轮，让 LLM 基于工具结果决策
                continue

            # LLM 返回 content：作为最终回复
            content = response.get("content") or ""
            yield AgentEvent(type="done", data={"content": content})
            return

        # 达到最大轮数仍未回答：强制结束，告知用户已无更多轮次
        logger.warning(
            f"AGENT 达到最大工具调用轮数 {self._config.max_tool_rounds}，强制结束"
        )
        yield AgentEvent(
            type="done",
            data={"content": "已达到最大工具调用轮数，请提供更具体的问题或联系人工客服。"},
        )

    async def _call_llm(
        self,
        messages: list[dict],
        tools: list[dict],
        images: list[str] | None = None,
    ) -> dict:
        """调用 OpenAI Chat Completions（非流式，带 tools 参数）

        返回结构：{"content": str | None, "tool_calls": list[dict] | None}

        多模态：images 非空且配置了 vision_model 时切换到视觉模型。

        超时：tool_llm_timeout_sec（单轮 LLM 决策上限）
        预算：调用前 check_budget，调用后 record_usage（endpoint=chatbot_agent）

        异常处理：
        - 预算超限：抛 RuntimeError 由上层 run 捕获转 error 事件
        - 网络/超时：抛出由上层捕获
        """
        # 预算检查
        if self._ai_usage is not None:
            budget_ok, reason = self._ai_usage.check_budget()
            if not budget_ok:
                raise RuntimeError(f"AGENT LLM 预算超限: {reason}")

        # 有图片时用 vision_model（如已配置）
        use_model = (
            self._llm_config.vision_model
            if images and self._llm_config.vision_model
            else self._llm_config.model
        )
        payload: dict[str, Any] = {
            "model": use_model,
            "messages": messages,
            "temperature": self._llm_config.temperature,
            "max_tokens": self._llm_config.max_tokens,
        }
        # 仅当存在工具 schema 时才传 tools，避免无工具场景下 API 报错
        if tools:
            payload["tools"] = tools
            # tool_choice="auto" 让 LLM 自主决定是否调用工具
            payload["tool_choice"] = "auto"

        # 用 asyncio.wait_for 控制单轮 LLM 决策超时
        try:
            response = await asyncio.wait_for(
                self._http.post("/chat/completions", json=payload),
                timeout=self._config.tool_llm_timeout_sec,
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"AGENT LLM 单轮决策超时（>{self._config.tool_llm_timeout_sec}s）"
            )
            raise

        response.raise_for_status()
        data = response.json()

        # 记录用量（非流式响应直接含 usage 字段）
        if self._ai_usage is not None:
            try:
                self._ai_usage.record_usage(
                    endpoint="chatbot_agent",
                    model=self._llm_config.model,
                    response_data=data,
                )
            except Exception as e:
                # 用量记录失败不影响决策流程
                logger.warning(f"record_usage 失败（忽略）: {e}")

        # 提取 content 与 tool_calls
        choices = data.get("choices") or []
        if not choices:
            return {"content": None, "tool_calls": None}

        message = choices[0].get("message", {}) or {}
        return {
            "content": message.get("content"),
            "tool_calls": message.get("tool_calls"),
        }

    def _build_initial_messages(
        self,
        query: str,
        context: str,
        history: list[dict],
        images: list[str] | None = None,
    ) -> list[dict]:
        """构造初始 messages 序列

        结构与 RAGEngine._build_messages 一致：
        system(指令) + history + system(context) + user
        保持一致性便于 LLM 在 RAG-only 与 AGENT 模式间无缝切换。

        多模态：images 非空时 user content 改为 Vision 数组结构。
        """
        if images:
            user_content: str | list[dict] = [
                {"type": "text", "text": query},
                *[
                    {"type": "image_url", "image_url": {"url": img}}
                    for img in images
                ],
            ]
        else:
            user_content = query

        return [
            {"role": "system", "content": self._SYSTEM_PROMPT},
            *[{"role": m["role"], "content": m["content"]} for m in history],
            {"role": "system", "content": f"参考资料：\n{context}"},
            {"role": "user", "content": user_content},
        ]
