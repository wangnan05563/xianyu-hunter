"""Cookie 注入 API - 支持多种方式注入闲鱼 Cookie

端点：
- POST /api/auth/cookie          手动注入 Cookie（name=value 格式）
- POST /api/auth/cookie/file     从上传的 cookie 文件导入
- POST /api/auth/cookie/path     从服务器本地路径读取 cookie 文件导入
- GET  /api/auth/cookie/domains  列出已有 cookie 域名（调试用）
- GET  /api/auth/cookie/saved    获取已保存的 cookie 摘要信息

支持的 Cookie 文件格式：
1. Netscape 格式（cookies.txt）— 浏览器扩展导出最常见格式
2. JSON 格式 — EditThisCookie 等扩展导出格式
3. Header 字符串格式 — name=value; name2=value2
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path

from fastapi import APIRouter, Depends, Form, UploadFile, File, Request
from fastapi.responses import JSONResponse

from xianyu_hunter.container import Container
from xianyu_hunter.infra.yaml_config import get_config
from xianyu_hunter.paths import get_browser_data_dir
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.routes.auth_helpers import make_auth_response
from xianyu_hunter.web.services.cookie_db import init_cookie_table, upsert_cookie
from xianyu_hunter.web.services.cookie_store import get_cookie_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["cookie-inject"])

# 提取重复的域名常量，便于统一维护  # NOSONAR
# 注入时需同时覆盖淘宝系多域名，闲鱼共享淘宝认证
_DOMAIN_GOOFISH = "goofish.com"
_DOMAIN_GOOFISH_DOT = ".goofish.com"
_DOMAIN_TAOBAO = "taobao.com"
_DOMAIN_TAOBAO_DOT = ".taobao.com"
_DOMAIN_ALIPAY = "alipay.com"
_DOMAIN_ALIPAY_DOT = ".alipay.com"
_DOMAIN_LOGIN_TAOBAO = "login.taobao.com"
_DOMAIN_LOGIN_TAOBAO_DOT = ".login.taobao.com"

# 注入域名：从配置读取（cookie_management.domains）
# 配置化修复了原代码遗漏：原 _INJECT_DOMAINS 仅 4 个域名，缺少 taobao.com /
# alipay.com / login.taobao.com / .login.taobao.com，导致 cookie 写入不完整
# 与 cookie_rotator.DOMAINS 共享同一份配置，避免域名列表漂移
_INJECT_DOMAINS = tuple(get_config().cookie_management.domains)
_DEFAULT_DOMAIN = _DOMAIN_GOOFISH_DOT
# S1192: 提取重复字符串字面量为常量
_COOKIE_INJECT_FAILED_PREFIX = "Cookie 注入失败: "
_UNRECOGNIZED_FORMAT_ERROR = "无法识别文件格式，请使用 Netscape (cookies.txt) 或 JSON 格式"


def _identify_user_from_cookies(cookies: list[dict] | list[tuple[str, str]]) -> str:
    """从 Cookie 列表识别用户身份，不存在则创建。

    手动注入场景下用户可能只粘贴部分 Cookie，identify_or_create 内部
    会按 unb > sha256(cookie2) > "default" 降级，确保总有 user_id 返回。
    """
    try:
        from xianyu_hunter.web.services.user_manager import get_user_manager
        # 统一转换为 [{"name": n, "value": v}] 格式
        if cookies and isinstance(cookies[0], tuple):
            cookie_list = [{"name": n, "value": v} for n, v in cookies]
        else:
            cookie_list = cookies  # type: ignore[assignment]
        return get_user_manager().identify_or_create(cookie_list)
    except Exception as e:
        logger.warning("识别用户身份失败，降级到 default: %s", e)
        return "default"


def _inject_to_sqlite(cookie_db: Path, cookies_to_inject: list[tuple[str, str]]) -> tuple[int, list[str]]:
    """直接写入 SQLite 数据库（浏览器未运行时可用）

    Returns:
        (injected_count, errors)
    """
    now_utc = int(time.time()) + 11644473600  # Chrome 时间戳（Windows epoch）
    injected = 0
    errors = []
    # S2737: 原外层 try-except 仅做 raise e，无任何处理，删除以避免冗余
    with sqlite3.connect(str(cookie_db)) as conn:
        init_cookie_table(conn)
        for name, value in cookies_to_inject:
            try:
                # 同一 cookie 写入多个域名：闲鱼共享淘宝系认证，
                # 需同时覆盖 .goofish.com / goofish.com / .taobao.com / .alipay.com
                for domain in _INJECT_DOMAINS:
                    upsert_cookie(conn, {
                        "host_key": domain,
                        "name": name,
                        "value": value,
                        "path": "/",
                        "expires_utc": now_utc + 86400 * 365,
                        "is_secure": 1,
                        "is_httponly": 1,
                        "creation_utc": now_utc,
                        "last_access_utc": now_utc,
                    })
                injected += 1
            except Exception as e:
                errors.append(f"{name}: {e}")
        conn.commit()
    return injected, errors


async def _inject_via_browser(cookies_to_inject: list[tuple[str, str]]) -> tuple[int, list[str], str]:
    """通过运行中的浏览器上下文注入 Cookie

    浏览器运行时 SQLite 被锁定且加密存储，需通过 BrowserManager.add_cookies()
    注入到 Playwright context（Chromium 会在内存中接受并适时持久化）。
    """
    from xianyu_hunter.web.deps import get_container

    container = get_container()
    if not container.browser or not container.browser._context:
        raise RuntimeError("浏览器实例不可用（browser 或 _context 为空）")

    injected = 0
    errors = []
    pw_cookies = []
    for name, value in cookies_to_inject:
        for domain in _INJECT_DOMAINS:
            pw_cookies.append({
                "name": name,
                "value": value,
                "domain": domain,
                "path": "/",
            })
        injected += 1

    success = await container.browser.add_cookies(pw_cookies)
    if not success:
        errors.append("浏览器上下文注入后目标 Cookie 验证未通过")
        return 0, errors, "browser_context"
    return injected, errors, "browser_context"


def _parse_cookie_string_to_pairs(cookie_string: str) -> list[tuple[str, str]]:
    """解析 cookie 字符串为 (name, value) 对

    支持分隔符：; 或换行符（用户从浏览器DevTools复制时常见）
    """
    pairs = []
    # 先按换行分割，再按分号分割（处理混合格式）
    for line in cookie_string.split("\n"):
        for part in line.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            name, _, value = part.partition("=")
            name = name.strip()
            value = value.strip()
            if name and value:
                pairs.append((name, value))
    return pairs


async def _write_json_fallback_and_sync(
    cookies_to_inject: list[tuple[str, str]], injected: int, method: str,
) -> tuple[int, str, bool, str]:
    """写入 JSON 兜底并同步 CookieRotator 层状态与 Worker 浏览器

    Returns:
        (injected, method, json_written, user_id)
        user_id 用于上层签发多用户 session_token，确保 /api/auth/me 能识别登录态
    """
    json_written = False
    # 默认 user_id，识别失败时降级
    user_id = "default"
    if cookies_to_inject:
        # 动态识别 user_id：手动注入场景也支持多账号，不再硬编码 "default"
        user_id = _identify_user_from_cookies(cookies_to_inject)
        # 用 merge_cookies 合并写而非 export_cookies 覆盖写
        # 为什么：用户从 DevTools 复制时可能只粘贴部分 cookie（如仅 4 个身份 cookie），
        # 覆盖写会丢失原有 22 个完整 cookie 集，导致详情页 SPA 渲染失败；
        # 合并写只增量更新同名 cookie，保留原有 cna/tracknick/_tb_token_ 等追踪/会话 cookie
        json_written = get_cookie_store().merge_cookies([
            {"name": n, "value": v, "domain": _DEFAULT_DOMAIN, "path": "/"}
            for n, v in cookies_to_inject
        ], method="cookie", user_id=user_id)
        # JSON 写入成功时，即使 browser+sqlite 都没写入成功，也算注入完成
        if json_written and injected == 0:
            injected = len(cookies_to_inject)
            method = "json_fallback"
        # 同步 CookieRotator 层状态：与 /cookies/update 端点行为一致，
        # 避免注入后 /cookies/layers 仍显示 identity/session/tracking 失效
        if json_written:
            try:
                from xianyu_hunter.modules.login_orchestrator import sync_cookie_layers_from_json
                sync_cookie_layers_from_json()
            except Exception as e:
                logger.debug("cookie 注入后同步层状态失败: %s", e)
            try:
                from xianyu_hunter.web.services.cookie_runtime_sync import inject_cookie_store_to_worker_browser
                await inject_cookie_store_to_worker_browser("手动 Cookie 注入")
            except Exception as e:
                logger.debug("cookie 注入后同步 Worker 浏览器失败: %s", e)
    return injected, method, json_written, user_id


def _build_inject_success_response(
    injected: int, total_parsed: int, method: str, errors: list[str],
    user_id: str = "default",
) -> JSONResponse:
    """构建注入成功的响应，并自动启动会话管理

    Args:
        user_id: 注入时识别出的用户 ID。必须传给 make_auth_response 签发
                 session_token，否则 /api/auth/me 无法识别登录态，前端会
                 被路由守卫重定向回登录页（issue: 注入cookie登录后未进入系统）
    """
    result = {
        "ok": True,
        "injected": injected,
        "total_parsed": total_parsed,
        "method": method,
        "message": f"成功注入 {injected} 个 cookie（方式: {method}）",
    }
    if errors:
        result["errors"] = errors[:5]
    # 注入成功后自动启动会话管理：与登录入口行为一致
    try:
        from xianyu_hunter.web.services.session_starter import trigger_session_start
        trigger_session_start()
    except Exception as e:
        logger.debug("自动启动会话失败: %s", e)
    # 签发多用户 session_token：与浏览器登录路径一致（unified_login.py）
    # 不传 session_token 时 make_auth_response 会回退到全局 web_token，
    # /api/auth/me 的 verify_session(web_token) 返回 None → 查 cookies_default.json
    # → 找不到 cookies_{user_id}.json → logged_in=False → 重定向回登录页
    session_token = None
    try:
        from xianyu_hunter.web.services.user_manager import get_user_manager
        session_token = get_user_manager().issue_session(user_id)
    except Exception as e:
        logger.warning("签发 session_token 失败，降级到全局 web_token: %s", e)
    return make_auth_response(result, session_token=session_token)


@router.post("/cookie")
async def inject_cookie(cookie_string: str = Form(...)) -> JSONResponse:
    """手动注入闲鱼 Cookie

    Args:
        cookie_string: 格式如 "_m_h5_tk=abc123; cookie2=xyz789; unb=uid123"

    注入策略（按优先级尝试）：
    1. 直接写入 SQLite（浏览器未运行时成功）
    2. 通过运行中的浏览器 BrowserManager.add_cookies() 注入（浏览器运行时使用）
    3. 仅写入 JSON 文件（最终兜底，下次浏览器启动时可读取）
    """
    if not cookie_string or not cookie_string.strip():
        return JSONResponse(content={"ok": False, "error": "Cookie 字符串为空"})

    cfg = get_config()
    cookie_db = get_browser_data_dir(cfg.browser.user_data_dir) / "Default" / "Network" / "Cookies"

    # 解析 cookie 字符串为 (name, value) 对
    cookies_to_inject = _parse_cookie_string_to_pairs(cookie_string)

    if not cookies_to_inject:
        return JSONResponse(content={"ok": False, "error": "未能解析出有效的 cookie 键值对"})

    # 确保 Cookies 数据库目录存在
    cookie_db.parent.mkdir(parents=True, exist_ok=True)

    injected = 0
    errors: list[str] = []
    method = "unknown"
    browser_error = None

    # 策略1：优先通过浏览器上下文注入（Chromium 加密存储，SQLite 明文写入无效）
    try:
        injected, errors, method = await _inject_via_browser(cookies_to_inject)
    except Exception as e:
        browser_error = str(e)
        # 浏览器上下文不可用，尝试 SQLite 直写（仅当浏览器完全未启动时可行）
        try:
            injected, errors = _inject_to_sqlite(cookie_db, cookies_to_inject)
            method = "sqlite_direct"
            logger.info("浏览器不可用，已通过 SQLite 直写 %d 个 cookie", injected)
        except Exception as sqlite_err:
            logger.warning("SQLite 直写也失败: %s", sqlite_err)

    # 策略2：写入 JSON 兜底（即使 browser+sqlite 都失败，JSON 兜底也能独立工作）
    injected, method, _, user_id = await _write_json_fallback_and_sync(cookies_to_inject, injected, method)

    # 构建响应
    if injected > 0:
        return _build_inject_success_response(
            injected, len(cookies_to_inject), method, errors, user_id,
        )

    # 全部失败
    error_detail = browser_error or "浏览器不可用"
    return JSONResponse(content={
        "ok": False,
        "error": f"Cookie 注入失败: {error_detail}",
        "hint": "请使用「扫码登录」方式，或先停止服务再注入 Cookie",
    })


@router.get("/cookie/domains")
def list_cookie_domains() -> dict:
    """列出当前 browser-data 中已有的 cookie 域名和关键字（用于调试）"""
    cfg = get_config()
    cookie_db = get_browser_data_dir(cfg.browser.user_data_dir) / "Default" / "Network" / "Cookies"
    if not cookie_db.exists():
        return {"exists": False, "domains": [], "key_names": []}
    try:
        with sqlite3.connect(f"file:{cookie_db}?mode=ro", uri=True) as conn:
            domains = [r[0] for r in conn.execute("SELECT DISTINCT host_key FROM cookies").fetchall()]
            key_names = [r[0] for r in conn.execute(
                "SELECT DISTINCT name FROM cookies WHERE host_key LIKE '%goofish%' OR host_key LIKE '%taobao%'"
            ).fetchall()]
        return {"exists": True, "domains": domains, "key_names": key_names}
    except Exception as e:
        return {"exists": True, "error": str(e), "domains": [], "key_names": []}


# ============== Cookie 文件解析 ==============

def _parse_netscape_cookies(text: str) -> list[dict]:
    """解析 Netscape 格式的 cookie 文件

    格式：每行 tab 分隔，字段为 domain \\t include_subdomains \\t path \\t secure \\t expiry \\t name \\t value
    以 # 开头的行为注释，空行跳过。
    这是浏览器扩展（如 Cookie Editor、EditThisCookie）最常用的导出格式。
    """
    cookies = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            domain = parts[0]
            path = parts[2]
            name = parts[5]
            value = parts[6]
            if name and value:
                cookies.append({
                    "name": name,
                    "value": value,
                    "domain": domain,
                    "path": path or "/",
                })
    return cookies


def _extract_cookie_list_from_object(data: dict) -> list | None:
    """从 JSON 对象的常见字段中提取 cookie 数组

    支持 "cookies"/"data"/"items" 字段名（不同扩展导出格式不一致）。
    """
    for key in ("cookies", "data", "items"):
        if key in data and isinstance(data[key], list):
            return data[key]
    return None


def _parse_single_json_cookie(item: object) -> dict | None:
    """解析单个 JSON cookie 条目，无效条目返回 None"""
    if not isinstance(item, dict):
        return None
    name = item.get("name", "")
    value = item.get("value", "")
    if not name or not value:
        return None
    return {
        "name": name,
        "value": value,
        "domain": item.get("domain", _DEFAULT_DOMAIN),
        "path": item.get("path", "/"),
    }


def _parse_json_cookies(text: str) -> list[dict]:
    """解析 JSON 格式的 cookie 数据

    支持两种常见格式：
    1. 数组格式：[{"name":"x","value":"y","domain":".goofish.com",...}, ...]
    2. 对象格式：{"cookies": [...]}
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []

    # 如果是对象，尝试从常见字段中提取数组
    if isinstance(data, dict):
        extracted = _extract_cookie_list_from_object(data)
        if extracted is None:
            return []
        data = extracted

    if not isinstance(data, list):
        return []

    cookies = []
    for item in data:
        parsed = _parse_single_json_cookie(item)
        if parsed:
            cookies.append(parsed)
    return cookies


