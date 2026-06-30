"""ContextManager 测试：覆盖历史截断、超时检测、标题生成、消息保存

用 MagicMock 替换 ChatbotRepository，避免 DB 依赖。
仅测试纯逻辑：截断策略、超时判定、状态机约束等。
"""
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta, timezone

from xianyu_hunter.modules.chatbot.context_manager import Context, ContextManager
from xianyu_hunter.infra.yaml_config import ChatbotConfig


@pytest.fixture
def mock_repo():
    """Mock 仓库：所有方法返回预设值，避免实际 DB 操作"""
    repo = MagicMock()
    repo.create_session.return_value = {
        "id": "test-session-id",
        "title": "新对话",
        "status": "active",
    }
    return repo


@pytest.fixture
def config():
    """默认配置：max_history_turns=10, session_timeout_min=30"""
    return ChatbotConfig()


@pytest.fixture
def manager(mock_repo, config):
    return ContextManager(repo=mock_repo, config=config)


class TestBuildHistoryMessages:
    """历史消息构建与截断"""

    def test_empty_messages_returns_empty(self, manager):
        """空消息列表返回空列表"""
        ctx = Context(session_id="s1", messages=[])
        assert manager.build_history_messages(ctx) == []

    def test_within_limit_kept_all(self, manager):
        """消息数 < max_msgs 时全部保留"""
        messages = []
        for i in range(5):
            messages.append({"role": "user", "content": f"问题{i}"})
            messages.append({"role": "assistant", "content": f"回答{i}"})
        ctx = Context(session_id="s1", messages=messages)
        result = manager.build_history_messages(ctx)
        # 10 条消息 = max_history_turns(10) * 2，正好等于 max_msgs，全部保留
        assert len(result) == 10

    def test_exceeds_limit_keeps_recent(self, manager):
        """消息数 > max_msgs 时仅保留最近 max_msgs 条

        截断策略：保留末尾的成对消息，丢弃最早的历史。
        """
        messages = []
        for i in range(15):
            messages.append({"role": "user", "content": f"问题{i}"})
            messages.append({"role": "assistant", "content": f"回答{i}"})
        ctx = Context(session_id="s1", messages=messages)
        result = manager.build_history_messages(ctx)
        # max_history_turns=10 → max_msgs=20，30 条消息仅保留末 20 条
        assert len(result) == 20
        # 验证保留的是最近的消息（i=5..14 的 user 消息）
        assert "问题5" in result[0]["content"]
        assert "问题14" in result[-2]["content"]

    def test_long_message_truncated(self, manager):
        """超长单条消息（>500字符）截断保留首尾各 250 字符"""
        long_content = "A" * 600
        ctx = Context(
            session_id="s1",
            messages=[{"role": "user", "content": long_content}],
        )
        result = manager.build_history_messages(ctx)
        # 截断后长度 = 250 + 3 ("...") + 250 = 503
        assert len(result[0]["content"]) == 503
        assert "..." in result[0]["content"]
        # 保留首尾内容
        assert result[0]["content"].startswith("A" * 250)
        assert result[0]["content"].endswith("A" * 250)

    def test_short_message_not_truncated(self, manager):
        """短消息（<=500字符）不截断"""
        content = "短消息"
        ctx = Context(
            session_id="s1",
            messages=[{"role": "user", "content": content}],
        )
        result = manager.build_history_messages(ctx)
        assert result[0]["content"] == content


class TestTruncateMessage:
    """_truncate_message 单元测试"""

    def test_short_text_unchanged(self, manager):
        assert manager._truncate_message("短文本") == "短文本"

    def test_exactly_500_chars_unchanged(self, manager):
        """恰好 500 字符不截断（边界条件）"""
        text = "X" * 500
        assert manager._truncate_message(text) == text

    def test_over_500_chars_truncated(self, manager):
        """501 字符触发截断"""
        text = "X" * 501
        result = manager._truncate_message(text)
        # 保留 250 + "..." + 250 = 503
        assert len(result) == 503
        assert "..." in result


