from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xianyu_hunter.web.routes.api_evaluations import _ensure_official_collect_cookies
from xianyu_hunter.web.routes.api_task_links import _ensure_live_search_cookies
from xianyu_hunter.web.routes.unified_login import (
    _inject_cookies_to_worker_from_store,
    _verify_cookies,
)
from xianyu_hunter.web.routes import unified_login as unified_login_module
from xianyu_hunter.web.services.cookie_runtime_sync import inject_cookie_store_to_worker_browser
from xianyu_hunter.web.services import cookie_store as cs_module
from xianyu_hunter.web.services.cookie_store import get_cookie_store


@pytest.fixture(autouse=True)
def _isolate_cookie_json(tmp_path, monkeypatch):
    """隔离 Cookie JSON 文件到临时目录，避免污染开发环境

    为什么 autouse：本测试模块多处直接写 JSON 文件（_write_cookie_json 等），
    autouse 确保所有测试都重定向到 tmp_path，无需每个测试单独声明。
    """
    monkeypatch.setattr(
        "xianyu_hunter.web.services.cookie_store.Path",
        lambda *args: tmp_path / args[-1] if args else tmp_path,
    )


def _cookie_sample() -> list[dict]:
    return [
        {"name": "unb", "value": "2209384756290", "domain": ".goofish.com", "path": "/", "expires": -1},
        {"name": "cookie2", "value": "c8421f9e5b6d7a3b9c0e1f2d3a4b5c6d", "domain": ".goofish.com", "path": "/", "expires": -1},
        {"name": "sgcookie", "value": "E100zRxEj%2FbXi%2B%2FbxVSJT%2Fg%2FaDG6MgjhL", "domain": ".goofish.com", "path": "/", "expires": -1},
        {"name": "_m_h5_tk", "value": "c7b2c44645275604a525e6287fea2c3a_1782530783399", "domain": ".goofish.com", "path": "/", "expires": -1},
        {"name": "_m_h5_tk_enc", "value": "abc123enc456def789", "domain": ".goofish.com", "path": "/", "expires": -1},
    ]


def _old_identity_cookies() -> list[dict]:
    return [
        {"name": "unb", "value": "2209384756291", "domain": ".goofish.com", "path": "/", "expires": -1},
        {"name": "cookie2", "value": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "domain": ".goofish.com", "path": "/", "expires": -1},
        {"name": "sgcookie", "value": "E100oldCookieValueLongEnough", "domain": ".goofish.com", "path": "/", "expires": -1},
    ]