def _parse_header_cookies(text: str) -> list[dict]:
    """解析 Header 字符串格式的 cookie（name=value; name2=value2）"""
    cookies = []
    for line in text.split("\n"):
        for part in line.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            name, _, value = part.partition("=")
            name = name.strip()
            value = value.strip()
            if name and value:
                cookies.append({
                    "name": name,
                    "value": value,
                    "domain": _DEFAULT_DOMAIN,
                    "path": "/",
                })
    return cookies


def _parse_cookie_file(text: str) -> list[dict]:
    """自动识别并解析 cookie 文件格式

    优先级：Netscape > JSON > Header 字符串
    """
    # 先尝试 Netscape 格式（有 tab 分隔的特征行）
    netscape_cookies = _parse_netscape_cookies(text)
    if netscape_cookies:
        logger.info("识别为 Netscape 格式，解析到 %d 个 cookie", len(netscape_cookies))
        return netscape_cookies

    # 再尝试 JSON 格式
    json_cookies = _parse_json_cookies(text)
    if json_cookies:
        logger.info("识别为 JSON 格式，解析到 %d 个 cookie", len(json_cookies))
        return json_cookies

    # 最后尝试 Header 字符串格式
    header_cookies = _parse_header_cookies(text)
    if header_cookies:
        logger.info("识别为 Header 字符串格式，解析到 %d 个 cookie", len(header_cookies))
        return header_cookies

    return []


