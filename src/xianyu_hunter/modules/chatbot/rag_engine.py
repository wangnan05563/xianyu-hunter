"""RAGEngine — 文档检索 + context 构建 + LLM 流式生成 + 引用后处理

职责（详见 docs/chatbot-详细设计.md §5.2）：
- retrieve：向量化 query → ChromaDB 检索 → 阈值过滤 → similarity 降序
- to_sources：转换为 SSE sources 事件格式（不含 content，仅元数据）
- build_context：拼接 LLM 上下文，超长时从最低 similarity 整片丢弃
- generate：httpx 直调 OpenAI Chat Completions（stream=true），首字超时检测
- postprocess_citations：校验 [来源:N] 引用编号有效性
- _build_messages：构造 system(指令) + history + system(context) + user 的消息序列

设计要点：
- 无状态：可被多个会话共享，不在实例上保存请求级状态
- httpx.AsyncClient 连接池复用，减少 TLS 握手开销
- 异常向上抛出由 Orchestrator 决定降级链（见 §8.3）
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any, AsyncIterator

import httpx
from loguru import logger

from xianyu_hunter.modules.chatbot.embedding_service import EmbeddingService
from xianyu_hunter.modules.chatbot.vector_store import VectorStore
from xianyu_hunter.infra.yaml_config import ChatbotLLMConfig, ChatbotRAGConfig


@dataclass
class RetrievedChunk:
    """RAG 检索返回的原始片段

    字段对齐 VectorStore.search 返回的 dict 结构，
    额外补充 truncated/code_block/redacted 三个标记位供后续策略使用。
    """
    content: str
    source_file: str
    section_path: str
    line_start: int
    line_end: int
    doc_type: str
    similarity: float
    truncated: bool = False
    code_block: bool = False
    redacted: bool = False


@dataclass
class Source:
    """SSE sources 事件中的引用来源

    前端按 index 与 [来源:N] 对应，line 用 "L{start}-L{end}" 字符串表达。
    """
    index: int
    file: str
    section: str
    line: str
    doc_type: str
    similarity: float


class RAGEngine:
    """RAG 引擎：无状态，可被多会话共享

    异常边界：
    - retrieve 内部异常由 EmbeddingService/VectorStore 自行兜底（返回空）
    - generate 异常向上抛出，由 Orchestrator 走降级链（LLM_TIMEOUT / LLM_NETWORK 等）
    """

    # 引用编号正则：[来源:1] [来源:12]，仅匹配纯数字编号便于校验
    _CITATION_RE = re.compile(r"\[来源:(\d+)\]")

    # 系统提示词：定义客服角色 + 回答规则 + 引用约定
    # 写在类常量而非配置文件，因为这是行为约束而非可调参数，
    # 与 _build_messages 中"上下文作为 system 消息"配合防 Prompt Injection
    _SYSTEM_PROMPT = (
        "你是闲鱼猎人智能客服助手，基于以下文档片段回答问题。\n"
        "回答规则：\n"
        "1. 仅基于提供的参考资料回答，不要编造未在资料中出现的信息\n"
        "2. 引用资料时使用 [来源:N] 格式，N 为资料编号（从 1 开始）\n"
        "3. 若资料不足以回答，明确告知用户并建议转人工\n"
        "4. 涉及配置/操作步骤时给出具体字段值，避免泛泛而谈\n"
        "5. 不回答与闲鱼猎人系统无关的问题\n"
    )

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        config: ChatbotRAGConfig,
        llm_config: ChatbotLLMConfig,
        ai_usage: Any = None,
    ) -> None:
        self._embedding = embedding_service
        self._vector_store = vector_store
        self._config = config
        self._llm_config = llm_config
        self._ai_usage = ai_usage

        # OpenAI base_url 与 api_key 不在 ChatbotLLMConfig 中（仅含模型/温度/超时），
        # 这里从 settings 读取，与 api_ai.py 的 httpx 直调模式保持一致
        from xianyu_hunter.config import get_settings
        settings = get_settings()
        self._openai_base_url = settings.openai_base_url.rstrip("/")
        self._api_key = settings.openai_api_key

        # httpx 客户端复用：连接池 + keep-alive，避免每次请求重新握手
        # read 超时用 http_timeout_sec 覆盖整个流式响应过程
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

    async def retrieve(self, query: str) -> list[RetrievedChunk]:
        """检索 top_k 相关片段，过滤 similarity < threshold

        算法：
        1. 向量化 query（embed 失败返回空列表，不抛出）
        2. ChromaDB 向量检索（top_k）
        3. 阈值过滤：similarity < similarity_threshold 的丢弃
        4. 按 similarity 降序排序
        """
        query_vec = await self._embedding.embed(query)
        if not query_vec:
            # embed 失败（如预算超限/网络异常）由 EmbeddingService 内部已记录日志
            return []

        raw_chunks = await self._vector_store.search(
            query_vec, top_k=self._config.top_k
        )
        if not raw_chunks:
            return []

        filtered = [
            c for c in raw_chunks
            if c.get("similarity", 0.0) >= self._config.similarity_threshold
        ]
        # 按 similarity 降序：最相关的排在前面，对应 [来源:1]
        filtered.sort(key=lambda c: c.get("similarity", 0.0), reverse=True)

        return [
            RetrievedChunk(
                content=c.get("content", ""),
                source_file=c.get("source_file", ""),
                section_path=c.get("section_path", ""),
                line_start=c.get("line_start", 0),
                line_end=c.get("line_end", 0),
                doc_type=c.get("doc_type", "manual"),
                similarity=c.get("similarity", 0.0),
            )
            for c in filtered
        ]

    def to_sources(self, chunks: list[RetrievedChunk]) -> list[Source]:
        """将 RetrievedChunk 转换为前端友好的 Source 列表

        index 从 1 开始，与 [来源:N] 中的 N 一一对应；
        不包含 content，避免 sources 事件体积过大。
        """
        return [
            Source(
                index=i + 1,
                file=c.source_file,
                section=c.section_path,
                line=f"L{c.line_start}-L{c.line_end}",
                doc_type=c.doc_type,
                similarity=round(c.similarity, 3),
            )
            for i, c in enumerate(chunks)
        ]

    def build_context(self, chunks: list[RetrievedChunk]) -> str:
        """构建 LLM system message 中的 context 文本

        截断策略（概要设计 §3.2.2）：
        1. 按相似度降序排列，确保保留最相关的
        2. 从最低相似度开始整片丢弃，直到总长 ≤ max_context_chars
        3. 若仅剩 1 片仍超长，按字符截断（任务要求保持简洁，不做单片截断标记）

        每片格式：[来源:N] {file} > {section} (L{start}-L{end})\n{content}\n\n
        """
        max_chars = self._config.max_context_chars
        # 排序副本，避免修改入参
        sorted_chunks = sorted(chunks, key=lambda c: c.similarity, reverse=True)

        # 从尾部（最低 similarity）开始丢弃整片，直到总长 ≤ max_context_chars 或只剩 1 片
        while len(sorted_chunks) > 1:
            # 估算总长：每片内容长度 + 头部开销（约 80 字符）
            total = sum(len(c.content) + 80 for c in sorted_chunks)
            if total <= max_chars:
                break
            sorted_chunks.pop()

        parts: list[str] = []
        for i, c in enumerate(sorted_chunks, start=1):
            header = (
                f"[来源:{i}] {c.source_file} > {c.section_path} "
                f"(L{c.line_start}-L{c.line_end})"
            )
            parts.append(f"{header}\n{c.content}\n\n")

        context = "".join(parts)

        # 单片仍超长：按字符硬截断，保留尾部 "..." 提示 LLM 资料被截断
        if len(context) > max_chars:
            original_len = len(context)
            context = context[: max_chars - 3] + "..."
            logger.warning(
                f"context 单片截断：原 {original_len} 字符 → {max_chars}"
            )

        return context

    async def generate(
        self,
        query: str,
        context: str,
        history: list[dict],
        images: list[str] | None = None,
    ) -> AsyncIterator[str]:
        """流式生成 LLM 回复

        算法：
        1. 构造 OpenAI Chat Completions 请求
        2. POST /chat/completions with stream=true
        3. 首 token 超时检测：超过 first_token_timeout_sec 仍未收到首 token 抛 TimeoutError
        4. 逐 chunk 解析 SSE，yield delta.content

        多模态：images 非空时，user content 改为 [{text}, {image_url}...] 数组结构，
        并切换到 vision_model（如已配置），使视觉模型解析图片内容。

        预算控制：
        - 调用前 check_budget，超限则抛 RuntimeError 由 Orchestrator 转 FAQ/RAG 降级
        - 调用后 record_usage（endpoint=chatbot_llm）

        异常处理：
        - 网络/解析异常：logger.exception 记录后 re-raise，由 Orchestrator 走降级链
        - asyncio.CancelledError：向上传播触发资源清理
        """
        messages = self._build_messages(query, context, history, images)
        # 有图片时用 vision_model（如已配置），否则用主 model（可能不支持 vision）
        use_model = (
            self._llm_config.vision_model
            if images and self._llm_config.vision_model
            else self._llm_config.model
        )
        payload = {
            "model": use_model,
            "messages": messages,
            "temperature": self._llm_config.temperature,
            "max_tokens": self._llm_config.max_tokens,
            "stream": True,
        }

        # 预算检查：避免超额调用导致费用失控
        if self._ai_usage is not None:
            budget_ok, reason = self._ai_usage.check_budget()
            if not budget_ok:
                raise RuntimeError(f"LLM 预算超限: {reason}")

        first_token_received = False
        # 累积完整响应用于 record_usage（流式响应 usage 字段需 stream_options 才返回，
        # 这里保守地用 messages 估算输入 token，输出 token 用实际 yield 的字符数估算）
        collected_output: list[str] = []

        try:
            # 首字超时用 asyncio.wait_for 包装 aiter_lines 的首个有效 token
            # 总超时由 httpx client 的 read timeout 控制
            async with self._http.stream(
                "POST", "/chat/completions", json=payload
            ) as resp:
                resp.raise_for_status()

                # 构造异步迭代器，便于对首 token 单独施加超时
                line_iter = resp.aiter_lines()
                try:
                    # 首字超时：first_token_timeout_sec 内必须收到首个有效 token
                    first_line = await asyncio.wait_for(
                        line_iter.__anext__(), timeout=self._llm_config.first_token_timeout_sec
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        f"LLM 首 token 超时（>{self._llm_config.first_token_timeout_sec}s）"
                    )
                    raise TimeoutError("LLM 首 token 超时")

                async def _iter_all() -> AsyncIterator[str]:
                    """逐行解析 SSE，yield delta.content"""
                    nonlocal first_token_received
                    async for line in self._iter_from(first_line, line_iter):
                        token = self._parse_stream_line(line)
                        if token:
                            first_token_received = True
                            collected_output.append(token)
                            yield token

                async for token in _iter_all():
                    yield token

        # S2737: asyncio.CancelledError 继承自 BaseException，不会被下方 except Exception 捕获，
        # 显式 except+raise 是冗余的，删除以简化
        # S5713: httpx.TimeoutException 是 httpx.HTTPError 的子类，移除冗余子类
        except httpx.HTTPError as e:
            # 网络层异常：记录后向上抛出，由 Orchestrator 决定 LLM_NETWORK 降级
            logger.exception(f"RAGEngine.generate 网络异常: {e}")
            # H5 修复：流式请求中途失败，已生成的 tokens 仍会被 OpenAI 计费，需记录用量
            self._record_llm_usage(messages, collected_output)
            raise
        except Exception as e:
            # JSON 解析等其他异常：同样向上抛出走降级链
            logger.exception(f"RAGEngine.generate 异常: {e}")
            self._record_llm_usage(messages, collected_output)
            raise

        if not first_token_received:
            # 模型返回空响应：视为异常，由 Orchestrator 走 LLM_PARSE 降级
            logger.warning("LLM 未返回任何 token")
            # 空响应也消耗 input tokens（请求已到达 OpenAI 并被计费）
            self._record_llm_usage(messages, collected_output)
            raise RuntimeError("LLM returned empty response")

        # 正常路径记录用量（流式响应通常无 usage 字段，用估算值）
        self._record_llm_usage(messages, collected_output)

    def _record_llm_usage(
        self, messages: list[dict], collected_output: list[str]
    ) -> None:
        """记录 LLM 用量（H5 修复：异常路径与空响应路径也需记录）

        流式响应无 usage 字段，用 messages 与 collected_output 估算 token 数。
        OpenAI 对流式请求即使中途失败也计费已生成的 tokens，因此异常路径不能跳过。
        ai_usage 为 None 或记录失败时静默忽略，不影响业务流程。
        """
        if self._ai_usage is None:
            return
        try:
            # 粗略估算：输入字符数 / 4，输出字符数 / 4（中文约 1.5 字/token，此处保守估算）
            input_tokens = sum(len(m.get("content", "")) for m in messages) // 4
            output_tokens = sum(len(t) for t in collected_output) // 4
            self._ai_usage.record_usage(
                endpoint="chatbot_llm",
                model=self._llm_config.model,
                response_data={
                    "usage": {
                        "prompt_tokens": input_tokens,
                        "completion_tokens": output_tokens,
                    }
                },
            )
        except Exception as e:
            # 用量记录失败不影响业务流程，仅记录
            logger.warning(f"record_usage 失败（忽略）: {e}")

    async def _iter_from(
        self, first_line: str, rest_iter: AsyncIterator[str]
    ) -> AsyncIterator[str]:
        """复用首行 + 剩余行的迭代器

        为什么单独抽出：首 token 已被 wait_for 取出，需把它和后续行一起处理，
        避免丢失首行内容（如首个 data: chunk）。
        """
        yield first_line
        async for line in rest_iter:
            yield line

    def _parse_stream_line(self, line: str) -> str | None:
        """解析单行 SSE，返回 delta.content 或 None

        OpenAI 流式响应每行格式：`data: {json}` 或 `data: [DONE]`
        非 data 行（如心跳/空行）直接跳过。
        """
        if not line.startswith("data: "):
            return None
        data = line[6:]
        if data == "[DONE]":
            return None
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            # 单行解析失败不终止流，记录后继续（可能是半行/特殊字符）
            logger.debug(f"流式响应 JSON 解析失败，跳过该行: {data[:100]}")
            return None
        choices = chunk.get("choices") or []
        if not choices:
            return None
        delta = choices[0].get("delta", {}) or {}
        content = delta.get("content")
        return content if content else None

    def postprocess_citations(
        self, text: str, chunks: list[RetrievedChunk]
    ) -> str:
        """校验 [来源:N] 引用编号有效性

        规则：N 必须在 1~len(chunks) 范围内，否则视为无效引用移除。
        移除方式：替换为空字符串（保留语义流畅性），不替换为 [来源:?]
        以避免误导用户。
        """
        max_idx = len(chunks)

        def _replace(match: re.Match) -> str:
            idx = int(match.group(1))
            # 有效引用保留原样，无效引用移除
            return match.group(0) if 1 <= idx <= max_idx else ""

        return self._CITATION_RE.sub(_replace, text)

    def _build_messages(
        self, query: str, context: str, history: list[dict], images: list[str] | None = None,
    ) -> list[dict]:
        """构造 OpenAI messages：system(指令) + history + system(context) + user

        为什么 context 放在 system 而非 user：
        - 防止 Prompt Injection：用户消息中的"忽略上述指令"无法覆盖 system 中的 context
        - 与 OpenAI 官方推荐一致（system 用于设定 assistant 行为与可信上下文）

        多模态：images 非空时，user content 改为 OpenAI Vision 规范的数组结构
        [{"type":"text",...}, {"type":"image_url","image_url":{"url":"data:..."}}]，
        使视觉模型能同时读取文字和图片。
        """
        # 有图片时构造多模态 content 数组（OpenAI Vision 规范）
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
            # history 由 ContextManager 已截断为 max_history_turns 内的消息
            *[{"role": m["role"], "content": m["content"]} for m in history],
            {"role": "system", "content": f"参考资料：\n{context}"},
            {"role": "user", "content": user_content},
        ]

    # 后续问题预测专用 system prompt：独立于主回答 prompt，
    # 因为主回答 prompt 限制了"仅基于参考资料"，而后续问题需要基于完整对话上下文发散
    _FOLLOW_UP_PROMPT = (
        "基于用户的提问和客服的回答，预测用户可能想继续了解的后续问题。\n"
        "要求：\n"
        "1. 生成 {count} 个与当前话题密切相关的后续问题\n"
        "2. 问题应帮助用户深入理解或解决实际操作问题\n"
        "3. 问题要简洁明了、口语化，符合用户提问习惯\n"
        "4. 只返回 JSON 数组格式，不要任何额外文本："
        '["问题1", "问题2", "问题3"]'
    )

    async def generate_follow_ups(
        self,
        query: str,
        answer: str,
        history: list[dict],
        count: int = 3,
    ) -> list[str]:
        """生成后续推荐问题

        非流式轻量 LLM 调用，在主回答完成后执行。
        失败时返回空列表，不影响主回答流程（调用方应静默降级）。

        为什么用独立调用而非在主 prompt 中追加：
        - 不污染主回答流（用户看到的回答不含推荐问题）
        - 可以传入完整 answer 供 LLM 参考，生成更相关的问题
        - 失败可静默降级，不影响已生成的主回答
        """
        # answer 截断：避免过长的回答导致 LLM 输入过大、增加延迟和成本
        truncated_answer = answer[:800] if len(answer) > 800 else answer
        # history 仅取最近 2 轮（4 条），后续问题主要依赖当前问答上下文
        recent_history = history[-4:] if len(history) > 4 else history
        history_text = "\n".join(
            f"{'用户' if m['role'] == 'user' else '客服'}: {m['content'][:200]}"
            for m in recent_history
        ) or "（无历史对话）"

        messages = [
            {
                "role": "system",
                "content": self._FOLLOW_UP_PROMPT.format(count=count),
            },
            {
                "role": "user",
                "content": (
                    f"用户提问：{query}\n\n"
                    f"客服回答：{truncated_answer}\n\n"
                    f"对话历史：\n{history_text}"
                ),
            },
        ]
        payload = {
            "model": self._llm_config.model,
            "messages": messages,
            "temperature": 0.5,  # 略高于主回答的 0.3，鼓励问题多样性
            "max_tokens": 300,  # 3-5 个问题足够，避免浪费
            "stream": False,
        }

        try:
            resp = await self._http.post("/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            # LLM 可能返回带 markdown 代码块的 JSON，提取首个 JSON 数组
            json_match = re.search(r'\[.*?\]', content, re.DOTALL)
            if not json_match:
                logger.warning(f"follow_ups 响应非 JSON 数组格式: {content[:100]}")
                return []
            questions = json.loads(json_match.group())
            # 过滤空字符串和过长问题（>100 字的问题不适合作为快捷推荐）
            questions = [q.strip() for q in questions if q and len(q.strip()) <= 100]
            return questions[:count]
        except Exception as e:
            logger.warning(f"generate_follow_ups 失败（静默降级）: {e}")
            return []
