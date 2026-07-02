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
import sqlite3
import time
from pathlib import Path

from fastapi import APIRouter, Depends, Form, UploadFile, File
from fastapi.responses import JSONResponse

from xianyu_hunter.container import Container
from xianyu_hunter.infra.yaml_config import get_config
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.routes.auth_helpers import make_auth_response
from xianyu_hunter.web.services.cookie_db import init_cookie_table, upsert_cookie
from xianyu_hunter.web.services.cookie_store import get_cookie_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["cookie-inject"])

# S1192: 提取重复的域名常量，便于统一维护
# 注入时需同时覆盖淘宝系多域名（闲鱼共享淘宝认证）
_DOMAIN_GOOFISH = "goofish.com"
_DOMAIN_GOOFISH_DOT = ".goofish.com"
_DOMAIN_TAOBAO = "taobao.com"
_DOMAIN_TAOBAO_DOT = ".taobao.com"
_DOMAIN_ALIPAY = "alipay.com"
_DOMAIN_ALIPAY_DOT = ".alipay.com"
_DOMAIN_LOGIN_TAOBAO = "login.taobao.com"
_DOMAIN_LOGIN_TAOBAO_DOT = ".login.taobao.com"

_INJECT_DOMAINS = (
    _DOMAIN_GOOFISH_DOT, _DOMAIN_GOOFISH,
    _DOMAIN_TAOBAO_DOT, _DOMAIN_ALIPAY_DOT,
)
_DEFAULT_DOMAIN = _DOMAIN_GOOFISH_DOT


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
    cookie_db = Path(cfg.browser.user_data_dir) / "Default" / "Network" / "Cookies"

    # 解析 cookie 字符串为 (name, value) 对
    # 支持分隔符：; 或换行符（用户从浏览器DevTools复制时常见）
    cookies_to_inject = []
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
                cookies_to_inject.append((name, value))

    if not cookies_to_inject:
        return JSONResponse(content={"ok": False, "error": "未能解析出有效的 cookie 键值对"})

    # 确保 Cookies 数据库目录存在
    cookie_db.parent.mkdir(parents=True, exist_ok=True)

    injected = 0
    errors = []
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
    json_written = False
    if cookies_to_inject:
        json_written = get_cookie_store().export_cookies([
            {"name": n, "value": v, "domain": _DEFAULT_DOMAIN, "path": "/"}
            for n, v in cookies_to_inject
        ], method="cookie", user_id="default")
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

    # 构建响应
    if injected > 0:
        result = {
            "ok": True,
            "injected": injected,
            "total_parsed": len(cookies_to_inject),
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
        return make_auth_response(result)

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
    cookie_db = Path(cfg.browser.user_data_dir) / "Default" / "Network" / "Cookies"
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
        for key in ("cookies", "data", "items"):
            if key in data and isinstance(data[key], list):
                data = data[key]
                break
        else:
            return []

    if not isinstance(data, list):
        return []

    cookies = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = item.get("name", "")
        value = item.get("value", "")
        if not name or not value:
            continue
        cookies.append({
            "name": name,
            "value": value,
            "domain": item.get("domain", _DEFAULT_DOMAIN),
            "path": item.get("path", "/"),
        })
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
        # 匹配 goofish / taobao / alipay 及其子域名
        if any(domain == d.lstrip(".") or domain.endswith(d.lstrip("."))
               for d in _GOOFISH_DOMAINS):
            filtered.append(c)
        # 也保留没有明确域名但名字匹配闲鱼关键 cookie 的条目
        elif not c.get("domain") or c["domain"] == _DEFAULT_DOMAIN:
            filtered.append(c)
    return filtered


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
    cookie_db = Path(cfg.browser.user_data_dir) / "Default" / "Network" / "Cookies"
    cookie_db.parent.mkdir(parents=True, exist_ok=True)

    # 转换为 (name, value) 元组列表供注入函数使用
    cookies_to_inject = [(c["name"], c["value"]) for c in goofish_cookies]

    injected = 0
    errors = []
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
    if cookies_to_inject:
        json_written = get_cookie_store().export_cookies(goofish_cookies, method=source, user_id="default")
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

    if injected > 0:
        result = {
            "ok": True,
            "injected": injected,
            "total_parsed": len(goofish_cookies),
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
        return make_auth_response(result)

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
            "error": "无法识别文件格式，请使用 Netscape (cookies.txt) 或 JSON 格式",
        })

    return await _do_inject_cookies(cookies, source=f"path:{path.name}")


