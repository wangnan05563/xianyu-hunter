"""实时搜索登录 Cookie 完整性检查测试"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from xianyu_hunter.web.routes.api_task_links import (
    _get_browser_cookies_by_name,
    _inject_cookies_from_json,
    _missing_live_search_cookie_names,
)


def test_live_search_cookie_check_passes_with_required_identity_cookies() -> None:
    names = {"cookie2", "sgcookie", "unb", "_m_h5_tk"}

    assert _missing_live_search_cookie_names(names) == []


def test_live_search_cookie_check_reports_missing_identity_cookies() -> None:
    names = {"cookie2", "_m_h5_tk", "_tb_token_"}

    assert _missing_live_search_cookie_names(names) == ["sgcookie", "unb"]


# ============== Fix A: ensure_alive 前置检查 ==============


class TestGetBrowserCookiesEnsureAlive:
    """_get_browser_cookies_by_name 调用 ensure_alive 测试"""

    @pytest.mark.asyncio
    async def test_calls_ensure_alive_before_get_cookies(self):
        """get_cookies 前应先调用 ensure_alive"""
        container = MagicMock()
        container.browser = MagicMock()
        container.browser.ensure_alive = AsyncMock(return_value=True)
        container.browser.get_cookies = AsyncMock(return_value=[
            {"name": "unb", "value": "12345678"},
        ])

        result = await _get_browser_cookies_by_name(container)

        container.browser.ensure_alive.assert_awaited_once()
        container.browser.get_cookies.assert_awaited_once()
        assert "unb" in result

    @pytest.mark.asyncio
    async def test_returns_empty_when_ensure_alive_fails(self):
        """ensure_alive 失败时应返回空字典，不调用 get_cookies"""
        container = MagicMock()
        container.browser = MagicMock()
        container.browser.ensure_alive = AsyncMock(return_value=False)
        container.browser.get_cookies = AsyncMock()

        result = await _get_browser_cookies_by_name(container)

        assert result == {}
        container.browser.ensure_alive.assert_awaited_once()
        container.browser.get_cookies.assert_not_called()


class TestInjectCookiesEnsureAlive:
    """_inject_cookies_from_json 调用 ensure_alive 测试"""

    @pytest.mark.asyncio
    async def test_calls_ensure_alive_before_add_cookies(self):
        """add_cookies 前应先调用 ensure_alive"""
        container = MagicMock()
        container.browser = MagicMock()
        container.browser.ensure_alive = AsyncMock(return_value=True)
        container.browser.add_cookies = AsyncMock(return_value=True)

        result = await _inject_cookies_from_json(
            container, [{"name": "unb", "value": "12345678"}],
            missing=["unb"], expired=[], stale=[],
        )

        assert result is True
        container.browser.ensure_alive.assert_awaited_once()
        container.browser.add_cookies.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_false_when_ensure_alive_fails(self):
        """ensure_alive 失败时应返回 False，不调用 add_cookies"""
        container = MagicMock()
        container.browser = MagicMock()
        container.browser.ensure_alive = AsyncMock(return_value=False)
        container.browser.add_cookies = AsyncMock()

        result = await _inject_cookies_from_json(
            container, [{"name": "unb", "value": "12345678"}],
            missing=["unb"], expired=[], stale=[],
        )

        assert result is False
        container.browser.ensure_alive.assert_awaited_once()
        container.browser.add_cookies.assert_not_called()


# ============== Fix C: 二次 cookie 完整性检查 ==============


class TestEnsureLiveSearchCookiesBrowserUnavailable:
    """_ensure_live_search_cookies 浏览器不可用时抛 503 而非 403/440（Fix C）"""

    @pytest.mark.asyncio
    async def test_raises_503_when_browser_unavailable_but_json_has_cookies(self):
        """浏览器不可用但 JSON 持有 cookie 时应抛 503（浏览器不可用）而非 403（未登录）

        场景：ensure_alive 重启失败 → get_cookies 返回空 → 所有 cookie 误判 missing
        → 但 JSON 中持有这些 cookie → 应识别为浏览器不可用而非未登录
        """
        from xianyu_hunter.web.routes.api_task_links import _ensure_live_search_cookies

        container = MagicMock()
        container.browser = MagicMock()
        # ensure_alive 失败（重启失败）
        container.browser.ensure_alive = AsyncMock(return_value=False)
        # get_cookies 返回空（浏览器不可用）
        container.browser.get_cookies = AsyncMock(return_value=[])
        container.browser.add_cookies = AsyncMock(return_value=False)
        container.collector = MagicMock()
        container.collector.should_reset_m5tk = MagicMock(return_value=False)

        # _load_pw_cookies_from_json 返回 JSON 中持有 cookie
        json_identity_values = {"unb": "12345678", "cookie2": "abc"}
        pw_cookies = [{"name": "unb", "value": "12345678"}]

        with patch(
            "xianyu_hunter.web.routes.api_task_links._load_pw_cookies_from_json",
            return_value=(pw_cookies, json_identity_values),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await _ensure_live_search_cookies(container)

            assert exc_info.value.status_code == 503
            assert "浏览器不可用" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_raises_403_when_json_also_missing_cookies(self):
        """JSON 中也没有 cookie 时应抛 403（真正未登录）而非 503

        场景：浏览器不可用 + JSON 也无 cookie → 真正未登录，抛 403
        """
        from xianyu_hunter.web.routes.api_task_links import _ensure_live_search_cookies

        container = MagicMock()
        container.browser = MagicMock()
        container.browser.ensure_alive = AsyncMock(return_value=False)
        container.browser.get_cookies = AsyncMock(return_value=[])
        container.browser.add_cookies = AsyncMock(return_value=False)
        container.collector = MagicMock()
        container.collector.should_reset_m5tk = MagicMock(return_value=False)

        # JSON 中也无 cookie（空字典）
        json_identity_values = {}
        pw_cookies = []

        with patch(
            "xianyu_hunter.web.routes.api_task_links._load_pw_cookies_from_json",
            return_value=(pw_cookies, json_identity_values),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await _ensure_live_search_cookies(container)

            # JSON 无 cookie 时不走 503 分支，走 _raise_live_cookie_errors 的 403
            assert exc_info.value.status_code == 403
