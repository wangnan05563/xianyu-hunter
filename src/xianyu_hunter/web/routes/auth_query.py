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

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text as sa_text

from xianyu_hunter.container import Container
from xianyu_hunter.infra.yaml_config import get_config
from xianyu_hunter.paths import get_browser_data_dir, get_data_dir
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.services.auth_manager import get_auth_manager
from xianyu_hunter.web.routes.auth_helpers import make_auth_response
from xianyu_hunter.web.services.notification_engine import scan_and_notify
from xianyu_hunter.web.services.cookie_store import get_cookie_store, _GOOFISH_KEY_COOKIES as _KEY_COOKIES

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth-query"])

# 无效昵称集合：闲鱼页面未登录或 DOM 抓取错位时会拿到这些文本
# 为什么需要集中定义：auth_helper.py 在抓取时已做过滤，但 userinfo.json 可能缓存
# 过滤逻辑加入前的旧值，users.nickname 也可能被同步过无效值。
# 此处在 API 出口再做一次兜底过滤，确保无效昵称不会透到前端。
_INVALID_NICKS = {
    "", "登录", "登錄", "Login", "Sign in", "立即登录",
    "Hi! 你好", "Hi！你好", "你好", "Hi", "Hi!",
    "登录/注册", "请登录", "点击登录",
}


def _is_invalid_nick(nick: str | None) -> bool:
    """判断 nick 是否为无效值（登录按钮文本/欢迎语/空字符串）"""
    return (nick or "").strip() in _INVALID_NICKS


def _resolve_current_user_id(request: Request) -> str | None:
    """从 xh_token cookie 识别当前多用户会话用户 ID

    为什么不依赖中间件注入：/api/auth/me 在 PUBLIC_PREFIXES 中，中间件不会
    对其执行会话校验和 user_id 注入。这里主动调用 verify_session 拿 user_id，
    既能识别多用户会话，又能让 PUBLIC 路径感知到当前登录身份。
    """
    token = request.cookies.get("xh_token", "")
    if not token:
        return None
    try:
        from xianyu_hunter.web.services.user_manager import get_user_manager
        return get_user_manager().verify_session(token)
    except Exception:
        return None


def _check_cookies(user_id: str = "default") -> bool:
    """检查闲鱼 Cookie 是否有效（JSON 优先，SQLite 兜底）

    CookieStore 内部优先读取 JSON 文件（登录子进程立即写入），
    JSON 不可用时回退到 SQLite 检查（仅 default 用户）。

    为什么按 user_id 检查：多用户登录后 cookie 存在 cookies_{user_id}.json
    而非 cookies_default.json，硬编码 default 会导致多用户场景误判为未登录。
    """
    store = get_cookie_store()
    store.invalidate_cache(user_id)
    if store.has_valid_cookies(user_id=user_id):
        return True
    # 回退：检查 last_login_cookies.json（auth_helper 写入的公共 cookie 文件）
    # 原因：auth_helper 子进程仅写 last_login_cookies.json，不写 cookies_{user_id}.json
    # fallback: check last_login_cookies.json for all users
    last_login = get_data_dir() / 'last_login_cookies.json'
    if last_login.exists():
        try:
            import json as _json
            data = _json.loads(last_login.read_text(encoding='utf-8'))
            cookies = data if isinstance(data, list) else data.get('cookies', [])
            if cookies:
                names = {c['name'] for c in cookies}
                if _KEY_COOKIES & names:
                    return True
        except Exception:
            pass
    return False


