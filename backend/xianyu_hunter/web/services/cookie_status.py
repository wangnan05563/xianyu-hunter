"""Cookie 有效性统一判定（meta-rule #96 单一调度函数）

问题背景：Cookie 有效性此前由 3+ 条独立代码路径各自计算，校验深度与数据源不一致：
- /api/auth/cookie/health（右上角悬浮面板）：按 xh_token 解析 user_id 读 cookies_{uid}.json，
  含 last_login_cookies.json / cookies_default.json 兜底，但**不感知 collector 的会话失效标志**
- /api/anticrawl/health（反爬健康检查）：cookie_checker 硬编码读 cookies_default.json（无多用户隔离），
  含浏览器内存兜底与 collector.last_session_invalid 粘性标志检查，但**无 last_login 文件兜底**
- api_orders 抢单前校验：按 request.state.user_id 读，含三层兜底（与 cookie/health 同源）

结果：同一份 Cookie 在两处状态矛盾（如"右上角正常 / 反爬无效"）。
根因：服务端已注销会话（RGV587/超时）时，collector 置 last_session_invalid=True，
cookie 文件里的 token 仍"未过期"，纯文件判定的右上角报"正常"，而会查 collector 标志的反爬报"无效"。

修复：抽取 evaluate_cookie_status() 单一调度函数，所有入口共用同一套
（user_id 解析 + 文件校验 + last_login/default 兜底 + m5tk 浏览器刷新 + 浏览器内存兜底
+ collector 会话失效标志），消除"不同入口校验深度不一致"。

设计约束：本函数为**纯判定**（只读 + 轻量浏览器读取 + 清除 sticky 标志），不触发
注入恢复等副作用；副作用（RGV587 注入恢复、层状态同步）由调用方在判定为无效后自行决定，
因不同入口的恢复策略不同（反爬做注入恢复，导航栏不做）。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from xianyu_hunter.infra.logger import get_logger
from xianyu_hunter.paths import get_data_dir
from xianyu_hunter.web.services.cookie_store import (
    get_cookie_store,
    _GOOFISH_KEY_COOKIES,
)

logger = get_logger()

# collector 粘性标志导致的失效原因，供调用方识别并决定是否做注入恢复
REASON_COLLECTOR_SESSION_INVALID = "collector_session_invalid"

# 仅 MTOP 运行时令牌（_m_h5_tk/_m_h5_tk_enc）过期、但 identity 登录态 Cookie 仍存在时的原因。
# 语义区别于 cookie_expired:*：登录态正常，令牌由系统访问闲鱼首页后自动恢复（通常数秒），
# 前端应显示为警告（"会话令牌待刷新"）而非错误（"Cookie 异常"），避免初登用户误判登录失败。
REASON_MTOP_TOKEN_STALE = "mtop_token_stale"


@dataclass
class CookieStatus:
    """统一 Cookie 有效性判定结果

    字段覆盖导航栏响应与反爬 cookie 维度所需信息，避免两处各自拼装。
    """

    is_valid: bool
    reason: str
    user_id: str
    source: str = "none"          # cookies_{uid} / last_login / default / browser
    method: str = "unknown"
    cookies_list: list[dict] = field(default_factory=list)
    names: set[str] = field(default_factory=set)
    expiry_ts: float | None = None
    # 导航栏响应派生字段
    exported_at: float = 0.0
    cookie_count: int = 0
    key_cookies_found: list[str] = field(default_factory=list)
    layers_status: dict[str, bool] = field(default_factory=dict)
    security_flags: dict[str, bool] = field(default_factory=dict)

    def as_navbar_payload(self) -> dict[str, Any]:
        """组装 /api/auth/cookie/health 的响应体（保持历史字段形状）"""
        return {
            "ok": True,
            "is_valid": self.is_valid,
            "reason": self.reason,
            "cookie_count": self.cookie_count,
            "key_cookies_found": self.key_cookies_found,
            "expiry_ts": self.expiry_ts,
            "expiry_human": _format_expiry(self.expiry_ts),
            "integrity": "complete" if self.is_valid else "incomplete",
            "integrity_reason": self.reason,
            "layers": self.layers_status,
            "security_flags": self.security_flags,
            "exported_at": self.exported_at,
            "method": self.method,
            "elapsed_ms": 0,
        }


def _format_expiry(expiry_ts: float | None) -> str:
    """把 Unix 时间戳格式化为人类可读字符串（复用导航栏历史逻辑）"""
    if not expiry_ts:
        return "未知"
    delta = expiry_ts - time.time()
    if delta <= 0:
        return "已过期"
    days = int(delta // 86400)
    hours = int((delta % 86400) // 3600)
    if days > 0:
        return f"{days} 天 {hours} 小时后过期"
    minutes = int((delta % 3600) // 60)
    if hours > 0:
        return f"{hours} 小时 {minutes} 分钟后过期"
    return f"{minutes} 分钟后过期"


def _load_cookie_data_for_health(store, user_id: str) -> tuple[dict | None, list[dict] | None]:
    """按优先级加载 Cookie 数据（与历史 cookie/health 同源）

    优先级：
    1. cookies_{user_id}.json（多用户隔离主文件）
    2. last_login_cookies.json（登录子进程/浏览器导入遗留的公共 Cookie 文件）
    3. cookies_default.json（单用户模式或迁移前文件）

    为什么需要：首次登录后 cookies_{user_id}.json 可能为空或损坏
    （多用户迁移时 export_cookies 写入 user_id 文件失败），
    但 cookies_default.json / last_login_cookies.json 仍有有效 Cookie。
    反爬健康检查此前缺第 2 步兜底，导致与导航栏状态矛盾。
    """
    # 1. 多用户隔离主文件
    data = store._read_json(user_id=user_id)
    if data and data.get("cookies"):
        return data, data["cookies"]

    # 2. 登录子进程/浏览器导入遗留的公共 Cookie 文件（列表格式）
    last_login = get_data_dir() / "last_login_cookies.json"
    if last_login.exists():
        try:
            import json as _json
            raw = _json.loads(last_login.read_text(encoding="utf-8"))
            if isinstance(raw, list) and raw:
                data = {
                    "exported_at": raw[0].get("expires", 0) if isinstance(raw[0], dict) else 0,
                    "method": "last_login_fallback",
                    "cookie_count": len(raw),
                    "cookies": raw,
                }
                return data, raw
        except (ValueError, OSError):
            pass

    # 3. 单用户模式/迁移前 default 文件
    data = store._read_json(user_id="default")
    if data and data.get("cookies"):
        return data, data["cookies"]

    return None, None


def _has_valid_m5tk_in_list(cookies_list: list[dict]) -> bool:
    """检查 cookie 列表中是否存在未过期的 _m_h5_tk（统一判定，避免规则漂移）"""
    from xianyu_hunter.modules.cookie_rotator import is_m5tk_expired
    return any(
        c.get("name") == "_m_h5_tk" and c.get("value")
        and not is_m5tk_expired(c.get("value", ""))
        for c in cookies_list
    )


async def _try_refresh_m5tk_from_browser(store, user_id: str) -> bool:
    """从浏览器内存读取最新 _m_h5_tk 并回写 JSON（支持多用户隔离）

    与 api_anticrawl._try_refresh_m5tk_from_browser 对齐，但支持 user_id 参数，
    避免跨路由模块依赖。返回 True 表示成功刷新未过期 token 并回写 JSON。
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
            if (name == "_m_h5_tk" and not is_m5tk_expired(value)) or name == "_m_h5_tk_enc":
                updates[name] = value
        if not updates:
            return False
        return store.update_cookie_values(updates, user_id=user_id)
    except Exception as e:
        logger.debug("从浏览器内存刷新 _m_h5_tk 回写 JSON 失败: %s", e)
        return False