@router.get("/cookie/saved")
def get_saved_cookie_info() -> dict:
    """获取已保存的 cookie 摘要信息（供前端显示上次登录状态）

    返回 cookie 数量、关键 cookie 名称列表、最后导出时间、登录方式。
    不返回 cookie 值（安全考虑）。
    """
    store = get_cookie_store()
    store.invalidate_cache("default")
    data = store._read_json("default")
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


@router.get("/cookie/fetch-keys")
async def fetch_cookie_keys(keys: str = "", container: Container = Depends(get_container)) -> JSONResponse:
    """从浏览器读取指定 cookie key 的值（用于前端自动填充 _m_h5_tk 等）

    读取顺序（优先级从高到低）：
    1. **Playwright CDP**（推荐）：通过已连接的系统 Edge 浏览器实时读取，无需复制文件
    2. 项目 browser-data 目录（服务启动的浏览器实例）
    3. 系统 Chrome 所有 Profile
    4. 系统 Edge（复制文件绕过锁定）

    Args:
        keys: 逗号分隔的 cookie name 列表，如 "_m_h5_tk,cookie2,sgcookie,unb"
    """
    import os
    import shutil
    import tempfile

    requested_keys = [k.strip() for k in keys.split(",") if k.strip()] if keys else []
    if not requested_keys:
        return JSONResponse(content={"ok": False, "error": "未指定要查询的 cookie key"})

    # ===== 先尝试系统浏览器 SQLite（用户期望读取系统浏览器的最新登录状态） =====

    def _copy_locked_file(src: str, dst: str) -> bool:
        """尝试复制文件，优先用 Windows API 绕过共享锁定，失败时回退 shutil"""
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

    requested_keys = [k.strip() for k in keys.split(",") if k.strip()] if keys else []
    if not requested_keys:
        return JSONResponse(content={"ok": False, "error": "未指定要查询的 cookie key"})

    # ===== 策略：系统浏览器 SQLite（最新登录）→ JSON 降级（v20加密时）→ CDP 兜底 =====
    # 系统浏览器优先：用户期望读取浏览器最新登录状态
    # JSON 降级：当系统浏览器 v20 加密不可读时，回退到之前浏览器登录保存的明文
    cfg = get_config()

    local_appdata = os.environ.get("LOCALAPPDATA", "")

    # 候选 DB 路径列表：(路径, 是否尝试复制)
    candidates: list[tuple[Path, bool]] = []

    # 1. Chrome 所有 Profile（直接读）- 优先于 Edge，因为用户更常用 Chrome 登录闲鱼
    if local_appdata:
        chrome_base = Path(local_appdata) / "Google" / "Chrome" / "User Data"
        if chrome_base.exists():
            for entry in sorted(os.listdir(chrome_base)):
                profile_dir = chrome_base / entry
                db = profile_dir / "Network" / "Cookies"
                # 跳过非目录和系统目录
                if not profile_dir.is_dir() or entry.startswith("."):
                    continue
                if db.exists():
                    candidates.append((db, False))

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
        candidates.append((edge_db, True))  # True = 尝试复制再读

    # 3. 项目 browser-data（最后才读，因为可能是旧数据）
    project_db = Path(cfg.browser.user_data_dir) / "Default" / "Network" / "Cookies"
    candidates.append((project_db, False))

    def _query_db(db_path: Path) -> tuple[dict[str, str], bool]:
        """从 SQLite DB 中查询目标 cookie，返回 ({name: value}, v20_detected)

        Chrome v20 加密将值存储在 encrypted_value 列，value 列为空。
        无法离线解密 v20，因此跳过空值并标记 v20_detected。
        """
        result: dict[str, str] = {}
        v20_detected = False
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            # 先检查 cookies 表是否存在（项目 browser-data 可能是 Playwright 创建的空库）
            try:
                table_check = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='cookies'"
                ).fetchone()
                if not table_check:
                    return result, v20_detected  # 无表 → 静默跳过
            except sqlite3.OperationalError:
                return result, v20_detected  # 数据库损坏 → 静默跳过

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
                if name in result:
                    continue
                # value 非空 → 明文 cookie，直接使用
                if value:
                    result[name] = value
                # value 为空但 encrypted_value 存在 → 检测加密格式
                elif enc_value:
                    enc_bytes = bytes(enc_value) if enc_value else b""
                    if enc_bytes[:3] == b"v20":
                        v20_detected = True
                    # v10 等旧格式理论上可解密，但 fetch-keys 场景不依赖解密
                    # 留空让后续 CDP 路径或手动输入兜底
        return result, v20_detected

    # 逐个候选尝试
    last_error = None
    any_v20_detected = False
    for cookie_db, try_copy in candidates:
        if not cookie_db.exists():
            continue

        actual_db = cookie_db
        temp_copy = None
        try:
            # 如果需要复制（如 Edge 正在运行时），先复制到临时文件
            if try_copy:
                fd, temp_copy = tempfile.mkstemp(suffix=".db")
                os.close(fd)
                _copy_locked_file(str(cookie_db), temp_copy)
                actual_db = Path(temp_copy)

            result, v20_detected = _query_db(actual_db)
            if v20_detected:
                any_v20_detected = True

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
                })

        except sqlite3.OperationalError as e:
            err_msg = str(e).lower()
            if "locked" in err_msg or "unable to open" in err_msg:
                last_error = f"{cookie_db.parent.parent.name} 浏览器正在运行，数据库被锁定"
            elif "no such table" in err_msg:
                # 技术性错误，不展示给用户（空库/表不存在已静默跳过）
                last_error = None
            else:
                last_error = str(e)
        except PermissionError:
            last_error = f"{cookie_db.parent.parent.name} 文件被占用（请关闭浏览器后重试）"
        except Exception as e:
            last_error = str(e)
        finally:
            if temp_copy and os.path.exists(temp_copy):
                try:
                    os.unlink(temp_copy)
                except OSError:
                    pass

    # ===== SQLite 候选都失败 → JSON 降级（v20 加密时读取之前保存的明文） =====
    try:
        from xianyu_hunter.web.services.cookie_store import is_test_cookie
        store = get_cookie_store()
        store.invalidate_cache("default")
        json_data = store._read_json("default")
        if json_data and json_data.get("cookies"):
            json_result: dict[str, str] = {}
            for c in json_data["cookies"]:
                name = c.get("name", "")
                domain = c.get("domain", "")
                value = c.get("value", "")
                if name in requested_keys and any(
                    d in domain for d in (_DOMAIN_GOOFISH, _DOMAIN_TAOBAO)
                ):
                    if name not in json_result:
                        # 过滤掉测试数据（unb=123456 / cookie2=abc 等）
                        if is_test_cookie(name, value):
                            logger.warning(
                                "fetch_cookie_keys: 跳过测试 Cookie %s=%s",
                                name, value,
                            )
                            continue
                        json_result[name] = value
            if json_result:
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

    # ===== JSON 也不可用 → Playwright CDP 兜底（读取项目浏览器的 cookie） =====
    try:
        browser = container.browser
        if browser and browser._context:
            pw_cookies = await browser.get_cookies()
            cdp_result: dict[str, str] = {}
            for c in pw_cookies:
                name = c.get("name", "")
                domain = c.get("domain", "")
                if name in requested_keys and any(
                    d in domain for d in (_DOMAIN_GOOFISH, _DOMAIN_TAOBAO)
                ):
                    if name not in cdp_result:
                        cdp_result[name] = c.get("value", "")
            logger.info(
                "Playwright CDP 兜底: 读取到 %d 个 cookie，匹配 %d 个目标 key: %s",
                len(pw_cookies), len(cdp_result), list(cdp_result.keys()),
            )
            if cdp_result:
                return make_auth_response({
                    "ok": True,
                    "cookies": cdp_result,
                    "found": list(cdp_result.keys()),
                    "missing": [k for k in requested_keys if k not in cdp_result],
                    "source": "playwright_cdp",
                })
    except Exception as e:
        logger.warning("Playwright CDP 兜底也失败: %s", e)

    # 所有候选都失败 → 构建详细错误提示
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
