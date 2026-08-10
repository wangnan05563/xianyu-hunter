# tests/test_cookie_samesite.py
"""验证认证 cookie 的 Secure / SameSite 配置随请求协议自适应

- HTTPS：SameSite=None;Secure（保留移动端跨域携带能力）
- HTTP ：SameSite=Lax;不加 Secure（否则浏览器丢弃 cookie，导致纯 HTTP 访问下
        登录 / 切换账号后整页刷新，导航栏 / 反爬页误读 cookies_default.json
        而报 "Cookie 异常" / 身份层 / 会话层 / 追踪层 "缺失"，见 bug #2/#3）
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    from xianyu_hunter.web.app import create_app
    return create_app()


class _FakeReq:
    """最小请求桩：仅需 url.scheme 与 headers（供 _resolve_secure_policy 使用）"""

    def __init__(self, scheme: str, fwd: str | None = None) -> None:
        self.url = type("U", (), {"scheme": scheme})()
        self.headers: dict = {}
        if fwd:
            self.headers["x-forwarded-proto"] = fwd


def test_policy_https_is_secure_none():
    from xianyu_hunter.web.routes.auth_helpers import _resolve_secure_policy
    assert _resolve_secure_policy(_FakeReq("https")) == (True, "none")


def test_policy_http_is_lax_non_secure():
    from xianyu_hunter.web.routes.auth_helpers import _resolve_secure_policy
    assert _resolve_secure_policy(_FakeReq("http")) == (False, "lax")


def test_policy_x_forwarded_proto_overrides():
    from xianyu_hunter.web.routes.auth_helpers import _resolve_secure_policy
    # 反向代理终止 TLS：上游 scheme 为 http，但真实协议在 X-Forwarded-Proto
    assert _resolve_secure_policy(_FakeReq("http", "https")) == (True, "none")


def test_policy_no_request_defaults_https():
    from xianyu_hunter.web.routes.auth_helpers import _resolve_secure_policy
    # 无 request 且无中间件上下文时，默认 https（保持旧行为，避免意外降级）
    assert _resolve_secure_policy(None) == (True, "none")


def test_make_auth_response_http_non_secure_lax():
    from xianyu_hunter.web.routes.auth_helpers import make_auth_response
    resp = make_auth_response({"ok": True}, request=_FakeReq("http"))
    sc = resp.headers.get("set-cookie", "").lower()
    assert "secure" not in sc
    assert "samesite=lax" in sc


def test_make_auth_response_https_secure_none():
    from xianyu_hunter.web.routes.auth_helpers import make_auth_response
    resp = make_auth_response({"ok": True}, request=_FakeReq("https"))
    sc = resp.headers.get("set-cookie", "").lower()
    assert "secure" in sc
    assert "samesite=none" in sc


def _verify_set_cookie(client: TestClient, token: str) -> str:
    resp = client.post(f"/api/auth/verify?token={token}")
    assert resp.status_code == 200
    return resp.headers.get("set-cookie", "").lower()


def test_verify_token_https_sets_samesite_none_secure(app):
    """HTTPS 下应 SameSite=None;Secure 以支持移动端跨域访问"""
    from xianyu_hunter.config import get_settings
    token = get_settings().web_token
    client = TestClient(app, base_url="https://test")
    sc = _verify_set_cookie(client, token)
    assert "samesite=none" in sc
    assert "secure" in sc


def test_verify_token_http_sets_lax_without_secure(app):
    """HTTP（IP 访问）下应 SameSite=Lax 且不加 Secure，否则浏览器丢弃 cookie"""
    from xianyu_hunter.config import get_settings
    token = get_settings().web_token
    client = TestClient(app)  # 默认 http scheme
    sc = _verify_set_cookie(client, token)
    assert "samesite=lax" in sc
    assert "secure" not in sc