def _is_collector_session_invalid() -> bool:
    """读取 collector 的会话失效粘性标志（服务端已注销会话的权威信号）

    为什么纳入统一判定：collector 在采集时若收到 RGV587_ERROR 或服务端注销会话，
    会把 last_session_invalid 置 True。此时 cookie 文件里的 token 仍"未过期"，
    纯文件判定会误报有效，但实时搜索/采集已不可用。导航栏此前看不到该标志，
    导致与反爬健康检查矛盾。读取为内存操作，开销可忽略，纳入统一判定后两处一致。
    """
    try:
        from xianyu_hunter.web.deps import get_container
        container = get_container()
        if container.collector and getattr(container.collector, "last_session_invalid", False):
            return True
    except Exception as e:
        logger.debug("读取 collector 会话失效标志失败: %s", e)
    return False


async def _browser_cookies_fallback() -> tuple[bool, list[dict] | None]:
    """JSON 判定无效时的浏览器内存兜底复核（与 api_anticrawl 对齐）

    判定标准与实时搜索 _ensure_live_search_cookies 对齐：
    - _m_h5_tk 存在、有值、未过期
    - identity 层至少一个 cookie 存在
    - 关键 cookie（identity + session 层）的 expires 未过期
    - 浏览器内存 token 实际有效时清除 collector 粘性标志

    Returns:
        (passed, cookies_list) - passed=True 表示浏览器内存 cookie 有效
    """
    try:
        from xianyu_hunter.web.deps import get_container
        from xianyu_hunter.modules.cookie_rotator import (
            LAYER_DEFINITIONS,
            CookieLayer,
            is_m5tk_expired,
        )

        container = get_container()
        if not container.browser:
            return False, None
        cookies = await container.browser.get_cookies()
        if not cookies:
            return False, None

        names = {c.get("name", "") for c in cookies}

        # 1. _m_h5_tk 必须有效
        if not any(
            c.get("name") == "_m_h5_tk" and c.get("value")
            and not is_m5tk_expired(c.get("value", ""))
            for c in cookies
        ):
            return False, None

        # 2. identity 层至少一个
        identity_cookies = LAYER_DEFINITIONS[CookieLayer.IDENTITY].cookies
        if not (identity_cookies & names):
            return False, None

        # 3. 关键 cookie 的 expires 未过期
        key_cookie_names = identity_cookies | LAYER_DEFINITIONS[CookieLayer.SESSION].cookies
        now = time.time()
        for c in cookies:
            if c.get("name") not in key_cookie_names:
                continue
            expires = c.get("expires", -1)
            if expires and expires > 0 and expires < now:
                return False, None

        # 4. 浏览器内存 token 实际有效时清除 collector 粘性标志
        if container.collector and getattr(container.collector, "last_session_invalid", False):
            logger.info("cookie_status: 浏览器内存 token 有效，清除 collector 粘性标志")
            container.collector.last_session_invalid = False

        return True, cookies
    except Exception as e:
        logger.debug("浏览器内存兜底检查失败: %s", e)
        return False, None


