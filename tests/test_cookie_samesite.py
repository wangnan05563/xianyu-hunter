# tests/test_cookie_samesite.py
"""验证认证 cookie 在跨域场景下的 SameSite 配置"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from xianyu_hunter.web.app import create_app
    return TestClient(create_app())


def test_verify_token_sets_samesite_none_for_cross_origin(client):
    """POST /api/auth/verify 应设置 SameSite=None;Secure 以支持移动端跨域访问"""
    from xianyu_hunter.config import get_settings
    token = get_settings().web_token
    resp = client.post(f"/api/auth/verify?token={token}")
    assert resp.status_code == 200
    set_cookie = resp.headers.get("set-cookie", "").lower()
    assert "samesite=none" in set_cookie
    assert "secure" in set_cookie  # 验证 Secure 属性
