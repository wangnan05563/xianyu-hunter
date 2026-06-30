"""Runtime Cookie synchronization helpers.

These helpers bridge the persistent CookieStore JSON and the long-running
Playwright worker browser context. Login/import paths may update JSON while the
worker browser is already running, so the in-memory context needs an explicit
replacement injection before search/detail/buy flows rely on it.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def cookies_from_store_for_playwright(log_prefix: str = "Cookie 同步") -> list[dict]:
    """Read fresh CookieStore JSON and convert it to Playwright add_cookies input."""
    try:
        from xianyu_hunter.web.services.cookie_store import get_cookie_store, is_test_cookie

        store = get_cookie_store()
        store.invalidate_cache()
        data = store._read_json()
        if not data or not data.get("cookies"):
            return []

        pw_cookies: list[dict] = []
        for c in data["cookies"]:
            name = str(c.get("name") or "")
            value = str(c.get("value") or "")
            if not name or not value:
                continue
            if is_test_cookie(name, value):
                logger.warning("%s：跳过测试 Cookie %s=%s", log_prefix, name, value)
                continue

            item = {
                "name": name,
                "value": value,
                "domain": c.get("domain") or ".goofish.com",
                "path": c.get("path") or "/",
            }
            try:
                expires = float(c.get("expires", -1) or -1)
            except (TypeError, ValueError):
                expires = -1
            if expires > 0:
                item["expires"] = expires
            pw_cookies.append(item)
        return pw_cookies
    except Exception as e:  # noqa: BLE001
        logger.debug("%s：读取 CookieStore JSON 失败: %s", log_prefix, e)
        return []


async def inject_cookie_store_to_browser(
    browser,
    log_prefix: str = "Cookie 同步",
    *,
    collector=None,
    force_refresh_m5tk: bool = True,
) -> bool:
    """Inject latest CookieStore cookies into a running BrowserManager."""
    if not browser:
        logger.debug("%s：浏览器未初始化，跳过运行时注入", log_prefix)
        return False

    pw_cookies = cookies_from_store_for_playwright(log_prefix)
    if not pw_cookies:
        logger.warning("%s：CookieStore 中没有可注入的 Cookie", log_prefix)
        return False

    success = await browser.add_cookies(pw_cookies)
    if not success:
        logger.warning("%s：注入浏览器后目标 Cookie 验证未通过", log_prefix)
        return False

    logger.info("%s：已注入/替换 %d 个 Cookie 到浏览器", log_prefix, len(pw_cookies))
    try:
        from xianyu_hunter.modules.login_orchestrator import sync_cookie_layers_from_json

        sync_cookie_layers_from_json()
    except Exception as e:  # noqa: BLE001
        logger.debug("%s：注入后同步 Cookie 层状态失败: %s", log_prefix, e)

    if force_refresh_m5tk and collector and hasattr(collector, "force_refresh_m5tk_next"):
        collector.force_refresh_m5tk_next()
    return True


async def inject_cookie_store_to_worker_browser(
    log_prefix: str = "Cookie 同步",
    *,
    force_refresh_m5tk: bool = True,
) -> bool:
    """Inject latest CookieStore cookies into the global worker browser.

    Returns True when the worker browser accepted the cookies. Missing browser
    context is treated as a non-fatal False because CLI/import flows can still
    persist cookies for the next browser start.
    """
    try:
        from xianyu_hunter.web.deps import get_container

        container = get_container()
        browser = getattr(container, "browser", None)
        collector = getattr(container, "collector", None)
        return await inject_cookie_store_to_browser(
            browser,
            log_prefix,
            collector=collector,
            force_refresh_m5tk=force_refresh_m5tk,
        )
    except Exception as e:  # noqa: BLE001
        logger.debug("%s：运行时 Cookie 注入失败: %s", log_prefix, e)
        return False