def _compute_expiry_ts(cookies_list: list[dict] | None) -> float | None:
    """计算最早过期的闲鱼关键 Cookie 过期时间"""
    if not cookies_list:
        return None
    key_cookies = [c for c in cookies_list if c.get("name") in _GOOFISH_KEY_COOKIES]
    if not key_cookies:
        return None
    expiries = [
        c.get("expires", -1) for c in key_cookies
        if c.get("expires", -1) and c.get("expires", -1) > 0
    ]
    return min(expiries) if expiries else None


def _compute_layers_status(names: set[str]) -> dict[str, bool]:
    """计算 Cookie 分层状态（identity / session / tracking）"""
    from xianyu_hunter.modules.cookie_rotator import (
        LAYER_DEFINITIONS,
        CookieLayer,
    )
    result: dict[str, bool] = {}
    for layer in (CookieLayer.IDENTITY, CookieLayer.SESSION, CookieLayer.TRACKING):
        layer_cookies = LAYER_DEFINITIONS[layer].cookies
        result[layer.value] = bool(layer_cookies & names)
    return result


def _compute_security_flags(data: dict | None) -> dict[str, bool]:
    """计算安全标记（HTTPS-only / HttpOnly / 近期导出）"""
    flags: dict[str, bool] = {
        "has_secure": False,
        "has_httponly": False,
        "recent_export": False,
    }
    if not data or not data.get("cookies"):
        return flags
    cookies = data["cookies"]
    for c in cookies:
        if c.get("secure"):
            flags["has_secure"] = True
        if c.get("httpOnly") or c.get("httponly"):
            flags["has_httponly"] = True
    exported_at = data.get("exported_at", 0)
    if exported_at:
        flags["recent_export"] = (time.time() - exported_at) < 86400
    return flags


