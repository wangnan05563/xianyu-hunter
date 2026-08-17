"""智能客服配置验证测试

覆盖 yaml_config.py 中 ChatbotConfig 及子配置的 Pydantic 验证逻辑。
为什么优先测试此模块：配置验证是系统稳定性的第一道防线，
错误的配置值（如 top_k=0、similarity_threshold>1）会导致运行时异常。
"""
import pytest
from pydantic import ValidationError

from xianyu_hunter.infra.yaml_config import (
    ChatbotConfig,
    ChatbotRAGConfig,
    ChatbotLLMConfig,
    ChatbotAgentConfig,
    ChatbotKBConfig,
    ChatbotFAQConfig,
    ChatbotEscalationConfig,
)


class TestChatbotRAGConfig:
    def test_default_values(self):
        cfg = ChatbotRAGConfig()
        assert cfg.top_k == 5
        assert cfg.similarity_threshold == 0.65
        assert cfg.max_context_chars == 8000

    def test_top_k_range(self):
        """top_k 必须在 1-20 之间"""
        with pytest.raises(ValidationError):
            ChatbotRAGConfig(top_k=0)
        with pytest.raises(ValidationError):
            ChatbotRAGConfig(top_k=21)

    def test_similarity_threshold_range(self):
        """相似度阈值必须在 0-1 之间"""
        with pytest.raises(ValidationError):
            ChatbotRAGConfig(similarity_threshold=-0.1)
        with pytest.raises(ValidationError):
            ChatbotRAGConfig(similarity_threshold=1.1)

    def test_max_context_chars_range(self):
        with pytest.raises(ValidationError):
            ChatbotRAGConfig(max_context_chars=100)  # < 500
        with pytest.raises(ValidationError):
            ChatbotRAGConfig(max_context_chars=50000)  # > 32000


class TestChatbotLLMConfig:
    def test_defaults(self):
        cfg = ChatbotLLMConfig()
        assert cfg.model == "gpt-4o-mini"
        assert cfg.temperature == 0.3

    def test_temperature_range(self):
        with pytest.raises(ValidationError):
            ChatbotLLMConfig(temperature=-0.1)
        with pytest.raises(ValidationError):
            ChatbotLLMConfig(temperature=2.1)


class TestChatbotAgentConfig:
    def test_max_tool_rounds_range(self):
        with pytest.raises(ValidationError):
            ChatbotAgentConfig(max_tool_rounds=0)
        with pytest.raises(ValidationError):
            ChatbotAgentConfig(max_tool_rounds=11)

    def test_timeouts_range(self):
        with pytest.raises(ValidationError):
            ChatbotAgentConfig(tool_call_timeout_sec=0)
        with pytest.raises(ValidationError):
            ChatbotAgentConfig(tool_total_timeout_sec=5)  # < 10


class TestChatbotKBConfig:
    def test_defaults(self):
        cfg = ChatbotKBConfig()
        assert cfg.auto_update_enabled is True
        assert cfg.update_interval_hours == 6
        assert cfg.embedding_model == "text-embedding-3-small"
        assert cfg.embedding_dimensions == 1536

    def test_update_interval_range(self):
        with pytest.raises(ValidationError):
            ChatbotKBConfig(update_interval_hours=0)
        with pytest.raises(ValidationError):
            ChatbotKBConfig(update_interval_hours=200)  # > 168

    def test_doc_paths_default(self):
        cfg = ChatbotKBConfig()
        assert "docs/" in cfg.doc_paths
        assert "backend/xianyu_hunter/" in cfg.doc_paths


class TestChatbotFAQConfig:
    def test_threshold_ordering_not_enforced(self):
        """FAQ 阈值不强制 confirm < similarity，业务层处理区间判断"""
        cfg = ChatbotFAQConfig(similarity_threshold=0.65, confirm_threshold=0.85)
        assert cfg.similarity_threshold == 0.65

    def test_threshold_range(self):
        with pytest.raises(ValidationError):
            ChatbotFAQConfig(similarity_threshold=1.5)


class TestChatbotEscalationConfig:
    def test_defaults(self):
        cfg = ChatbotEscalationConfig()
        assert cfg.feedback_threshold == 2
        assert cfg.feedback_window_min == 30
        assert cfg.sanitize_pii is True

    def test_feedback_threshold_range(self):
        with pytest.raises(ValidationError):
            ChatbotEscalationConfig(feedback_threshold=0)
        with pytest.raises(ValidationError):
            ChatbotEscalationConfig(feedback_threshold=11)


class TestChatbotConfig:
    def test_full_config_defaults(self):
        """完整配置应含所有子配置的默认值"""
        cfg = ChatbotConfig()
        assert cfg.enabled is True
        assert cfg.max_history_turns == 10
        assert cfg.session_timeout_min == 30
        assert isinstance(cfg.rag, ChatbotRAGConfig)
        assert isinstance(cfg.llm, ChatbotLLMConfig)
        assert isinstance(cfg.agent, ChatbotAgentConfig)
        assert isinstance(cfg.kb, ChatbotKBConfig)
        assert isinstance(cfg.faq, ChatbotFAQConfig)
        assert isinstance(cfg.escalation, ChatbotEscalationConfig)

    def test_max_history_turns_range(self):
        with pytest.raises(ValidationError):
            ChatbotConfig(max_history_turns=0)
        with pytest.raises(ValidationError):
            ChatbotConfig(max_history_turns=21)

    def test_session_timeout_range(self):
        with pytest.raises(ValidationError):
            ChatbotConfig(session_timeout_min=1)  # < 5
        with pytest.raises(ValidationError):
            ChatbotConfig(session_timeout_min=1500)  # > 1440

    def test_nested_override(self):
        """嵌套配置可通过 dict 覆盖"""
        cfg = ChatbotConfig.model_validate({
            "enabled": False,
            "rag": {"top_k": 10},
        })
        assert cfg.enabled is False
        assert cfg.rag.top_k == 10
        # 未覆盖的字段保持默认
        assert cfg.rag.similarity_threshold == 0.65
