"""T01717 回归测试：过期 Cookie 的注入过滤与续期回写保护

根因链（2026-10-10 实测）：
1. Chromium CookieMonster 惰性回收 → context.cookies() 返回已过期但未 GC 的
   Cookie（实测过期 15 天的 unb 仍在内存）；
2. TokenRenewer 续期后 sync_browser_cookies_to_store_after_renew 把浏览器内存
   Cookie **覆盖写**回档案 → 过期 unb "复活"进 cookies_{uid}.json，且把登录刚
   写入的新鲜档案整体回滚；
3. 实时搜索从档案注入过期 unb → add_cookies 被 Chromium 丢弃 →
   「注入后仍缺失」→ 重试同样失败 → 503「请重新登录」→ 前端警示条常驻。

修复：
- browser.add_cookies 咽喉处过滤过期 Cookie（is_expired_cookie）；
- 续期回写过滤过期 Cookie 并改用 merge_cookies（防覆盖新鲜档案）。
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

from xianyu_hunter.infra.browser import BrowserManager, is_expired_cookie
from xianyu_hunter.web.services import cookie_runtime_sync


def _cookie(name: str, expires: float) -> dict:
    return {"name": name, "value": f"v-{name}", "domain": ".goofish.com",
            "path": "/", "expires": expires}


FUTURE = time.time() + 3600
PAST = time.time() - 3600


# ============================================================
# is_expired_cookie 基础语义
# ============================================================

def test_session_cookie_never_expired() -> None:
    assert not is_expired_cookie({"name": "c", "expires": -1})
    assert not is_expired_cookie({"name": "c", "expires": 0})
    assert not is_expired_cookie({"name": "c"})
    assert not is_expired_cookie({"name": "c", "expires": "bad"})


def test_expired_and_future_cookies() -> None:
    assert is_expired_cookie(_cookie("unb", PAST))
    assert not is_expired_cookie(_cookie("unb", FUTURE))


# ============================================================
# browser.add_cookies：过滤过期 Cookie（注入咽喉）
# ============================================================

def _make_manager(context: AsyncMock) -> BrowserManager:
    mgr = object.__new__(BrowserManager)
    mgr._context = context
    return mgr


def test_add_cookies_skips_expired_and_injects_fresh() -> None:
    context = AsyncMock()
    context.cookies.return_value = [{"name": "cookie2", "value": "v-cookie2"}]
    mgr = _make_manager(context)

    ok = asyncio.run(mgr.add_cookies([
        _cookie("cookie2", FUTURE),
        _cookie("unb", PAST),  # 已过期：Chromium 会拒收
    ]))

    assert ok is True
    injected = context.add_cookies.call_args[0][0]
    assert [c["name"] for c in injected] == ["cookie2"]  # 过期 unb 未被提交


def test_add_cookies_all_expired_returns_false_without_call() -> None:
    context = AsyncMock()
    mgr = _make_manager(context)

    ok = asyncio.run(mgr.add_cookies([_cookie("unb", PAST)]))

    assert ok is False
    context.add_cookies.assert_not_called()


def test_add_cookies_keeps_session_cookies() -> None:
    """expires=-1 的 session cookie（如 cookie2）不应被误过滤"""
    context = AsyncMock()
    context.cookies.return_value = [{"name": "cookie2", "value": "v-cookie2"}]
    mgr = _make_manager(context)

    session_cookie = {"name": "cookie2", "value": "v", "domain": ".goofish.com",
                      "path": "/", "expires": -1}
    ok = asyncio.run(mgr.add_cookies([session_cookie]))

    assert ok is True
    assert context.add_cookies.call_args[0][0] == [session_cookie]


# ============================================================
# sync_browser_cookies_to_store_after_renew：过期过滤 + merge 防覆盖
# ============================================================

def _run_renew_sync(browser_cookies: list[dict]) -> tuple[MagicMock, MagicMock]:
    """跑一次续期回写，返回 (store_mock, container_mock) 供断言"""
    container = MagicMock()
    container.browser = AsyncMock()
    container.browser.get_cookies.return_value = browser_cookies

    store = MagicMock()
    with patch("xianyu_hunter.web.services.cookie_store.get_cookie_store",
               return_value=store), \
         patch("xianyu_hunter.web.services.user_manager.get_user_manager") as mgr_cls, \
         patch("xianyu_hunter.modules.login_orchestrator.sync_cookie_layers_from_json"):
        mgr_cls.return_value.get_active_user_id.return_value = "u1"
        asyncio.run(cookie_runtime_sync.sync_browser_cookies_to_store_after_renew(
            container, log_prefix="测试续期"))
    return store, container


def test_renew_sync_filters_expired_and_uses_merge() -> None:
    fresh = [_cookie("cookie2", FUTURE), _cookie("sgcookie", FUTURE)]
    store, container = _run_renew_sync(fresh + [_cookie("unb", PAST)])

    # 过期 unb 不回写
    merged = store.merge_cookies.call_args[0][0]
    assert {c["name"] for c in merged} == {"cookie2", "sgcookie"}
    # 必须用 merge（防覆盖新鲜登录档案），不再用覆盖写
    store.merge_cookies.assert_called_once()
    assert store.merge_cookies.call_args.kwargs.get("method") == "renew"
    assert store.merge_cookies.call_args.kwargs.get("user_id") == "u1"
    store.export_cookies.assert_not_called()
    # 过期过滤不影响浏览器读取本身
    container.browser.get_cookies.assert_awaited_once()


def test_renew_sync_all_expired_skips_write() -> None:
    store, _ = _run_renew_sync([_cookie("unb", PAST)])

    store.merge_cookies.assert_not_called()
    store.export_cookies.assert_not_called()


def test_renew_sync_no_cookies_skips_write() -> None:
    store, _ = _run_renew_sync([])

    store.merge_cookies.assert_not_called()
