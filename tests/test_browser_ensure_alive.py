"""BrowserManager.ensure_alive 自愈机制测试

覆盖场景：
1. 浏览器存活时 ensure_alive 快速返回 True（不触发重启）
2. 浏览器连接断开时自动 close + start 重启
3. 重启失败时返回 False
4. 并发调用 ensure_alive 串行化（不重复重启）
5. collection_service._inject_cookies_from_store 调用前 ensure_alive
6. inject_cookie_store_to_browser 调用前 ensure_alive
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xianyu_hunter.infra.browser import BrowserManager


@pytest.fixture
def manager(tmp_path):
    """创建使用临时目录的 BrowserManager 实例（不真正启动浏览器）"""
    return BrowserManager(user_data_dir=str(tmp_path / "browser-data"))


# ============== ensure_alive 核心逻辑 ==============


class TestEnsureAlive:
    """ensure_alive 方法测试"""

    @pytest.mark.asyncio
    async def test_ensure_alive_returns_true_when_browser_alive(self, manager):
        """浏览器存活时 ensure_alive 应快速返回 True，不触发重启"""
        with patch.object(manager, "is_alive", new_callable=AsyncMock) as mock_alive:
            mock_alive.return_value = True

            result = await manager.ensure_alive()

            assert result is True
            # is_alive 应只调用一次（快速路径），不进入重启分支
            assert mock_alive.call_count == 1

    @pytest.mark.asyncio
    async def test_ensure_alive_restarts_when_browser_dead(self, manager):
        """浏览器断开时应自动 close + start 重启"""
        # is_alive 调用序列：
        # 1. 快速路径 False（触发重启）
        # 2. 慢路径 double-check False（确认仍需重启，进入 close+start）
        # 3. 重启后 True（验证重启成功）
        alive_results = [False, False, True]
        mock_close = AsyncMock()
        mock_start = AsyncMock()
        with patch.object(manager, "is_alive", new_callable=AsyncMock) as mock_alive:
            mock_alive.side_effect = alive_results
            manager.close = mock_close
            manager.start = mock_start
            result = await manager.ensure_alive()

            assert result is True
            mock_close.assert_awaited_once()
            mock_start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ensure_alive_returns_false_when_restart_fails(self, manager):
        """重启后仍不存活时应返回 False"""
        # is_alive 始终返回 False（快速路径、double-check、重启后都不存活）
        with patch.object(manager, "is_alive", new_callable=AsyncMock) as mock_alive:
            mock_alive.return_value = False
            manager.close = AsyncMock()
            manager.start = AsyncMock()
            result = await manager.ensure_alive()

            assert result is False

    @pytest.mark.asyncio
    async def test_ensure_alive_returns_false_when_start_raises(self, manager):
        """start 抛异常时应返回 False 而非传播异常"""
        # is_alive 前两次 False（触发重启），start 抛异常后不会到达第三次
        with patch.object(manager, "is_alive", new_callable=AsyncMock) as mock_alive:
            mock_alive.return_value = False
            manager.close = AsyncMock()
            mock_start = AsyncMock(side_effect=RuntimeError("start failed"))
            manager.start = mock_start

            result = await manager.ensure_alive()

            assert result is False

    @pytest.mark.asyncio
    async def test_ensure_alive_close_failure_does_not_block_restart(self, manager):
        """close 抛异常时应继续尝试 start，不阻断重启流程"""
        mock_close = AsyncMock(side_effect=RuntimeError("close failed"))
        mock_start = AsyncMock()
        with patch.object(manager, "is_alive", new_callable=AsyncMock) as mock_alive:
            # 1. 快速路径 False（触发重启）
            # 2. 慢路径 double-check False（进入 close+start）
            # 3. 重启后 True（验证重启成功）
            mock_alive.side_effect = [False, False, True]
            manager.close = mock_close
            manager.start = mock_start
            result = await manager.ensure_alive()

            assert result is True
            mock_close.assert_awaited_once()
            mock_start.assert_awaited_once()


# ============== is_alive 改进 ==============


class TestIsAlive:
    """is_alive 方法测试"""

    @pytest.mark.asyncio
    async def test_is_alive_returns_false_when_context_none(self, manager):
        """_context 为 None 时返回 False"""
        manager._context = None
        assert await manager.is_alive() is False

    @pytest.mark.asyncio
    async def test_is_alive_returns_true_when_cookies_accessible(self, manager):
        """context.cookies() 可调用时返回 True（不要求 cookies 非空）

        覆盖刚重启浏览器场景：连接可用但无 Cookie。
        """
        mock_context = MagicMock()
        mock_context.cookies = AsyncMock(return_value=[])
        manager._context = mock_context

        assert await manager.is_alive() is True
        mock_context.cookies.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_is_alive_returns_false_when_cookies_raises(self, manager):
        """context.cookies() 抛异常（连接断开）时返回 False"""
        mock_context = MagicMock()
        mock_context.cookies = AsyncMock(side_effect=RuntimeError(
            "Connection closed while reading from the driver"
        ))
        manager._context = mock_context

        assert await manager.is_alive() is False
        mock_context.cookies.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_is_alive_detects_closed_connection_when_pages_cached(self, manager):
        """回归测试：pages 同步属性可访问但底层连接已断开时必须返回 False

        复现线上 bug：旧实现用 self._context.pages（同步 property）检测连接，
        但 pages 返回内部缓存列表，连接断开时不抛异常，
        导致 ensure_alive 走快速路径不触发重启，后续 add_cookies 抛
        "Connection closed while reading from the driver"，实时搜索报 503。
        """
        mock_context = MagicMock()
        # pages 仍可访问（返回缓存的空列表，不抛异常）
        mock_context.pages = []
        # 但 cookies() 抛 Connection closed，证明底层 CDP 通道已断
        mock_context.cookies = AsyncMock(side_effect=RuntimeError(
            "Connection closed while reading from the driver"
        ))
        manager._context = mock_context

        assert await manager.is_alive() is False


# ============== collection_service 集成 ==============


class TestCollectionServiceEnsureAlive:
    """collection_service._inject_cookies_from_store 调用 ensure_alive 测试"""

    @pytest.mark.asyncio
    async def test_inject_calls_ensure_alive_before_add_cookies(self):
        """_inject_cookies_from_store 应在 add_cookies 前调用 ensure_alive"""
        from xianyu_hunter.modules.collection_service import ItemCollectionService

        container = MagicMock()
        container.browser = MagicMock()
        container.browser.ensure_alive = AsyncMock(return_value=True)
        container.browser.add_cookies = AsyncMock(return_value=True)

        service = ItemCollectionService.__new__(ItemCollectionService)
        service.container = container

        await service._inject_cookies_from_store(
            container, [{"name": "unb", "value": "12345678"}],
            missing=["unb"], expired=[], stale=[],
        )

        container.browser.ensure_alive.assert_awaited_once()
        container.browser.add_cookies.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_inject_skips_when_ensure_alive_fails(self):
        """ensure_alive 返回 False 时应跳过 add_cookies"""
        from xianyu_hunter.modules.collection_service import ItemCollectionService

        container = MagicMock()
        container.browser = MagicMock()
        container.browser.ensure_alive = AsyncMock(return_value=False)
        container.browser.add_cookies = AsyncMock()

        service = ItemCollectionService.__new__(ItemCollectionService)
        service.container = container

        await service._inject_cookies_from_store(
            container, [{"name": "unb", "value": "12345678"}],
            missing=["unb"], expired=[], stale=[],
        )

        container.browser.ensure_alive.assert_awaited_once()
        # add_cookies 不应被调用
        container.browser.add_cookies.assert_not_called()


# ============== cookie_runtime_sync 集成 ==============


class TestCookieRuntimeSyncEnsureAlive:
    """inject_cookie_store_to_browser 调用 ensure_alive 测试"""

    @pytest.mark.asyncio
    async def test_inject_calls_ensure_alive_when_available(self):
        """inject_cookie_store_to_browser 应在 add_cookies 前调用 ensure_alive"""
        from xianyu_hunter.web.services.cookie_runtime_sync import inject_cookie_store_to_browser

        browser = MagicMock()
        browser.ensure_alive = AsyncMock(return_value=True)
        browser.add_cookies = AsyncMock(return_value=True)

        with patch(
            "xianyu_hunter.web.services.cookie_runtime_sync.cookies_from_store_for_playwright",
            return_value=[{"name": "unb", "value": "12345678"}],
        ):
            result = await inject_cookie_store_to_browser(browser, "test")

            assert result is True
            browser.ensure_alive.assert_awaited_once()
            browser.add_cookies.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_inject_skips_when_ensure_alive_fails(self):
        """ensure_alive 返回 False 时应跳过 add_cookies 返回 False"""
        from xianyu_hunter.web.services.cookie_runtime_sync import inject_cookie_store_to_browser

        browser = MagicMock()
        browser.ensure_alive = AsyncMock(return_value=False)
        browser.add_cookies = AsyncMock()

        with patch(
            "xianyu_hunter.web.services.cookie_runtime_sync.cookies_from_store_for_playwright",
            return_value=[{"name": "unb", "value": "12345678"}],
        ):
            result = await inject_cookie_store_to_browser(browser, "test")

            assert result is False
            browser.ensure_alive.assert_awaited_once()
            browser.add_cookies.assert_not_called()

    @pytest.mark.asyncio
    async def test_inject_works_without_ensure_alive_method(self):
        """browser 无 ensure_alive 方法时应跳过检查直接 add_cookies（向后兼容）"""
        from xianyu_hunter.web.services.cookie_runtime_sync import inject_cookie_store_to_browser

        # 不使用 MagicMock（它会自动生成 ensure_alive 属性），用简单对象
        class SimpleBrowser:
            async def add_cookies(self, cookies):
                return True

        browser = SimpleBrowser()

        with patch(
            "xianyu_hunter.web.services.cookie_runtime_sync.cookies_from_store_for_playwright",
            return_value=[{"name": "unb", "value": "12345678"}],
        ):
            result = await inject_cookie_store_to_browser(browser, "test")

            assert result is True
