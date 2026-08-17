"""反爬登录管理 API - 暴露 LoginOrchestrator 能力给前端

端点：
- GET  /api/anticrawl/strategy          评估推荐登录策略
- POST /api/anticrawl/initialize         初始化协调器（launch/CDP 模式）
- GET  /api/anticrawl/session/status     获取会话状态摘要
- POST /api/anticrawl/session/start      启动会话管理（TokenRenewer 后台续期）
- POST /api/anticrawl/session/stop       停止会话管理
- GET  /api/anticrawl/health             执行健康检查
- GET  /api/anticrawl/fingerprint        获取当前指纹信息
- GET  /api/anticrawl/freq/stats         获取频率伪装统计
- POST /api/anticrawl/cookies/update     登录成功后分层更新 Cookie
- GET  /api/anticrawl/cookies/layers     获取 Cookie 层状态

设计原则：
- 所有端点都通过 LoginOrchestrator 单例操作，保证状态一致
- 写操作（initialize/start/stop/update）用 POST，读操作用 GET
- 异步操作（start/stop/health）使用 async 路由
"""
from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from xianyu_hunter.modules.cookie_rotator import CookieLayer, LAYER_DEFINITIONS, is_m5tk_expired
from xianyu_hunter.modules.freq_disguise import ActionType
from xianyu_hunter.modules.login_orchestrator import get_orchestrator
from xianyu_hunter.modules.login_strategy import LoginStrategy
from xianyu_hunter.modules.session_health import WAFStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/anticrawl", tags=["anticrawl"])


def _sync_layer_states_if_needed(orch, cookies_list: list[dict]) -> None:
    """自动同步层状态（对所有非用户主动失效的层）

    为什么不再只检查 updated_at==0：被系统失效的层（RGV587/续期失败）
    updated_at>0 但 valid=False，需能被自动同步恢复。
    仅跳过 manual_invalidate=True 的层（用户通过 /cookies/invalidate 主动失效）。
    """
    states = orch.cookie_rotator.get_all_states()
    identity_state = states.get(CookieLayer.IDENTITY)
    needs_sync = (
        not identity_state
        or (not identity_state.valid and not identity_state.manual_invalidate)
    )
    if needs_sync:
        logger.info("cookie_checker: Cookie 有效但层状态失效，自动同步")
        cookie_map = {c.get("name", ""): c.get("value", "") for c in cookies_list}
        orch.cookie_rotator.sync_state_from_cookies(cookie_map)


def _compute_waf_status(orch) -> WAFStatus:
    """WAF 状态提供器：基于验证码处理统计推断风控状态

    阈值：
    - fail_rate > 0.5: BLOCKED
    - fail_rate > 0.2: WARNING
    - 其他: CLEAR
    """
    stats = orch.captcha_handler.get_stats()
    failed = stats.get("failed", 0)
    total = stats.get("total_detected", 0)
    if total == 0:
        return WAFStatus.CLEAR
    fail_rate = failed / total
    if fail_rate > 0.5:
        return WAFStatus.BLOCKED
    if fail_rate > 0.2:
        return WAFStatus.WARNING
    return WAFStatus.CLEAR


def _configure_default_health_checkers(orch) -> None:
    """为协调器配置默认健康检查器

    为什么在 initialize 时自动配置：避免前端需要额外调用 configure 端点，
    初始化后健康检查即可直接使用。api/page 维度未配置时默认通过，
    主要依赖 cookie（权重40）和 waf（权重10）维度。
    """
    # Cookie 检查器：基于 JSON 实际内容判断 + 自动同步层状态 + 浏览器内存兜底
    # 为什么不依赖 CookieRotator 内存状态：browser_login / auth_helper /
    # browser_import / cookie_inject 等登录路径只调用 export_cookies 写入 JSON，
    # 未调用 on_login_success，导致层状态为默认 False，引发误判
    #
    # 为什么需要浏览器内存兜底：JSON 与浏览器内存存在同步延迟
    # （MTOP Set-Cookie 回写 JSON 可能失败/部分回写），健康检查只读 JSON 会误判。
    # 浏览器内存是实时搜索实际使用的数据源，以它为兜底标准能与实时搜索行为对齐。
    async def cookie_checker(user_id: str | None = None) -> bool:
        """Cookie 检查器：委托统一判定 evaluate_cookie_status（meta-rule #96）

        与导航栏 /api/auth/cookie/health 共用同一调度函数，按同一 user_id
        读取 cookies_{user_id}.json，消除"右上角正常 / 反爬无效"的状态矛盾。

        user_id 透传：多用户场景读取当前会话用户的 cookie 文件，
        单用户/管理令牌场景中间件注入 user_id="default"。

        保留的副作用：Cookie 有效时同步 CookieRotator 层状态（与 /cookies/layers 对齐）。
        collector 会话失效标志不再在此静默恢复（注入恢复改由显式动作完成），
        保证与导航栏（纯判定）状态一致。
        """
        try:
            uid = user_id or "default"
            from xianyu_hunter.web.services.cookie_status import evaluate_cookie_status
            status = await evaluate_cookie_status(uid)
            if status.is_valid:
                # 保留历史副作用：Cookie 有效时同步层状态（/cookies/layers 也做同样同步）
                _sync_layer_states_if_needed(orch, status.cookies_list)
                return True
            # 失效：统一判定已含 collector 会话失效标志；反爬页面如实反映状态，
            # RGV587 注入恢复交由显式动作（重新登录/恢复按钮），不再静默恢复。
            return False
        except Exception as e:
            logger.warning("cookie_checker 失败: %s", e)
            return False

    # WAF 状态提供器：基于验证码处理统计推断风控状态
    def waf_provider() -> WAFStatus:
        return _compute_waf_status(orch)

    orch.configure_health_checkers(
        cookie_checker=cookie_checker,
        waf_provider=waf_provider,
    )