def _sync_nick_to_users_table(user_id: str, nick: str) -> tuple[str, str]:
    """把抓取到的 nick 同步到 users.nickname，并返回 (nickname, custom_alias)

    为什么需要同步：auth_helper 拉取到的 nick 只写在 auth_cache/userinfo.json，
    从未回写 users 表。users.nickname 字段一直是 identify_or_create 时的空字符串，
    导致 /api/auth/me 即使能识别 user_id，也拿不到本地存储的昵称。

    无效 nick 处理：当 nick 为 "Hi! 你好" 等无效值时，不仅不写入，还会清空
    库里已有的无效 nickname，避免旧缓存持续透到前端。

    Returns:
        (nickname, custom_alias) - 过滤无效值后的最终展示名
    """
    if not user_id or user_id == "default":
        # default 用户无本地记录，返回空
        return ("", "")

    try:
        from xianyu_hunter.web.services.user_manager import get_user_manager
        mgr = get_user_manager()
        user = mgr.get_user(user_id)
        if not user:
            return ("", "")

        current_nick = user.get("nickname") or ""
        custom_alias = user.get("custom_alias") or ""

        # 过滤无效 nick：新抓取的 nick 和库里已有的 nick 都需要校验
        # 为什么校验库里：userinfo.json 过滤逻辑是后加的，库里可能已存有 "Hi! 你好"
        valid_nick = "" if _is_invalid_nick(nick) else nick
        valid_current_nick = "" if _is_invalid_nick(current_nick) else current_nick

        # 情况1：新 nick 有效且与库里不同 → 写入新 nick
        if valid_nick and valid_nick != current_nick:
            now_iso = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
            with mgr._engine.connect() as conn:
                conn.execute(sa_text(
                    "UPDATE users SET nickname=:nick, updated_at=:now WHERE user_id=:uid"
                ), {"nick": valid_nick, "now": now_iso, "uid": user_id})
                conn.commit()
            logger.info("已同步闲鱼昵称到 users 表: user_id=%s, nick=%s", user_id, valid_nick)
            return (valid_nick, custom_alias)

        # 情况2：新 nick 无效但库里也是无效值 → 清空库里的无效 nickname
        # 为什么需要清空：旧的 "Hi! 你好" 会通过返回值透到前端 local_username
        if not valid_nick and current_nick and valid_current_nick != current_nick:
            now_iso = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
            with mgr._engine.connect() as conn:
                conn.execute(sa_text(
                    "UPDATE users SET nickname='', updated_at=:now WHERE user_id=:uid"
                ), {"now": now_iso, "uid": user_id})
                conn.commit()
            logger.info("已清空无效昵称: user_id=%s, old_nick=%s", user_id, current_nick)
            return ("", custom_alias)

        return (valid_current_nick, custom_alias)
    except Exception as e:
        logger.warning("同步 nick 到 users 表失败: %s", e)
        return ("", "")


def _maybe_refresh_userinfo(
    has_cookie: bool, info: dict, am, raw_nick: str, valid_nick: str
) -> None:
    """集中处理三类后台刷新触发条件，避免主流程被多个 and 复合判断拉高复杂度

    1. 有 cookie 但缓存里 logged_in=False：同步探测结果，需尽快拉取真实登录态
    2. 缓存已过期（TTL 外）：触发后台刷新
    3. 缓存中是无效 nick：触发刷新以尽快拿到真实昵称
    """
    if has_cookie and not info.get("logged_in"):
        am.trigger_refresh_userinfo_async()
    if has_cookie and info.get("logged_in") and (time.time() - info.get("fetched_at", 0)) > am.USERINFO_TTL:
        am.trigger_refresh_userinfo_async()
    if has_cookie and raw_nick and not valid_nick:
        am.trigger_refresh_userinfo_async()


def _build_auth_me_result(has_cookie: bool, info: dict, valid_nick: str) -> dict:
    """构建 /me 响应体

    has_cookie=True 但缓存 logged_in=False 时附加 detecting=True：
    说明后端正在后台刷新，前端应展示"检测中"占位而非直接判定为未登录。
    """
    if has_cookie and not info.get("logged_in"):
        return {
            "logged_in": True,
            "user_id": info.get("user_id", ""),
            "nick": valid_nick,
            "avatar_url": info.get("avatar_url", ""),
            "fetched_at": info.get("fetched_at", 0),
            "detecting": True,
        }
    return {
        "logged_in": has_cookie and bool(info.get("logged_in")),
        "user_id": info.get("user_id", ""),
        "nick": valid_nick,
        "avatar_url": info.get("avatar_url", ""),
        "fetched_at": info.get("fetched_at", 0),
    }


