"""Escalation 转人工测试：覆盖 5 个触发条件与脱敏响应构建

用 MagicMock 替换 ChatbotRepository，避免 DB 依赖。
重点测试：关键词触发、状态机约束、降级响应、PII 脱敏开关。
"""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from xianyu_hunter.modules.chatbot.escalation import Escalation, EscalationResponse
from xianyu_hunter.infra.yaml_config import ChatbotEscalationConfig


@pytest.fixture
def mock_repo():
    """Mock 仓库：默认无负面反馈、无消息、无会话超时"""
    repo = MagicMock()
    repo.count_recent_negative_feedback.return_value = 0
    repo.list_messages.return_value = []
    repo.get_session.return_value = None
    return repo


@pytest.fixture
def config():
    """默认配置：feedback_threshold=3, sanitize_pii=True"""
    return ChatbotEscalationConfig(
        contact="QQ群: 123456",
        feedback_threshold=3,
        feedback_window_min=60,
        sanitize_pii=True,
    )


@pytest.fixture
def escalation(mock_repo, config):
    return Escalation(repo=mock_repo, config=config)


class TestShouldEscalateKeywords:
    """触发条件 1：用户消息含转人工关键词"""

    @pytest.mark.parametrize("keyword", [
        "转人工", "人工客服", "联系客服", "找客服",
        "真人", "人工", "转接", "客服",
    ])
    def test_keyword_triggers_escalation(self, escalation, mock_repo, keyword):
        """任一关键词命中即触发转人工"""
        # 配置 mock 避免其他触发条件干扰：状态非 escalated，无负面反馈，无超时
        mock_repo.get_session.return_value = None
        should, reason = escalation.should_escalate("s1", f"我要{keyword}", "active")
        assert should is True
        assert reason == "用户请求转人工"

    def test_keyword_takes_priority_over_other_conditions(self, escalation, mock_repo):
        """关键词触发优先级最高，即使会话已 escalated 也只返回关键词原因"""
        mock_repo.get_session.return_value = None
        should, reason = escalation.should_escalate("s1", "转人工", "escalated")
        assert should is True
        assert reason == "用户请求转人工"  # 而非"会话已转人工"


class TestShouldEscalateStatus:
    """触发条件 2：会话状态已是 escalated"""

    def test_escalated_status_triggers(self, escalation, mock_repo):
        """context_status=escalated 直接触发（避免重复判定）"""
        should, reason = escalation.should_escalate("s1", "继续问题", "escalated")
        assert should is True
        assert reason == "会话已转人工"


class TestShouldEscalateFeedback:
    """触发条件 3：负面反馈达阈值"""

    def test_feedback_below_threshold_not_triggered(self, escalation, mock_repo):
        """负面反馈数 < threshold 不触发"""
        mock_repo.count_recent_negative_feedback.return_value = 2  # threshold=3
        mock_repo.get_session.return_value = None
        should, reason = escalation.should_escalate("s1", "问题", "active")
        assert should is False

    def test_feedback_at_threshold_triggered(self, escalation, mock_repo):
        """负面反馈数 >= threshold 触发"""
        mock_repo.count_recent_negative_feedback.return_value = 3  # threshold=3
        should, reason = escalation.should_escalate("s1", "问题", "active")
        assert should is True
        assert reason == "负面反馈触发阈值"


class TestShouldEscalateTimeout:
    """触发条件 4：会话超时且未结束"""

    def test_timeout_active_triggers(self, escalation, mock_repo):
        """active 会话超时触发转人工（引导用户重新开始）"""
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=60)).isoformat()
        mock_repo.get_session.return_value = {"last_active_at": old_time}
        mock_repo.count_recent_negative_feedback.return_value = 0
        should, reason = escalation.should_escalate("s1", "问题", "active")
        assert should is True
        assert reason == "会话超时"

    def test_timeout_ended_not_triggered(self, escalation, mock_repo):
        """ended 会话即使超时也不触发（已是终态）"""
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=60)).isoformat()
        mock_repo.get_session.return_value = {"last_active_at": old_time}
        mock_repo.count_recent_negative_feedback.return_value = 0
        should, reason = escalation.should_escalate("s1", "问题", "ended")
        assert should is False

    def test_no_session_not_triggered(self, escalation, mock_repo):
        """会话不存在（get_session=None）不触发超时"""
        mock_repo.get_session.return_value = None
        mock_repo.count_recent_negative_feedback.return_value = 0
        should, reason = escalation.should_escalate("s1", "问题", "active")
        assert should is False


