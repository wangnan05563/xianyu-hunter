# tests/test_auth_middleware_mu2.py
"""MU2 认证中间件与 auth_helpers 多用户测试"""
from http.cookies import SimpleCookie

from xianyu_hunter.config import get_settings
from xianyu_hunter.web.routes.auth_helpers import make_auth_response


def _get_cookie_value(resp, key: str) -> str | None:
    """从 JSONResponse 的 set-cookie header 解析指定 cookie 的值

    为什么不用 resp.cookies：JSONResponse（starlette.Response）没有公开
    cookies 属性，set_cookie 内部把 cookie 拼进 set-cookie header。
    用 SimpleCookie 解析 header 是最稳健的验证方式。
    """
    cookie_header = resp.headers.get("set-cookie", "")
    jar = SimpleCookie()
    jar.load(cookie_header)
    morsel = jar.get(key)
    return morsel.value if morsel else None


def test_make_auth_response_with_session_token():
    """传入 session_token 时写入 session_token 而非 web_token"""
    resp = make_auth_response({"ok": True}, session_token="abc123session")
    assert "xh_token" in resp.headers.get("set-cookie", "")
    # xh_token 的值应该是 session_token
    assert _get_cookie_value(resp, "xh_token") == "abc123session"


def test_make_auth_response_without_session_token_fallback():
    """不传 session_token 时回退到 web_token（向后兼容）"""
    resp = make_auth_response({"ok": True})
    # 仍然写入 web_token
    assert _get_cookie_value(resp, "xh_token") == get_settings().web_token


# === Task 3: 三路校验测试 ===
import asyncio
from unittest.mock import MagicMock, patch
from starlette.testclient import TestClient
from fastapi import FastAPI, Request


def _build_app_with_middleware():
    """构建带 BearerAuthMiddleware 的测试 app"""
    app = FastAPI()
    from xianyu_hunter.web.middleware.auth import setup_auth_middleware
    setup_auth_middleware(app)

    @app.get("/api/whoami")
    def whoami(request: Request):
        # 返回 request.state.user_id（由中间件注入）
        uid = getattr(request.state, "user_id", "not_set")
        return {"user_id": uid}

    return app


def test_web_token_passes_through():
    """WEB_TOKEN 管理令牌直通，user_id 设为 default"""
    from xianyu_hunter.config import get_settings
    app = _build_app_with_middleware()
    client = TestClient(app)
    token = get_settings().web_token
    resp = client.get("/api/whoami", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["user_id"] == "default"


def test_session_token_injects_user_id():
    """有效 session_token 注入对应 user_id"""
    app = _build_app_with_middleware()
    client = TestClient(app)

    with patch("xianyu_hunter.web.services.user_manager.get_user_manager") as mock:
        mgr = MagicMock()
        mgr.verify_session.return_value = "user_abc"
        mock.return_value = mgr

        resp = client.get("/api/whoami", headers={"Authorization": "Bearer valid_session_token"})
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "user_abc"
        mgr.verify_session.assert_called_once_with("valid_session_token")


def test_invalid_token_returns_401():
    """无效 token 返回 401"""
    app = _build_app_with_middleware()
    client = TestClient(app)

    with patch("xianyu_hunter.web.services.user_manager.get_user_manager") as mock:
        mgr = MagicMock()
        mgr.verify_session.return_value = None
        mock.return_value = mgr

        resp = client.get("/api/whoami", headers={"Authorization": "Bearer invalid"})
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Unauthorized"


def test_public_path_no_auth_required():
    """公开路径不需要认证"""
    app = _build_app_with_middleware()
    client = TestClient(app)
    resp = client.get("/healthz")
    # /healthz 不在路由中，但中间件放行后会 404（而非 401）
    assert resp.status_code != 401


def test_make_auth_response_with_empty_session_token_falls_back():
    """空字符串 session_token 视为未传，回退到 web_token"""
    resp = make_auth_response({"ok": True}, session_token="")
    # 复用文件顶部的 _get_cookie_value 解析 set-cookie header
    assert _get_cookie_value(resp, "xh_token") == get_settings().web_token
