"""Runtime Cookie synchronization helpers.

These helpers bridge the persistent CookieStore JSON and the long-running
Playwright worker browser context. Login/import paths may update JSON while the
worker browser is already running, so the in-memory context needs an explicit
replacement injection before search/detail/buy flows rely on it.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# 多个函数共用的日志前缀默认值
DEFAULT_LOG_PREFIX = "Cookie 同步"


def cookies_from_store_for_playwright(log_prefix: str = DEFAULT_LOG_PREFIX, user_id: str = "default") -> list[dict]:
    """Read fresh CookieStore JSON and convert it to Playwright add_cookies input.

    多用户隔离：按 user_id 读取 cookies_{user_id}.json。Worker 浏览器是全局单例，
    调用方需传入当前活跃用户（通常通过 UserManager.get_active_user_id() 获取）。
    """
    try:
        from xianyu_hunter.web.services.cookie_store import get_cookie_store, is_test_cookie

        store = get_cookie_store()
        store.invalidate_cache(user_id)
        data = store._read_json(user_id)
        if not data or not data.get("cookies"):
            return []

        pw_cookies: list[dict] = []
        for c in data["cookies"]:
            item = _convert_cookie_to_playwright_format(c, log_prefix, is_test_cookie)
            if item is not None:
                pw_cookies.append(item)
        return pw_cookies
    except Exception as e:  # noqa: BLE001
        logger.debug("%s：读取 CookieStore JSON 失败: %s", log_prefix, e)
        return []


def _convert_cookie_to_playwright_format(
    raw: dict, log_prefix: str, is_test_cookie_fn,
) -> dict | None:
    """将单条 CookieStore JSON 记录转为 Playwright add_cookies 格式

    为什么提取为模块级函数：原 cookies_from_store_for_playwright 的 for 循环内
    嵌套多个 if (or/continue) + 内嵌 try/except 解析 expires，认知复杂度堆积。
    提取后主函数仅保留遍历骨架，单条 cookie 的校验/解析/构造职责分离。
    返回 None 表示该 cookie 应跳过（空值/测试数据）。
    """
    name = str(raw.get("name") or "")
    value = str(raw.get("value") or "")
    if not name or not value:
        return None
    if is_test_cookie_fn(name, value):
        logger.warning("%s：跳过测试 Cookie %s=%s", log_prefix, name, value)
        return None

    item = {
        "name": name,
        "value": value,
        "domain": raw.get("domain") or ".goofish.com",
        "path": raw.get("path") or "/",
    }
    try:
        expires = float(raw.get("expires", -1) or -1)
    except (TypeError, ValueError):
        expires = -1
    if expires > 0:
        item["expires"] = expires
    return item


async def inject_cookie_store_to_browser(
    browser,
    log_prefix: str = DEFAULT_LOG_PREFIX,
    *,
    collector=None,
    force_refresh_m5tk: bool = True,
    user_id: str = "default",
) -> bool:
    """Inject latest CookieStore cookies into a running BrowserManager.

    多用户隔离：按 user_id 读取 cookies_{user_id}.json 注入到浏览器。
    """
    if not browser:
        logger.debug("%s：浏览器未初始化，跳过运行时注入", log_prefix)
        return False

    pw_cookies = cookies_from_store_for_playwright(log_prefix, user_id)
    if not pw_cookies:
        logger.warning("%s：CookieStore 中没有可注入的 Cookie", log_prefix)
        return False

    # ensure_alive：浏览器连接断开时自动重启，否则 add_cookies 必然失败
    # 触发场景：浏览器进程崩溃、CDP 连接意外断开、内存压力下被系统杀死
    if hasattr(browser, "ensure_alive"):
        if not await browser.ensure_alive():
            logger.warning("%s：浏览器不可用且重启失败，跳过注入", log_prefix)
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
    log_prefix: str = DEFAULT_LOG_PREFIX,
    *,
    force_refresh_m5tk: bool = True,
    user_id: str | None = None,
) -> bool:
    """Inject latest CookieStore cookies into the global worker browser.

    Returns True when the worker browser accepted the cookies. Missing browser
    context is treated as a non-fatal False because CLI/import flows can still
    persist cookies for the next browser start.

    多用户隔离：user_id 为 None 时自动获取最近活跃用户（后台调度场景）。
    显式传入 user_id 时按该用户读取（登录/导入端点已识别 user_id）。
    """
    try:
        from xianyu_hunter.web.deps import get_container

        # 未指定 user_id 时获取最近活跃用户（后台调度场景）
        if user_id is None:
            try:
                from xianyu_hunter.web.services.user_manager import get_user_manager
                user_id = get_user_manager().get_active_user_id()
            except Exception:
                user_id = "default"

        container = get_container()
        browser = getattr(container, "browser", None)
        collector = getattr(container, "collector", None)
        return await inject_cookie_store_to_browser(
            browser,
            log_prefix,
            collector=collector,
            force_refresh_m5tk=force_refresh_m5tk,
            user_id=user_id,
        )
    except Exception as e:  # noqa: BLE001
        logger.debug("%s：运行时 Cookie 注入失败: %s", log_prefix, e)
        return False


async def sync_browser_cookies_to_store_after_renew(container, log_prefix: str = "token 续期") -> None:
    """导航续期后提取浏览器 cookie 回写 CookieStore + 同步层状态

    统一入口：消除 login_orchestrator._default_renew_callback 与
    api_anticrawl._renew_token_via_browser_navigation 的重复逻辑。
    两者都是导航到 m.taobao.com 触发 Set-Cookie 后需要回写 JSON + 同步层状态。

    为什么必须回写 + 同步：导航的 Set-Cookie 只更新浏览器内存，
    CookieStore JSON 和 CookieRotator 层状态仍是旧值，
    不同步会导致健康检查误判 token 过期、层状态与浏览器振荡。
    """
    try:
        cookies = await container.browser.get_cookies(["goofish.com", "taobao.com"])
        if not cookies:
            return
        from xianyu_hunter.web.services.cookie_store import get_cookie_store
        # 多用户隔离：回写到最近活跃用户的 cookie 文件
        try:
            from xianyu_hunter.web.services.user_manager import get_user_manager
            renew_user_id = get_user_manager().get_active_user_id()
        except Exception:
            renew_user_id = "default"
        get_cookie_store().export_cookies(cookies, method="renew", user_id=renew_user_id)
        # 同步层状态：让 CookieRotator 反映续期后的真实状态
        from xianyu_hunter.modules.login_orchestrator import sync_cookie_layers_from_json
        sync_cookie_layers_from_json()
        logger.debug("%s：已回写 %d 个 cookie 并同步层状态 [user=%s]", log_prefix, len(cookies), renew_user_id)
    except Exception as e:
        # 回写失败不影响续期成功状态（token 已在浏览器内存中刷新）
        logger.warning("%s：回写 CookieStore / 同步层状态失败: %s", log_prefix, e)