# ============================================================
# 策略评估
# ============================================================
@router.get("/strategy")
def get_strategy() -> dict:
    """评估当前环境并推荐最优登录策略

    返回 LoginStrategySelector 的评估结果，包含：
    - recommended: 推荐策略
    - reason: 推荐原因
    - available_strategies: 所有可用策略列表
    - details: 各策略检测结果
    """
    orch = get_orchestrator()
    evaluation = orch.evaluate_strategy()
    return {
        "ok": True,
        "recommended": evaluation.recommended.value,
        "reason": evaluation.reason,
        "available_strategies": [s.value for s in evaluation.available_strategies],
        "details": evaluation.details,
    }


# ============================================================
# 协调器初始化
# ============================================================
@router.post("/initialize")
def initialize(request: dict = Body(...)) -> JSONResponse:
    """初始化 LoginOrchestrator

    Request body:
        {"use_cdp": false}  - launch 模式（生成指纹 profile）
        {"use_cdp": true}   - CDP 模式（真实浏览器，无需指纹）

    launch 模式会生成随机的 FingerprintProfile，BrowserManager 启动时
    会自动读取该 profile 注入一致的 stealth 脚本和 UA。
    """
    use_cdp = bool(request.get("use_cdp", False))
    orch = get_orchestrator()
    orch.initialize(use_cdp=use_cdp)
    _configure_default_health_checkers(orch)

    profile = orch.get_fingerprint_profile()
    return JSONResponse(content={
        "ok": True,
        "mode": "cdp" if use_cdp else "launch",
        "fingerprint_profile": profile.name if profile else None,
        "user_agent": profile.ua if profile else None,
        "stealth_scripts_count": len(orch.get_stealth_scripts()),
        "message": f"协调器已初始化（{'CDP' if use_cdp else 'launch'} 模式）",
    })


# ============================================================
# 会话管理
# ============================================================
@router.get("/session/status")
def get_session_status() -> dict:
    """获取会话状态摘要

    返回 SessionStatus 的完整字典，包含：
    - active: 会话是否活跃
    - strategy: 当前登录策略
    - fingerprint_profile: 指纹 profile 名称
    - token_age_sec / token_expired: token 状态
    - health_score / health_action / waf_status: 健康状态
    - cookie_layers: 各 Cookie 层有效性
    - freq_stats: 频率伪装统计
    - captcha_stats: 验证码统计
    - uptime_sec: 会话已运行时间
    """
    orch = get_orchestrator()
    status = orch.get_session_status()
    return {"ok": True, **status.to_dict()}


def _read_cookie_provider_value(cookie_name: str) -> str | None:
    """从 CookieStore 读取指定名称的 cookie 值

    作为 TokenRenewer 的 cookie_provider 实现：每次调用都读取最新值，
    因为 token 会随续期更新，不能缓存。
    """
    try:
        from xianyu_hunter.web.services.cookie_store import get_cookie_store
        store = get_cookie_store()
        store.invalidate_cache()
        data = store._read_json()
        if not data or not data.get("cookies"):
            return None
        for c in data["cookies"]:
            if c.get("name") == cookie_name:
                return c.get("value", "")
        return None
    except Exception as e:
        logger.warning("cookie_provider 读取 %s 失败: %s", cookie_name, e)
        return None


async def _renew_token_via_browser_navigation() -> bool:
    """通过浏览器导航到 m.taobao.com 触发 token 续期

    为什么用导航而非 API：导航是用户自然行为，
    风控压力低于直接调用 getTimestamp API。

    续期后必须回写 JSON + 同步层状态：导航触发的 Set-Cookie 更新了浏览器内存，
    但 CookieStore JSON 仍是旧值，CookieRotator 层状态也未同步。
    不回写会导致健康检查误判 token 过期、实时搜索从 JSON 补注入旧 token。
    与 login_orchestrator._default_renew_callback 保持一致的完整闭环。
    """
    page = None
    try:
        from xianyu_hunter.web.deps import get_container
        container = get_container()
        if not container.browser or not container.browser._context:
            logger.warning("浏览器不可用，无法续期 token")
            return False
        page = await container.browser.new_page()
        try:
            await page.goto("https://h5.m.taobao.com/", wait_until="domcontentloaded", timeout=10000)
        finally:
            await page.close()

        # 导航成功后回写 Cookie + 同步层状态（统一入口，消除与其他续期回调的重复）
        from xianyu_hunter.web.services.cookie_runtime_sync import sync_browser_cookies_to_store_after_renew
        await sync_browser_cookies_to_store_after_renew(container, log_prefix="api_anticrawl renew")
        return True
    except Exception as e:
        logger.warning("token 续期回调失败: %s", e)
        return False


