"""回归测试：identity 层 unb cookie 的过期 expires 不再被误判为 cookie_expired:unb

背景：扫码登录/本地持久化导出时，unb（纯用户唯一ID标识，identity 层 ttl=session）
的 expires 字段会被写成过去的绝对时间戳（实测 cookies_default.json /
last_login_cookies.json 中 unb expires 为过去时间），而实际登录态有效。
修复前 _find_expired_cookie / _check_key_cookies_expiry / _check_single_cookie_expiry
三个判定路径会据此误报 cookie_expired:unb，导致扫码登录后右上角悬浮 Cookie 状态
显示"未登录/原因 cookie_expired:unb"。

真正登录态由 session 层 cookie2/_m_h5_tk 判定，unb 只做存在性检查。
本测试锁定：unb 的 expires 为过去时间戳时不应被当作过期依据（与 _m_h5_tk_enc
跳过不可靠 expires 字段的既有修复一致）。
"""
from __future__ import annotations

import time

from xianyu_hunter.web.services.cookie_status import _find_expired_cookie
from xianyu_hunter.web.services.cookie_store import (
    _GOOFISH_KEY_COOKIES,
    CookieStore,
)
from xianyu_hunter.web.routes.auth_query import _check_single_cookie_expiry


def _cookie_with_expired_expires() -> dict:
    """unb cookie：expires 为过去的绝对时间戳（模拟扫码登录导出场景）"""
    return {"name": "unb", "value": "135379349", "expires": time.time() - 3600}


def test_find_expired_cookie_skips_unb_expired_expires():
    """_find_expired_cookie 不应因 unb 过期 expires 返回 cookie_expired:unb"""
    identity = {"unb", "cookie2", "sgcookie"}
    session = {"_m_h5_tk", "_m_h5_tk_enc"}
    cookies = [
        _cookie_with_expired_expires(),
        {"name": "cookie2", "value": "x", "expires": -1},
        {"name": "_m_h5_tk", "value": "deadbeef_123", "expires": -1},
    ]
    assert _find_expired_cookie(cookies, identity, session) is None


def test_check_key_cookies_expiry_skips_unb():
    """CookieStore 判定不应因 unb 过去 expires 误报 cookie_expired:unb"""
    store = CookieStore()
    # _GOOFISH_KEY_COOKIES 应包含 unb（确保测试有判定意义）
    assert "unb" in _GOOFISH_KEY_COOKIES
    ok, reason = store._check_key_cookies_expiry(
        cookies_list=[_cookie_with_expired_expires()],
        is_m5tk_expired=lambda _v: False,
    )
    assert ok is True
    assert reason == "ok"


def test_auth_query_check_single_cookie_expiry_skips_unb():
    """auth_query 单 cookie 判定不应因 unb 过去 expires 误报"""
    assert _check_single_cookie_expiry(_cookie_with_expired_expires(), time.time()) is None


def test_non_unb_key_cookie_still_detected_expired():
    """降噪验证：其他 key cookie（如 cookie2）过期仍应被识别，避免修复过宽"""
    identity = {"unb", "cookie2", "sgcookie"}
    session = {"_m_h5_tk", "_m_h5_tk_enc"}
    cookies = [
        {"name": "cookie2", "value": "x", "expires": time.time() - 3600},
        {"name": "unb", "value": "135379349", "expires": time.time() - 3600},
    ]
    assert _find_expired_cookie(cookies, identity, session) == "cookie2"