def _as_valid(
    uid: str, source: str, method: str,
    cookies_list: list[dict], data: dict | None,
) -> CookieStatus:
    """组装有效的 CookieStatus（JSON / 浏览器兜底共用，避免字段拼装漂移）"""
    names = {c.get("name", "") for c in cookies_list}
    expiry_ts = _compute_expiry_ts(cookies_list)
    return CookieStatus(
        is_valid=True,
        reason="ok",
        user_id=uid,
        source=source,
        method=method,
        cookies_list=cookies_list,
        names=names,
        expiry_ts=expiry_ts,
        exported_at=(data or {}).get("exported_at", 0) if data else 0,
        cookie_count=len(cookies_list),
        key_cookies_found=sorted(_GOOFISH_KEY_COOKIES & names),
        layers_status=_compute_layers_status(names),
        security_flags=_compute_security_flags(data),
    )


def _get_method_str(data: dict | None, default: str = "unknown") -> str:
    """从 data 中提取 method 字段（兼容 None）"""
    return (data or {}).get("method", default) if data else default


def _get_source_str(data: dict | None) -> str:
    """从 data 中提取 source（method 复用）或 'none'"""
    return (data or {}).get("method", "unknown") if data else "none"


def _make_invalid_status(
    uid: str, reason: str,
    data: dict | None, cookies_list: list[dict], names: set[str],
) -> CookieStatus:
    """组装无效的 CookieStatus（统一字段拼装，消除重复）

    O-08-11 修复：invalid 场景也必须返回真实的 cookie_count / layers_status /
    security_flags，否则前端会显示"Cookie 数 0 个"与"各层缺失"——明明 JSON 里有
    15 个 cookie，却报 0 个，严重误导用户。无效仅表示 key cookie（如 _m_h5_tk）过期
    或服务端会话失效，不等于没有 cookie。
    """
    # 即使无效，也从实际 cookie 计算层数状态，让用户看到"身份层✓/会话层✗"而非全空
    layers_status = _compute_layers_status(names) if names else {}
    security_flags = _compute_security_flags(data)
    return CookieStatus(
        is_valid=False, reason=reason,
        user_id=uid,
        source=_get_source_str(data),
        method=_get_method_str(data),
        cookies_list=cookies_list, names=names,
        cookie_count=len(cookies_list),
        key_cookies_found=sorted(_GOOFISH_KEY_COOKIES & names),
        layers_status=layers_status,
        security_flags=security_flags,
    )


async def _try_browser_fallback(uid: str) -> CookieStatus | None:
    """尝试浏览器内存兜底，成功返回有效 CookieStatus，否则返回 None"""
    passed, browser_cookies = await _browser_cookies_fallback()
    if passed and browser_cookies:
        return _as_valid(uid, "browser", "browser_fallback", browser_cookies, None)
    return None