# 只导入闲鱼相关的域名（引用常量避免重复字面量）
_GOOFISH_DOMAINS = {
    _DOMAIN_GOOFISH, _DOMAIN_GOOFISH_DOT,
    _DOMAIN_TAOBAO, _DOMAIN_TAOBAO_DOT,
    _DOMAIN_ALIPAY, _DOMAIN_ALIPAY_DOT,
    _DOMAIN_LOGIN_TAOBAO, _DOMAIN_LOGIN_TAOBAO_DOT,
}


def _filter_goofish_cookies(cookies: list[dict]) -> list[dict]:
    """过滤出闲鱼/淘宝/支付宝相关的 cookie"""
    filtered = []
    for c in cookies:
        domain = c.get("domain", "").lower().lstrip(".")
        # 匹配 goofish / taobao / alipay 及其子域名；也保留没有明确域名但
        # 名字匹配闲鱼关键 cookie 的条目（S1871: 两分支均 append，合并条件）
        if (any(domain == d.lstrip(".") or domain.endswith(d.lstrip("."))
                for d in _GOOFISH_DOMAINS)
                or not c.get("domain") or c["domain"] == _DEFAULT_DOMAIN):
            filtered.append(c)
    return filtered


async def _write_import_json_fallback_and_sync(
    goofish_cookies: list[dict],
    cookies_to_inject: list[tuple[str, str]],
    injected: int,
    method: str,
    source: str,
) -> tuple[int, str, str]:
    """写入 JSON 兜底并同步 CookieRotator 层状态与 Worker 浏览器（文件导入专用）

    Returns:
        (injected, method, user_id)
        user_id 用于上层签发多用户 session_token
    """
    # 默认 user_id，识别失败时降级
    user_id = "default"
    if cookies_to_inject:
        # 动态识别 user_id：文件导入场景也支持多账号，不再硬编码 "default"
        user_id = _identify_user_from_cookies(goofish_cookies)
        # 文件导入也用 merge_cookies：用户从浏览器导出的 Netscape/JSON 文件
        # 通常包含完整 cookie 集，合并写更安全（保留旧的同名 cookie 的额外字段如 expires）
        json_written = get_cookie_store().merge_cookies(goofish_cookies, method=source, user_id=user_id)
        # 必须检查 json_written：export_cookies 返回 False 时 JSON 未写入，
        # 不应报告 json_fallback 成功（修复原有 BUG：原代码未检查 json_written）
        if json_written and injected == 0:
            injected = len(cookies_to_inject)
            method = "json_fallback"
        # 同步 CookieRotator 层状态，避免 /cookies/layers 仍显示失效
        if json_written:
            try:
                from xianyu_hunter.modules.login_orchestrator import sync_cookie_layers_from_json
                sync_cookie_layers_from_json()
            except Exception as e:
                logger.debug("cookie 导入后同步层状态失败: %s", e)
            try:
                from xianyu_hunter.web.services.cookie_runtime_sync import inject_cookie_store_to_worker_browser
                await inject_cookie_store_to_worker_browser("Cookie 文件导入")
            except Exception as e:
                logger.debug("cookie 导入后同步 Worker 浏览器失败: %s", e)
    return injected, method, user_id