@router.post("/session/start")
async def start_session(request: dict = Body(default_factory=dict)) -> JSONResponse:
    """启动会话管理（TokenRenewer 后台续期）

    Request body (可选):
        {"cookie_provider_name": "_m_h5_tk"}  - Cookie 名称（默认 _m_h5_tk）

    启动后 TokenRenewer 会定期检查 token 年龄，过期前自动续期。
    续期失败会触发 session 层 Cookie 失效。
    """
    orch = get_orchestrator()

    # 幂等处理：会话已活跃时返回 ok:True + already_active 标记
    # 为什么不用 ok:False：登录流程会通过 trigger_session_start() 自动启动会话，
    # 用户手动点击"启动会话"按钮时往往会话已是活跃状态，标记为失败会让用户误以为出错，
    # 而实际上会话功能完全正常。前端根据 already_active 显示不同的成功提示。
    if orch.is_session_active:
        return JSONResponse(content={
            "ok": True,
            "already_active": True,
            "message": "会话已处于活跃状态，无需重复启动",
        })

    # 默认从 CookieStore 读取 _m_h5_tk
    cookie_name = request.get("cookie_provider_name", "_m_h5_tk")

    # 闭包包装：保持 cookie_provider 每次调用读取最新值的语义
    # 为什么用闭包而非直接传值：token 会随续期更新，provider 函数每次调用都读取最新值
    def cookie_provider() -> str | None:
        return _read_cookie_provider_value(cookie_name)

    try:
        # start_session 是同步函数（无 await 的 async 已移除以避免 S7503）
        orch.start_session(cookie_provider=cookie_provider, renew_callback=_renew_token_via_browser_navigation)
        return JSONResponse(content={
            "ok": True,
            "message": "会话管理已启动，TokenRenewer 后台续期已开启",
        })
    except Exception as e:
        logger.error("启动会话失败: %s", e)
        return JSONResponse(content={"ok": False, "error": f"启动会话失败: {e}"})


@router.post("/session/stop")
async def stop_session() -> JSONResponse:
    """停止会话管理"""
    orch = get_orchestrator()

    if not orch.is_session_active:
        return JSONResponse(content={
            "ok": False,
            "error": "会话未启动",
        })

    try:
        await orch.stop_session()
        return JSONResponse(content={"ok": True, "message": "会话管理已停止"})
    except Exception as e:
        logger.error("停止会话失败: %s", e)
        return JSONResponse(content={"ok": False, "error": f"停止会话失败: {e}"})


# ============================================================
# 健康检查
# ============================================================
@router.get("/health")
async def check_health(request: Request) -> JSONResponse:
    """执行健康检查

    返回 HealthReport，包含：
    - score: 0-100 健康分
    - cookie_valid / api_reachable / page_accessible: 各维度状态
    - waf_status: 风控状态（clear/warning/blocked）
    - action: 建议动作（none/renew_token/relogin/pause）
    - details: 各维度评分详情
    """
    orch = get_orchestrator()

    # 若未配置检查器，返回提示
    if not orch.health_checker._cookie_checker and not orch.health_checker._api_checker:
        return JSONResponse(content={
            "ok": False,
            "error": "未配置健康检查器，请先调用 POST /api/anticrawl/initialize",
            "hint": "initialize 会自动配置默认的 cookie 和 waf 检查器",
        })

    # 透传当前会话用户（多用户隔离）：与导航栏 /api/auth/cookie/health 读取同一
    # cookies_{user_id}.json，消除"右上角正常但反爬无效"的状态矛盾（meta-rule #96）。
    # 单用户/管理令牌场景中间件注入 user_id="default"，多用户场景为真实 user_id。
    current_user_id = getattr(getattr(request, "state", None), "user_id", None) or "default"

    try:
        report = await orch.check_health(user_id=current_user_id)
        return JSONResponse(content={
            "ok": True,
            "score": report.score,
            "cookie_valid": report.cookie_valid,
            "api_reachable": report.api_reachable,
            "page_accessible": report.page_accessible,
            "waf_status": report.waf_status.value,
            "action": report.action.value,
            "details": report.details,
            "is_healthy": report.is_healthy,
            "needs_attention": report.needs_attention,
        })
    except Exception as e:
        logger.error("健康检查失败: %s", e)
        return JSONResponse(content={"ok": False, "error": f"健康检查失败: {e}"})