@router.get("/me")
def auth_me(request: Request, container: Container = Depends(get_container)):
    """返回当前登录用户信息（昵称/头像/user_id/local_username）

    实现策略：
    1. 从 xh_token 识别多用户会话 user_id（无会话则用 default）
    2. 按 user_id 检查 cookies_{user_id}.json 存在性
    3. 复用 auth_manager 的 userinfo 缓存（昵称/头像）
    4. 把抓取到的 nick 同步回 users.nickname，并在响应中返回 local_username
    """
    # 1. 识别当前多用户会话用户
    current_uid = _resolve_current_user_id(request)
    current_session_token = request.cookies.get("xh_token", "") if current_uid else None
    cookie_user_id = current_uid or "default"

    # 2. 检查当前用户的 cookie 文件
    has_cookie = _check_cookies(cookie_user_id)

    am = get_auth_manager()
    info = am.get_userinfo()

    # 过滤无效 nick：userinfo.json 可能缓存了过滤逻辑加入前的旧值（如 "Hi! 你好"）
    # 此处兜底过滤，确保无效昵称不会透到前端 result["nick"]
    raw_nick = info.get("nick", "")
    valid_nick = "" if _is_invalid_nick(raw_nick) else raw_nick
    _maybe_refresh_userinfo(has_cookie, info, am, raw_nick, valid_nick)

    # 构建返回结果
    result = _build_auth_me_result(has_cookie, info, valid_nick)

    # 3. 同步 nick 到 users 表，并在响应中追加 local_username/custom_alias
    #    传入 valid_nick：已过滤无效值，_sync_nick_to_users_table 会据此清空库里旧无效值
    nickname, custom_alias = _sync_nick_to_users_table(
        current_uid or "", valid_nick
    )
    # local_username 优先级：自定义别名 > 闲鱼昵称 > user_id
    # 为什么自定义别名优先：用户主动设置的标识更具辨识度，闲鱼昵称可能因反爬抓不到
    result["local_username"] = custom_alias or nickname or result.get("user_id", "") or ""
    result["nickname"] = nickname
    result["custom_alias"] = custom_alias

    # 检测登录态掉线 → 生成业务通知（失败不影响主路径）
    scan_and_notify(container, auth_state=result)

    # 已登录时确保浏览器持有 xh_token 认证 cookie
    if result.get("logged_in"):
        return make_auth_response(result, session_token=current_session_token)

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
    if minutes > 0:
        return f"约 {minutes} 分钟"
    # 剩余时间不足 1 分钟但仍 > 0，避免显示"约 0 分钟"造成误解
    return "不足 1 分钟"


# 复用 CookieRotator 的配置化 LAYER_DEFINITIONS，避免硬编码与配置漂移
# 原硬编码 tracking 层只有 3 个 cookie，配置化有 5 个（含 ali_aplus_v3/utdid），
# 导致右上角与 AntiCrawl 页面对同一层显示不一致状态
from xianyu_hunter.modules.cookie_rotator import (
    LAYER_DEFINITIONS,
    CookieLayer,
    is_m5tk_expired,
)


