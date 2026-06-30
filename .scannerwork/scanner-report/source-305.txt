"""智能客服 API 降级测试

验证 container.chatbot=None 时（chromadb 未安装或 chatbot.enabled=false），
所有 chatbot API 返回 403 而非 500，避免 AttributeError 崩溃。

为什么重要：生产环境中 chromadb 为可选依赖，未安装时主系统应正常工作，
chatbot API 优雅降级返回明确错误信息。
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from xianyu_hunter.web.routes import api_chatbot, api_kb, api_chatbot_config


@pytest.fixture
def degraded_app():
    """构造 chatbot=None 的降级测试应用

    mock get_container 返回 chatbot=None 的 container，模拟 chromadb 未安装场景。
    三个 router 共享同一个 mock_container，确保所有 _get_chatbot_or_403() 走降级分支。
    """
    app = FastAPI()
    app.include_router(api_chatbot.router)
    app.include_router(api_kb.router)
    app.include_router(api_chatbot_config.router)

    # mock get_container 返回 chatbot=None 的 container
    mock_container = MagicMock()
    mock_container.chatbot = None
    mock_container.config = MagicMock()
    mock_container.config.chatbot = MagicMock()
    mock_container.config.chatbot.enabled = False

    with patch("xianyu_hunter.web.routes.api_chatbot.get_container", return_value=mock_container), \
         patch("xianyu_hunter.web.routes.api_kb.get_container", return_value=mock_container), \
         patch("xianyu_hunter.web.routes.api_chatbot_config.get_container", return_value=mock_container):
        yield app


class TestChatbotAPIDegraded:
    """chatbot=None 时 API 降级测试

    覆盖所有 21 个 chatbot 路由（api_chatbot 11 + api_kb 8 + api_chatbot_config 2），
    确保统一返回 403 + CHATBOT_DISABLED 错误码。
    """

    # ============== 会话管理 ==============
    def test_list_sessions_returns_403(self, degraded_app):
        """GET /sessions 应返回 403"""
        client = TestClient(degraded_app)
        resp = client.get("/api/chatbot/sessions")
        assert resp.status_code == 403
        data = resp.json()
        assert data["detail"]["code"] == "CHATBOT_DISABLED"

    def test_create_session_returns_403(self, degraded_app):
        """POST /sessions 应返回 403

        必须传 json={}：SessionCreateRequest 是 Pydantic 模型，
        FastAPI 默认要求 POST 请求带 body，否则返回 422 而非进入路由处理函数。
        """
        client = TestClient(degraded_app)
        resp = client.post("/api/chatbot/sessions", json={})
        assert resp.status_code == 403

    def test_chat_returns_403(self, degraded_app):
        """POST /chat 应返回 403

        必须传有效 body：session_id=None（不传）+ message 非空。
        session_id 若传非 UUID32 字符串会触发 422 校验失败，绕过 403 检查。
        """
        client = TestClient(degraded_app)
        resp = client.post(
            "/api/chatbot/chat",
            json={"message": "hello"},
        )
        assert resp.status_code == 403

    def test_get_session_returns_403(self, degraded_app):
        """GET /sessions/{id} 应返回 403"""
        client = TestClient(degraded_app)
        resp = client.get("/api/chatbot/sessions/abc123def456")
        assert resp.status_code == 403

    def test_delete_session_returns_403(self, degraded_app):
        """DELETE /sessions/{id} 应返回 403"""
        client = TestClient(degraded_app)
        resp = client.delete("/api/chatbot/sessions/abc123def456")
        assert resp.status_code == 403

    def test_end_session_returns_403(self, degraded_app):
        """POST /sessions/{id}/end 应返回 403"""
        client = TestClient(degraded_app)
        resp = client.post("/api/chatbot/sessions/abc123def456/end")
        assert resp.status_code == 403

    def test_update_session_title_returns_403(self, degraded_app):
        """PATCH /sessions/{id}/title 应返回 403

        必须传 json：SessionUpdateTitleRequest 是 Pydantic 模型，
        FastAPI 默认要求 PATCH 请求带 body，否则返回 422 而非进入路由处理函数。
        """
        client = TestClient(degraded_app)
        resp = client.patch(
            "/api/chatbot/sessions/abc123def456/title",
            json={"title": "新标题"},
        )
        assert resp.status_code == 403

    def test_list_messages_returns_403(self, degraded_app):
        """GET /sessions/{id}/messages 应返回 403"""
        client = TestClient(degraded_app)
        resp = client.get("/api/chatbot/sessions/abc123def456/messages")
        assert resp.status_code == 403

    # ============== 知识库管理 ==============
    def test_kb_status_returns_403(self, degraded_app):
        """GET /kb/status 应返回 403"""
        client = TestClient(degraded_app)
        resp = client.get("/api/chatbot/kb/status")
        assert resp.status_code == 403

    def test_kb_rebuild_returns_403(self, degraded_app):
        """POST /kb/rebuild 应返回 403"""
        client = TestClient(degraded_app)
        resp = client.post("/api/chatbot/kb/rebuild")
        assert resp.status_code == 403

    def test_kb_versions_returns_403(self, degraded_app):
        """GET /kb/versions 应返回 403"""
        client = TestClient(degraded_app)
        resp = client.get("/api/chatbot/kb/versions")
        assert resp.status_code == 403

    def test_kb_rollback_returns_403(self, degraded_app):
        """POST /kb/rollback/{version_id} 应返回 403"""
        client = TestClient(degraded_app)
        resp = client.post("/api/chatbot/kb/rollback/abc123")
        assert resp.status_code == 403

    # ============== FAQ 管理 ==============
    def test_faq_list_returns_403(self, degraded_app):
        """GET /faqs 应返回 403（注意复数形式 faqs，非 faq）"""
        client = TestClient(degraded_app)
        resp = client.get("/api/chatbot/faqs")
        assert resp.status_code == 403

    def test_faq_create_returns_403(self, degraded_app):
        """POST /faqs 应返回 403"""
        client = TestClient(degraded_app)
        resp = client.post(
            "/api/chatbot/faqs",
            json={"question": "Q", "answer": "A"},
        )
        assert resp.status_code == 403

    def test_faq_update_returns_403(self, degraded_app):
        """PUT /faqs/{id} 应返回 403"""
        client = TestClient(degraded_app)
        resp = client.put(
            "/api/chatbot/faqs/1",
            json={"question": "Q", "answer": "A"},
        )
        assert resp.status_code == 403

    def test_faq_delete_returns_403(self, degraded_app):
        """DELETE /faqs/{id} 应返回 403"""
        client = TestClient(degraded_app)
        resp = client.delete("/api/chatbot/faqs/1")
        assert resp.status_code == 403

    # ============== 反馈 ==============
    def test_feedback_returns_403(self, degraded_app):
        """POST /messages/{id}/feedback 应返回 403

        注意路径：反馈接口挂在 /messages/{message_id}/feedback 下，非 /feedback。
        """
        client = TestClient(degraded_app)
        resp = client.post(
            "/api/chatbot/messages/test-message-id/feedback",
            json={"rating": "positive"},
        )
        assert resp.status_code == 403

    def test_recent_feedback_returns_403(self, degraded_app):
        """GET /feedback/recent 应返回 403"""
        client = TestClient(degraded_app)
        resp = client.get("/api/chatbot/feedback/recent")
        assert resp.status_code == 403

    # ============== 配置与审计 ==============
    def test_config_get_returns_403(self, degraded_app):
        """GET /config 应返回 403"""
        client = TestClient(degraded_app)
        resp = client.get("/api/chatbot/config")
        assert resp.status_code == 403

    def test_config_update_returns_403(self, degraded_app):
        """PUT /config 应返回 403"""
        client = TestClient(degraded_app)
        resp = client.put(
            "/api/chatbot/config",
            json={"key": "enabled", "value": "true"},
        )
        assert resp.status_code == 403

    def test_audit_logs_returns_403(self, degraded_app):
        """GET /audit-logs 应返回 403"""
        client = TestClient(degraded_app)
        resp = client.get("/api/chatbot/audit-logs")
        assert resp.status_code == 403