def _write_cookie_json(cookies: list[dict]) -> None:
    cs_module._cookie_json_path("default").parent.mkdir(parents=True, exist_ok=True)
    cs_module._cookie_json_path("default").write_text(
        json.dumps(
            {
                "exported_at": time.time(),
                "method": "test",
                "cookie_count": len(cookies),
                "cookies": cookies,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    get_cookie_store().invalidate_cache()


def _write_cookie_json_without_cache_invalidation(cookies: list[dict]) -> None:
    cs_module._cookie_json_path("default").parent.mkdir(parents=True, exist_ok=True)
    cs_module._cookie_json_path("default").write_text(
        json.dumps(
            {
                "exported_at": time.time(),
                "method": "test",
                "cookie_count": len(cookies),
                "cookies": cookies,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_unified_login_injects_latest_cookie_store_into_worker_browser() -> None:
    _write_cookie_json(_cookie_sample())

    browser = MagicMock()
    browser.add_cookies = AsyncMock(return_value=True)
    container = MagicMock()
    container.browser = browser

    with patch("xianyu_hunter.web.deps.get_container", return_value=container):
        ok = asyncio.run(_inject_cookies_to_worker_from_store())

    assert ok is True
    browser.add_cookies.assert_awaited_once()
    injected = browser.add_cookies.await_args.args[0]
    assert {c["name"] for c in injected} >= {"unb", "cookie2", "sgcookie"}


def test_official_collect_replaces_stale_worker_identity_cookies() -> None:
    fresh = _cookie_sample()
    _write_cookie_json(fresh)

    browser = MagicMock()
    browser.get_cookies = AsyncMock(side_effect=[_old_identity_cookies(), fresh])
    browser.add_cookies = AsyncMock(return_value=True)
    container = MagicMock()
    container.browser = browser

    asyncio.run(_ensure_official_collect_cookies(container))

    browser.add_cookies.assert_awaited_once()
    injected = browser.add_cookies.await_args.args[0]
    by_name = {c["name"]: c["value"] for c in injected}
    assert by_name["unb"] == "2209384756290"
    assert by_name["cookie2"] == "c8421f9e5b6d7a3b9c0e1f2d3a4b5c6d"


def test_live_search_replaces_stale_worker_identity_cookies() -> None:
    fresh = _cookie_sample()
    _write_cookie_json(fresh)

    browser = MagicMock()
    browser.get_cookies = AsyncMock(side_effect=[_old_identity_cookies(), fresh])
    browser.add_cookies = AsyncMock(return_value=True)
    collector = MagicMock()
    collector.should_reset_m5tk.return_value = False
    container = MagicMock()
    container.browser = browser
    container.collector = collector

    asyncio.run(_ensure_live_search_cookies(container))

    browser.add_cookies.assert_awaited_once()
    injected = browser.add_cookies.await_args.args[0]
    by_name = {c["name"]: c["value"] for c in injected}
    assert by_name["unb"] == "2209384756290"
    assert by_name["cookie2"] == "c8421f9e5b6d7a3b9c0e1f2d3a4b5c6d"
    collector.force_refresh_m5tk_next.assert_called_once()


def test_runtime_cookie_sync_invalidates_cache_and_injects_worker() -> None:
    store = get_cookie_store()
    # 模拟缓存命中但数据为空：使 _read_json 直接返回缓存的空数据，
    # 验证 runtime_sync 会失效缓存并重新读取磁盘上的新 JSON
    store._cache = {"default": ({"cookies": []}, time.time())}
    _write_cookie_json_without_cache_invalidation(_cookie_sample())

    browser = MagicMock()
    browser.add_cookies = AsyncMock(return_value=True)
    collector = MagicMock()
    container = MagicMock()
    container.browser = browser
    container.collector = collector

    with patch("xianyu_hunter.web.deps.get_container", return_value=container):
        ok = asyncio.run(inject_cookie_store_to_worker_browser("test"))

    assert ok is True
    browser.add_cookies.assert_awaited_once()
    injected = browser.add_cookies.await_args.args[0]
    assert {c["name"] for c in injected} >= {"unb", "cookie2", "sgcookie"}
    collector.force_refresh_m5tk_next.assert_called_once()


def test_verify_cookies_invalidates_stale_json_cache() -> None:
    store = get_cookie_store()
    # 模拟缓存命中但数据为空：使 _read_json 直接返回缓存的空数据，
    # 验证 _verify_cookies 会失效缓存并读取磁盘上的新 JSON
    store._cache = {"default": ({"cookies": []}, time.time())}
    _write_cookie_json_without_cache_invalidation(_cookie_sample())

    assert _verify_cookies(max_retries=1) is True


def test_login_status_reads_live_browser_login_status_file(tmp_path) -> None:
    status_file = tmp_path / "browser_login.json"
    status_file.write_text(
        json.dumps(
            {
                "status": "opening",
                "message": "正在打开闲鱼...",
                "elapsed": 12.5,
                "timings": {"launch_context_sec": 9.2},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class RunningProc:
        def poll(self):
            return None

    old_session = dict(unified_login_module._session)
    with unified_login_module._session_lock:
        unified_login_module._session = {
            "method": "browser",
            "status": "running",
            "message": "正在启动浏览器窗口...",
            "status_file": str(status_file),
            "proc": RunningProc(),
            "pid": 123,
            "qr_png_b64": None,
            "started_at": time.time() - 13,
            "cookies_injected": False,
        }

    try:
        result = asyncio.run(unified_login_module.login_status())
    finally:
        with unified_login_module._session_lock:
            unified_login_module._session = old_session

    assert result["status"] == "running"
    assert result["phase"] == "opening"
    assert result["message"] == "正在打开闲鱼..."
    assert result["child_elapsed"] == 12.5
    assert result["timings"]["launch_context_sec"] == 9.2