def _build_import_success_response(
    injected: int, total_parsed: int, method: str, source: str, errors: list[str],
    user_id: str = "default",
) -> JSONResponse:
    """构建文件导入成功的响应，并自动启动会话管理

    Args:
        user_id: 导入时识别出的用户 ID，用于签发 session_token（同 _build_inject_success_response）
    """
    result = {
        "ok": True,
        "injected": injected,
        "total_parsed": total_parsed,
        "method": method,
        "source": source,
        "message": f"成功导入 {injected} 个 Cookie（来源: {source}, 方式: {method}）",
    }
    if errors:
        result["errors"] = errors[:5]
    # 导入成功后自动启动会话管理：与登录入口行为一致
    try:
        from xianyu_hunter.web.services.session_starter import trigger_session_start
        trigger_session_start()
    except Exception as e:
        logger.debug("自动启动会话失败: %s", e)
    # 签发多用户 session_token：原因同 _build_inject_success_response
    session_token = None
    try:
        from xianyu_hunter.web.services.user_manager import get_user_manager
        session_token = get_user_manager().issue_session(user_id)
    except Exception as e:
        logger.warning("签发 session_token 失败，降级到全局 web_token: %s", e)
    return make_auth_response(result, session_token=session_token)


async def _do_inject_cookies(cookies: list[dict], source: str = "file") -> JSONResponse:
    """通用 cookie 注入逻辑（被文件导入和手动注入共用）

    Args:
        cookies: 已解析的 cookie 列表 [{name, value, domain, path}, ...]
        source: 来源标识（file / path / cookie）
    """
    if not cookies:
        return JSONResponse(content={"ok": False, "error": "未找到有效的闲鱼 Cookie"})

    # 过滤出闲鱼相关的 cookie
    goofish_cookies = _filter_goofish_cookies(cookies)
    if not goofish_cookies:
        # 如果过滤后为空，保留原始 cookie（用户可能用了非标准域名）
        goofish_cookies = cookies

    cfg = get_config()
    cookie_db = get_browser_data_dir(cfg.browser.user_data_dir) / "Default" / "Network" / "Cookies"
    cookie_db.parent.mkdir(parents=True, exist_ok=True)

    # 转换为 (name, value) 元组列表供注入函数使用
    cookies_to_inject = [(c["name"], c["value"]) for c in goofish_cookies]

    injected = 0
    errors: list[str] = []
    method = "unknown"
    browser_error = None

    # 策略1：通过浏览器上下文注入
    try:
        injected, errors, method = await _inject_via_browser(cookies_to_inject)
    except Exception as e:
        browser_error = str(e)
        try:
            injected, errors = _inject_to_sqlite(cookie_db, cookies_to_inject)
            method = "sqlite_direct"
        except Exception:
            pass

    # 策略2：写入 JSON（即使 browser+sqlite 都失败，JSON 兜底也能独立工作）
    injected, method, user_id = await _write_import_json_fallback_and_sync(
        goofish_cookies, cookies_to_inject, injected, method, source,
    )

    if injected > 0:
        return _build_import_success_response(
            injected, len(goofish_cookies), method, source, errors, user_id,
        )

    return JSONResponse(content={
        "ok": False,
        "error": f"Cookie 注入失败: {browser_error or '浏览器不可用'}",
        "hint": "请确保浏览器已关闭后重试，或使用手动粘贴 Cookie 方式",
    })