# ============================================================
# 指纹信息
# ============================================================
@router.get("/fingerprint")
def get_fingerprint() -> dict:
    """获取当前指纹 profile 信息

    返回 FingerprintProfile 的关键字段（不返回 canvas_noise_seed 等敏感种子）。
    CDP 模式下返回空 profile。
    """
    orch = get_orchestrator()
    profile = orch.get_fingerprint_profile()

    if profile is None:
        return {
            "ok": True,
            "mode": "cdp",
            "profile": None,
            "stealth_scripts_count": 0,
            "message": "CDP 模式，无需指纹注入",
        }

    return {
        "ok": True,
        "mode": "launch",
        "profile": {
            "name": profile.name,
            "ua": profile.ua,
            "platform": profile.platform,
            "vendor": profile.vendor,
            "hardware_concurrency": profile.hardware_concurrency,
            "device_memory": profile.device_memory,
            "gpu_vendor": profile.gpu_vendor,
            "gpu_renderer": profile.gpu_renderer,
            "screen_width": profile.screen_width,
            "screen_height": profile.screen_height,
            "color_depth": profile.color_depth,
            "pixel_ratio": profile.pixel_ratio,
            "languages": profile.languages,
        },
        "stealth_scripts_count": len(orch.get_stealth_scripts()),
    }


# ============================================================
# 频率伪装
# ============================================================
@router.get("/freq/stats")
def get_freq_stats() -> dict:
    """获取频率伪装统计

    返回 FreqDisguise 的统计信息：
    - total_requests: 总请求数
    - noise_requests: 噪声请求数
    - noise_ratio: 噪声占比
    - mean_interval / median_interval / std_interval: 间隔分布统计
    """
    orch = get_orchestrator()
    return {"ok": True, **orch.freq_disguiser.get_stats()}


@router.get("/freq/delay", response_model=None)
def get_request_delay(action: str = "browse") -> dict | JSONResponse:
    """获取指定操作的请求延迟（秒）

    Args:
        action: 操作类型（browse/search/scroll/detail/login）
    """
    try:
        action_type = ActionType(action)
    except ValueError:
        return JSONResponse(content={
            "ok": False,
            "error": f"无效的操作类型: {action}",
            "valid_actions": [a.value for a in ActionType],
        })

    orch = get_orchestrator()
    delay = orch.get_request_delay(action_type)
    return {"ok": True, "action": action, "delay_sec": delay}


# ============================================================
# Cookie 分层管理
# ============================================================
@router.get("/cookies/current")
def get_current_cookies(request: Request) -> dict:
    """读取当前 CookieStore JSON 中的全部 Cookie（供更新弹窗自动预填）

    为什么用此接口而不是直接读 layers：layers 端点只返回每层是否有效与数量，
    不包含 cookie 明文。前端"更新 Cookie"弹窗需要 name=>value 字典来预填文本框。

    多用户隔离：从 request.state.user_id 获取当前登录用户，按 user_id 读取
    cookies_{user_id}.json。
    """
    from xianyu_hunter.web.services.cookie_store import get_cookie_store
    cookie_user_id = getattr(request.state, "user_id", None) or "default"
    store = get_cookie_store()
    store.invalidate_cache(cookie_user_id)
    data = store._read_json(cookie_user_id)
    if not data or not data.get("cookies"):
        return {"ok": True, "cookies": {}, "count": 0}
    cookies = {
        c["name"]: c["value"]
        for c in data["cookies"]
        if c.get("name")
    }
    return {"ok": True, "cookies": cookies, "count": len(cookies)}


@router.post("/cookies/import-from-browser/preview")
def import_from_browser_preview(request: dict = Body(...)) -> JSONResponse:
    """从系统已登录浏览器（Edge/Chrome）读取 Cookie，仅返回不写入

    Request body:
        {"browser": "edge", "auto_close": false}

    与 /api/auth/import-from-browser 的区别：那个端点读取后会立即 export_cookies
    写入 CookieStore，覆盖现有登录态；本接口仅返回 cookie 字典供前端预填文本框，
    由用户确认后调 /cookies/update 才会真正分层写入。
    """
    browser = request.get("browser", "edge")
    auto_close = bool(request.get("auto_close", False))
    # 避免循环导入：放在函数内延迟导入
    from xianyu_hunter.web.routes.browser_import import _do_import_from_browser
    result = _do_import_from_browser(browser, auto_close=auto_close, dry_run=True)
    return JSONResponse(content=result)


def _merge_existing_with_incoming(
    existing_cookies: list[dict], incoming_cookies: dict[str, str],
) -> list[dict]:
    """合并现有 cookie 列表与传入的 cookie 覆盖项

    为什么独立：原 update_cookies 中两个 for 循环 + 嵌套 if 推高认知复杂度。
    合并规则：同名覆盖 value，新增的用默认元信息（.goofish.com 域）。
    """
    # name => cookie_obj 映射（同名取第一条，丢弃其他域名的重复项）
    existing_map: dict[str, dict] = {}
    for c in existing_cookies:
        name = c.get("name", "")
        if name and name not in existing_map:
            existing_map[name] = dict(c)

    # 传入的 cookie 覆盖同名 value，新增的用默认元信息
    for name, value in incoming_cookies.items():
        if name in existing_map:
            existing_map[name]["value"] = value
        else:
            existing_map[name] = {
                "name": name,
                "value": value,
                "domain": ".goofish.com",
                "path": "/",
                "expires": -1,
            }
    return list(existing_map.values())