def _find_expired_cookie(
    cookies_list: list[dict],
    identity_cookies: set[str],
    session_cookies: set[str],
) -> str | None:
    """检查 identity + session 层是否有已过期的 cookie，返回过期 cookie 名或 None"""
    now = time.time()
    for c in cookies_list:
        name = c.get("name")
        # 跳过 _m_h5_tk / _m_h5_tk_enc / unb：三者都是「expires 字段不可靠」的 cookie。
        # - _m_h5_tk/_m_h5_tk_enc：内嵌 timestamp 的 token，expires 字段无可靠语义，
        #   有效性统一由 _has_valid_m5tk_in_list 判定（本地多处特判保持一致）。
        # - unb：纯用户唯一ID标识（identity 层 ttl=session），扫码登录/本地持久化
        #   导出时其 expires 会被写成过去的绝对时间戳（实际登录态有效），
        #   据此误判会报 cookie_expired:unb。真正登录态由 cookie2/_m_h5_tk 判定，
        #   unb 只做存在性检查，其 expires 字段不应作为过期依据。
        #   与 cookie_store._check_key_cookies_expiry、auth_query._check_single_cookie_expiry
        #   保持同一跳过名单，避免规则漂移导致「导航栏/反爬/抢单」判定不一致。
        if name not in (identity_cookies | session_cookies) or name in ("_m_h5_tk", "_m_h5_tk_enc", "unb"):
            continue
        expires = c.get("expires", -1)
        if expires and expires > 0 and expires < now:
            return name
    return None


async def _try_refresh_and_recheck(
    store, uid: str,
    data: dict | None, cookies_list: list[dict], names: set[str],
) -> CookieStatus | None:
    """尝试从浏览器刷新 m5tk 并重新检查，返回有效 CookieStatus 或 None"""
    m5tk_present = any(
        c.get("name") == "_m_h5_tk" and c.get("value") for c in cookies_list
    )
    refreshed = await _try_refresh_m5tk_from_browser(store, uid)
    if refreshed:
        store.invalidate_cache(uid)
        data2 = store._read_json(user_id=uid)
        cookies_list2 = (data2 or {}).get("cookies", []) if data2 else []
        names2 = {c.get("name", "") for c in cookies_list2}
        if _has_valid_m5tk_in_list(cookies_list2):
            # 刷新成功：返回有效状态（而非 None），避免主流程继续用旧数据误判
            return _as_valid(uid, _get_method_str(data2), _get_source_str(data2), cookies_list2, data2)
        # 刷新后仍无效，继续尝试浏览器兜底
        data, cookies_list, names = data2 or data, cookies_list2, names2
    # 浏览器内存兜底复核
    status = await _try_browser_fallback(uid)
    if status:
        return status
    # 刷新与兜底都失败：区分「登录态仍在，仅运行时令牌待恢复」与「真正未登录」。
    # 为什么：_m_h5_tk 是短时 MTOP 令牌（15-22 分钟 TTL），登录后首次健康检查若
    # 首页刷新失败（如 DNS/网络抖动，见 2026-10-10 打包版日志 ERR_NAME_NOT_RESOLVED），
    # 此处会立即命中；此时 identity 层 Cookie 仍在，报 cookie_expired:_m_h5_tk 会让
    # 用户面板显示"Cookie 异常"误判为登录失败。归为 mtop_token_stale（警告级）。
    if m5tk_present:
        from xianyu_hunter.modules.cookie_rotator import LAYER_DEFINITIONS, CookieLayer

        identity_cookies = LAYER_DEFINITIONS[CookieLayer.IDENTITY].cookies
        has_identity = bool(identity_cookies & names)
        reason = REASON_MTOP_TOKEN_STALE if has_identity else "cookie_expired:_m_h5_tk"
    else:
        reason = "no_session_token"
    return _make_invalid_status(uid, reason, data, cookies_list, names)