@router.post("/cookie/file")
async def import_cookie_file(file: UploadFile = File(...)) -> JSONResponse:
    """从上传的 cookie 文件导入

    支持格式：Netscape (cookies.txt)、JSON、Header 字符串
    """
    if not file.filename:
        return JSONResponse(content={"ok": False, "error": "未选择文件"})

    try:
        content = await file.read()
        text = content.decode("utf-8", errors="replace")
    except Exception as e:
        return JSONResponse(content={"ok": False, "error": f"读取文件失败: {e}"})

    if not text.strip():
        return JSONResponse(content={"ok": False, "error": "文件内容为空"})

    cookies = _parse_cookie_file(text)
    if not cookies:
        return JSONResponse(content={
            "ok": False,
            "error": "无法识别文件格式，请使用 Netscape (cookies.txt) 或 JSON 格式",
        })

    return await _do_inject_cookies(cookies, source=f"file:{file.filename}")


@router.post("/cookie/path")
async def import_cookie_path(file_path: str = Form(...)) -> JSONResponse:
    """从服务器本地路径读取 cookie 文件并导入

    适用于本机部署场景，用户可以直接指定 cookie 文件路径。
    限制：仅允许读取项目根目录及 browser-data 目录下的文件，防止路径穿越。
    """
    if not file_path or not file_path.strip():
        return JSONResponse(content={"ok": False, "error": "文件路径为空"})

    path = Path(file_path.strip()).expanduser().resolve()

    # 路径穿越防护：仅允许项目根目录和 browser-data 目录下的文件
    from xianyu_hunter.config import get_settings
    project_root = get_settings().project_root.resolve()
    browser_data_dir = (project_root / "browser-data").resolve()
    allowed_dirs = [project_root, browser_data_dir]
    if not any(str(path).startswith(str(d)) for d in allowed_dirs):
        return JSONResponse(content={"ok": False, "error": "路径不在允许范围内（仅限项目根目录和 browser-data 目录）"})

    if not path.exists():
        return JSONResponse(content={"ok": False, "error": f"文件不存在: {path}"})
    if not path.is_file():
        return JSONResponse(content={"ok": False, "error": f"路径不是文件: {path}"})
    if path.stat().st_size > 10 * 1024 * 1024:
        return JSONResponse(content={"ok": False, "error": "文件过大（超过 10MB）"})

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return JSONResponse(content={"ok": False, "error": f"读取文件失败: {e}"})

    cookies = _parse_cookie_file(text)
    if not cookies:
        return JSONResponse(content={
            "ok": False,
            "error": _UNRECOGNIZED_FORMAT_ERROR,
        })

    return await _do_inject_cookies(cookies, source=f"path:{path.name}")


@router.get("/cookie/saved")
def get_saved_cookie_info(request: Request) -> dict:
    """获取已保存的 cookie 摘要信息（供前端显示上次登录状态）

    返回 cookie 数量、关键 cookie 名称列表、最后导出时间、登录方式。
    不返回 cookie 值（安全考虑）。

    多用户隔离：从 request.state.user_id 获取当前登录用户，按 user_id 读取
    cookies_{user_id}.json。
    """
    cookie_user_id = getattr(request.state, "user_id", None) or "default"
    store = get_cookie_store()
    store.invalidate_cache(cookie_user_id)
    data = store._read_json(cookie_user_id)
    if not data or not data.get("cookies"):
        return {"has_cookies": False, "logged_in": False}

    names = [c["name"] for c in data["cookies"] if c.get("name")]
    from xianyu_hunter.web.services.cookie_store import _GOOFISH_KEY_COOKIES
    has_key = bool(_GOOFISH_KEY_COOKIES & set(names))

    return {
        "has_cookies": True,
        "logged_in": has_key,
        "cookie_count": data.get("cookie_count", len(names)),
        "key_cookies_found": sorted(_GOOFISH_KEY_COOKIES & set(names)),
        "exported_at": data.get("exported_at", 0),
        "method": data.get("method", "unknown"),
        "all_names": sorted(names),
    }


# ============== fetch_cookie_keys 辅助函数（从原方法提取，保持功能不变） ==============


