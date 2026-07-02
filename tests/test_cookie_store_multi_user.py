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