async def evaluate_cookie_status(user_id: str | None = None) -> CookieStatus:
    """统一 Cookie 有效性判定（单一调度函数，meta-rule #96）

    所有 Cookie 状态消费者（导航栏 / 反爬健康检查 / 抢单校验）必须调用本函数，
    禁止各自直接拼装判定逻辑，避免不同入口校验深度不一致。

    判定严格度与历史反爬 cookie_checker 对齐（两层都强制）：
    - session 层：_m_h5_tk 必须存在且内嵌 timestamp 未过期（缺 token 即无效）
    - identity 层：至少一个 identity cookie 存在
    - 关键 cookie 过期：identity/session 层任一 cookie 的 expires 过期即无效
    - collector 会话失效粘性标志：服务端已注销会话的权威信号，置位即无效

    与导航栏 /api/auth/cookie/health 共用本函数 + 同一 user_id，
    确保两处读取 cookies_{user_id}.json 且校验深度完全一致，
    消除"右上角正常 / 反爬无效"的状态矛盾。

    Args:
        user_id: 目标用户标识。None 退化为 "default"（单用户/管理令牌场景）。
            多用户场景调用方应传入 request.state.user_id，确保与导航栏读取同一文件。

    Returns:
        CookieStatus：含 is_valid / reason / user_id / cookies_list / names 等，
        调用方据此组装各自响应或决定是否做副作用恢复。
    """
    from xianyu_hunter.modules.cookie_rotator import (
        LAYER_DEFINITIONS,
        CookieLayer,
    )

    uid = user_id or "default"
    store = get_cookie_store()
    store.invalidate_cache(uid)

    identity_cookies = LAYER_DEFINITIONS[CookieLayer.IDENTITY].cookies

    # 1. 加载数据（含 last_login/default 兜底）
    data, cookies_list = _load_cookie_data_for_health(store, uid)
    if not data or not cookies_list:
        status = await _try_browser_fallback(uid)
        if status:
            return status
        return _make_invalid_status(uid, "no_cookie_data", data, [], set())

    names = {c.get("name", "") for c in cookies_list}

    # 2. session 层（_m_h5_tk）必须存在且未过期
    if not _has_valid_m5tk_in_list(cookies_list):
        status = await _try_refresh_and_recheck(store, uid, data, cookies_list, names)
        if status:
            return status

    # 3. identity 层至少一个 cookie 存在
    if not (identity_cookies & names):
        status = await _try_browser_fallback(uid)
        if status:
            return status
        return _make_invalid_status(uid, "no_identity_cookies", data, cookies_list, names)

    # 4. 关键 cookie 过期检查（identity + session 层）
    session_cookies = LAYER_DEFINITIONS[CookieLayer.SESSION].cookies
    expired_name = _find_expired_cookie(cookies_list, identity_cookies, session_cookies)
    if expired_name:
        return _make_invalid_status(uid, f"cookie_expired:{expired_name}", data, cookies_list, names)

    # 5. collector 会话失效粘性标志
    if _is_collector_session_invalid():
        return _make_invalid_status(uid, REASON_COLLECTOR_SESSION_INVALID, data, cookies_list, names)

    # 6. 组装成功结果
    return _as_valid(
        uid,
        _get_method_str(data),
        _get_method_str(data),
        cookies_list,
        data,
    )


# ============================================================
# 统一健康度端点（PRD FR-C1-1 / FR-C1-2，REQ-001/002）
# ============================================================

# 身份 Cookie 三件套（PRD FR-C1-2）：登录态是否成立的判定基元
_UNIFIED_IDENTITY_COOKIES: tuple[str, ...] = ("cookie2", "sgcookie", "unb")
# expires 字段不可信名单（与 _find_expired_cookie 同一口径，防规则漂移）：
# unb 导出时常写历史时间戳但登录态有效；_m_h5_tk/_enc 有效性由内嵌 timestamp 判定
_EXPIRY_UNRELIABLE_COOKIES: frozenset[str] = frozenset({"_m_h5_tk", "_m_h5_tk_enc", "unb"})