def _copy_locked_cookie_file(src: str, dst: str) -> bool:
    """尝试复制被锁定的 Cookie DB 文件

    优先用 Windows API 绕过共享锁定，失败时回退 shutil 普通复制。
    """
    # 策略1：Windows ctypes CreateFile + ReadFile（可读取被其他进程以共享模式打开的文件）
    try:
        import ctypes
        from ctypes import wintypes

        GENERIC_READ = 0x80000000
        FILE_SHARE_READ = 0x00000001
        FILE_SHARE_WRITE = 0x00000002
        OPEN_EXISTING = 3
        INVALID_HANDLE_VALUE = -1

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        src_handle = kernel32.CreateFileW(
            src, GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None, OPEN_EXISTING, 0, None,
        )
        if src_handle == INVALID_HANDLE_VALUE:
            return False  # 回退到普通复制

        try:
            with open(dst, "wb") as out_f:
                buf = ctypes.create_string_buffer(64 * 1024)  # 64KB chunks
                n_read = wintypes.DWORD()
                while True:
                    ok = kernel32.ReadFile(
                        src_handle, buf, len(buf), ctypes.byref(n_read), None,
                    )
                    if not ok or n_read.value == 0:
                        break
                    out_f.write(buf.raw[:n_read.value])
            return True
        finally:
            kernel32.CloseHandle(src_handle)
    except Exception:
        pass

    # 策略2：普通 shutil 复制（文件未被锁定时可用）
    try:
        shutil.copy2(src, dst)
        return True
    # S5713: PermissionError 是 OSError 的子类，仅保留父类
    except OSError:
        return False


def _list_chrome_profile_cookie_dbs(local_appdata: str) -> list[tuple[Path, bool]]:
    """列出 Chrome 所有 Profile 下的 Cookie DB（直接读，无需复制）

    为什么独立：原 _build_cookie_db_candidates 中 if+if+for+if+if 多层嵌套
    是认知复杂度主要来源。Chrome Profile 遍历逻辑独立后主函数更清晰。
    跳过非目录和系统目录（如 .DS_Store、Lock File 等以 . 开头的条目）。
    """
    if not local_appdata:
        return []
    chrome_base = Path(local_appdata) / "Google" / "Chrome" / "User Data"
    if not chrome_base.exists():
        return []

    result: list[tuple[Path, bool]] = []
    for entry in sorted(os.listdir(chrome_base)):
        profile_dir = chrome_base / entry
        # 跳过非目录和系统目录
        if not profile_dir.is_dir() or entry.startswith("."):
            continue
        db = profile_dir / "Network" / "Cookies"
        if db.exists():
            result.append((db, False))
    return result


def _build_cookie_db_candidates(cfg) -> list[tuple[Path, bool]]:
    """构建候选 Cookie DB 路径列表（按优先级排序）

    顺序：Chrome 所有 Profile → Edge Default → 项目 browser-data
    Edge 可能被锁定，标记为需要复制后读取。
    """
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    candidates: list[tuple[Path, bool]] = []

    # 1. Chrome 所有 Profile（直接读）- 优先于 Edge，因为用户更常用 Chrome 登录闲鱼
    candidates.extend(_list_chrome_profile_cookie_dbs(local_appdata))

    # 2. Edge Default Profile（可能被锁定，用复制方式读）
    if local_appdata:
        edge_db = (
            Path(local_appdata)
            / "Microsoft"
            / "Edge"
            / "User Data"
            / "Default"
            / "Network"
            / "Cookies"
        )
        candidates.append((edge_db, True))  # True 表示尝试复制再读

    # 3. 项目 browser-data（最后才读，因为可能是旧数据）
    project_db = get_browser_data_dir(cfg.browser.user_data_dir) / "Default" / "Network" / "Cookies"
    candidates.append((project_db, False))

    return candidates


def _cookies_table_exists(conn: sqlite3.Connection) -> bool:
    """检查 cookies 表是否存在（项目 browser-data 可能是 Playwright 创建的空库）

    为什么独立：原 _query_cookie_db 中 try/except + if 嵌套推高了认知复杂度，
    拆分后主函数只需 if not _cookies_table_exists: return 即可。
    """
    try:
        return conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='cookies'"
        ).fetchone() is not None
    except sqlite3.OperationalError:
        return False  # 数据库损坏 → 视为无表，静默跳过


def _process_cookie_row(
    name: str, value: str, enc_value: bytes | None, result: dict[str, str],
) -> bool:
    """处理单行 cookie：明文优先，否则检测 v20 加密格式

    返回是否检测到 v20 加密（用于上层引导用户改用 CDP 方式）。
    为什么独立：原 for+if/elif+if 三层嵌套是认知复杂度的主要来源。
    """
    if name in result:
        return False
    # value 非空 → 明文 cookie，直接使用
    if value:
        result[name] = value
        return False
    # value 为空但 encrypted_value 存在 → 检测加密格式
    if not enc_value:
        return False
    enc_bytes = bytes(enc_value)
    # v10 等旧格式理论上可解密，但 fetch-keys 场景不依赖解密
    # 留空让后续 CDP 路径或手动输入兜底
    return enc_bytes[:3] == b"v20"


def _query_cookie_db(db_path: Path, requested_keys: list[str]) -> tuple[dict[str, str], bool]:
    """从 SQLite DB 中查询目标 cookie，返回 ({name: value}, v20_detected)

    Chrome v20 加密将值存储在 encrypted_value 列，value 列为空。
    无法离线解密 v20，因此跳过空值并标记 v20_detected。
    """
    result: dict[str, str] = {}
    v20_detected = False
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        if not _cookies_table_exists(conn):
            return result, v20_detected  # 无表或数据库损坏 → 静默跳过

        placeholders = ",".join(["?"] * len(requested_keys))
        rows = conn.execute(
            f"""
            SELECT name, value, encrypted_value FROM cookies
            WHERE name IN ({placeholders})
              AND (host_key LIKE '%goofish.com%'
                   OR host_key LIKE '%taobao.com%'
                   OR host_key LIKE '%h5.m.taobao%'
                   OR host_key LIKE '%h5api.m.taobao%')
            """,
            requested_keys,
        ).fetchall()
        for name, value, enc_value in rows:
            if _process_cookie_row(name, value, enc_value, result):
                v20_detected = True
    return result, v20_detected


