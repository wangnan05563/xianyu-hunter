"""FAQMatcher：基于向量相似度的常见问题匹配器

职责：
- 对用户问题向量化，与 FAQ 库中的问题向量计算 cosine 相似度
- 命中 ≥ similarity_threshold 直接返回答案；命中 ≥ confirm_threshold 需用户确认
- FAQ 缺失 embedding 时按需批量生成并回写 DB（懒初始化，避免启动时全量计算）
- FAQ 列表带 5 分钟内存缓存，减少 DB 查询（FAQ 总数 < 1000，内存占用可忽略）

设计要点（详见 docs/chatbot-详细设计.md §5.6、docs/chatbot-概要设计.md §3.2.6）：
- 为什么用应用层 cosine 而非 ChromaDB：FAQ 量小（<1000），DB 查询 + 应用层
  cosine 即可，避免 ChromaDB 双集合管理复杂度（见 repo_chatbot.update_faq_embedding 注释）
- embedding 失败时降级到编辑距离（rapidfuzz/difflib），保证匹配链路不中断
- _ensure_faq_embeddings 失败的 FAQ 被跳过，不阻塞其他 FAQ 匹配（部分失败容忍）
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from loguru import logger

from xianyu_hunter.infra.repo_chatbot import ChatbotRepository
from xianyu_hunter.infra.yaml_config import ChatbotFAQConfig
from xianyu_hunter.modules.chatbot.embedding_service import EmbeddingService


@dataclass
class FAQMatchResult:
    """FAQ 匹配结果

    - matched: similarity >= confirm_threshold（命中，需返回给上层）
    - direct_answer: similarity >= similarity_threshold（可直接返回答案，无需确认）
    - 仅 matched=True 时才有意义；match 未命中时上层走 RAG 流程
    """
    matched: bool
    direct_answer: bool
    faq_id: int | None
    question: str
    answer: str
    similarity: float
    category: str = "general"


class FAQMatcher:
    """FAQ 匹配器：无状态可共享，仅 FAQ 列表带 TTL 缓存"""

    _FAQ_CACHE_TTL_SEC: float = 300.0

    def __init__(
        self,
        repo: ChatbotRepository,
        embedding_service: EmbeddingService,
        config: ChatbotFAQConfig,
    ) -> None:
        self._repo = repo
        self._embedding_service = embedding_service
        self._config = config
        # FAQ 列表缓存：避免每次请求都查 DB（active FAQ 数量稳定，适合缓存）
        self._faq_cache: list[dict] | None = None
        self._faq_cache_time: float = 0.0

    async def match(self, query: str) -> FAQMatchResult | None:
        """FAQ 匹配

        流程：
        1. 加载 active FAQ（带 5 分钟缓存）
        2. 确保 FAQ 有 embedding（无则批量生成并回写 DB）
        3. query 向量化，与每条 FAQ 计算 cosine 相似度
        4. embedding 不可用时降级到编辑距离相似度
        5. 取最高分：≥ similarity_threshold 直接返回；≥ confirm_threshold 标记命中

        Returns:
            FAQMatchResult: 命中（≥ confirm_threshold）；None: 未命中，上层走 RAG
        """
        faqs = self._load_faqs()
        if not faqs:
            return None

        # 确保 FAQ 有 embedding（懒生成 + 持久化，下次请求直接复用）
        await self._ensure_faq_embeddings(faqs)

        query_embedding = await self._embedding_service.embed(query)

        if query_embedding:
            # 主路径：向量 cosine 相似度
            best_score, best_faq = self._find_best_faq(
                faqs, lambda faq: self._score_faq_by_embedding(faq, query_embedding),
            )
        else:
            # 降级路径：embedding 服务不可用时用编辑距离兜底，保证匹配链路不中断
            logger.warning("query embedding 为空，降级到编辑距离匹配")
            best_score, best_faq = self._find_best_faq(
                faqs, lambda faq: self._levenshtein_ratio(query, faq.get("question", "")),
            )

        if best_faq is None or best_score < self._config.confirm_threshold:
            return None

        return FAQMatchResult(
            matched=True,
            direct_answer=best_score >= self._config.similarity_threshold,
            faq_id=best_faq.get("id"),
            question=best_faq.get("question", ""),
            answer=best_faq.get("answer", ""),
            similarity=round(best_score, 4),
            category=best_faq.get("category", "general"),
        )

    def _find_best_faq(
        self,
        faqs: list[dict],
        score_fn,
    ) -> tuple[float, dict | None]:
        """遍历 FAQ 列表，返回 (最高分, 对应 FAQ)

        为什么提取：原 match 方法主路径（向量）与降级路径（编辑距离）的
        for + if score > best_score 逻辑完全重复，重复结构推高认知复杂度。
        提取后两条路径共用同一遍历骨架，score_fn 注入打分差异。
        score_fn 返回 -1.0 表示跳过该 FAQ（如缺 embedding）。
        """
        best_score = 0.0
        best_faq: dict | None = None
        for faq in faqs:
            score = score_fn(faq)
            if score < 0:
                continue
            if score > best_score:
                best_score = score
                best_faq = faq
        return best_score, best_faq

    def _score_faq_by_embedding(
        self, faq: dict, query_embedding: list[float],
    ) -> float:
        """单条 FAQ 的向量相似度打分

        返回 -1.0 表示该 FAQ 缺 embedding 应跳过（_find_best_faq 据此过滤），
        避免在遍历骨架中再嵌套一层 if not faq_embedding 分支。
        """
        faq_embedding = faq.get("question_embedding")
        if not faq_embedding:
            return -1.0
        return self._compute_similarity(query_embedding, faq_embedding)

    def _compute_similarity(
        self, query_embedding: list[float], faq_embedding: list[float]
    ) -> float:
        """cosine 相似度 = dot(a,b) / (|a| * |b|)

        防止除零：任一向量为零向量时返回 0.0（理论上 embedding 不应为零，
        但 OpenAI 极端输入下可能返回近零向量）
        """
        # M-22 修复：维度不一致时 zip 会静默截断导致相似度失真
        # 常见诱因：配置 dimensions 变更后旧 FAQ embedding 仍是旧维度
        if len(query_embedding) != len(faq_embedding):
            logger.warning(
                f"embedding 维度不一致：query={len(query_embedding)} "
                f"faq={len(faq_embedding)}，跳过该 FAQ"
            )
            return 0.0
        dot = 0.0
        norm_a = 0.0
        norm_b = 0.0
        for a, b in zip(query_embedding, faq_embedding):
            dot += a * b
            norm_a += a * a
            norm_b += b * b
        if norm_a <= 0.0 or norm_b <= 0.0:
            return 0.0
        return dot / ((norm_a ** 0.5) * (norm_b ** 0.5))

    def _levenshtein_ratio(self, s1: str, s2: str) -> float:
        """编辑距离相似度（embedding 降级方案）

        优先 rapidfuzz（C 实现，比 python-Levenshtein 快 10x）；
        未安装时回退到 difflib.SequenceMatcher（标准库，性能略低但无额外依赖）。
        返回 0.0 ~ 1.0。
        """
        try:
            from rapidfuzz import fuzz
            return fuzz.ratio(s1, s2) / 100.0
        except ImportError:
            from difflib import SequenceMatcher
            return SequenceMatcher(None, s1, s2).ratio()

    async def _ensure_faq_embeddings(self, faqs: list[dict]) -> None:
        """为缺失 embedding 的 FAQ 批量生成并回写 DB

        部分失败容忍：失败的 FAQ 跳过（不阻塞匹配，该 FAQ 在本次匹配中被排除）。
        embed_batch 返回 (success_vectors, failed_indices)，success_vectors 按原序
        跳过失败项，需通过 failed_indices 重建原始索引到向量的映射。
        """
        pending = [(i, faq) for i, faq in enumerate(faqs) if not faq.get("question_embedding")]
        if not pending:
            return

        texts = [faq["question"] for _, faq in pending]
        vectors, failed_indices = await self._embedding_service.embed_batch(texts)
        if not vectors:
            # 全部失败或返回空：跳过，不阻塞匹配
            logger.warning("FAQ embedding 批量生成失败，本次匹配将跳过这些 FAQ")
            return

        # embed_batch 的 success_vectors 按原序跳过失败项，需用 failed_indices 还原对应关系
        failed_set = set(failed_indices)
        success_idx = 0
        for local_idx, (_orig_idx, faq) in enumerate(pending):
            if local_idx in failed_set:
                continue
            vec = vectors[success_idx]
            success_idx += 1
            faq["question_embedding"] = vec
            try:
                self._repo.update_faq_embedding(faq["id"], vec)
            except Exception as e:
                # 持久化失败不影响本次匹配（内存中已设置），仅记录告警
                logger.warning(f"FAQ {faq.get('id')} embedding 持久化失败: {e}")

    def _load_faqs(self) -> list[dict]:
        """加载 active FAQ 列表（带 TTL 缓存）

        缓存而非每次查 DB：FAQ 总数 < 1000 且变更低频，5 分钟最终一致性可接受。
        """
        now = time.time()
        if self._faq_cache is None or (now - self._faq_cache_time) > self._FAQ_CACHE_TTL_SEC:
            self._faq_cache = self._repo.list_faqs(active_only=True)
            self._faq_cache_time = now
        return self._faq_cache