class TestShouldEscalateLLMFailures:
    """触发条件 5：连续 3 次 LLM 调用失败"""

    def test_three_consecutive_failures_triggers(self, escalation, mock_repo):
        """最近 3 条 assistant 消息全部标记 llm_failed 触发转人工"""
        mock_repo.count_recent_negative_feedback.return_value = 0
        mock_repo.get_session.return_value = None
        mock_repo.list_messages.return_value = [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1", "metadata": {"llm_failed": True}},
            {"role": "user", "content": "Q2"},
            {"role": "assistant", "content": "A2", "metadata": {"llm_failed": True}},
            {"role": "user", "content": "Q3"},
            {"role": "assistant", "content": "A3", "metadata": {"llm_failed": True}},
        ]
        should, reason = escalation.should_escalate("s1", "问题", "active")
        assert should is True
        assert reason == "LLM 持续失败"

    def test_two_failures_not_triggers(self, escalation, mock_repo):
        """仅 2 次失败不触发"""
        mock_repo.count_recent_negative_feedback.return_value = 0
        mock_repo.get_session.return_value = None
        mock_repo.list_messages.return_value = [
            {"role": "assistant", "content": "A1", "metadata": {"llm_failed": True}},
            {"role": "assistant", "content": "A2", "metadata": {"llm_failed": True}},
            {"role": "assistant", "content": "A3", "metadata": {}},
        ]
        should, reason = escalation.should_escalate("s1", "问题", "active")
        assert should is False

    def test_failure_streak_broken_not_triggers(self, escalation, mock_repo):
        """失败被一条成功消息打断，不视为连续"""
        mock_repo.count_recent_negative_feedback.return_value = 0
        mock_repo.get_session.return_value = None
        mock_repo.list_messages.return_value = [
            {"role": "assistant", "content": "A1", "metadata": {"llm_failed": True}},
            {"role": "assistant", "content": "A2", "metadata": {"llm_failed": True}},
            {"role": "assistant", "content": "A3", "metadata": {}},  # 成功
            {"role": "assistant", "content": "A4", "metadata": {"llm_failed": True}},
            {"role": "assistant", "content": "A5", "metadata": {"llm_failed": True}},
        ]
        # 从后向前数：2 次失败（A5、A4），然后 A3 成功打断，不达阈值 3
        should, reason = escalation.should_escalate("s1", "问题", "active")
        assert should is False


class TestBuildEscalationResponse:
    """build_escalation_response 响应构建"""

    def test_response_with_contact(self, escalation):
        """配置了联系方式时，message_to_user 含 contact"""
        resp = escalation.build_escalation_response(reason="用户请求转人工")
        assert isinstance(resp, EscalationResponse)
        assert resp.should_escalate is True
        assert resp.reason == "用户请求转人工"
        assert resp.contact == "QQ群: 123456"
        assert "QQ群: 123456" in resp.message_to_user

    def test_response_without_contact_fallback(self, mock_repo):
        """未配置联系方式时降级为"请联系管理员" """
        config_no_contact = ChatbotEscalationConfig(contact="", sanitize_pii=True)
        esc = Escalation(repo=mock_repo, config=config_no_contact)
        resp = esc.build_escalation_response(reason="测试")
        assert resp.contact == "请联系管理员"
        assert "请联系管理员" in resp.message_to_user

    def test_no_session_data_no_sanitization(self, escalation):
        """未提供 session_data 时 sanitized_session=None（避免无意义脱敏）"""
        resp = escalation.build_escalation_response(reason="测试", session_data=None)
        assert resp.sanitized_session is None

    def test_sanitization_disabled_returns_raw(self, mock_repo):
        """sanitize_pii=False 时即使提供 session_data 也不脱敏"""
        config_no_pii = ChatbotEscalationConfig(contact="x", sanitize_pii=False)
        esc = Escalation(repo=mock_repo, config=config_no_pii)
        session_data = {"messages": [{"role": "user", "content": "手机: 13812345678"}]}
        resp = esc.build_escalation_response(reason="测试", session_data=session_data)
        assert resp.sanitized_session is None

    def test_sanitization_enabled_redacts_pii(self, escalation):
        """sanitize_pii=True 时对 session_data 做脱敏（手机号被掩码）"""
        session_data = {
            "messages": [
                {"role": "user", "content": "我的手机是 13812345678"},
            ],
        }
        resp = escalation.build_escalation_response(reason="测试", session_data=session_data)
        assert resp.sanitized_session is not None
        sanitized_content = resp.sanitized_session["messages"][0]["content"]
        assert "13812345678" not in sanitized_content


class TestIsSessionTimedOut:
    """_is_session_timed_out 超时判定（30 分钟默认超时）"""

    def test_no_last_active(self, escalation):
        assert escalation._is_session_timed_out({}) is False

    def test_invalid_datetime(self, escalation):
        assert escalation._is_session_timed_out({"last_active_at": "invalid"}) is False

    def test_recent_not_timeout(self, escalation):
        recent = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        assert escalation._is_session_timed_out({"last_active_at": recent}) is False

    def test_old_timeout(self, escalation):
        """60 分钟前活跃视为超时（默认 30 分钟超时）"""
        old = (datetime.now(timezone.utc) - timedelta(minutes=60)).isoformat()
        assert escalation._is_session_timed_out({"last_active_at": old}) is True


class TestHasConsecutiveLLMFailures:
    """_has_consecutive_llm_failures 连续失败检测"""

    def test_empty_messages(self, escalation, mock_repo):
        mock_repo.list_messages.return_value = []
        assert escalation._has_consecutive_llm_failures("s1") is False

    def test_no_assistant_messages(self, escalation, mock_repo):
        """仅有 user 消息时不算失败"""
        mock_repo.list_messages.return_value = [
            {"role": "user", "content": "Q1"},
            {"role": "user", "content": "Q2"},
        ]
        assert escalation._has_consecutive_llm_failures("s1") is False

    def test_metadata_not_dict(self, escalation, mock_repo):
        """metadata 非 dict 时不算失败（避免类型错误）"""
        mock_repo.list_messages.return_value = [
            {"role": "assistant", "content": "A1", "metadata": "not a dict"},
            {"role": "assistant", "content": "A2", "metadata": None},
            {"role": "assistant", "content": "A3", "metadata": 123},
        ]
        assert escalation._has_consecutive_llm_failures("s1") is False
