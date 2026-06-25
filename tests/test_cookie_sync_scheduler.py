"""cookie_sync_scheduler 模块单元测试"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from xianyu_hunter.modules.cookie_sync_scheduler import CookieSyncScheduler


def _make_cookie_store(valid: bool, expiring: bool = False) -> MagicMock:
    """创建 mock cookie_store"""
    store = MagicMock()
    store.has_valid_cookies.return_value = valid
    if expiring:
        store.get_cookie_expiry.return_value = time.time() + 300  # 5 分钟后过期
    else:
        store.get_cookie_expiry.return_value = time.time() + 3600  # 1 小时后过期
    return store


def test_sync_job_cookies_valid():
    """Cookie 有效且未即将过期时不触发同步"""
    store = _make_cookie_store(valid=True, expiring=False)
    scheduler = CookieSyncScheduler(store, auto_sync_interval=30, expiry_threshold=10)

    with patch("xianyu_hunter.web.routes.browser_import._do_import_from_browser") as mock_import:
        scheduler._run_sync_job()
    mock_import.assert_not_called()


def test_sync_job_cookies_expiring():
    """Cookie 即将过期时触发同步"""
    store = _make_cookie_store(valid=True, expiring=True)
    scheduler = CookieSyncScheduler(store, auto_sync_interval=30, expiry_threshold=10)

    with patch("xianyu_hunter.web.routes.browser_import._do_import_from_browser") as mock_import:
        mock_import.return_value = {"ok": True, "imported_count": 5}
        scheduler._run_sync_job()
    mock_import.assert_called_once()


def test_sync_job_no_cookies():
    """无 Cookie 时触发同步"""
    store = _make_cookie_store(valid=False)
    scheduler = CookieSyncScheduler(store, auto_sync_interval=30, expiry_threshold=10)

    with patch("xianyu_hunter.web.routes.browser_import._do_import_from_browser") as mock_import:
        mock_import.return_value = {"ok": True, "imported_count": 5}
        scheduler._run_sync_job()
    mock_import.assert_called_once()


def test_sync_job_fallback_to_cdp():
    """离线导入失败时降级到 CDP"""
    store = _make_cookie_store(valid=False)
    scheduler = CookieSyncScheduler(store, auto_sync_interval=30, expiry_threshold=10)

    with patch("xianyu_hunter.web.routes.browser_import._do_import_from_browser") as mock_offline, \
         patch("xianyu_hunter.web.routes.browser_import_cdp._check_cdp_reachable") as mock_cdp_check, \
         patch("xianyu_hunter.web.routes.browser_import_cdp._collect_cookies_via_cdp") as mock_cdp_collect:
        mock_offline.return_value = {"ok": False, "has_v20": True}
        mock_cdp_check.return_value = True
        mock_cdp_collect.return_value = [{"name": "_m_h5_tk", "value": "abc", "domain": ".goofish.com"}]
        scheduler._run_sync_job()

    mock_offline.assert_called_once()
    mock_cdp_check.assert_called_once()


def test_sync_job_all_failed_backoff():
    """全部失败时触发退避（连续失败计数增加）"""
    store = _make_cookie_store(valid=False)
    scheduler = CookieSyncScheduler(store, auto_sync_interval=30, expiry_threshold=10)

    with patch("xianyu_hunter.web.routes.browser_import._do_import_from_browser") as mock_offline, \
         patch("xianyu_hunter.web.routes.browser_import_cdp._check_cdp_reachable") as mock_cdp_check:
        mock_offline.return_value = {"ok": False}
        mock_cdp_check.return_value = False
        # 模拟连续 3 次失败
        for _ in range(3):
            scheduler._run_sync_job()

    assert scheduler._consecutive_failures == 3
    assert scheduler._current_interval > 30  # 间隔已翻倍