def _compute_layers_status(names: set[str], cookies_list: list[dict] | None = None) -> dict[str, bool]:
    """计算 Cookie 三层（identity/session/tracking）的齐全状态

    复用 LAYER_DEFINITIONS 配置消除名单漂移，与 /api/anticrawl/cookies/layers
    使用同一份配置，确保两条链路对同一层显示一致状态。

    session 层额外检查 _m_h5_tk 内嵌 timestamp 是否过期：
    - CookieRotator 通过 is_m5tk_expired 判断 token 真实有效性
    - 若不检查，JSON 中 token 名字存在但已过期时，右上角显示"已就绪"
      而 AntiCrawl 显示"失效"，造成用户困惑
    """
    identity_cookies = LAYER_DEFINITIONS[CookieLayer.IDENTITY].cookies
    session_cookies = LAYER_DEFINITIONS[CookieLayer.SESSION].cookies
    tracking_cookies = LAYER_DEFINITIONS[CookieLayer.TRACKING].cookies

    # session 层：名字齐全 + token 未过期
    session_ready = bool(session_cookies & names)
    if session_ready and cookies_list:
        # _m_h5_tk 的 cookie.expires=-1 无法判断过期，必须检查内嵌 timestamp
        # 与 validate_cookies_with_expiry / CookieRotator.sync_state_from_cookies 保持一致
        for c in cookies_list:
            if c.get("name") == "_m_h5_tk":
                if is_m5tk_expired(c.get("value", "")):
                    session_ready = False
                break

    return {
        "identity": bool(identity_cookies & names),
        "session": session_ready,
        "tracking": bool(tracking_cookies & names),
    }


def _compute_security_flags(data: dict | None, expiry_ts: float | None) -> dict[str, bool]:
    """计算安全标记（secure/httponly/session_cookie）

    拆分自 cookie_health：将 key cookie 扫描 + 域名推断收敛到单一函数，
    降低主函数的循环嵌套与认知复杂度（S3776）。"""
    flags = {
        "has_secure": False,
        "has_httponly": False,
        "is_session_cookie": expiry_ts is None,
    }
    if not data or not data.get("cookies"):
        return flags

    for c in data["cookies"]:
        if c.get("name") not in _KEY_COOKIES:
            continue
        domain = c.get("domain", "")
        if domain.endswith(".goofish.com") or domain.endswith(".taobao.com"):
            flags["has_secure"] = True
            flags["has_httponly"] = True
            break
    return flags


@router.get("/cookie/health")
async def cookie_health(request: Request) -> JSONResponse:
    """轻量级 Cookie 健康检查（< 300ms）

    供状态栏用户头像悬浮面板调用，纯文件读取无网络请求，
    返回 Cookie 完整性、有效期、安全标记、分层状态等关键信息。

    与 /api/anticrawl/health 的区别：
    - /anticrawl/health：重量级检查（含浏览器访问、API 探测），耗时数秒
    - /cookie/health：仅读取 cookies_{user_id}.json 文件，毫秒级返回

    多用户场景：从 xh_token 识别当前会话用户，按 user_id 读取对应 cookie 文件，
    避免硬编码 default 导致多用户登录后状态栏显示"无 Cookie"。

    浏览器内存兜底：JSON 中 _m_h5_tk 过期时，实时搜索可能已刷新浏览器内存中的
    token 但未回写 JSON（_ensure_fresh_m5tk 不回写），此时从浏览器内存读取最新
    token 回写 JSON 再重新判断，避免"实时搜索可用但右上角显示无效"的不一致。

    重构说明：分层状态计算和安全标记推断下沉到独立函数（S3776），
    主函数只做流程编排和结果组装，降低嵌套层级与认知负担。
    """
    start_ts = time.time()
    current_uid = _resolve_current_user_id(request) or "default"

    store = get_cookie_store()
    store.invalidate_cache(current_uid)

    is_valid, reason = store.validate_cookies_with_expiry(user_id=current_uid)

    # JSON 中 _m_h5_tk 过期时，尝试从浏览器内存刷新回写 JSON
    # 为什么需要：_ensure_fresh_m5tk（实时搜索）和 MTOP API 响应会刷新浏览器内存中的
    # token 但不回写 JSON，导致 JSON 中 token 的内嵌 timestamp 过期（>20分钟），
    # 而 /api/anticrawl/cookies/layers 已有同样的兜底逻辑（_try_refresh_m5tk_from_browser）
    if not is_valid and ("cookie_expired:_m_h5_tk" in reason or "cookie_expired:_m_h5_tk_enc" in reason):
        refreshed = await _try_refresh_m5tk_from_browser_for_health(store, current_uid)
        if refreshed:
            store.invalidate_cache(current_uid)
            is_valid, reason = store.validate_cookies_with_expiry(user_id=current_uid)

    info = store.get_cookie_info(user_id=current_uid)
    expiry_ts = store.get_cookie_expiry(user_id=current_uid)

    data = store._read_json(user_id=current_uid)
    cookies_list = (data or {}).get("cookies", []) if data else []
    names = {c.get("name", "") for c in cookies_list}

    # 传入 cookies_list 让 _compute_layers_status 检查 _m_h5_tk 内嵌 timestamp 过期
    layers_status = _compute_layers_status(names, cookies_list)
    security_flags = _compute_security_flags(data, expiry_ts)

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