def _build_cookie_map_from_fresh(fresh_cookies: list[dict]) -> dict[str, str]:
    """从最新 JSON cookie 列表构造 name->value 映射（仅含有效 name/value 的条目）

    为什么独立：原 update_cookies 中字典推导式内的多重 and 条件贡献认知复杂度。
    """
    return {
        c.get("name", ""): c.get("value", "")
        for c in fresh_cookies
        if c.get("name") and c.get("value")
    }


@router.post("/cookies/update")
async def update_cookies(request: Request, body: dict = Body(...)) -> JSONResponse:
    """分层更新 Cookie（合并写入，不丢失已有 Cookie）

    Request body:
        {"cookies": {"unb": "123", "_m_h5_tk": "tk_123", ...}}

    与 on_login_success 的区别：
    - on_login_success 分3次调用 atomic_update，每次触发 export_cookies 覆盖写 JSON,
      导致只有最后一层的 Cookie 被保留，且 session 层因 identity 层未更新而抛异常。
    - 本端点改为：先读取现有 JSON 全量 Cookie，合并传入值后一次性写入，
      再用 sync_state_from_cookies 同步所有层状态，避免覆盖丢失和依赖检查失败。

    多用户隔离：从 request.state.user_id 获取当前登录用户，按 user_id 读写
    cookies_{user_id}.json。原实现硬编码 default，多用户场景下会把 A 用户的
    cookie 写到 default 文件，B 用户切换后读不到自己的 cookie。
    """
    cookies = body.get("cookies", {})
    if not cookies:
        return JSONResponse(content={"ok": False, "error": "cookies 为空"})

    orch = get_orchestrator()
    cookie_user_id = getattr(request.state, "user_id", None) or "default"

    from xianyu_hunter.web.services.cookie_store import get_cookie_store
    cookie_store = get_cookie_store()

    # 1. 读取现有 JSON 中的全部 Cookie（保留 domain/path/expires 等元信息）
    # 必须先清除缓存：浏览器登录子进程写入 JSON 后只更新子进程自己的缓存，
    # 主进程 30 秒 TTL 缓存仍是旧数据（空数据或旧 cookie）。
    # 若不清除，合并时会用旧缓存覆盖丢失子进程刚写入的新 cookie，导致层状态失效
    cookie_store.invalidate_cache(cookie_user_id)
    existing_data = cookie_store._read_json(cookie_user_id)
    existing_cookies: list[dict] = existing_data.get("cookies", []) if existing_data else []

    # 2. 合并现有 cookie 与传入 cookie
    merged_list = _merge_existing_with_incoming(existing_cookies, cookies)

    # 3. 一次性写入合并后的完整列表（export_cookies 内部会过滤测试数据）
    success = cookie_store.export_cookies(merged_list, method="orchestrator_api", user_id=cookie_user_id)
    if not success:
        return JSONResponse(content={
            "ok": False,
            "error": "Cookie 写入失败（可能全部被识别为测试数据）",
        })

    # 4. 直接同步所有层状态，不走 atomic_update 的依赖检查
    # 为什么不用 on_login_success：它会分3次覆盖写 JSON，且 session 层因
    # identity 层未更新而抛 SessionExpiredError，导致只有 tracking 层写入
    # 为什么重新读 JSON 而非用 merged_list：export_cookies 内部会过滤测试数据，
    # 用 merged_list 构造 cookie_map 会包含被过滤的测试数据，导致层状态与 JSON
    # 实际内容不一致（如 unb=123456 被过滤但层状态仍标记 identity 有效）
    fresh_data = cookie_store._read_json(cookie_user_id)
    fresh_cookies = fresh_data.get("cookies", []) if fresh_data else []
    cookie_map = _build_cookie_map_from_fresh(fresh_cookies)
    orch.cookie_rotator.sync_state_from_cookies(cookie_map)

    written = len(fresh_cookies)
    logger.info("Cookie 分层更新完成: 写入后 %d 个 Cookie，已同步层状态", written)

    worker_injected = False
    try:
        from xianyu_hunter.web.services.cookie_runtime_sync import inject_cookie_store_to_worker_browser

        worker_injected = await inject_cookie_store_to_worker_browser("Cookie 分层更新")
    except Exception as e:
        logger.debug("Cookie 分层更新后注入 Worker 浏览器失败: %s", e)

    return JSONResponse(content={
        "ok": True,
        "written": written,
        "worker_injected": worker_injected,
        "message": f"已分层更新 {written} 个 Cookie",
    })