def _cleanup_temp_db_copy(temp_copy: str | None) -> None:
    """清理临时复制的 DB 文件（忽略清理失败）"""
    if temp_copy and os.path.exists(temp_copy):
        try:
            os.unlink(temp_copy)
        except OSError:
            pass


# 用 sentinel 区分"不更新 last_error"与"将 last_error 置为 None"（如 no such table 情况）
_LAST_ERROR_NO_UPDATE = object()


def _try_single_cookie_candidate(
    cookie_db: Path,
    try_copy: bool,
    requested_keys: list[str],
) -> tuple[dict[str, str] | None, bool, object | str | None]:
    """尝试单个候选 DB，返回 (result, v20_detected, last_error_update)

    last_error_update 为 _LAST_ERROR_NO_UPDATE 表示不更新外部 last_error，
    其他值（含 None）表示用该值更新 last_error。
    """
    if not cookie_db.exists():
        return None, False, _LAST_ERROR_NO_UPDATE

    actual_db = cookie_db
    temp_copy = None
    try:
        # 如果需要复制（如 Edge 正在运行时），先复制到临时文件
        if try_copy:
            fd, temp_copy = tempfile.mkstemp(suffix=".db")
            os.close(fd)
            _copy_locked_cookie_file(str(cookie_db), temp_copy)
            actual_db = Path(temp_copy)

        result, v20_detected = _query_cookie_db(actual_db, requested_keys)
        # 查询成功（无论有无结果）都不更新 last_error
        return result, v20_detected, _LAST_ERROR_NO_UPDATE

    except sqlite3.OperationalError as e:
        err_msg = str(e).lower()
        if "locked" in err_msg or "unable to open" in err_msg:
            return None, False, f"{cookie_db.parent.parent.name} 浏览器正在运行，数据库被锁定"
        elif "no such table" in err_msg:
            # 技术性错误，不展示给用户（空库/表不存在已静默跳过）
            return None, False, None
        else:
            return None, False, str(e)
    except PermissionError:
        return None, False, f"{cookie_db.parent.parent.name} 文件被占用（请关闭浏览器后重试）"
    except Exception as e:
        return None, False, str(e)
    finally:
        _cleanup_temp_db_copy(temp_copy)


def _try_sqlite_cookie_candidates(
    candidates: list[tuple[Path, bool]],
    requested_keys: list[str],
) -> tuple[JSONResponse | None, str | None, bool]:
    """遍历 SQLite 候选 DB，返回 (成功响应, 最后错误, 是否检测到v20)

    成功时返回 JSONResponse；全部失败时返回 None 和错误状态。
    """
    last_error: str | None = None
    any_v20_detected = False
    for cookie_db, try_copy in candidates:
        result, v20_detected, last_error_update = _try_single_cookie_candidate(
            cookie_db, try_copy, requested_keys
        )
        if v20_detected:
            any_v20_detected = True
        if last_error_update is not _LAST_ERROR_NO_UPDATE:
            last_error = last_error_update  # type: ignore[assignment]
        if result:
            logger.info(
                "从 %s 成功获取 %d 个 cookie 值",
                cookie_db,
                len(result),
            )
            return make_auth_response({
                "ok": True,
                "cookies": result,
                "found": list(result.keys()),
                "missing": [k for k in requested_keys if k not in result],
                "source": str(cookie_db),
            }), last_error, any_v20_detected
    return None, last_error, any_v20_detected


def _filter_json_cookies_for_fetch(
    cookies: list[dict], requested_keys: list[str],
) -> dict[str, str]:
    """从 JSON cookie 列表中筛选目标 key 且域名匹配的 cookie

    为什么独立：原 _fallback_to_cookie_store_json 中 for + 多重 and 条件 + 嵌套 if
    是认知复杂度的主要来源，拆分后主函数只处理 IO 和响应构建。
    """
    from xianyu_hunter.web.services.cookie_store import is_test_cookie
    result: dict[str, str] = {}
    for c in cookies:
        name = c.get("name", "")
        domain = c.get("domain", "")
        value = c.get("value", "")
        # S1066: 合并外层与"未填充"两个 if，避免嵌套
        if (name in requested_keys and any(
            d in domain for d in (_DOMAIN_GOOFISH, _DOMAIN_TAOBAO)
        ) and name not in result):
            # 过滤掉测试数据（unb=123456 / cookie2=abc 等）
            if is_test_cookie(name, value):
                logger.warning("fetch_cookie_keys: 跳过测试 Cookie %s=%s", name, value)
                continue
            result[name] = value
    return result


def _fallback_to_cookie_store_json(requested_keys: list[str], user_id: str = "default") -> JSONResponse | None:
    """JSON 降级：当系统浏览器 v20 加密不可读时，回退到之前浏览器登录保存的明文

    多用户隔离：按 user_id 读取 cookies_{user_id}.json。
    """
    try:
        store = get_cookie_store()
        store.invalidate_cache(user_id)
        json_data = store._read_json(user_id)
        if not json_data or not json_data.get("cookies"):
            return None

        json_result = _filter_json_cookies_for_fetch(json_data["cookies"], requested_keys)
        if not json_result:
            return None

        logger.info(
            "SQLite 不可读，从 CookieStore JSON 降级获取 %d 个 cookie 值: %s",
            len(json_result), list(json_result.keys()),
        )
        return make_auth_response({
            "ok": True,
            "cookies": json_result,
            "found": list(json_result.keys()),
            "missing": [k for k in requested_keys if k not in json_result],
            "source": "cookie_store_json_fallback",
            "hint": "系统浏览器 Cookie 加密不可读，已回退到上次保存的 Cookie。如需更新，请使用「浏览器登录」功能重新扫码登录。",
        })
    except Exception as e:
        logger.warning("CookieStore JSON 降级读取失败: %s", e)
    return None


