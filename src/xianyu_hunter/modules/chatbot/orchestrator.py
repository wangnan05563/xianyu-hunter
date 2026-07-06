"""ChatbotOrchestrator — 对话编排器

职责：
- 串联 FAQ → Intent → RAG → Agent → Context → Escalation，编排完整对话流程
- 管理 per-session asyncio.Lock，串行化同一会话的编排，避免上下文错乱
- 实现降级链：LLM → RAG 片段 → 转人工，每级降级发布 CHATBOT_DEGRADED 事件

设计要点（详见 docs/chatbot-详细设计.md §5.1、docs/chatbot-概要设计.md §3.2.1）：
- 不持有请求级状态（如当前 session_id），保证可被多会话共享
- per-session Lock 用 _locks_guard 保护 _session_locks 字典的并发访问
- 异常不向外抛出，统一转为 SSEEvent(ERROR) 或 SSEEvent(ESCALATE)
- asyncio.CancelledError 是唯一例外，向上传播以触发资源清理
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import AsyncIterator

import httpx
from loguru import logger

from xianyu_hunter.domain.events import Event, EventType
from xianyu_hunter.infra.repo_chatbot import ChatbotRepository
from xianyu_hunter.infra.yaml_config import ChatbotConfig
from xianyu_hunter.modules.chatbot.agent import Agent
from xianyu_hunter.modules.chatbot.context_manager import Context, ContextManager
from xianyu_hunter.modules.chatbot.escalation import Escalation
from xianyu_hunter.modules.chatbot.faq_matcher import FAQMatcher
from xianyu_hunter.modules.chatbot.intent_classifier import IntentClassifier, IntentResult
from xianyu_hunter.modules.chatbot.rag_engine import RAGEngine, RetrievedChunk
from xianyu_hunter.modules.chatbot.sanitizer import check_user_input_safety


class SSEEventType(str, Enum):
    """SSE 事件类型

    继承 str, Enum 使其值即为字符串，便于直接作为 SSE event 字段序列化。
    """

    TOKEN = "token"
    SOURCES = "sources"
    TOOL_CALL = "tool_call"
    INTENT = "intent"
    DONE = "done"
    ERROR = "error"
    ESCALATE = "escalate"
    FAQ_CONFIRM = "faq_confirm"


@dataclass
class SSEEvent:
    """SSE 事件

    event: SSEEventType 值（字符串），对应 SSE 协议的 event 字段
    data: 事件数据字典，按 SSE 协议序列化为 JSON
    """

    event: str
    data: dict


class ChatbotOrchestrator:
    """对话编排器：单例，通过 container 注入

    设计要点：
    - 持有 per-session asyncio.Lock 字典，串行化同一会话的编排
    - 持有所有子模块引用，编排流程不直接访问 DB / ChromaDB
    - 不持有任何请求级状态（如当前 session_id），保证线程安全
    """

    def __init__(
        self,
        faq_matcher: FAQMatcher,
        intent_classifier: IntentClassifier,
        rag_engine: RAGEngine,
        agent: Agent,
        context_manager: ContextManager,
        escalation: Escalation,
        chatbot_repo: ChatbotRepository,
        config: ChatbotConfig,
        event_bus=None,
    ) -> None:
        self._faq = faq_matcher
        self._intent = intent_classifier
        self._rag = rag_engine
        self._agent = agent
        self._ctx = context_manager
        self._esc = escalation
        self._repo = chatbot_repo
        self._config = config
        self._event_bus = event_bus
        # per-session 锁：session_id → Lock，串行化同一会话的编排
        self._session_locks: dict[str, asyncio.Lock] = {}
        # 保护 _session_locks 字典本身的锁（防止并发创建同一 session 的多个 Lock）
        self._locks_guard = asyncio.Lock()

    async def orchestrate(
        self,
        session_id: str | None,
        message: str,
        enable_tools: bool | None = None,
        images: list[str] | None = None,
    ) -> AsyncIterator[SSEEvent]:
        """编排对话流程，流式返回 SSE 事件

        10 步流程详见 docs/chatbot-详细设计.md §5.1.2。
        整个流程在 per-session Lock 内执行，避免同一会话并发编排导致上下文错乱。

        Args:
            session_id: 会话 ID；None 表示首次对话，内部创建新会话
            message: 用户消息（已由 API 层校验长度 1-2000）
            enable_tools: 是否启用工具；None 表示用 config 默认值

        Yields:
            SSEEvent: 按 SSE 协议顺序产生的事件流
        """
        # 1. 安全检查：Prompt Injection 检测，不安全则拒绝处理避免 LLM 被操纵
        safe, rule_name = check_user_input_safety(message)
        if not safe:
            logger.warning(f"用户输入触发安全规则: {rule_name}")
            yield SSEEvent(
                event=SSEEventType.ERROR,
                data={"code": "SECURITY_VIOLATION", "message": f"检测到不安全输入: {rule_name}"},
            )
            return

        # 2. 加载/创建会话上下文（load_context 内部处理 session_id=None 的新建逻辑）
        context = self._ctx.load_context(session_id)

        # H1 修复：ended 是终态不可恢复（状态机 §6.1），返回错误并清理 lock
        # 双重收益：1) 符合设计语义 2) 防止 _session_locks 无限增长导致内存泄漏
        if context.status == "ended":
            async with self._locks_guard:
                self._session_locks.pop(context.session_id, None)
            yield SSEEvent(
                event=SSEEventType.ERROR,
                data={"code": "SESSION_ENDED", "message": "会话已结束，请创建新会话"},
            )
            return

        # 3. 获取 per-session Lock，串行化同一会话的编排
        lock = await self._get_session_lock(context.session_id)
        async with lock:
            # 4. 检查转人工触发（优先级最高，即便 FAQ 命中也要转人工）
            should_escalate, esc_reason = self._esc.should_escalate(
                context.session_id, message, context.status,
            )
            if should_escalate:
                async for event in self._escalate(context.session_id, esc_reason):
                    yield event
                return

            # 5. FAQ 快速匹配：命中且高置信度则直接返回，跳过 LLM 调用节省成本
            faq_result = await self._faq.match(message)
            # 提取为独立 async generator 避免 if/else 双分支 + 多 yield 嵌套推高复杂度
            faq_handled = False
            async for event in self._try_faq_shortcut(message, context, faq_result):
                yield event
                faq_handled = True
            if faq_handled:
                return

            # 6. 意图分类：超范围则拒绝，避免 LLM 被滥用回答无关问题
            intent = await self._intent.classify(message)
            yield SSEEvent(
                event=SSEEventType.INTENT,
                data={
                    "in_scope": intent.in_scope,
                    "method": "llm" if intent.used_llm else "rule",
                    "action": intent.suggested_action,
                },
            )
            if not intent.in_scope:
                yield SSEEvent(
                    event=SSEEventType.ERROR,
                    data={"code": "OUT_OF_SCOPE", "message": intent.reason},
                )
                return

            # 7. 保存用户消息（先存，便于失败时追溯）
            # M4：同时持久化 images，刷新历史后图片不丢失
            self._ctx.save_message(context.session_id, "user", message, images=images or None)

            # 8. RAG 检索 + 生成：根据 enable_tools 和 intent 决定走 RAG 还是 Agent
            # 闭包工厂模式：提取 flow 事件跟踪逻辑，避免 if/else 两分支重复 async for + 状态更新
            flow_tracker, flow_state = self._make_flow_state_tracker()
            flow = (
                self._run_agent_flow(message, context, images)
                if self._should_trigger_agent(intent, enable_tools)
                else self._run_rag_flow(message, context, images)
            )
            async for event in flow_tracker(flow):
                yield event

            # 9. 保存 AI 消息（转人工时不保存，_escalate 已更新会话状态）
            # 10. 发布事件
            # 提取为独立方法避免双 and 条件嵌套推高 orchestrate 复杂度
            await self._finalize_response(context, flow_state)

    async def _try_faq_shortcut(
        self,
        message: str,
        context: Context,
        faq_result,
    ) -> AsyncIterator[SSEEvent]:
        """尝试 FAQ 快速回复，命中则 yield 对应事件（调用方据此短路返回）

        为什么独立方法：原 orchestrate 中 FAQ direct_answer 与 matched 两个分支
        各含 and 条件 + 多个 yield + save_message + publish_event，
        内联会让主流程的 10 步编排被 FAQ 细节淹没。
        """
        if faq_result and faq_result.direct_answer:
            # FAQ 命中分支在步骤 7 之前返回，需单独保存用户消息以保证历史完整
            self._ctx.save_message(context.session_id, "user", message)
            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={"content": faq_result.answer},
            )
            yield SSEEvent(
                event=SSEEventType.DONE,
                data={
                    "content": faq_result.answer,
                    "degraded": False,
                    "metadata": {"faq_id": faq_result.faq_id, "degraded": False},
                },
            )
            self._ctx.save_message(
                context.session_id, "assistant", faq_result.answer,
                {"faq_id": faq_result.faq_id},
            )
            await self._publish_event(
                EventType.CHATBOT_MESSAGE_SAVED,
                {"session_id": context.session_id, "role": "assistant"},
            )
            return

        # FAQ 模糊命中（需用户确认）：返回确认事件，不进入 LLM 流程
        if faq_result and faq_result.matched:
            yield SSEEvent(
                event=SSEEventType.FAQ_CONFIRM,
                data={"question": faq_result.question, "answer": faq_result.answer},
            )

    async def _finalize_response(self, context: Context, flow_state: dict) -> None:
        """处理 flow 完成后的收尾：将 follow_ups 存入 metadata，保存 AI 消息并发布事件

        为什么独立方法：原 orchestrate 中此段含 `follow_ups and metadata is not None`
        与 `not escalated and full_response` 两个 and 条件，叠加 nesting 推高复杂度。
        """
        full_response = flow_state["full_response"]
        metadata = flow_state["metadata"]
        tokens_used = flow_state["tokens_used"]
        escalated = flow_state["escalated"]
        follow_ups = flow_state["follow_ups"]

        # 将 follow_ups 存入 metadata，使历史消息也能展示推荐问题
        if follow_ups and metadata is not None:
            metadata["follow_ups"] = follow_ups

        # 转人工时不保存（_escalate 已更新会话状态）
        if not escalated and full_response:
            self._ctx.save_message(
                context.session_id, "assistant", full_response, metadata, tokens_used,
            )
            await self._publish_event(
                EventType.CHATBOT_MESSAGE_SAVED,
                {"session_id": context.session_id, "role": "assistant"},
            )

    def _make_flow_state_tracker(self):
        """创建 flow 事件跟踪闭包

        闭包工厂模式：返回 (tracker async generator factory, state dict)。
        tracker 转发事件并更新 state，调用方通过 state 读取最终结果，
        避免 orchestrate 中 if/else 两分支重复 async for + 状态更新逻辑导致认知复杂度堆积。
        """
        state = {
            "full_response": "",
            "metadata": None,
            "tokens_used": None,
            "escalated": False,
            "follow_ups": [],
        }

        async def tracker(flow):
            async for event in flow:
                if event.event == SSEEventType.DONE:
                    state["full_response"] = event.data.get("content", "")
                    state["metadata"] = event.data.get("metadata")
                    state["tokens_used"] = event.data.get("tokens_used")
                    state["follow_ups"] = event.data.get("follow_ups", [])
                elif event.event == SSEEventType.ESCALATE:
                    state["escalated"] = True
                yield event

        return tracker, state

    async def _get_session_lock(self, session_id: str) -> asyncio.Lock:
        """获取或创建会话级锁（双检锁模式）

        用 _locks_guard 保护 _session_locks 字典，防止并发请求为同一 session
        创建多个 Lock 实例（会导致锁失效）。
        """
        async with self._locks_guard:
            if session_id not in self._session_locks:
                self._session_locks[session_id] = asyncio.Lock()
            return self._session_locks[session_id]

    def _should_trigger_agent(
        self, intent: IntentResult, enable_tools: bool | None,
    ) -> bool:
        """判断是否触发 Agent 工具调用

        决策逻辑：
        - enable_tools=False：强制禁用工具
        - enable_tools=True：显式启用，且意图建议 agent 时触发
        - enable_tools=None：用 config.agent.enable_tools 默认值
        - 仅当 intent.suggested_action == "agent" 时才触发，避免无谓的 Agent 调用
        """
        if enable_tools is False:
            return False
        if enable_tools is True:
            return intent.suggested_action == "agent"
        # enable_tools is None → 用 config 默认值
        return bool(self._config.agent.enable_tools) and intent.suggested_action == "agent"

    async def _run_rag_flow(
        self, query: str, context: Context, images: list[str] | None = None,
    ) -> AsyncIterator[SSEEvent]:
        """RAG + LLM 流式生成流程（含降级链）

        流程：
        1. retrieve chunks → yield SOURCES
        2. build_context → generate（流式 yield TOKEN）
        3. postprocess_citations（校验 [来源:N] 引用编号）
        4. 异常降级：LLM 超时/错误/预算超限 → _fallback_to_rag_fragments
           chunks 为空时降级到 _escalate（降级链末端）
        """
        chunks = await self._rag.retrieve(query)
        sources = self._rag.to_sources(chunks)
        if sources:
            yield SSEEvent(
                event=SSEEventType.SOURCES,
                data={"sources": [s.__dict__ for s in sources]},
            )

        context_str = self._rag.build_context(chunks)
        history = self._ctx.build_history_messages(context)

        try:
            full_response: list[str] = []
            async for token in self._rag.generate(query, context_str, history, images):
                full_response.append(token)
                yield SSEEvent(event=SSEEventType.TOKEN, data={"content": token})

            response = "".join(full_response)
            response = self._rag.postprocess_citations(response, chunks)

            # 后续问题预测：主回答完成后生成推荐问题，失败静默降级
            follow_ups: list[str] = []
            if self._config.rag.enable_follow_ups:
                follow_ups = await self._rag.generate_follow_ups(
                    query, response, history, self._config.rag.follow_up_count,
                )

            yield SSEEvent(
                event=SSEEventType.DONE,
                data={
                    "content": response,
                    "degraded": False,
                    "follow_ups": follow_ups,
                    "metadata": {
                        "sources": [s.__dict__ for s in sources],
                        "degraded": False,
                    },
                },
            )
        except (asyncio.TimeoutError, httpx.HTTPError) as e:
            # LLM 超时/网络错误 → 降级到 RAG 片段
            logger.warning(f"RAG flow LLM 异常 {type(e).__name__}，降级到 RAG 片段: {e}")
            await self._publish_degraded("llm", "rag_fragments", str(e))
            async for event in self._fallback_after_llm_failure(
                chunks, str(e), context.session_id,
            ):
                yield event
        except RuntimeError as e:
            # 预算超限或空响应（RAGEngine.generate 抛 RuntimeError）→ 降级到 RAG 片段
            logger.warning(f"RAG flow 运行时异常，降级到 RAG 片段: {e}")
            await self._publish_degraded("llm", "rag_fragments", str(e))
            async for event in self._fallback_after_llm_failure(
                chunks, str(e), context.session_id,
            ):
                yield event
        except asyncio.CancelledError:
            # 取消向上传播：触发上层资源清理
            raise
        except Exception as e:
            # 未知异常 → 转人工（降级链末端）
            logger.exception(f"RAG flow 未知异常: {e}")
            async for event in self._escalate(
                context.session_id, f"内部错误: {type(e).__name__}",
            ):
                yield event

    async def _fallback_after_llm_failure(
        self,
        chunks: list[RetrievedChunk],
        reason: str,
        session_id: str,
    ) -> AsyncIterator[SSEEvent]:
        """LLM 失败后降级：有 chunks 走 _fallback_to_rag_fragments，无则转人工

        为什么提取：原 _run_rag_flow 两个 except 分支的降级逻辑完全相同，
        重复 if not chunks / else 双分支会让认知复杂度叠加。
        """
        if not chunks:
            # 降级链末端：RAG 片段为空 → 转人工
            async for event in self._escalate(
                session_id, f"RAG 无匹配片段: {reason}",
            ):
                yield event
        else:
            async for event in self._fallback_to_rag_fragments(chunks, reason):
                yield event

    async def _run_agent_flow(
        self, query: str, context: Context, images: list[str] | None = None,
    ) -> AsyncIterator[SSEEvent]:
        """Agent 多步工具调用流程

        流程：
        1. retrieve chunks → yield SOURCES
        2. agent.run → 迭代 AgentEvent
        3. tool_call/tool_result → yield TOOL_CALL
        4. done → yield TOKEN + DONE
        5. error → 降级到 _run_rag_flow（Agent 失败回退到 RAG）
        """
        chunks = await self._rag.retrieve(query)
        sources = self._rag.to_sources(chunks)
        if sources:
            yield SSEEvent(
                event=SSEEventType.SOURCES,
                data={"sources": [s.__dict__ for s in sources]},
            )

        context_str = self._rag.build_context(chunks)
        history = self._ctx.build_history_messages(context)

        try:
            async for agent_event in self._agent.run(query, context_str, history, images):
                if agent_event.type == "tool_call":
                    yield SSEEvent(event=SSEEventType.TOOL_CALL, data=agent_event.data)
                elif agent_event.type == "tool_result":
                    # tool_result 转为 TOOL_CALL 事件并标记 status=done，
                    # 前端可据此更新工具调用状态为"完成"
                    yield SSEEvent(
                        event=SSEEventType.TOOL_CALL,
                        data={
                            "tool": agent_event.data.get("tool"),
                            "status": "done",
                        },
                    )
                elif agent_event.type == "done":
                    content = agent_event.data.get("content", "")
                    async for event in self._emit_agent_done_event(
                        query, content, sources, history,
                    ):
                        yield event
                    return
                elif agent_event.type == "error":
                    # Agent 异常 → 降级到 RAG flow（Agent 失败回退到 RAG）
                    logger.warning(f"Agent 异常，降级到 RAG flow: {agent_event.data}")
                    async for event in self._fallback_to_rag_flow(
                        query, context, images, agent_event.data.get("message", ""),
                    ):
                        yield event
                    return
        except asyncio.CancelledError:
            raise
        except Exception as e:
            # Agent flow 异常 → 降级到 RAG flow
            logger.exception(f"Agent flow 异常，降级到 RAG flow: {e}")
            async for event in self._fallback_to_rag_flow(
                query, context, images, str(e),
            ):
                yield event

    async def _emit_agent_done_event(
        self,
        query: str,
        content: str,
        sources: list,
        history: list,
    ) -> AsyncIterator[SSEEvent]:
        """构造 Agent flow 的 TOKEN + DONE 事件流

        为什么提取：原 _run_agent_flow 的 done 分支内嵌 follow_ups 生成 + DONE 构造，
        与 elif 链叠加推高认知复杂度。提取后 done 分支仅保留事件转发。
        """
        yield SSEEvent(event=SSEEventType.TOKEN, data={"content": content})

        # 后续问题预测：与 RAG flow 保持一致
        follow_ups: list[str] = []
        if self._config.rag.enable_follow_ups:
            follow_ups = await self._rag.generate_follow_ups(
                query, content, history, self._config.rag.follow_up_count,
            )

        yield SSEEvent(
            event=SSEEventType.DONE,
            data={
                "content": content,
                "degraded": False,
                "follow_ups": follow_ups,
                "metadata": {
                    "sources": [s.__dict__ for s in sources],
                    "tool_used": True,
                    "degraded": False,
                },
            },
        )

    async def _fallback_to_rag_flow(
        self,
        query: str,
        context: Context,
        images: list[str] | None,
        reason: str,
    ) -> AsyncIterator[SSEEvent]:
        """Agent 失败后降级到 RAG flow（含降级事件发布）

        为什么提取：原 _run_rag_flow 的 error 分支与 except 分支均执行
        publish_degraded + _run_rag_flow 转发，重复逻辑导致认知复杂度叠加。
        """
        await self._publish_degraded("agent", "rag", reason)
        async for event in self._run_rag_flow(query, context, images):
            yield event

    async def _fallback_to_rag_fragments(
        self, chunks: list[RetrievedChunk], reason: str,
    ) -> AsyncIterator[SSEEvent]:
        """降级：返回检索片段 + 免责声明

        当 LLM 不可用时，将 RAG 检索到的片段直接拼接返回，避免用户完全无响应。
        标记 degraded=True 供前端显示"降级回答"标识。
        """
        fragments = "\n\n---\n\n".join(c.content for c in chunks)
        content = f"抱歉，AI 回复暂时不可用。以下是与您问题相关的文档片段：\n\n{fragments}"
        yield SSEEvent(event=SSEEventType.TOKEN, data={"content": content})
        yield SSEEvent(
            event=SSEEventType.ERROR,
            data={"code": "LLM_DEGRADED", "message": reason, "fallback": "rag_fragments"},
        )
        yield SSEEvent(
            event=SSEEventType.DONE,
            data={
                "content": content,
                "degraded": True,
                "metadata": {"degraded": True, "fallback": "rag_fragments"},
            },
        )

    async def _escalate(
        self, session_id: str, reason: str,
    ) -> AsyncIterator[SSEEvent]:
        """转人工流程

        - 构建转人工响应（含联系方式与友好提示）
        - 标记会话为 escalated（状态机 §6.3：pending → escalated）
        - 发布 CHATBOT_ESCALATED 事件
        """
        resp = self._esc.build_escalation_response(reason)
        self._esc.mark_session_escalated(session_id, reason)
        yield SSEEvent(
            event=SSEEventType.ESCALATE,
            data={
                "reason": reason,
                "contact": resp.contact,
                "message": resp.message_to_user,
            },
        )
        await self._publish_event(
            EventType.CHATBOT_ESCALATED,
            {"session_id": session_id, "reason": reason},
        )

    async def _publish_event(self, event_type: EventType, payload: dict) -> None:
        """发布领域事件（event_bus 为 None 时静默跳过）

        事件发布失败不影响业务流程，仅记录告警。
        """
        if self._event_bus is None:
            return
        event = Event(type=event_type, payload=payload)
        try:
            await self._event_bus.publish(event)
        except Exception as e:
            logger.warning(f"事件发布失败 {event_type.value}: {e}")

    async def _publish_degraded(
        self, from_level: str, to_level: str, reason: str,
    ) -> None:
        """发布降级事件（降级链每级均发布，便于监控与审计）"""
        await self._publish_event(
            EventType.CHATBOT_DEGRADED,
            {"from": from_level, "to": to_level, "reason": reason},
        )
