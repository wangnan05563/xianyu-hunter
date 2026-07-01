"""用户信息查询 API - 登录态检测 / 用户资料

端点：
- GET  /api/auth/me              当前登录用户信息（缓存）
- GET  /api/auth/me/refresh      强制后台刷新（不等完成）
- GET  /api/auth/cookie/health   轻量级 Cookie 健康检查（< 300ms，纯文件读取）
- POST /api/auth/logout          退出登录（清除 Cookie/会话/认证 token）
"""
from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from xianyu_hunter.container import Container
from xianyu_hunter.infra.yaml_config import get_config
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.services.auth_manager import get_auth_manager
from xianyu_hunter.web.routes.auth_helpers import make_auth_response
from xianyu_hunter.web.services.notification_engine import scan_and_notify
from xianyu_hunter.web.services.cookie_store import get_cookie_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth-query"])


def _check_cookies() -> bool:
    """检查闲鱼 Cookie 是否有效（JSON 优先，SQLite 兜底）

    CookieStore 内部优先读取 JSON 文件（登录子进程立即写入），
    JSON 不可用时回退到 SQLite 检查。
    """
    store = get_cookie_store()
    store.invalidate_cache()
    return store.has_valid_cookies()


@router.get("/me")
def auth_me(container: Container = Depends(get_container)):
    """返回当前登录用户信息（昵称/头像/user_id）

    实现策略：复用现有 cookie 探测 + 后台 Playwright 拉取
    - 同步部分：从持久化 cookies 立即判断 has_login（基于 cookie 存在性）
    - 异步部分：触发后台拉取 userinfo（首次 / 缓存过期时）
    """
    has_cookie = _check_cookies()

    am = get_auth_manager()
    info = am.get_userinfo()

    # 同步探测有 cookie 但缓存里 logged_in=False → 触发后台刷新
    if has_cookie and not info.get("logged_in"):
        am.trigger_refresh_userinfo_async()
    # 缓存过期 → 触发后台刷新
    if has_cookie and info.get("logged_in") and (time.time() - info.get("fetched_at", 0)) > am.USERINFO_TTL:
        am.trigger_refresh_userinfo_async()

    # 构建返回结果
    if has_cookie and not info.get("logged_in"):
        result = {
            "logged_in": True,
            "user_id": info.get("user_id", ""),
            "nick": info.get("nick", ""),
            "avatar_url": info.get("avatar_url", ""),
            "fetched_at": info.get("fetched_at", 0),
            "detecting": True,
        }
    else:
        result = {
            "logged_in": has_cookie and bool(info.get("logged_in")),
            "user_id": info.get("user_id", ""),
            "nick": info.get("nick", ""),
            "avatar_url": info.get("avatar_url", ""),
            "fetched_at": info.get("fetched_at", 0),
        }

    # 检测登录态掉线 → 生成业务通知（失败不影响主路径）
    scan_and_notify(container, auth_state=result)

    # 已登录时确保浏览器持有 xh_token 认证 cookie
    if result.get("logged_in"):
        return make_auth_response(result)

    return result


@router.post("/me/refresh")
def auth_refresh() -> dict:
    """强制后台刷新用户信息（不等完成）"""
    am = get_auth_manager()
    am.trigger_refresh_userinfo_async()
    return {"ok": True, "message": "后台刷新已触发"}


@router.post("/verify-session")
def verify_session() -> dict:
    """验证当前闲鱼登录会话是否有效

    与 /me 不同，本端点会实际访问闲鱼页面验证登录态，
    而不是仅检查 Cookie 文件是否存在。
    适用于登录后验证、登录态掉线检测等场景。
    """
    has_cookie = _check_cookies()

    if not has_cookie:
        return {"ok": False, "logged_in": False, "reason": "no_login_cookies"}

    # 尝试用 auth_helper 拉取用户信息来验证会话有效性
    # 如果 auth_helper 能成功获取用户信息，说明会话有效
    try:
        am = get_auth_manager()
        am.trigger_refresh_userinfo_async()
        return {"ok": True, "logged_in": True, "message": "会话验证已触发，请稍后查看 /api/auth/me"}
    except Exception as e:
        return {"ok": False, "logged_in": False, "reason": f"verify_error: {e}"}