def _filter_pw_cookies_for_cdp(
    pw_cookies: list[dict], requested_keys: list[str],
) -> dict[str, str]:
    """从 Playwright cookie 列表中筛选目标 key 且域名匹配的 cookie

    为什么独立：原 _fallback_to_playwright_cdp 中 try + if + for + 多重 and 条件
    嵌套推高认知复杂度，拆分后主函数只处理 IO 和响应构建。
    """
    result: dict[str, str] = {}
    for c in pw_cookies:
        name = c.get("name", "")
        domain = c.get("domain", "")
        # S1066: 合并外层与"未填充"两个 if，避免嵌套
        if (name in requested_keys and any(
            d in domain for d in (_DOMAIN_GOOFISH, _DOMAIN_TAOBAO)
        ) and name not in result):
            result[name] = c.get("value", "")
    return result


async def _fallback_to_playwright_cdp(
    container: Container, requested_keys: list[str],
) -> JSONResponse | None:
    """Playwright CDP 兜底：读取项目浏览器内存中的 cookie"""
    try:
        browser = container.browser
        if not browser or not browser._context:
            return None

        pw_cookies = await browser.get_cookies()
        cdp_result = _filter_pw_cookies_for_cdp(pw_cookies, requested_keys)
        logger.info(
            "Playwright CDP 兜底: 读取到 %d 个 cookie，匹配 %d 个目标 key: %s",
            len(pw_cookies), len(cdp_result), list(cdp_result.keys()),
        )
        if not cdp_result:
            return None
        return make_auth_response({
            "ok": True,
            "cookies": cdp_result,
            "found": list(cdp_result.keys()),
            "missing": [k for k in requested_keys if k not in cdp_result],
            "source": "playwright_cdp",
        })
    except Exception as e:
        logger.warning("Playwright CDP 兜底也失败: %s", e)
    return None


def _build_fetch_keys_failure_response(
    requested_keys: list[str],
    any_v20_detected: bool,
    last_error: str | None,
    container: Container,
) -> JSONResponse:
    """所有候选都失败时，构建详细的错误提示响应"""
    hints = []

    # v20 加密检测：Chrome/Edge 新版使用 app-bound encryption，无法离线解密
    if any_v20_detected:
        hints.append("检测到 Chrome/Edge 使用 v20 应用绑定加密，无法离线读取 Cookie")
        hints.append("请改用「浏览器登录」功能（弹出 Playwright 窗口扫码登录），或手动粘贴 Cookie")

    # 诊断 CDP 状态
    try:
        browser = container.browser
        if browser is None:
            hints.append("Web 进程未启动浏览器（非 --with-scheduler 模式）")
        elif browser._context is None:
            hints.append("浏览器 context 未初始化（CDP 连接可能失败）")
        else:
            hints.append("CDP 浏览器已连接但未找到 goofish.com 的 cookie，请在「浏览器登录」页面登录闲鱼")
    except Exception:
        pass

    if last_error:
        hints.append(last_error)
    hints.append("建议：1) 点击「浏览器登录」在 CDP Edge 中登录 goofish.com；2) 或手动粘贴 Cookie")

    return JSONResponse(content={
        "ok": False,
        "cookies": {},
        "error": f"未找到闲鱼 Cookie（{', '.join(requested_keys)}）",
        "hint": "；".join(hints),
    })


@router.get("/cookie/fetch-keys")
async def fetch_cookie_keys(request: Request, keys: str = "", container: Container = Depends(get_container)) -> JSONResponse:
    """从浏览器读取指定 cookie key 的值（用于前端自动填充 _m_h5_tk 等）

    读取顺序（优先级从高到低）：
    1. **Playwright CDP**（推荐）：通过已连接的系统 Edge 浏览器实时读取，无需复制文件
    2. 项目 browser-data 目录（服务启动的浏览器实例）
    3. 系统 Chrome 所有 Profile
    4. 系统 Edge（复制文件绕过锁定）

    Args:
        keys: 逗号分隔的 cookie name 列表，如 "_m_h5_tk,cookie2,sgcookie,unb"

    多用户隔离：JSON 降级时按 request.state.user_id 读取对应 cookie 文件。
    """
    requested_keys = [k.strip() for k in keys.split(",") if k.strip()] if keys else []
    if not requested_keys:
        return JSONResponse(content={"ok": False, "error": "未指定要查询的 cookie key"})

    cookie_user_id = getattr(request.state, "user_id", None) or "default"

    # ===== 策略：系统浏览器 SQLite（最新登录）→ JSON 降级（v20加密时）→ CDP 兜底 =====
    # 系统浏览器优先：用户期望读取浏览器最新登录状态
    # JSON 降级：当系统浏览器 v20 加密不可读时，回退到之前浏览器登录保存的明文
    cfg = get_config()
    candidates = _build_cookie_db_candidates(cfg)

    sqlite_response, last_error, any_v20_detected = _try_sqlite_cookie_candidates(
        candidates, requested_keys,
    )
    if sqlite_response is not None:
        return sqlite_response

    # ===== SQLite 候选都失败 → JSON 降级（v20 加密时读取之前保存的明文） =====
    json_response = _fallback_to_cookie_store_json(requested_keys, cookie_user_id)
    if json_response is not None:
        return json_response

    # ===== JSON 也不可用 → Playwright CDP 兜底（读取项目浏览器的 cookie） =====
    cdp_response = await _fallback_to_playwright_cdp(container, requested_keys)
    if cdp_response is not None:
        return cdp_response

    # 所有候选都失败 → 构建详细错误提示
    return _build_fetch_keys_failure_response(
        requested_keys, any_v20_detected, last_error, container,
    )