class TestIsSessionTimedOut:
    """_is_session_timed_out 超时判定"""

    def test_no_last_active(self, manager):
        """无 last_active_at 字段视为未超时"""
        assert manager._is_session_timed_out({}) is False

    def test_invalid_datetime(self, manager):
        """无效时间字符串视为未超时（避免异常阻断流程）"""
        assert manager._is_session_timed_out({"last_active_at": "invalid"}) is False

    def test_recent_activity_not_timeout(self, manager):
        """最近活跃（5 分钟前）未超时（默认 30 分钟超时）"""
        recent = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        assert manager._is_session_timed_out({"last_active_at": recent}) is False

    def test_old_activity_timeout(self, manager):
        """60 分钟前活跃视为超时（默认 30 分钟超时）"""
        old = (datetime.now(timezone.utc) - timedelta(minutes=60)).isoformat()
        assert manager._is_session_timed_out({"last_active_at": old}) is True

    def test_naive_datetime_treated_as_utc(self, manager):
        """无时区信息的 datetime 视为 UTC（避免时区歧义）"""
        # 用 now(UTC).replace(tzinfo=None) 构造 naive UTC 时间
        # 避免 datetime.utcnow() 在 Python 3.12+ 的弃用警告
        naive_old = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=60)).isoformat()
        assert manager._is_session_timed_out({"last_active_at": naive_old}) is True


class TestGenerateTitle:
    """generate_title 标题生成（H7 修复后为同步方法）"""

    def test_short_message_as_title(self, manager, mock_repo):
        """短消息（<=20 字符）直接作为标题"""
        manager.generate_title("s1", "如何配置价格策略？")
        mock_repo.update_session_title.assert_called_once_with("s1", "如何配置价格策略？")

    def test_long_message_truncated(self, manager, mock_repo):
        """长消息（>20 字符）取前 20 字符 + "..." """
        # 25 字符：超过 20 字符触发截断
        long_msg = "这是一个非常长的用户消息需要被截断成标题对吧"
        manager.generate_title("s1", long_msg)
        expected = long_msg[:20] + "..."
        mock_repo.update_session_title.assert_called_once_with("s1", expected)

    def test_exactly_20_chars_not_truncated(self, manager, mock_repo):
        """恰好 20 字符不截断（边界条件）"""
        msg = "一二三四五六七八九十一二三四五六七八九十"  # 20 字符
        manager.generate_title("s1", msg)
        mock_repo.update_session_title.assert_called_once_with("s1", msg)


class TestCheckAndMarkTimeout:
    """check_and_mark_timeout 状态机约束"""

    def test_not_timeout_returns_false(self, manager, mock_repo):
        """未超时不做任何更新"""
        ctx = Context(session_id="s1", is_timeout=False, status="active")
        assert manager.check_and_mark_timeout(ctx) is False
        mock_repo.update_session_status.assert_not_called()

    def test_timeout_active_marks_ended(self, manager, mock_repo):
        """active 会话超时 → 标记 ended，并更新 Context.status"""
        ctx = Context(session_id="s1", is_timeout=True, status="active")
        assert manager.check_and_mark_timeout(ctx) is True
        mock_repo.update_session_status.assert_called_once_with("s1", "ended")
        assert ctx.status == "ended"

    def test_timeout_already_ended_idempotent(self, manager, mock_repo):
        """ended 会话超时 → 幂等返回 True，不重复更新"""
        ctx = Context(session_id="s1", is_timeout=True, status="ended")
        assert manager.check_and_mark_timeout(ctx) is True
        mock_repo.update_session_status.assert_not_called()

    def test_timeout_escalated_keeps_status(self, manager, mock_repo):
        """escalated 会话超时 → 返回 True 但保留 escalated 状态用于审计"""
        ctx = Context(session_id="s1", is_timeout=True, status="escalated")
        assert manager.check_and_mark_timeout(ctx) is True
        # 不调用 update_session_status，保留 escalated
        mock_repo.update_session_status.assert_not_called()
        assert ctx.status == "escalated"
