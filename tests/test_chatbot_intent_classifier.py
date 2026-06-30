"""IntentClassifier 测试：覆盖规则分类与降级放行逻辑

仅测试阶段1（规则预筛）与降级路径，不实际调用 LLM API：
- 规则命中范围内/范围外关键词：直接返回，不调 LLM
- LLM 未配置（_http=None）：保守放行 in_scope=True
- 空消息：直接拒绝

为什么不对 LLM 路径做单元测试：依赖外网 API 与预算模块，应集成测试覆盖。
"""
import pytest
from unittest.mock import MagicMock, patch

from xianyu_hunter.modules.chatbot.intent_classifier import (
    IntentClassifier,
    IntentResult,
)
from xianyu_hunter.infra.yaml_config import ChatbotConfig


@pytest.fixture
def classifier_no_llm():
    """无 LLM 客户端的分类器（_http=None，走保守放行）

    H2 修复后 IntentClassifier 通过 get_settings() 读取 api_key（支持 keyring），
    不再读 os.environ，因此需 patch get_settings 返回空 api_key 触发 _http=None。
    """
    config = ChatbotConfig()
    mock_settings = MagicMock()
    mock_settings.openai_api_key = ""
    mock_settings.openai_base_url = "https://api.openai.com/v1"
    with patch(
        "xianyu_hunter.modules.chatbot.intent_classifier.get_settings",
        return_value=mock_settings,
    ):
        clf = IntentClassifier(config=config)
    assert clf._http is None, "测试前置：分类器应处于无 LLM 模式"
    return clf


class TestRuleClassify:
    """阶段1：规则预筛（命中即返回，不调 LLM）"""

    @pytest.mark.parametrize("message,expected_action", [
        ("如何创建任务？", "rag"),         # 命中"任务"→rag
        ("采集任务怎么配置？", "rag"),     # 命中"采集"→rag
        ("Cookie 怎么登录？", "faq"),      # 命中"Cookie"→faq
        ("AI 模型用哪个？", "faq"),        # 命中"AI"+"模型"→faq
        ("商品价格怎么算？", "agent"),     # 命中"商品"→agent
        ("卖家信息在哪看？", "agent"),     # 命中"卖家"→agent
        ("闲鱼猎人有什么功能？", "rag"),   # 命中"闲鱼猎人"→rag
    ])
    def test_in_scope_keyword_hit(self, classifier_no_llm, message, expected_action):
        """范围内关键词命中：in_scope=True，suggested_action 按 FAQ/AGENT/RAG 推荐"""
        result = _sync_call(classifier_no_llm, message)
        assert result.in_scope is True
        assert result.used_llm is False
        assert result.suggested_action == expected_action


def _sync_call(classifier: IntentClassifier, message: str) -> IntentResult:
    """辅助：同步运行 async classify（pytest 同步测试用）

    用 asyncio.run 简化测试代码，避免每个测试都写 async。
    """
    import asyncio
    return asyncio.run(classifier.classify(message))


class TestOutOfScope:
    """范围外关键词：直接拒绝"""

    @pytest.mark.parametrize("keyword", [
        "天气", "新闻", "股票", "游戏", "电影",
        "音乐", "菜谱", "旅游", "笑话", "翻译",
    ])
    def test_out_of_scope_rejected(self, classifier_no_llm, keyword):
        """范围外关键词命中：in_scope=False，suggested_action=reject"""
        result = _sync_call(classifier_no_llm, f"今天{keyword}怎么样？")
        assert result.in_scope is False
        assert result.suggested_action == "reject"
        assert result.used_llm is False
        assert "范围外关键词" in result.reason


class TestEmptyMessage:
    """空消息：直接拒绝，避免无意义调用"""

    def test_empty_string_rejected(self, classifier_no_llm):
        result = _sync_call(classifier_no_llm, "")
        assert result.in_scope is False
        assert result.suggested_action == "reject"
        assert result.reason == "空消息"

    def test_whitespace_only_rejected(self, classifier_no_llm):
        """纯空白消息（strip 后为空）应被拒绝"""
        result = _sync_call(classifier_no_llm, "   ")
        assert result.in_scope is False
        assert result.suggested_action == "reject"


class TestLLMUnavailableFallback:
    """LLM 未配置时（_http=None）：规则无法判定时保守放行

    保守策略：分类器故障不应阻断用户对话，让 RAG/AGENT 兜底。
    """

    def test_unknown_message_falls_back_to_in_scope(self, classifier_no_llm):
        """既不在范围内也不在范围外的消息，LLM 不可用时保守放行"""
        # "你好" 不在任何关键词列表中
        result = _sync_call(classifier_no_llm, "你好")
        assert result.in_scope is True
        assert result.used_llm is False
        assert "保守放行" in result.reason
        assert result.suggested_action == "rag"

    def test_unrelated_question_falls_back(self, classifier_no_llm):
        """与系统无关但不在范围外关键词列表的问题，保守放行"""
        # "今天几号" 不在关键词列表
        result = _sync_call(classifier_no_llm, "今天几号")
        assert result.in_scope is True
        assert result.suggested_action == "rag"


class TestSuggestAction:
    """_suggest_action 路由推荐逻辑"""

    def test_faq_keywords_routed_to_faq(self, classifier_no_llm):
        """配置/概念类关键词 → faq"""
        for kw in ["Cookie", "cookie", "配置", "Prompt", "AI", "模型", "预算"]:
            assert classifier_no_llm._suggest_action(kw) == "faq"

    def test_agent_keywords_routed_to_agent(self, classifier_no_llm):
        """数据查询类关键词 → agent"""
        for kw in ["价格", "商品", "卖家", "买家", "订单"]:
            assert classifier_no_llm._suggest_action(kw) == "agent"

    def test_other_scope_keywords_routed_to_rag(self, classifier_no_llm):
        """其余业务操作类关键词 → rag"""
        for kw in ["任务", "采集", "评估", "抢单", "通知", "反爬", "闲鱼猎人"]:
            assert classifier_no_llm._suggest_action(kw) == "rag"