def _filter_valid_cookies_for_sync(
    cookies: list[dict], needed_names: set[str],
) -> dict[str, str]:
    """从 cookie 列表筛选未过期且属于 needed_names 的 cookie，构造 name->value 映射

    为什么独立：JSON 同步（第一步）与浏览器兜底（第二步）使用完全相同的过滤规则，
    提取后避免规则漂移（如修改一处过期判断但另一处漏改）。

    过滤规则：
    - 必须有 name 和 value
    - name 必须在 needed_names 中
    - expires 未过期（session cookie 不过滤）
    - _m_h5_tk 检查内嵌 timestamp 是否过期（cookie.expires=-1 无法判断真实过期，
      否则会与 TokenRenewer 失效标记振荡）
    """
    now = time.time()
    result: dict[str, str] = {}
    for c in cookies:
        name = c.get("name", "")
        value = c.get("value", "")
        if not name or not value or name not in needed_names:
            continue
        expires = c.get("expires", -1)
        if expires and expires > 0 and expires < now:
            continue
        if name == "_m_h5_tk" and is_m5tk_expired(value):
            continue
        result[name] = value
    return result


def _sync_layers_from_json(orch, user_id: str = "default") -> None:
    """第一步：从 JSON 同步层状态（对所有非用户主动失效的层）

    为什么不再只检查 updated_at==0：被 worker.py/cookie_checker 系统失效的层
    updated_at>0 但 valid=False，自动同步需能恢复这些层（cookie 实际仍有效时）。
    仅跳过 manual_invalidate=True 的层：用户通过 /cookies/invalidate 主动失效的层
    不应被自动同步覆盖，需用户重新调用 /cookies/update 才能恢复。

    C-08 修复：接受 user_id 参数，按当前登录用户读取 cookies_{user_id}.json。
    原实现硬编码 default，多用户切换后读取错误用户的 cookie 文件，
    导致层状态显示 invalid（实际新用户 cookie 有效）。
    """
    try:
        from xianyu_hunter.web.services.cookie_store import get_cookie_store
        from xianyu_hunter.modules.cookie_rotator import LAYER_DEFINITIONS

        store = get_cookie_store()
        # 先清除缓存再读取：浏览器登录子进程写入 JSON 后只更新子进程自己的缓存，
        # 主进程的 30 秒 TTL 缓存仍是旧数据。此端点会被前端轮询，必须读到最新 JSON
        store.invalidate_cache(user_id)
        data = store._read_json(user_id)
        if data and data.get("cookies"):
            current_states = orch.cookie_rotator.get_all_states()
            # 筛选需要同步的层：排除用户主动失效的层
            sync_needed_layers = {
                layer for layer, state in current_states.items()
                if not state.manual_invalidate
            }
            if sync_needed_layers:
                needed_names: set[str] = set()
                for layer in sync_needed_layers:
                    needed_names |= LAYER_DEFINITIONS[layer].cookies

                valid_cookies = _filter_valid_cookies_for_sync(data["cookies"], needed_names)
                if valid_cookies:
                    orch.cookie_rotator.sync_state_from_cookies(valid_cookies)
    except Exception as e:
        logger.warning("get_cookie_layers JSON 同步失败: %s", e)


async def _sync_invalid_layers_from_browser(
    orch, still_invalid_layers: set,
) -> None:
    """从浏览器内存读取 cookie 并同步 still_invalid_layers 中各层的状态

    为什么独立：原 _sync_layers_from_browser 中 try + 多层 if 嵌套（4 层）
    是认知复杂度主要来源。拆分后主函数只决定是否进入兜底。
    """
    from xianyu_hunter.web.deps import get_container
    container = get_container()
    if not container.browser or not container.browser._context:
        return

    # 从浏览器内存读取所有 goofish/taobao 域 cookie
    browser_cookies = await container.browser.get_cookies(
        ["goofish.com", "taobao.com"]
    )
    if not browser_cookies:
        return

    from xianyu_hunter.modules.cookie_rotator import LAYER_DEFINITIONS
    needed_names: set[str] = set()
    for layer in still_invalid_layers:
        needed_names |= LAYER_DEFINITIONS[layer].cookies

    # 构造 cookie_map（过滤过期 cookie）
    browser_cookie_map = _filter_valid_cookies_for_sync(browser_cookies, needed_names)
    if not browser_cookie_map:
        return

    orch.cookie_rotator.sync_state_from_cookies(browser_cookie_map)
    # 回写浏览器内存中的关键 cookie 到 JSON，避免下次再兜底
    _write_browser_cookies_to_json(browser_cookies, needed_names)
    logger.info(
        "浏览器内存兜底同步: 从浏览器读取 %d 个 cookie 同步层状态",
        len(browser_cookie_map),
    )


async def _sync_layers_from_browser(orch) -> None:
    """第二步：浏览器内存兜底同步

    为什么需要：JSON 可能缺少 MTOP token（_m_h5_tk）或部分 identity cookie，
    但浏览器内存中有（功能正常）。从浏览器读取后同步层状态 + 回写 JSON。
    兜底同步也排除用户主动失效的层。
    """
    try:
        current_states = orch.cookie_rotator.get_all_states()
        # 兜底同步也排除用户主动失效的层
        still_invalid_layers = {
            layer for layer, state in current_states.items()
            if not state.manual_invalidate and not state.valid
        }
        if still_invalid_layers:
            await _sync_invalid_layers_from_browser(orch, still_invalid_layers)
    except Exception as e:
        logger.debug("get_cookie_layers 浏览器兜底同步失败: %s", e)