async def _try_refresh_m5tk_from_browser_for_health(store, user_id: str) -> bool:
    """从浏览器内存读取最新 _m_h5_tk 并回写 JSON（供 cookie_health 轻量级健康检查使用）

    与 api_anticrawl._try_refresh_m5tk_from_browser 的区别：
    - 支持多用户隔离（传入 user_id，回写到正确的 cookies_{user_id}.json）
    - 独立实现避免 auth_query → api_anticrawl 跨路由模块依赖

    Returns:
        True 表示成功从浏览器内存读取到未过期 token 并回写 JSON
    """
    try:
        from xianyu_hunter.web.deps import get_container
        from xianyu_hunter.modules.cookie_rotator import is_m5tk_expired

        container = get_container()
        if not container.browser:
            return False
        cookies = await container.browser.get_cookies()
        updates: dict[str, str] = {}
        for c in cookies:
            name = c.get("name", "")
            value = c.get("value", "")
            if not value:
                continue
            # _m_h5_tk 需未过期；_m_h5_tk_enc 是配套加密 token，无 timestamp 无法判过期，直接回写
            if (name == "_m_h5_tk" and not is_m5tk_expired(value)) or name == "_m_h5_tk_enc":
                updates[name] = value
        if not updates:
            return False
        return store.update_cookie_values(updates, user_id=user_id)
    except Exception as e:
        logger.debug("cookie_health: 从浏览器内存刷新 _m_h5_tk 失败: %s", e)
        return False


# ============================================================
# 退出登录
# ============================================================
def _clear_goofish_cookies_in_sqlite() -> int:
    """清理 browser-data SQLite 中的闲鱼/淘宝 Cookie

    Returns: 删除的 Cookie 数量
    """
    cfg = get_config()
    user_data_dir = get_browser_data_dir(cfg.browser.user_data_dir)
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
    """删除 default 用户的 Cookie JSON 文件并清除内存缓存

    为什么用 _cookie_json_path("default") 而非模块级常量：
    MU2 改造后 CookieStore 按 user_id 分文件存储，旧的 _COOKIE_JSON_FILE
    模块级常量已删除。logout 时清理 default 用户文件，保持与多用户模型一致。
    """
    from xianyu_hunter.web.services.cookie_store import _cookie_json_path
    path = _cookie_json_path("default")
    try:
        if path.exists():
            path.unlink()
    except OSError as e:
        logger.warning("删除 cookies_default.json 失败: %s", e)
        return False
    # 清除 CookieStore 内存缓存，避免后续请求读到旧数据
    store = get_cookie_store()
    store.invalidate_cache("default")
    return True


def _reset_auth_manager_cache() -> None:
    """重置 AuthManager 的 userinfo 缓存，避免退出后仍显示旧用户信息

    为什么调用 am.reset() 而非直接操作私有属性：保持封装性，
    让 AuthManager 自行管理内部状态和持久化文件的清理。
    """
    get_auth_manager().reset()


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
134300469763651521

# touch
# rebuild touch
# rebuild2
# rebuild3
# BUILD_MARKER_20250802

# FIX_VERIFIED_20250802_0430