# ============================================================
# Cookie 健康检查（轻量级，供状态栏悬浮面板调用）
# ============================================================
# 闲鱼关键 Cookie 名称（与 cookie_store._GOOFISH_KEY_COOKIES 对齐）
# 为什么在此重复定义而非导入：避免 auth_query 与 cookie_store 形成循环导入依赖
_KEY_COOKIES = {"_m_h5_tk", "_m_h5_tk_enc", "unb", "sgcookie", "cookie2", "lg2"}


def _format_expiry(expiry_ts: float | None) -> str:
    """把 Unix 时间戳格式化为人类可读的剩余时间"""
    if expiry_ts is None:
        return "会话级（浏览器关闭后失效）"
    remaining = expiry_ts - time.time()
    if remaining <= 0:
        return "已过期"
    days = int(remaining // 86400)
    hours = int((remaining % 86400) // 3600)
    minutes = int((remaining % 3600) // 60)
    if days > 0:
        return f"约 {days} 天 {hours} 小时"
    if hours > 0:
        return f"约 {hours} 小时 {minutes} 分钟"
    return f"约 {minutes} 分钟"


@router.get("/cookie/health")
def cookie_health() -> JSONResponse:
    """轻量级 Cookie 健康检查（< 300ms）

    供状态栏用户头像悬浮面板调用，纯文件读取无网络请求，
    返回 Cookie 完整性、有效期、安全标记、分层状态等关键信息。

    与 /api/anticrawl/health 的区别：
    - /anticrawl/health：重量级检查（含浏览器访问、API 探测），耗时数秒
    - /cookie/health：仅读取 cookies.json 文件，毫秒级返回
    """
    start_ts = time.time()
    store = get_cookie_store()
    store.invalidate_cache()

    # 完整性检查：返回 (is_valid, reason)
    is_valid, reason = store.validate_cookies_with_expiry()
    # 摘要信息：cookie_count / exported_at / method / key_cookies_found
    info = store.get_cookie_info()
    # 最早过期时间戳
    expiry_ts = store.get_cookie_expiry()

    # 分层状态：基于 Cookie 名称判断 identity/session/tracking 三层是否齐全
    # 为什么直接读 JSON 而非调 CookieRotator：避免引入 login_orchestrator 的副作用
    data = store._read_json()
    names = {c.get("name", "") for c in (data or {}).get("cookies", [])} if data else set()
    layers_status = {
        "identity": bool({"unb", "cookie2", "sgcookie", "t", "_tb_token_", "lg2"} & names),
        "session": bool({"_m_h5_tk", "_m_h5_tk_enc"} & names),
        "tracking": bool({"cna", "tfstk", "xlly_s"} & names),
    }

    # 安全标记：基于 Cookie 属性推断
    # - has_secure: 是否标记 Secure（HTTPS 传输）
    # - has_httponly: 是否标记 HttpOnly（防 XSS）
    # - is_session_cookie: 是否为会话级 Cookie（无 expires）
    security_flags = {
        "has_secure": False,
        "has_httponly": False,
        "is_session_cookie": expiry_ts is None,
    }
    if data and data.get("cookies"):
        for c in data["cookies"]:
            if c.get("name") in _KEY_COOKIES:
                # JSON 存储未保留 secure/httponly 标记，根据域名推断
                domain = c.get("domain", "")
                if domain.endswith(".goofish.com") or domain.endswith(".taobao.com"):
                    security_flags["has_secure"] = True
                    security_flags["has_httponly"] = True
                    break

    elapsed_ms = int((time.time() - start_ts) * 1000)
    return JSONResponse(content={
        "ok": True,
        "is_valid": is_valid,
        "reason": reason,
        "cookie_count": info.get("cookie_count", 0),
        "key_cookies_found": sorted(_KEY_COOKIES & names) if names else [],
        "expiry_ts": expiry_ts,
        "expiry_human": _format_expiry(expiry_ts),
        "integrity": "complete" if is_valid else "incomplete",
        "integrity_reason": reason,
        "layers": layers_status,
        "security_flags": security_flags,
        "exported_at": info.get("exported_at", 0),
        "method": info.get("method", "unknown"),
        "elapsed_ms": elapsed_ms,
    })


# ============================================================
# 退出登录
# ============================================================
def _clear_goofish_cookies_in_sqlite() -> int:
    """清理 browser-data SQLite 中的闲鱼/淘宝 Cookie

    Returns: 删除的 Cookie 数量
    """
    cfg = get_config()
    user_data_dir = Path(cfg.browser.user_data_dir)
    if not user_data_dir.is_absolute():
        user_data_dir = Path.cwd() / user_data_dir
    cookie_db = user_data_dir / "Default" / "Network" / "Cookies"
    if not cookie_db.exists():
        return 0
    deleted = 0
    try:
        with sqlite3.connect(str(cookie_db)) as conn:
            for domain in ("goofish", "taobao", "alipay", "login.taobao"):
                cur = conn.execute(
                    "DELETE FROM cookies WHERE host_key LIKE ?",
                    (f"%{domain}%",),
                )
                deleted += cur.rowcount
            conn.commit()
    except sqlite3.OperationalError as e:
        # 文件锁定时跳过（浏览器运行中），不阻断退出流程
        logger.warning("清理 SQLite Cookie 失败（文件锁定）: %s", e)
    except Exception as e:
        logger.error("清理 SQLite Cookie 失败: %s", e)
    return deleted


def _delete_cookie_json() -> bool:
    """删除 cookies.json 文件并清除 CookieStore 内存缓存"""
    from xianyu_hunter.web.services.cookie_store import _COOKIE_JSON_FILE
    try:
        if _COOKIE_JSON_FILE.exists():
            _COOKIE_JSON_FILE.unlink()
    except OSError as e:
        logger.warning("删除 cookies.json 失败: %s", e)
        return False
    # 清除 CookieStore 内存缓存，避免后续请求读到旧数据
    store = get_cookie_store()
    store.invalidate_cache()
    return True


def _reset_auth_manager_cache() -> None:
    """重置 AuthManager 的 userinfo 缓存，避免退出后仍显示旧用户信息"""
    am = get_auth_manager()
    with am._lock:
        am._userinfo = {"logged_in": False, "user_id": "", "nick": "", "avatar_url": "", "fetched_at": 0}
        am._userinfo_at = time.time()


@router.post("/logout")
def logout() -> JSONResponse:
    """退出登录

    清理顺序（任一步失败不阻断后续）：
    1. 删除 cookies.json（主数据源，立即生效）
    2. 清理 browser-data SQLite 中的闲鱼/淘宝 Cookie
    3. 重置 AuthManager userinfo 缓存
    4. 清除浏览器 xh_token 认证 Cookie

    注意：不停止 Worker/Session 后台任务（避免退出操作引发连锁反应），
    用户如需完全停止服务，应使用「系统维护」或停止进程。
    """
    cleared = {"json": False, "sqlite_count": 0, "auth_cache": False}
    try:
        cleared["json"] = _delete_cookie_json()
    except Exception as e:
        logger.error("删除 cookies.json 异常: %s", e)
    try:
        cleared["sqlite_count"] = _clear_goofish_cookies_in_sqlite()
    except Exception as e:
        logger.error("清理 SQLite Cookie 异常: %s", e)
    try:
        _reset_auth_manager_cache()
        cleared["auth_cache"] = True
    except Exception as e:
        logger.error("重置 AuthManager 缓存异常: %s", e)

    # 清除浏览器 xh_token 认证 Cookie
    resp = JSONResponse(content={
        "ok": True,
        "message": "已退出登录",
        "cleared": cleared,
    })
    resp.delete_cookie(key="xh_token", path="/", domain=None)
    return resp