def _collect_collector_signal() -> bool:
    """信号1：collector 至少搜索过一次且未检测到会话失效

    为什么需要 has_searched：last_session_invalid 初始值为 False，
    collector 刚启动还没搜索过时 False 不代表"功能正常"，只代表"还没机会检测到失效"。
    """
    try:
        from xianyu_hunter.web.deps import get_container
        container = get_container()
        if container.collector:
            # _last_m5tk_refresh 是 monotonic 时间戳，初始 0.0，搜索后 >0
            # 访问私有属性是防御性编程：Collector 未提供公共 getter
            has_searched = getattr(container.collector, '_last_m5tk_refresh', 0.0) > 0
            session_ok = not getattr(container.collector, 'last_session_invalid', True)
            if has_searched and session_ok:
                return True
    except Exception:
        pass
    return False


def _collect_json_m5tk_signal(user_id: str = "default") -> bool:
    """信号2：JSON 中存在未过期的 _m_h5_tk（session token 有效说明登录态仍有效）

    为什么检查 timestamp 过期：_m_h5_tk 可能存在但已过期（cookie.expires=-1 无法判断），
    此时不能作为"功能正常"的信号恢复 session 层，否则会与 TokenRenewer 振荡。

    C-08 修复：接受 user_id 参数，按当前登录用户读取 cookies_{user_id}.json。
    """
    try:
        from xianyu_hunter.web.services.cookie_store import get_cookie_store
        store_for_check = get_cookie_store()
        json_data = store_for_check._read_json(user_id)
        if json_data and json_data.get("cookies"):
            return any(
                c.get("name") == "_m_h5_tk" and c.get("value")
                and not is_m5tk_expired(c.get("value", ""))
                for c in json_data["cookies"]
            )
    except Exception:
        pass
    return False


def _compute_layers_to_restore(
    still_invalid: set, functional_signals: set[str],
) -> set:
    """根据功能信号组合计算可恢复的层集合

    不同信号能恢复的层范围不同（避免用 session 信号恢复 identity 层）：
    - collector.last_session_invalid=False: collector 实际搜索成功，
      说明整个登录链路有效，可恢复所有层
    - json_has_valid_m5tk: _m_h5_tk 属于 SESSION 层，
      只能证明 session 有效，且需 IDENTITY 已有效（SESSION 依赖 IDENTITY）
    """
    if "collector.last_session_invalid=False" in functional_signals:
        return still_invalid
    if "json_has_valid_m5tk" in functional_signals:
        if CookieLayer.IDENTITY in still_invalid:
            # IDENTITY 无效时 SESSION 也不能恢复（依赖关系）
            return set()
        return still_invalid & {CookieLayer.SESSION}
    # 防御性：未来新增信号未在此处处理时不应默认恢复所有层
    logger.warning("未识别的功能信号组合: %s", functional_signals)
    return set()


def _functional_fallback_restore(orch, user_id: str = "default") -> None:
    """第三步：功能可用性兜底——前两步同步后仍有层失效时，基于实际功能状态恢复

    为什么需要：JSON 可能缺少某些 cookie（子进程只写了部分），浏览器也可能未初始化，
    但实际功能正常（搜索/采集都能用），此时应反映真实可用性而非机械地依赖 cookie 检测。

    C-08 修复：接受 user_id 参数，透传给 _collect_json_m5tk_signal。
    """
    try:
        current_states = orch.cookie_rotator.get_all_states()
        still_invalid = {
            layer for layer, state in current_states.items()
            if not state.manual_invalidate and not state.valid
        }
        if not still_invalid:
            return

        # 收集功能可用信号：任一信号为真即认为功能正常
        functional_signals: set[str] = set()
        if _collect_collector_signal():
            functional_signals.add("collector.last_session_invalid=False")
        if _collect_json_m5tk_signal(user_id):
            functional_signals.add("json_has_valid_m5tk")

        if not functional_signals:
            return

        layers_to_restore = _compute_layers_to_restore(still_invalid, functional_signals)
        if not layers_to_restore:
            return

        restored = orch.cookie_rotator.force_restore_layers(
            layers_to_restore,
            reason=f"functional_signals={functional_signals}",
        )
        if restored:
            # 用 %d/%s 而非 {}：标准 logging 用 % 惰性格式化，{} 不会被替换
            logger.info(
                "功能可用性兜底恢复: %d 个层已恢复 (signals=%s)",
                len(restored), functional_signals,
            )
    except Exception as e:
        logger.warning("get_cookie_layers 功能可用性兜底失败: %s", e)


