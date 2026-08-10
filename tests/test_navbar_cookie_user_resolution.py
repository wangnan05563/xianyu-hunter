# tests/test_navbar_cookie_user_resolution.py
"""回归测试：IP(HTTP) 登录后导航栏 Cookie 状态误报为"异常/缺失"

根因：
    xh_token 以 ``Secure; SameSite=None`` 写入。HTTP/IP 场景下浏览器会丢弃
    Secure cookie，导致 ``request.cookies.get("xh_token")`` 为空。旧实现
    ``_resolve_current_user_id`` 只认 cookie，落回 "default"，导航栏读取
    ``cookies_default.json``（IP 路径不可靠）→ 误报 "Cookie 异常"，身份层/会话层/
    追踪层显示"缺失"。域名(HTTPS) 场景 Secure cookie 被保留，故无此问题。

修复：
    cookie 缺失时回退到 ``Authorization: Bearer`` 头（前端始终通过 localStorage
    在 header 携带会话 token），与 BearerAuthMiddleware 的 token 提取方式一致，
    正确解析出真实 user_id 并读取 ``cookies_{user_id}.json``。

本测试锁定两条关键路径：
    1. 单元层：_resolve_current_user_id 在「无 cookie + Bearer 头」时返回真实 user_id
    2. 集成层：/api/auth/cookie/health（PUBLIC 端点）在 HTTP/IP 场景解析真实 user_id
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from xianyu_hunter.web.app import app
from xianyu_hunter.web.routes import auth_query


client = TestClient(app)

# 模拟 IP 登录产生的会话 token 与对应真实 user_id
_IP_SESSION_TOKEN = "ip_login_session_token"
_REAL_USER_ID = "135379349"


@pytest.fixture
def patch_verify_session(monkeypatch):
    """把 verify_session 打桩为：仅识别 _IP_SESSION_TOKEN → _REAL_USER_ID"""
    def fake_verify(self, token: str):  # noqa: ANN001
        if token == _IP_SESSION_TOKEN:
            return _REAL_USER_ID
        return None

    monkeypatch.setattr(
        "xianyu_hunter.web.services.user_manager.UserManager.verify_session",
        fake_verify,
    )
    yield


class TestResolveCurrentUserIdBearerFallback:
    """单元层：_resolve_current_user_id 的 token 来源回退逻辑"""

    def test_bearer_fallback_returns_real_user(self, patch_verify_session):
        """无 xh_token cookie 但带 Bearer 头 → 返回真实 user_id（IP 场景）"""
        from starlette.requests import Request

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/auth/cookie/health",
            "headers": [(b"authorization", f"Bearer {_IP_SESSION_TOKEN}".encode())],
            "query_string": b"",
            "scheme": "http",
        }
        req = Request(scope)
        assert req.cookies.get("xh_token") is None  # 确认模拟的是无 cookie 场景

        result = auth_query._resolve_current_user_id(req)
        assert result == _REAL_USER_ID, (
            f"IP 登录场景应解析真实 user_id，实际得到 {result!r}"
        )

    def test_no_cookie_no_header_returns_none(self, patch_verify_session):
        """既无 cookie 也无 Bearer 头 → 返回 None（匿名，落回 default）"""
        from starlette.requests import Request

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/auth/cookie/health",
            "headers": [],
            "query_string": b"",
            "scheme": "http",
        }
        req = Request(scope)
        assert auth_query._resolve_current_user_id(req) is None

    def test_cookie_takes_precedence_over_bearer(self, patch_verify_session):
        """cookie 与 Bearer 同时存在时，仍以 cookie 为准（HTTPS 场景优先路径）"""
        from starlette.requests import Request

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/auth/cookie/health",
            "headers": [
                (b"cookie", f"xh_token={_IP_SESSION_TOKEN}".encode()),
                (b"authorization", f"Bearer {_IP_SESSION_TOKEN}".encode()),
            ],
            "query_string": b"",
            "scheme": "https",
        }
        req = Request(scope)
        # cookie 解析出的也映射为同一 _REAL_USER_ID，验证回退逻辑不冲突
        assert auth_query._resolve_current_user_id(req) == _REAL_USER_ID


class TestNavbarCookieHealthUserResolution:
    """集成层：/api/auth/cookie/health 在 HTTP/IP 场景解析真实 user_id"""

    def test_http_ip_login_resolves_real_user_not_default(self, monkeypatch, patch_verify_session):
        """不传 xh_token cookie（模拟浏览器丢弃 Secure cookie），仅带 Bearer 头，
        端点应将真实 user_id 透传给 evaluate_cookie_status，而非 "default"。"""
        captured: dict = {}

        async def spy_evaluate(user_id=None):  # noqa: ANN001
            captured["user_id"] = user_id or "default"

            class _Stub:
                def as_navbar_payload(self):
                    return {
                        "is_valid": True,
                        "reason": "ok",
                        "user_id": captured["user_id"],
                        "layers": {"identity": "ready", "session": "ready", "tracking": "ready"},
                    }

            return _Stub()

        monkeypatch.setattr(
            "xianyu_hunter.web.services.cookie_status.evaluate_cookie_status",
            spy_evaluate,
        )

        resp = client.get(
            "/api/auth/cookie/health",
            headers={"Authorization": f"Bearer {_IP_SESSION_TOKEN}"},
            # 故意不传 cookies=... ，复现 HTTP/IP 下浏览器丢弃 Secure cookie
        )
        assert resp.status_code == 200, resp.text
        assert captured["user_id"] == _REAL_USER_ID, (
            f"导航栏健康检查应解析真实 user_id，实际得到 {captured.get('user_id')!r}"
        )
        body = resp.json()
        assert body["user_id"] == _REAL_USER_ID
        # 状态一致：真实用户维度 cookie 有效，导航栏不应再误报异常
        assert body["is_valid"] is True

    def test_explicit_invalid_cookie_not_overridden_by_bearer(self, monkeypatch, patch_verify_session):
        """安全优先级：请求显式携带一个 verify 失败的 xh_token cookie 时，
        即使同时带有效 Bearer 头，也不应静默回退到 Bearer（避免伪造 cookie 被覆盖）。
        此时 verify_session 返回 None → 匿名（落回 default）。

        注：真实浏览器在 HTTP/IP 下会直接丢弃 Secure cookie，不会随请求发出，
        故该场景是安全语义的防御性验证，而非线上的典型路径。
        """
        captured: dict = {}

        async def spy_evaluate(user_id=None):  # noqa: ANN001
            captured["user_id"] = user_id or "default"

            class _Stub:
                def as_navbar_payload(self):
                    return {"is_valid": True, "reason": "ok", "user_id": captured["user_id"]}

            return _Stub()

        monkeypatch.setattr(
            "xianyu_hunter.web.services.cookie_status.evaluate_cookie_status",
            spy_evaluate,
        )

        resp = client.get(
            "/api/auth/cookie/health",
            headers={"Authorization": f"Bearer {_IP_SESSION_TOKEN}"},
            cookies={"xh_token": "stale_or_invalid_cookie"},
        )
        assert resp.status_code == 200, resp.text
        # 显式携带无效 cookie → 匿名（default），不回退 Bearer
        assert captured["user_id"] == "default"
