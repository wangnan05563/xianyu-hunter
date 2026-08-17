"""IntentClassifier：两阶段意图分类器（规则预筛 + LLM 兜底）

职责：
- 判断用户问题是否在闲鱼猎人系统范围内，避免 LLM 被滥用回答无关问题
- 阶段1：关键词规则预筛（< 1ms），覆盖 80% 场景
- 阶段2：仅规则无法判定时调用 LLM 兜底（~800ms），纳入预算控制
- 保守策略：LLM 不可用时放行（in_scope=True），让 RAG/AGENT 兜底，避免误拒

设计要点（详见 docs/chatbot-详细设计.md §5.4、docs/chatbot-概要设计.md §3.2.4）：
- 为什么规则优先：白/黑名单关键词覆盖常见问法，省去 LLM 调用延迟与费用
- 为什么 LLM 失败要放行：分类器故障不应阻断用户对话，RAG/AGENT 无答案时再拒绝
- suggested_action 仅作上层路由建议，最终走向由 Orchestrator 综合判断
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import httpx
from loguru import logger

from xianyu_hunter.config import get_settings
from xianyu_hunter.infra.yaml_config import ChatbotConfig


@dataclass
class IntentResult:
    """意图分类结果

    - in_scope: 是否在系统范围内
    - confidence: 置信度 0.0 ~ 1.0
    - used_llm: 是否使用了 LLM 分类（规则命中时为 False）
    - reason: 分类原因（用于日志排查，不直接展示给用户）
    - suggested_action: 建议动作 rag / agent / faq / reject
    """
    in_scope: bool
    confidence: float
    used_llm: bool
    reason: str
    suggested_action: str


class IntentClassifier:
    """两阶段意图分类器：规则预筛 + LLM 兜底"""

    # 范围内关键词（27 项）：业务/技术词 + 系统名称"闲鱼猎人"（最强范围内信号）
    _SCOPE_KEYWORDS: list[str] = [
        "任务", "采集", "评估", "抢单", "通知", "Cookie", "cookie",
        "反爬", "登录", "价格", "商品", "卖家", "买家", "订单",
        "调度", "定时", "cron", "搜索", "过滤", "排除", "区域",
        "配置", "Prompt", "AI", "模型", "预算", "闲鱼猎人",
    ]
    # 范围外关键词（10 项）：明确与系统无关的通用话题
    _OUT_OF_SCOPE_KEYWORDS: list[str] = [
        "天气", "新闻", "股票", "游戏", "电影",
        "音乐", "菜谱", "旅游", "笑话", "翻译",
    ]

    # 配置/概念类关键词 → 推荐 FAQ（常见问法，FAQ 库通常已覆盖）
    _FAQ_KEYWORDS: frozenset[str] = frozenset({
        "Cookie", "cookie", "配置", "Prompt", "AI", "模型", "预算",
    })
    # 数据查询类关键词 → 推荐 Agent（需工具调用获取实时数据）
    _AGENT_KEYWORDS: frozenset[str] = frozenset({
        "价格", "商品", "卖家", "买家", "订单",
    })

    def __init__(self, config: ChatbotConfig, ai_usage=None) -> None:
        self._config = config
        # ai_usage 为 None 时回退到 ai_usage 模块本身（模块级函数作为属性调用），
        # 与 EmbeddingService 的注入方式保持一致，便于独立测试与未注入场景
        if ai_usage is None:
            from xianyu_hunter.infra import ai_usage as _ai_usage_module
            self._ai_usage = _ai_usage_module
        else:
            self._ai_usage = ai_usage

        # H2 修复：从 settings 读取 api_key 与 base_url，支持 keyring 与 .env 双源配置
        # 原 os.getenv 只读 .env，忽略 keyring 中用户通过 UI 设置的密钥
        settings = get_settings()
        self._api_key = settings.openai_api_key
        self._base_url = settings.openai_base_url.rstrip("/")
        if self._api_key:
            self._http = httpx.AsyncClient(
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=httpx.Timeout(
                    connect=5.0,
                    read=float(config.llm.http_timeout_sec),
                    write=5.0,
                    pool=2.0,
                ),
            )
        else:
            self._http = None

    async def classify(self, message: str) -> IntentResult:
        """两阶段分类

        阶段1：_rule_classify（关键词规则），命中即返回
        阶段2：规则不确定时调用 _llm_classify

        边界条件：
        - 空字符串：直接拒绝（in_scope=False），避免无意义调用
        - LLM 不可用/失败：保守放行，让 RAG/AGENT 兜底
        """
        message = message.strip()
        if not message:
            return IntentResult(
                in_scope=False, confidence=1.0, used_llm=False,
                reason="空消息", suggested_action="reject",
            )

        # 阶段 1：规则预筛
        rule_result = self._rule_classify(message)
        if rule_result is not None:
            return rule_result

        # 阶段 2：LLM 兜底
        return await self._llm_classify(message)

    def _rule_classify(self, message: str) -> IntentResult | None:
        """规则预筛

        优先检查范围外关键词：明确无关则直接拒绝，避免无谓的 LLM 调用；
        再检查范围内关键词：命中则按关键词类型推荐路由动作。
        返回 None 表示规则无法判定，需 LLM 兜底。
        """
        for kw in self._OUT_OF_SCOPE_KEYWORDS:
            if kw in message:
                return IntentResult(
                    in_scope=False, confidence=0.95, used_llm=False,
                    reason=f"命中范围外关键词: {kw}", suggested_action="reject",
                )
        for kw in self._SCOPE_KEYWORDS:
            if kw in message:
                return IntentResult(
                    in_scope=True, confidence=0.9, used_llm=False,
                    reason=f"命中范围内关键词: {kw}",
                    suggested_action=self._suggest_action(kw),
                )
        return None

    def _suggest_action(self, keyword: str) -> str:
        """根据命中的范围内关键词推荐路由动作

        配置/概念类 → FAQ；数据查询类 → Agent；其余业务操作类 → RAG。
        仅作建议，上层 Orchestrator 可综合上下文覆盖。
        """
        if keyword in self._FAQ_KEYWORDS:
            return "faq"
        if keyword in self._AGENT_KEYWORDS:
            return "agent"
        return "rag"

    async def _llm_classify(self, message: str) -> IntentResult:
        """LLM 兜底分类

        失败策略：网络异常/超时/预算超限时保守返回 in_scope=True，
        让 RAG/AGENT 兜底处理（避免因分类器故障导致无法回答）。
        调用前 check_budget，调用后 record_usage（endpoint=chatbot_intent）。
        """
        if self._http is None:
            return IntentResult(
                in_scope=True, confidence=0.5, used_llm=False,
                reason="LLM 未配置，保守放行", suggested_action="rag",
            )

        # 预算检查：避免超额调用导致费用失控
        try:
            budget_ok, reason = self._ai_usage.check_budget()
            if not budget_ok:
                return IntentResult(
                    in_scope=True, confidence=0.5, used_llm=False,
                    reason=f"预算超限，保守放行: {reason}", suggested_action="rag",
                )
        except Exception as e:
            # 预算检查本身故障不应阻断分类，保守放行
            logger.warning(f"预算检查异常，保守放行: {e}")
            return IntentResult(
                in_scope=True, confidence=0.5, used_llm=False,
                reason=f"预算检查异常，保守放行: {type(e).__name__}",
                suggested_action="rag",
            )

        system_prompt = (
            "你是一个意图分类器。判断用户问题是否与「闲鱼自动捡漏与抢单系统」相关。"
            "系统功能包括：商品采集、卖家评估、自动抢单、Cookie 管理、反爬、"
            "任务调度、定时 cron、配置管理、AI 评估、Prompt、通知推送等。"
            "只返回 JSON，不要任何额外文本："
            '{"in_scope": true/false, "confidence": 0.0-1.0, "reason": "简短原因"}'
        )

        try:
            resp = await self._http.post(
                f"{self._base_url}/chat/completions",
                json={
                    "model": self._config.llm.model,
                    "temperature": 0.0,  # 分类任务用确定性输出，避免随机性
                    "max_tokens": 200,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": message},
                    ],
                },
            )
            resp.raise_for_status()
            data = resp.json()

            # 记录用量（endpoint 命名 chatbot_intent，便于按用途统计费用）
            try:
                self._ai_usage.record_usage(
                    endpoint="chatbot_intent",
                    model=self._config.llm.model,
                    response_data=data,
                )
            except Exception as e:
                logger.warning(f"record_usage 失败（不影响分类）: {e}")

            # M-11 修复：OpenAI 兼容 API 在触发安全过滤时可能返回 content: null
            # 用 .get + or "" 避免 None.strip() 抛 AttributeError
            content = (data["choices"][0]["message"].get("content") or "").strip()
            if not content:
                return IntentResult(
                    in_scope=True, confidence=0.5, used_llm=True,
                    reason="LLM 返回空内容，保守放行", suggested_action="rag",
                )
            # M-12 修复：LLM 偶尔返回非合法 JSON（如带 markdown 包裹），单独捕获便于排查
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as je:
                logger.warning(f"LLM 返回非 JSON 内容，保守放行: {je}; raw={content[:200]}")
                return IntentResult(
                    in_scope=True, confidence=0.5, used_llm=True,
                    reason=f"LLM 返回非 JSON，保守放行: {je}", suggested_action="rag",
                )
            in_scope = bool(parsed.get("in_scope", True))
            confidence = float(parsed.get("confidence", 0.5))
            reason = str(parsed.get("reason", "LLM 判定"))

            return IntentResult(
                in_scope=in_scope,
                confidence=confidence,
                used_llm=True,
                reason=f"LLM: {reason}",
                suggested_action="rag" if in_scope else "reject",
            )
        except Exception as e:
            logger.warning(f"LLM 意图分类失败，保守放行: {e}")
            return IntentResult(
                in_scope=True, confidence=0.5, used_llm=False,
                reason=f"LLM 不可用，保守放行: {type(e).__name__}",
                suggested_action="rag",
            )