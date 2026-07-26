"""验证 /api/auth/cookie/health 端点的浏览器内存兜底逻辑

覆盖场景：
1. JSON 中 _m_h5_tk 过期时，从浏览器内存刷新回写 JSON 后重新判断
2. 浏览器不可用时降级返回 JSON 原始判断结果
3. 浏览器内存中 token 也过期时返回失效
4. _try_refresh_m5tk_from_browser_for_health 多用户隔离

测试隔离：conftest.py 的 autouse fixture 已自动隔离 CookieStore JSON 路径，
所有写入操作落到 tmp_path，不会污染生产 data/cookies.json。
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from xianyu_hunter.config import get_settings
from xianyu_hunter.web.app import app
from xianyu_hunter.web.services.cookie_store import get_cookie_store

client = TestClient(app)
_AUTH_COOKIE = {"xh_token": get_settings().web_token}


def _make_expired_m5tk() -> str:
    """构造已过期的 _m_h5_tk token（时间戳比当前早 30 分钟，超过 1200 秒 TTL）"""
    expired_ts_ms = int((time.time() - 1800) * 1000)
    return f"c7b2c44645275604a525e6287fea2c3a_{expired_ts_ms}"


def _make_fresh_m5tk() -> str:
    """构造未过期的 _m_h5_tk token（时间戳为当前时间）"""
    fresh_ts_ms = int(time.time() * 1000)
    return f"d8c3d55756386715b636f7398afb3d4b_{fresh_ts_ms}"


def _write_cookie_json(
    cookie_json: Path,
    m5tk_value: str,
    *,
    user_id: str = "default",
) -> None:
    """写入 mock cookie JSON 数据"""
    cookies = [
        {"name": "unb", "value": "2209384756290", "domain": ".goofish.com", "path": "/", "expires": -1},
        {"name": "cookie2", "value": "c8421f9e5b6d7a3b9c0e1f2d3a4b5c6d", "domain": ".goofish.com", "path": "/", "expires": -1},
        {"name": "sgcookie", "value": "E100zRxEj%2FbXi%2B%2FbxVSJT%2Fg%2FaDG6MgjhL", "domain": ".goofish.com", "path": "/", "expires": -1},
        {"name": "_m_h5_tk", "value": m5tk_value, "domain": ".goofish.com", "path": "/", "expires": -1},
        {"name": "_m_h5_tk_enc", "value": "abc123enc456def789", "domain": ".goofish.com", "path": "/", "expires": -1},
        {"name": "cna", "value": "YcHJH+IsChycAXTQMyRJqgj+", "domain": ".goofish.com", "path": "/", "expires": -1},
        {"name": "tfstk", "value": "e1NjUcFrYBFsf7ReJcFrZ", "domain": ".goofish.com", "path": "/", "expires": -1},
    ]
    data = {
        "exported_at": time.time(),
        "method": "test",
        "cookie_count": len(cookies),
        "cookies": cookies,
    }
    cookie_json.parent.mkdir(parents=True, exist_ok=True)
    cookie_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    # 清除 CookieStore 缓存，确保下一次读取从磁盘加载
    store = get_cookie_store()
    store._cache = {}


def _mock_browser_with_cookies(cookies: list[dict]) -> MagicMock:
    """构造一个返回指定 cookies 的 mock 浏览器实例"""
    browser = MagicMock()
    browser.get_cookies = AsyncMock(return_value=cookies)
    return browser


class TestCookieHealthBrowserFallback:
    """验证 cookie_health 端点的浏览器内存兜底逻辑"""

    def test_expired_m5tk_refreshed_from_browser(self, tmp_path):
        """JSON 中 _m_h5_tk 过期时，应从浏览器内存刷新回写 JSON 并返回 is_valid=True

        场景：实时搜索已刷新浏览器内存中的 token 但未回写 JSON，
        右上角健康检查应从浏览器内存补取最新 token，避免误报无效。
        """
        cookie_json = tmp_path / "cookies_default.json"
        _write_cookie_json(cookie_json, _make_expired_m5tk())

        # 浏览器内存中有未过期的新 token
        browser_cookies = [
            {"name": "_m_h5_tk", "value": _make_fresh_m5tk(), "domain": ".goofish.com"},
            {"name": "_m_h5_tk_enc", "value": "new_enc_value", "domain": ".goofish.com"},
        ]
        mock_browser = _mock_browser_with_cookies(browser_cookies)
        mock_container = MagicMock()
        mock_container.browser = mock_browser

        with patch("xianyu_hunter.web.deps.get_container", return_value=mock_container):
            response = client.get("/api/auth/cookie/health", cookies=_AUTH_COOKIE)

        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is True, f"expected is_valid=True, reason={data.get('reason')}"
        assert data["reason"] == "ok"

    def test_expired_m5tk_browser_unavailable_returns_invalid(self, tmp_path):
        """浏览器不可用时，应降级返回 JSON 原始判断结果（is_valid=False）

        场景：Web 进程未启动浏览器（非 --with-scheduler 模式），
        无法从浏览器内存刷新 token，应如实返回失效状态。
        """
        cookie_json = tmp_path / "cookies_default.json"
        _write_cookie_json(cookie_json, _make_expired_m5tk())

        mock_container = MagicMock()
        mock_container.browser = None

        with patch("xianyu_hunter.web.deps.get_container", return_value=mock_container):
            response = client.get("/api/auth/cookie/health", cookies=_AUTH_COOKIE)

        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is False
        assert "cookie_expired:_m_h5_tk" in data["reason"]

    def test_expired_m5tk_browser_also_expired_returns_invalid(self, tmp_path):
        """浏览器内存中 token 也过期时，应返回 is_valid=False

        场景：JSON 和浏览器内存中的 token 都已过期（长时间无活动），
        无法通过浏览器内存兜底恢复，应如实返回失效状态。
        """
        cookie_json = tmp_path / "cookies_default.json"
        _write_cookie_json(cookie_json, _make_expired_m5tk())

        # 浏览器内存中的 token 也已过期
        browser_cookies = [
            {"name": "_m_h5_tk", "value": _make_expired_m5tk(), "domain": ".goofish.com"},
        ]
        mock_browser = _mock_browser_with_cookies(browser_cookies)
        mock_container = MagicMock()
        mock_container.browser = mock_browser

        with patch("xianyu_hunter.web.deps.get_container", return_value=mock_container):
            response = client.get("/api/auth/cookie/health", cookies=_AUTH_COOKIE)

        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is False
        assert "cookie_expired:_m_h5_tk" in data["reason"]

    def test_valid_m5tk_no_browser_refresh(self, tmp_path):
        """JSON 中 _m_h5_tk 未过期时，不应触发浏览器内存兜底

        场景：正常状态下 JSON 中 token 有效，不需要从浏览器内存刷新，
        应直接返回 is_valid=True，不调用 browser.get_cookies。
        """
        cookie_json = tmp_path / "cookies_default.json"
        _write_cookie_json(cookie_json, _make_fresh_m5tk())

        mock_browser = _mock_browser_with_cookies([])
        mock_container = MagicMock()
        mock_container.browser = mock_browser

        with patch("xianyu_hunter.web.deps.get_container", return_value=mock_container):
            response = client.get("/api/auth/cookie/health", cookies=_AUTH_COOKIE)

        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is True
        # 浏览器 get_cookies 不应被调用（token 未过期，无需兜底）
        mock_browser.get_cookies.assert_not_called()


class TestTryRefreshM5tkForHealth:
    """验证 _try_refresh_m5tk_from_browser_for_health 函数行为"""

    @pytest.mark.asyncio
    async def test_returns_false_when_browser_unavailable(self):
        """浏览器不可用时应返回 False"""
        from xianyu_hunter.web.routes.auth_query import _try_refresh_m5tk_from_browser_for_health

        store = MagicMock()
        mock_container = MagicMock()
        mock_container.browser = None

        with patch("xianyu_hunter.web.deps.get_container", return_value=mock_container):
            result = await _try_refresh_m5tk_from_browser_for_health(store, "default")
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_no_valid_m5tk_in_browser(self):
        """浏览器内存中无有效 _m_h5_tk 时应返回 False"""
        from xianyu_hunter.web.routes.auth_query import _try_refresh_m5tk_from_browser_for_health

        store = MagicMock()
        browser_cookies = [
            {"name": "_m_h5_tk", "value": _make_expired_m5tk(), "domain": ".goofish.com"},
        ]
        mock_browser = _mock_browser_with_cookies(browser_cookies)
        mock_container = MagicMock()
        mock_container.browser = mock_browser

        with patch("xianyu_hunter.web.deps.get_container", return_value=mock_container):
            result = await _try_refresh_m5tk_from_browser_for_health(store, "default")
        assert result is False

    @pytest.mark.asyncio
    async def test_writes_to_correct_user_id(self):
        """回写 JSON 时应使用传入的 user_id，支持多用户隔离"""
        from xianyu_hunter.web.routes.auth_query import _try_refresh_m5tk_from_browser_for_health

        store = MagicMock()
        store.update_cookie_values = MagicMock(return_value=True)
        browser_cookies = [
            {"name": "_m_h5_tk", "value": _make_fresh_m5tk(), "domain": ".goofish.com"},
            {"name": "_m_h5_tk_enc", "value": "new_enc", "domain": ".goofish.com"},
        ]
        mock_browser = _mock_browser_with_cookies(browser_cookies)
        mock_container = MagicMock()
        mock_container.browser = mock_browser

        with patch("xianyu_hunter.web.deps.get_container", return_value=mock_container):
            result = await _try_refresh_m5tk_from_browser_for_health(store, "user_123")

        assert result is True
        # 验证 update_cookie_values 被调用时传入了正确的 user_id
        store.update_cookie_values.assert_called_once()
        call_kwargs = store.update_cookie_values.call_args
        assert call_kwargs.kwargs.get("user_id") == "user_123" or call_kwargs[1].get("user_id") == "user_123"

    @pytest.mark.asyncio
    async def test_exception_returns_false(self):
        """浏览器 get_cookies 抛异常时应返回 False 而非抛出"""
        from xianyu_hunter.web.routes.auth_query import _try_refresh_m5tk_from_browser_for_health

        store = MagicMock()
        mock_browser = MagicMock()
        mock_browser.get_cookies = AsyncMock(side_effect=RuntimeError("browser crash"))
        mock_container = MagicMock()
        mock_container.browser = mock_browser

        with patch("xianyu_hunter.web.deps.get_container", return_value=mock_container):
            result = await _try_refresh_m5tk_from_browser_for_health(store, "default")
        assert result is False


class TestComputeLayersStatusUnified:
    """验证 _compute_layers_status 复用配置化 LAYER_DEFINITIONS + session 层 token 过期检查"""

    def test_tracking_layer_uses_configured_cookies(self):
        """tracking 层应使用配置化的 5 个 cookie（含 ali_aplus_v3/utdid）

        修复名单漂移：原硬编码只有 3 个（cna/tfstk/xlly_s），
        导致 JSON 中仅有 ali_aplus_v3 时右上角显示"缺失"而 AntiCrawl 显示"有效"。
        """
        from xianyu_hunter.web.routes.auth_query import _compute_layers_status

        # JSON 中只有 ali_aplus_v3 和 utdid，没有 cna/tfstk/xlly_s
        names = {"ali_aplus_v3", "utdid", "unb", "cookie2", "_m_h5_tk", "_m_h5_tk_enc"}
        result = _compute_layers_status(names, [])
        assert result["tracking"] is True, "配置化 tracking 层应匹配 ali_aplus_v3/utdid"

    def test_session_layer_false_when_m5tk_expired(self):
        """session 层在 _m_h5_tk 过期时应返回 False

        修复语义差异：原 _compute_layers_status 只检查名字存在不检查 token 过期，
        导致右上角显示 session 层"已就绪"而 AntiCrawl 显示"失效"。
        """
        from xianyu_hunter.web.routes.auth_query import _compute_layers_status

        expired_m5tk = _make_expired_m5tk()
        cookies_list = [
            {"name": "_m_h5_tk", "value": expired_m5tk},
            {"name": "_m_h5_tk_enc", "value": "abc123enc456def789"},
        ]
        names = {c["name"] for c in cookies_list}
        result = _compute_layers_status(names, cookies_list)
        assert result["session"] is False, "过期 token 应使 session 层返回 False"

    def test_session_layer_true_when_m5tk_fresh(self):
        """session 层在 _m_h5_tk 未过期时应返回 True"""
        from xianyu_hunter.web.routes.auth_query import _compute_layers_status

        fresh_m5tk = _make_fresh_m5tk()
        cookies_list = [
            {"name": "_m_h5_tk", "value": fresh_m5tk},
            {"name": "_m_h5_tk_enc", "value": "abc123enc456def789"},
        ]
        names = {c["name"] for c in cookies_list}
        result = _compute_layers_status(names, cookies_list)
        assert result["session"] is True

    def test_session_layer_true_when_no_cookies_list(self):
        """未传入 cookies_list 时 session 层只检查名字存在（向后兼容）"""
        from xianyu_hunter.web.routes.auth_query import _compute_layers_status

        names = {"_m_h5_tk", "_m_h5_tk_enc"}
        # 不传 cookies_list，不检查 token 过期
        result = _compute_layers_status(names, None)
        assert result["session"] is True

    def test_identity_layer_uses_configured_cookies(self):
        """identity 层应使用配置化的 cookie 集合"""
        from xianyu_hunter.web.routes.auth_query import _compute_layers_status

        # 只有一个 identity cookie 也应返回 True（与 CookieRotator 的"至少一个"语义一致）
        names = {"unb"}
        result = _compute_layers_status(names, [])
        assert result["identity"] is True

    def test_all_layers_false_when_empty(self):
        """空 names 时所有层应返回 False"""
        from xianyu_hunter.web.routes.auth_query import _compute_layers_status

        result = _compute_layers_status(set(), [])
        assert result["identity"] is False
        assert result["session"] is False
        assert result["tracking"] is False
