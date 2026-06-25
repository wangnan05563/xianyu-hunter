"""浏览器 Cookie 导入 - CDP 方式（方案 A：v20 加密的解决方案）

端点：
- POST /api/auth/import-from-browser/cdp   通过 CDP 协议从运行中的浏览器获取明文 Cookie

原理：
- 用户以 --remote-debugging-port=9222 启动 Edge/Chrome
- 项目通过 Playwright connect_over_cdp 连接浏览器
- 调用 context.cookies() 获取明文 Cookie，完全绕过 v20 加密

前置条件：
- 浏览器以调试端口启动（参见 scripts/start_edge_debug.ps1）
- Chrome 136+ 需配合 --user-data-dir 指向非标准目录
"""
from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from xianyu_hunter.web.routes.auth_helpers import make_auth_response
from xianyu_hunter.web.services.cookie_store import get_cookie_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["browser-import-cdp"])

# 闲鱼相关域名（用于过滤 Cookie）
_XIANYU_DOMAINS = ("goofish", "taobao", "alipay")


def _check_cdp_reachable(port: int) -> bool:
    """检测 CDP 端点是否可达

    先用 httpx 探测，避免 Playwright 连接超时（默认 30 秒）
    """
    try:
        resp = httpx.get(f"http://localhost:{port}/json/version", timeout=3.0)
        return resp.status_code == 200
    except Exception:
        return False


def _filter_xianyu_cookies(cookies: list[dict]) -> list[dict]:
    """过滤出闲鱼/淘宝/支付宝域名的 Cookie"""
    return [
        c for c in cookies
        if any(domain in c.get("domain", "") for domain in _XIANYU_DOMAINS)
    ]


def _collect_cookies_via_cdp(port: int) -> list[dict]:
    """通过 CDP 协议从运行中的浏览器获取明文 Cookie

    Args:
        port: CDP 调试端口

    Returns:
        过滤后的闲鱼相关 Cookie 列表
    """
    from playwright.sync_api import sync_playwright

    all_cookies: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://localhost:{port}")
        try:
            # 遍历所有浏览器上下文（每个 Profile 对应一个 context）
            for context in browser.contexts:
                all_cookies.extend(context.cookies())
        finally:
            # connect_over_cdp 不需要 close（会断开连接但浏览器继续运行）
            pass

    return _filter_xianyu_cookies(all_cookies)


@router.post("/import-from-browser/cdp")
def import_via_cdp(port: int = 9222) -> JSONResponse:
    """通过 CDP 协议从运行中的浏览器获取明文 Cookie

    前置条件：浏览器以 --remote-debugging-port=9222 启动
    """
    if not _check_cdp_reachable(port):
        return JSONResponse(content={
            "ok": False,
            "error": f"CDP 端点 localhost:{port} 不可达",
            "hint": (
                "请先运行调试浏览器脚本：\n"
                "  powershell -File scripts/start_edge_debug.ps1\n"
                "然后在浏览器中登录闲鱼，再重试此操作"
            ),
        })

    try:
        cookies = _collect_cookies_via_cdp(port)
    except Exception as e:
        logger.exception("CDP 获取 Cookie 失败")
        return JSONResponse(content={
            "ok": False,
            "error": f"CDP 连接失败: {e}",
            "hint": "请确认浏览器以 --remote-debugging-port 参数启动",
        })

    if not cookies:
        return JSONResponse(content={
            "ok": False,
            "error": "未在浏览器中找到闲鱼相关 Cookie",
            "hint": "请先在浏览器中访问 https://www.goofish.com 并登录",
        })

    # 写入 CookieStore（JSON + SQLite）
    success = get_cookie_store().export_cookies(cookies, method="cdp_import")
    if not success:
        return JSONResponse(content={
            "ok": False,
            "error": "Cookie 写入存储失败",
        })

    result = {
        "ok": True,
        "imported_count": len(cookies),
        "imported_cookies": [f"{c['name']}@{c.get('domain', '')}" for c in cookies],
        "source": "cdp",
        "message": f"通过 CDP 成功导入 {len(cookies)} 个 Cookie",
    }
    return make_auth_response(result)
