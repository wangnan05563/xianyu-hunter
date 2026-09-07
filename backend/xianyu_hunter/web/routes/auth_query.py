"""用户信息查询 API - 登录态检测 / 用户资料

端点：
- GET  /api/auth/me              当前登录用户信息（缓存）
- GET  /api/auth/me/refresh      强制后台刷新（不等完成）
- GET  /api/auth/cookie/health   轻量级 Cookie 健康检查（< 300ms，纯文件读取）
- POST /api/auth/logout          退出登录（清除 Cookie/会话/认证 token）
"""
from __future__ import annotations

import json
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
    """从 xh_token cookie 或 Authorization: Bearer 头识别当前多用户会话用户 ID

    为什么不依赖中间件注入：/api/auth/cookie 在 PUBLIC_PREFIXES 中，中间件不会
    对其执行会话校验和 user_id 注入。这里主动从 token 拿 user_id，
    既能识别多用户会话，又能让 PUBLIC 路径感知到当前登录身份。

    token 来源优先级（与 BearerAuthMiddleware._extract_candidate_tokens 一致）：
    1. xh_token cookie：HTTPS/域名场景可用（Secure cookie 被浏览器保留）
    2. Authorization: Bearer 头：HTTP/IP 场景下浏览器会丢弃 Secure cookie，
       但前端始终通过 localStorage 在 header 携带 token，故回退到此，
       避免 IP 登录后导航栏读取错误（default）用户的 cookie 文件而误报
       "Cookie 异常"/身份层/会话层/追踪层"缺失"。
    """
    token = request.cookies.get("xh_token", "")
    if not token:
        # HTTP(IP) 场景回退：浏览器丢弃 Secure cookie，改用 Bearer 头携带的 token
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[len("Bearer "):].strip()
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
    # 多用户隔离兜底：user_id 专属文件缺失时回退 default 文件
    # 为什么需要：扫码/浏览器登录子进程可能只导出到 cookies_default.json
    # （公共导出路径），而 xh_token 识别出的 user_id（如 cookie2 哈希账号）
    # 专属文件尚未生成。不回退会导致 /me 误判未登录 → MainLayout 跳登录页，
    # 与 /cookie/health 的 _load_cookie_data_for_health 三段 fallback 链不一致。
    if user_id != "default":
        store.invalidate_cache("default")
        if store.has_valid_cookies(user_id="default"):
            return True
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
            # 防复发：昵称就绪后检测同昵称重复账号（unb vs cookie2 哈希），自动合并
            # 为什么在昵称写入成功后才触发：识别重复依赖 nickname 非空，
            # identify_or_create 建号时 nickname 为空，此时检测必然无结果
            try:
                mgr.merge_duplicate_accounts(user_id)
            except Exception as e:
                logger.warning("重复账号自动合并检测失败 user_id=%s: %s", user_id, e)
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
    #    为什么用 info.user_id 兜底：无有效会话（current_uid 为空，如会话被 web_token
    #    降级）时若传空 user_id，_sync 会提前返回空，导致 users 表昵称不同步、
    #    local_username 退化为裸 user_id，前端 UserMenu 直接显示"未登录"。
    #    userinfo 缓存里的 user_id 由登录子进程识别（unb 优先），可作兜底身份。
    sync_uid = current_uid or info.get("user_id") or ""
    nickname, custom_alias = _sync_nick_to_users_table(
        sync_uid, valid_nick
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
        return make_auth_response(result, session_token=current_session_token, request=request)

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


def _check_single_cookie_expiry(c: dict, now: float) -> str | None:
    """检查单个 cookie 是否过期，返回过期原因或 None"""
    from xianyu_hunter.modules.cookie_rotator import is_m5tk_expired

    name = c.get("name")
    if name not in _KEY_COOKIES:
        return None

    if name == "_m_h5_tk":
        m5tk_value = c.get("value", "")
        if m5tk_value and is_m5tk_expired(m5tk_value):
            return "cookie_expired:_m_h5_tk"
        return None

    if name == "_m_h5_tk_enc":
        return None

    expires = c.get("expires", -1)
    if expires and expires > 0 and expires < now:
        return f"cookie_expired:{name}"
    return None


def _validate_cookies_list_with_expiry(cookies_list: list[dict]) -> tuple[bool, str]:
    """验证 cookie 列表是否有效（含过期时间判断）

    与 CookieStore.validate_cookies_with_expiry 逻辑保持一致，
    但直接操作 cookie 列表，用于 fallback 数据源的健康检查。
    """
    if not cookies_list:
        return False, "no_cookie_data"

    if not (_KEY_COOKIES & {c.get("name", "") for c in cookies_list}):
        return False, "no_key_cookies"

    now = time.time()
    for c in cookies_list:
        reason = _check_single_cookie_expiry(c, now)
        if reason:
            return False, reason

    return True, "ok"


def _compute_expiry_ts(cookies_list: list[dict] | None) -> float | None:
    """计算 cookie 列表中最早过期的关键 Cookie 过期时间"""
    if not cookies_list:
        return None
    key_cookies = [
        c for c in cookies_list
        if c.get("name") in _KEY_COOKIES
    ]
    if not key_cookies:
        return None
    expiries = [
        c.get("expires", -1) for c in key_cookies
        if c.get("expires", -1) and c.get("expires", -1) > 0
    ]
    return min(expiries) if expiries else None


def _load_cookie_data_for_health(
    store, user_id: str
) -> tuple[dict | None, list[dict] | None]:
    """按优先级加载 Cookie 数据供健康检查使用

    优先级：
    1. cookies_{user_id}.json（多用户隔离主数据源）
    2. last_login_cookies.json（登录子进程/浏览器导入遗留的公共 Cookie 文件）
    3. cookies_default.json（单用户模式或迁移前文件）

    为什么需要：首次登录后 cookies_{user_id}.json 可能为空或损坏
    （issue: 多用户迁移时 export_cookies 写入 user_id 文件失败），
    但 cookies_default.json / last_login_cookies.json 仍有有效 Cookie。
    此时 /api/auth/me 因 _check_cookies 有 last_login 回退而显示已登录，
    而 /api/auth/cookie/health 直接返回 no_cookie_data，导致状态栏显示不一致。

    Returns:
        (data, cookies_list) - data 为 JSON 包装对象（含 exported_at/method），
        cookies_list 为实际 cookie 列表。两者可能来自不同文件格式。
    """
    # 1. 多用户隔离主文件
    data = store._read_json(user_id=user_id)
    if data and data.get("cookies"):
        return data, data["cookies"]

    # 2. 登录子进程/浏览器导入遗留的公共 Cookie 文件（列表格式）
    last_login = get_data_dir() / "last_login_cookies.json"
    if last_login.exists():
        try:
            raw = json.loads(last_login.read_text(encoding="utf-8"))
            if isinstance(raw, list) and raw:
                # 统一包装为 cookies_{user_id}.json 的 dict 格式，方便后续字段访问
                data = {
                    "exported_at": raw[0].get("expires", 0) if isinstance(raw[0], dict) else 0,
                    "method": "last_login_fallback",
                    "cookie_count": len(raw),
                    "cookies": raw,
                }
                return data, raw
        except (json.JSONDecodeError, OSError):
            pass

    # 3. 单用户模式/迁移前 default 文件
    data = store._read_json(user_id="default")
    if data and data.get("cookies"):
        return data, data["cookies"]

    return None, None


def _repair_user_json_from_fallback(store, current_uid: str, fb_data, fb_cookies) -> tuple[bool, str, bool]:
    """尝试将 fallback cookie 数据回写到 user_id 专属 JSON 文件"""
    try:
        store.export_cookies(fb_cookies, method=fb_data.get("method", "fallback_recovery"), user_id=current_uid)
        store.invalidate_cache(current_uid)
        is_valid, reason = store.validate_cookies_with_expiry(user_id=current_uid)
        return is_valid, reason, True
    except OSError as e:
        logger.warning("cookie_health: 修复 cookies_%s.json 失败: %s", current_uid, e)
        return False, "", False


def _read_local_cookies(store, current_uid: str) -> tuple[list, list]:
    """读取本地 cookie JSON 文件，返回 (data, cookies_list)"""
    data = store._read_json(user_id=current_uid)
    cookies_list = (data or {}).get("cookies", []) if data else []
    return data, cookies_list


def _try_fallback_cookie_data(store, current_uid: str, is_valid: bool, reason: str):
    """尝试从 fallback 数据源加载 Cookie 数据并修复主文件

    当主文件 cookies_{user_id}.json 不可用时，回退到 last_login_cookies.json
    或 cookies_default.json，并尝试修复 user_id 文件。

    Returns:
        (fallback_used, data, cookies_list, is_valid, reason)
    """
    # 无需 fallback 时直接返回当前数据
    if is_valid or not ("no_cookie_data" in reason or "no_key_cookies" in reason):
        data, cookies_list = _read_local_cookies(store, current_uid)
        return False, data, cookies_list, is_valid, reason

    # 尝试加载 fallback 数据源
    fb_data, fb_cookies = _load_cookie_data_for_health(store, current_uid)
    if not fb_data or not fb_cookies:
        data, cookies_list = _read_local_cookies(store, current_uid)
        return False, data, cookies_list, is_valid, reason

    logger.info(
        "cookie_health: cookies_%s.json 不可用，回退到 %s，尝试修复 user_id 文件",
        current_uid, fb_data.get("method", "unknown"),
    )

    # 尝试将 fallback 数据写入 user_id 专属文件并重新校验
    repaired, rep_reason, repaired_ok = _repair_user_json_from_fallback(store, current_uid, fb_data, fb_cookies)
    if repaired_ok and repaired:
        data, cookies_list = _read_local_cookies(store, current_uid)
        return True, data, cookies_list, repaired, rep_reason

    data, cookies_list = fb_data, fb_cookies
    is_valid, reason = _validate_cookies_list_with_expiry(cookies_list)
    return True, data, cookies_list, is_valid, reason


def _build_health_response(
    start_ts: float,
    is_valid: bool,
    reason: str,
    info: dict,
    names: set,
    expiry_ts: float | None,
    layers_status: dict,
    security_flags: dict,
) -> JSONResponse:
    """构建 cookie/health 响应"""
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


async def _try_refresh_m5tk_if_needed(store, current_uid: str) -> tuple[bool, str]:
    """JSON 中 _m_h5_tk 过期时尝试从浏览器内存刷新回写"""
    is_valid, reason = store.validate_cookies_with_expiry(user_id=current_uid)
    if is_valid or not ("cookie_expired:_m_h5_tk" in reason or "cookie_expired:_m_h5_tk_enc" in reason):
        return is_valid, reason
    refreshed = await _try_refresh_m5tk_from_browser_for_health(store, current_uid)
    if refreshed:
        store.invalidate_cache(current_uid)
        return store.validate_cookies_with_expiry(user_id=current_uid)
    return is_valid, reason


def _build_fallback_info(data: dict | None, cookies_list: list[dict]) -> dict:
    """从 fallback 数据源构建 cookie info"""
    source = data.get("method", "unknown") if data else "none"
    cookie_count = len(cookies_list) if cookies_list else 0
    exported_at = data.get("exported_at", 0) if data else 0
    method = data.get("method", "unknown") if data else "unknown"
    return {
        "logged_in": True,
        "source": source,
        "cookie_count": cookie_count,
        "exported_at": exported_at,
        "method": method,
    }


@router.get("/cookie/health")
async def cookie_health(request: Request) -> JSONResponse:
    """轻量级 Cookie 健康检查（< 300ms）

    供状态栏用户头像悬浮面板调用，返回 Cookie 完整性、有效期、安全标记、
    分层状态等关键信息。

    与 /api/anticrawl/health 的区别：
    - /anticrawl/health：重量级检查（含浏览器访问、API 探测），耗时数秒
    - /cookie/health：文件读取 + 轻量浏览器读取，毫秒级返回

    多用户场景：从 xh_token 识别当前会话用户，按 user_id 读取对应 cookie 文件，
    避免硬编码 default 导致多用户登录后状态栏显示"无 Cookie"。

    同步机制（meta-rule #96）：本端点与 /api/anticrawl/health（反爬健康检查）、
    api_orders 抢单校验共用 evaluate_cookie_status() 单一调度函数，
    统一 user_id 解析 + 文件校验 + last_login/default 兜底 + m5tk 浏览器刷新
    + 浏览器内存兜底 + collector 会话失效标志，消除"不同入口校验深度不一致"
    导致的状态矛盾（如右上角显示正常但反爬显示无效）。
    """
    start_ts = time.time()
    current_uid = _resolve_current_user_id(request) or "default"

    # 单一调度函数：导航栏与反爬健康检查共用，保证两处 Cookie 状态一致
    from xianyu_hunter.web.services.cookie_status import evaluate_cookie_status
    status = await evaluate_cookie_status(current_uid)

    payload = status.as_navbar_payload()
    payload["elapsed_ms"] = int((time.time() - start_ts) * 1000)
    return JSONResponse(content=payload)


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
