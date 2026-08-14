"""回归测试：SearchMixin._unroute_search_api 的 TargetClosedError 修复

修复点回顾（src/xianyu_hunter/modules/collector/_search.py）：
  (1) 页面/上下文/浏览器已关闭时直接跳过 unroute —— 避免 wait_for 超时与
      孤儿 future；
  (2) 存活态用 asyncio.shield 包裹 unroute，wait_for 超时只取消外层等待、
      不取消内部 unroute task，并用 done_callback 取回异常，抑制
      TargetClosedError "Future exception was never retrieved" 告警。

该方法是模块级 logger，不依赖 self 的任何业务属性，故可用最小 mock 直接验证。
"""
import asyncio
from unittest.mock import MagicMock

import pytest

from xianyu_hunter.modules.collector._search import SearchMixin


def _make_page(is_page_closed=False, is_ctx_closed=False, is_browser_connected=True):
    """构造最小 mock Page，仅暴露 _unroute_search_api 探测/调用到的属性。"""
    browser = MagicMock()
    browser.is_connected = MagicMock(return_value=is_browser_connected)

    ctx = MagicMock()
    ctx.is_closed = MagicMock(return_value=is_ctx_closed)
    ctx.browser = browser

    page = MagicMock()
    page.is_closed = MagicMock(return_value=is_page_closed)
    page.context = ctx
    return page, browser, ctx


def _mixin():
    # 跳过 __init__，方法只用模块级 logger，无需真实业务状态
    return SearchMixin.__new__(SearchMixin)


@pytest.mark.asyncio
async def test_unroute_skips_when_page_closed():
    page, _, _ = _make_page(is_page_closed=True)
    page.unroute = MagicMock()  # 不应被调用
    await _mixin()._unroute_search_api(page, "**/api", lambda r: None)
    page.unroute.assert_not_called()


@pytest.mark.asyncio
async def test_unroute_skips_when_context_closed():
    page, _, ctx = _make_page(is_ctx_closed=True)
    page.unroute = MagicMock()
    await _mixin()._unroute_search_api(page, "**/api", lambda r: None)
    page.unroute.assert_not_called()
    ctx.is_closed.assert_called()


@pytest.mark.asyncio
async def test_unroute_skips_when_browser_disconnected():
    page, browser, _ = _make_page(is_browser_connected=False)
    page.unroute = MagicMock()
    await _mixin()._unroute_search_api(page, "**/api", lambda r: None)
    page.unroute.assert_not_called()
    browser.is_connected.assert_called()


@pytest.mark.asyncio
async def test_unroute_completes_normally_when_fast():
    page, _, _ = _make_page()
    loop = asyncio.get_running_loop()
    done = loop.create_future()
    done.set_result(None)
    page.unroute = MagicMock(return_value=done)
    # 不应抛异常，且确实调用了 unroute
    await asyncio.wait_for(
        _mixin()._unroute_search_api(page, "**/api", lambda r: None), timeout=5
    )
    page.unroute.assert_called_once()


@pytest.mark.asyncio
async def test_unroute_shield_prevents_inner_cancel_on_timeout():
    page, _, _ = _make_page()
    loop = asyncio.get_running_loop()
    # 模拟 route handler 仍在飞行：unroute 返回一个长时间不完成的 future
    slow = loop.create_future()
    page.unroute = MagicMock(return_value=slow)

    start = loop.time()
    # 方法应在 ~2.5s 超时后返回，且不抛 TimeoutError / CancelledError
    await _mixin()._unroute_search_api(page, "**/api", lambda r: None)
    elapsed = loop.time() - start

    # 超时分支触发：返回耗时约等于 wait_for 的 2.5s 超时
    assert elapsed >= 2.0, f"方法应在超时后返回，实际 {elapsed:.2f}s"
    # 核心修复点：shield 保护内部 unroute task 不被取消
    assert not slow.cancelled(), "shield 应保护内部 unroute task 不被取消"
    page.unroute.assert_called_once()

    # 清理：取消遗留的慢 future，避免 "pending task destroyed" 警告。
    # 注意 Future.cancel() 立即生效，无需 await —— 否则取消态 await 会抛
    # CancelledError（BaseException 子类，不被 except Exception 捕获）。
    if not slow.done():
        slow.cancel()
