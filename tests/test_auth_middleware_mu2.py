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