def _collect_health_sources(store, uid: str) -> list[dict]:
    """枚举全部落盘登录态档案源（FR-C1-1 聚合三处数据源的档案部分）

    覆盖：per-user 档案、default 档案、last_login 兜底文件。
    浏览器内存源由 _browser_health_source 单独采集（异步）。
    """
    sources: list[dict] = []
    # dict.fromkeys 去重保序：uid == "default" 时不重复读同一文件
    for sid in dict.fromkeys([uid, "default"]):
        data = store._read_json(user_id=sid)
        if data and data.get("cookies"):
            sources.append({
                "source": f"cookies_{sid}.json",
                "data": data,
                "exported_at": data.get("exported_at", 0) or 0,
            })
    last_login = get_data_dir() / "last_login_cookies.json"
    if last_login.exists():
        try:
            import json as _json

            raw = _json.loads(last_login.read_text(encoding="utf-8"))
            if isinstance(raw, list) and raw:
                sources.append({
                    "source": "last_login_cookies.json",
                    "data": {"method": "last_login_fallback", "cookies": raw},
                    "exported_at": 0,  # 列表格式无 exported_at，freshness 排序垫底
                })
        except (ValueError, OSError):
            pass
    return sources


def _assess_health_source(entry: dict) -> dict:
    """评估单个档案源的身份 Cookie 健康状况（FR-C1-2 判定基元）

    返回结构化评估：哪些身份 Cookie 有效/过期/缺失、会话令牌是否有效。
    reasons 聚合与 freshest 选择都依赖此结构。
    """
    cookies_list = entry["data"].get("cookies", [])
    now = time.time()
    by_name = {c.get("name"): c for c in cookies_list if c.get("name")}
    identity_valid: list[str] = []
    identity_expired: list[str] = []
    identity_missing: list[str] = []
    for name in _UNIFIED_IDENTITY_COOKIES:
        if name not in by_name:
            identity_missing.append(name)
            continue
        if name in _EXPIRY_UNRELIABLE_COOKIES:
            # expires 不可信：存在即视为有效（unb 只做存在性检查）
            identity_valid.append(name)
            continue
        expires = by_name[name].get("expires", -1)
        if expires and expires > 0 and expires < now:
            identity_expired.append(name)
        else:
            identity_valid.append(name)
    return {
        "source": entry["source"],
        "method": entry["data"].get("method", "unknown"),
        "exported_at": entry["exported_at"],
        "cookie_count": len(cookies_list),
        "identity_valid": identity_valid,
        "identity_expired": identity_expired,
        "identity_missing": identity_missing,
        "has_valid_m5tk": _has_valid_m5tk_in_list(cookies_list),
        # fresh 判定只看会话凭证（cookie2/sgcookie）：unb 仅是用户标识且 expires
        # 不可信，单独存在不代表登录态可用——否则「cookie2/sgcookie 全过期」场景
        # 会因 unb 存在而误判 fresh（PRD 验收要求该场景报 invalid）
        "fresh": bool({"cookie2", "sgcookie"} & set(identity_valid)),
        "expiry_ts": _compute_expiry_ts(cookies_list),
    }


async def _browser_health_source() -> dict | None:
    """采集浏览器内存作为候选数据源（运行中浏览器的登录态最新鲜）

    浏览器内存的登录态由真实页面会话维持，永远比落盘档案新鲜，
    freshness 排序时以当前时间作为 exported_at，天然排在最前。
    """
    try:
        from xianyu_hunter.web.deps import get_container

        container = get_container()
        if not container.browser or not getattr(container.browser, "_context", None):
            return None
        cookies = await container.browser.get_cookies()
        if not cookies:
            return None
        return {
            "source": "browser",
            "data": {"method": "browser_memory", "cookies": cookies},
            "exported_at": time.time(),
        }
    except Exception as e:
        logger.debug("unified health: 浏览器内存源采集失败: %s", e)
        return None