@router.get("/cookies/layers")
async def get_cookie_layers(request: Request) -> dict:
    """获取 Cookie 各层状态

    返回三层（identity/session/tracking）的有效性、更新时间、Cookie 数量。

    为什么需要自动同步：服务重启或协调器初始化后，内存层状态默认全 False，
    即使 JSON 中有有效 Cookie 也会显示失效。这里读取 JSON 实际内容并同步层状态，
    保证返回的状态与 JSON 真实内容一致（与 /health 中 cookie_checker 同样的同步策略）。

    同步条件：只同步 updated_at=0 的层（从未初始化过的层）。
    为什么不全量同步：invalidate_layer 是用户主动失效某层的操作，
    若全量同步会从 JSON 重新读取 cookie 覆盖失效状态，导致级联失效失效。

    浏览器内存兜底：JSON 可能缺少某些 cookie（如 MTOP token 未回写、登录路径
    只写了部分 cookie），但浏览器内存中有有效 cookie（功能正常）。
    当 JSON 同步后仍有层失效时，从浏览器内存读取 cookie 作为兜底同步源，
    确保层状态反映浏览器实际状态。

    C-08 修复：从 request.state.user_id 获取当前登录用户，传递给同步函数。
    原实现硬编码 default，多用户切换后读取错误用户的 cookie 文件。
    """
    orch = get_orchestrator()
    # 多用户场景：中间件注入 request.state.user_id，无会话时降级 default
    cookie_user_id = getattr(request.state, "user_id", None) or "default"

    _sync_layers_from_json(orch, cookie_user_id)
    await _sync_layers_from_browser(orch)
    _functional_fallback_restore(orch, cookie_user_id)

    states = orch.cookie_rotator.get_all_states()

    # 状态汇总日志：便于排查"功能正常但状态失效"问题
    states_summary = {
        layer.value: {
            "valid": state.valid,
            "cookies": state.cookie_count,
            "manual": state.manual_invalidate,
        }
        for layer, state in states.items()
    }
    logger.debug("Cookie 层状态返回: %s", states_summary)

    return {
        "ok": True,
        "layers": {
            layer.value: {
                "valid": state.valid,
                "updated_at": state.updated_at,
                "cookie_count": state.cookie_count,
            }
            for layer, state in states.items()
        },
    }


def _write_browser_cookies_to_json(browser_cookies: list[dict], needed_names: set[str]) -> None:
    """将浏览器内存中缺失的关键 cookie 回写到 JSON

    为什么需要：JSON 可能缺少某些 cookie（如 MTOP token），导致每次 /cookies/layers
    都要从浏览器兜底。回写后 JSON 数据完整，后续可直接从 JSON 同步。
    只回写 needed_names 中的 cookie，避免全量覆盖。
    用 upsert 而非 update：JSON 中可能完全不存在该 cookie 条目，需要能新增。
    """
    try:
        from xianyu_hunter.web.services.cookie_store import get_cookie_store
        store = get_cookie_store()
        # 构造 upserts 字典：包含 value/domain/path/expires 完整信息
        upserts = {
            c.get("name", ""): {
                "value": c.get("value", ""),
                "domain": c.get("domain", ".goofish.com"),
                "path": c.get("path", "/"),
                "expires": c.get("expires", -1),
            }
            for c in browser_cookies
            if c.get("name") in needed_names and c.get("value")
        }
        if upserts:
            store.upsert_cookie_values(upserts)
    except Exception:
        # 回写失败不影响层状态同步（层状态已通过 sync_state_from_cookies 更新）
        pass


@router.post("/cookies/invalidate")
def invalidate_cookie_layer(request: dict = Body(...)) -> JSONResponse:
    """使指定 Cookie 层失效

    Request body:
        {"layer": "session"}  - 失效层（identity/session/tracking）

    identity 层失效会级联导致 session 层失效。
    """
    layer_name = request.get("layer", "")
    try:
        layer = CookieLayer(layer_name)
    except ValueError:
        return JSONResponse(content={
            "ok": False,
            "error": f"无效的层名: {layer_name}",
            "valid_layers": [l.value for l in CookieLayer],
        })

    orch = get_orchestrator()
    # 为什么 manual=True：用户主动失效需被保留，避免 /cookies/layers 自动同步覆盖
    # 用户主动失效后通常需重新登录或调用 /cookies/update 才能恢复层状态
    orch.cookie_rotator.invalidate_layer(layer, manual=True)

    return JSONResponse(content={
        "ok": True,
        "message": f"层 {layer_name} 已标记失效（主动失效，需重新登录或更新 Cookie 恢复）",
        "cascaded": layer == CookieLayer.IDENTITY,
    })


# ============================================================
# 策略设置
# ============================================================
@router.post("/strategy/set")
def set_current_strategy(request: dict = Body(...)) -> JSONResponse:
    """设置当前使用的登录策略

    Request body:
        {"strategy": "cdp_connect"}  - 策略名

    用于记录实际使用的策略，状态查询时会返回此值。
    """
    strategy_name = request.get("strategy", "")
    try:
        strategy = LoginStrategy(strategy_name)
    except ValueError:
        return JSONResponse(content={
            "ok": False,
            "error": f"无效的策略名: {strategy_name}",
            "valid_strategies": [s.value for s in LoginStrategy],
        })

    orch = get_orchestrator()
    orch.set_current_strategy(strategy)

    return JSONResponse(content={
        "ok": True,
        "strategy": strategy.value,
        "message": f"当前策略已设置为: {strategy.value}",
    })
