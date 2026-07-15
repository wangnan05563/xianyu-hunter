# tests/test_cookie_store_multi_user.py
"""CookieStore 多用户隔离测试"""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from xianyu_hunter.web.services.cookie_store import CookieStore


@pytest.fixture
def store(tmp_path, monkeypatch):
    """创建使用临时目录的 CookieStore 实例"""
    monkeypatch.setattr("xianyu_hunter.web.services.cookie_store.Path", lambda *args: tmp_path / args[-1] if args else tmp_path)
    s = CookieStore()
    # 重置缓存
    s._cache = {}
    return s


def test_export_cookies_writes_user_specific_file(store, tmp_path):
    """export_cookies 按 user_id 写入独立文件"""
    cookies = [{"name": "unb", "value": "12345678", "domain": ".goofish.com"}]
    store.export_cookies(cookies, method="browser", user_id="user_a")
    store.export_cookies(cookies, method="browser", user_id="user_b")

    # 两个用户各有一个独立的 JSON 文件
    assert (tmp_path / "cookies_user_a.json").exists()
    assert (tmp_path / "cookies_user_b.json").exists()


def test_has_valid_cookies_isolated_per_user(store, tmp_path):
    """不同用户的 Cookie 互不影响"""
    cookies_a = [{"name": "unb", "value": "12345678", "domain": ".goofish.com"}]
    store.export_cookies(cookies_a, method="browser", user_id="user_a")

    # user_a 有 Cookie
    assert store.has_valid_cookies(user_id="user_a") is True
    # user_b 没有 Cookie
    assert store.has_valid_cookies(user_id="user_b") is False


def test_cache_is_per_user(store, tmp_path):
    """缓存按 user_id 分桶，互不污染"""
    cookies_a = [{"name": "unb", "value": "12345678", "domain": ".goofish.com"}]
    store.export_cookies(cookies_a, method="browser", user_id="user_a")

    # user_a 读取会缓存
    store.has_valid_cookies(user_id="user_a")
    assert "user_a" in store._cache

    # user_b 缓存应为空
    assert "user_b" not in store._cache


def test_default_user_id_backward_compat(store, tmp_path):
    """不传 user_id 时使用 default，向后兼容"""
    cookies = [{"name": "unb", "value": "12345678", "domain": ".goofish.com"}]
    store.export_cookies(cookies, method="browser")

    assert (tmp_path / "cookies_default.json").exists()
    assert store.has_valid_cookies() is True


# ============== validate_cookies_with_expiry (Fix 1) ==============
# 验证 _m_h5_tk 使用内嵌 timestamp 判断过期，而非 expires 字段

def _make_m5tk_value(age_sec: float) -> str:
    """构造 _m_h5_tk 值：32位hex + _ + 13位毫秒时间戳

    Args:
        age_sec: token 年龄（秒），0 表示当前时间，>0 表示已过去的时间
    """
    import time as _time
    ts_ms = int((_time.time() - age_sec) * 1000)
    return f"a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4_{ts_ms:013d}"


def test_validate_m5tk_not_expired_returns_ok(store):
    """_m_h5_tk 内嵌 timestamp 未过期时应返回 (True, 'ok')

    覆盖 Fix 1：expires=-1（session cookie）但内嵌 timestamp 有效 → 不应误报过期。
    """
    cookies = [
        {"name": "_m_h5_tk", "value": _make_m5tk_value(age_sec=60), "domain": ".taobao.com", "expires": -1},
        {"name": "unb", "value": "12345678", "domain": ".taobao.com", "expires": -1},
    ]
    store.export_cookies(cookies, method="browser")

    is_valid, reason = store.validate_cookies_with_expiry()
    assert is_valid is True
    assert reason == "ok"


def test_validate_m5tk_expired_returns_false(store):
    """_m_h5_tk 内嵌 timestamp 已过期（>1200s）时应返回 (False, 'cookie_expired:_m_h5_tk')

    覆盖 Fix 1：即使 expires=-1（session cookie），内嵌 timestamp 过期也应判失效。
    """
    cookies = [
        {"name": "_m_h5_tk", "value": _make_m5tk_value(age_sec=1300), "domain": ".taobao.com", "expires": -1},
        {"name": "unb", "value": "12345678", "domain": ".taobao.com", "expires": -1},
    ]
    store.export_cookies(cookies, method="browser")

    is_valid, reason = store.validate_cookies_with_expiry()
    assert is_valid is False
    assert reason == "cookie_expired:_m_h5_tk"


def test_validate_m5tk_expires_field_ignored_when_timestamp_valid(store):
    """_m_h5_tk expires 字段已过期但内嵌 timestamp 仍有效时不应误报

    核心验证 Fix 1：健康检查不再依赖 expires 字段判断 _m_h5_tk，
    避免 expires 已过期但 token 实际有效时的误报。
    """
    import time as _time
    # expires 设为过去时间（已过期），但 timestamp 是当前时间（有效）
    cookies = [
        {"name": "_m_h5_tk", "value": _make_m5tk_value(age_sec=10), "domain": ".taobao.com",
         "expires": _time.time() - 3600},  # expires 1 小时前已过期
        {"name": "unb", "value": "12345678", "domain": ".taobao.com", "expires": -1},
    ]
    store.export_cookies(cookies, method="browser")

    is_valid, reason = store.validate_cookies_with_expiry()
    assert is_valid is True
    assert reason == "ok"


def test_validate_other_cookie_expired_by_expires_field(store):
    """非 _m_h5_tk 的关键 cookie 仍用 expires 字段判断过期

    验证 Fix 1 只改了 _m_h5_tk 的判断逻辑，其他 cookie 仍用 expires 字段。
    """
    import time as _time
    cookies = [
        {"name": "_m_h5_tk", "value": _make_m5tk_value(age_sec=60), "domain": ".taobao.com", "expires": -1},
        {"name": "unb", "value": "12345678", "domain": ".taobao.com",
         "expires": _time.time() - 3600},  # unb expires 1 小时前已过期
    ]
    store.export_cookies(cookies, method="browser")

    is_valid, reason = store.validate_cookies_with_expiry()
    assert is_valid is False
    assert reason == "cookie_expired:unb"