async def evaluate_unified_health(user_id: str | None = None) -> dict:
    """统一登录态健康度判定（PRD FR-C1-1 聚合端点 + FR-C1-2 诊断优先级）

    与 evaluate_cookie_status 的分工：
    - evaluate_cookie_status：单用户单档案链路判定（导航栏/反爬/抢单消费），
      档案优先级是固定的 uid → last_login → default
    - evaluate_unified_health：跨档案 freshness 聚合，解决「per-user 档案过期
      但 default 新鲜时误报失效」（T01717 根因场景）——身份 Cookie 有效性以
      exported_at 最新且含有效身份 Cookie 的档案为准

    Returns:
        {status: healthy|degraded|invalid, reasons: [{source, cookie, issue}],
         self_healed, freshest_source, sources: [...]}
    """
    uid = user_id or "default"
    store = get_cookie_store()
    # 判定前失效缓存：健康检查要求读到最新落盘状态（导入/自愈刚写入）
    store.invalidate_cache(uid)
    store.invalidate_cache("default")

    sources = _collect_health_sources(store, uid)
    browser_src = await _browser_health_source()
    if browser_src:
        sources.append(browser_src)
    # FR-C1-2：exported_at 最新优先；无 exported_at 的 last_login 垫底
    assessed = sorted(
        (_assess_health_source(s) for s in sources),
        key=lambda a: a["exported_at"],
        reverse=True,
    )

    # reasons 逐条记录：哪个 Cookie / 哪个档案 / 过期还是缺失（PRD 契约）
    reasons: list[dict] = []
    for a in assessed:
        for name in a["identity_expired"]:
            reasons.append({"source": a["source"], "cookie": name, "issue": "expired"})
        for name in a["identity_missing"]:
            reasons.append({"source": a["source"], "cookie": name, "issue": "missing"})

    freshest = next((a for a in assessed if a["fresh"]), None)
    # collector 粘性标志读一次：多次调用虽是内存操作，但单次读取让分支语义更清晰
    collector_invalid = _is_collector_session_invalid()

    if freshest is None:
        status = "invalid"
        if not reasons:
            reasons.append({"source": "none", "cookie": None, "issue": "no_cookie_data"})
    elif freshest["source"] == "browser" and freshest["has_valid_m5tk"] and collector_invalid:
        # 浏览器内存实测有效但 collector 标志置位：标志为旧状态，
        # 清除之（与 _browser_cookies_fallback 的清理行为一致）
        try:
            from xianyu_hunter.web.deps import get_container

            container = get_container()
            if container.collector:
                container.collector.last_session_invalid = False
        except Exception as e:
            logger.debug("unified health: 清除 collector 标志失败: %s", e)
        status = "healthy"
    elif collector_invalid:
        # 身份档案有效但实时采集侧已确认会话失效（RGV587/服务端注销）——
        # 纯档案判定会误报有效，实时搜索实际不可用，必须报 invalid
        status = "invalid"
        reasons.append({
            "source": "collector", "cookie": None,
            "issue": REASON_COLLECTOR_SESSION_INVALID,
        })
    elif freshest["has_valid_m5tk"]:
        status = "healthy"
    else:
        # 身份 Cookie 有效但 MTOP 运行时令牌缺失/过期：登录态在，
        # 实时搜索暂不可用 → degraded（警告级而非错误级）
        status = "degraded"
        reasons.append({
            "source": freshest["source"], "cookie": "_m_h5_tk",
            "issue": REASON_MTOP_TOKEN_STALE,
        })

    return {
        "ok": True,
        "status": status,
        "reasons": reasons,
        # FR-C1-3 自动自愈由 M2（T01777）接入后置 True；当前恒 False
        "self_healed": False,
        "user_id": uid,
        "freshest_source": freshest["source"] if freshest else None,
        "expiry_ts": freshest["expiry_ts"] if freshest else None,
        "expiry_human": _format_expiry(freshest["expiry_ts"] if freshest else None),
        # sources 全量透出：供前端「诊断详情」抽屉（T01778）逐源展示
        "sources": [
            {k: v for k, v in a.items() if k != "expiry_ts"}
            for a in assessed
        ],
    }
