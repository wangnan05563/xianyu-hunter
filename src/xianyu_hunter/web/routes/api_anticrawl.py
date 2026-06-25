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
from typing import Any

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from xianyu_hunter.modules.cookie_rotator import CookieLayer, LAYER_DEFINITIONS
from xianyu_hunter.modules.freq_disguise import ActionType
from xianyu_hunter.modules.login_orchestrator import get_orchestrator
from xianyu_hunter.modules.login_strategy import LoginStrategy
from xianyu_hunter.modules.session_health import WAFStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/anticrawl", tags=["anticrawl"])


def _configure_default_health_checkers(orch) -> None:
    """为协调器配置默认健康检查器

    为什么在 initialize 时自动配置：避免前端需要额外调用 configure 端点，
    初始化后健康检查即可直接使用。api/page 维度未配置时默认通过，
    主要依赖 cookie（权重40）和 waf（权重10）维度。
    """
    # Cookie 检查器：基于 JSON 实际内容判断 + 自动同步层状态
    # 为什么不依赖 CookieRotator 内存状态：browser_login / auth_helper /
    # browser_import / cookie_inject 等登录路径只调用 export_cookies 写入 JSON，
    # 未调用 on_login_success，导致层状态为默认 False，引发误判
    def cookie_checker() -> bool:
        try:
            from xianyu_hunter.web.services.cookie_store import get_cookie_store
            store = get_cookie_store()
            data = store._read_json()
            if not data or not data.get("cookies"):
                logger.debug("cookie_checker: JSON 无 Cookie 数据")
                return False

            cookies_list = data["cookies"]
            names = {c.get("name", "") for c in cookies_list}

            # 1. session 层：_m_h5_tk 必须存在且有值
            has_token = any(
                c.get("name") == "_m_h5_tk" and c.get("value")
                for c in cookies_list
            )
            if not has_token:
                logger.debug("cookie_checker: _m_h5_tk 缺失或无值")
                return False

            # 2. identity 层：至少一个身份 Cookie 存在
            # 为什么用"至少一个"而非"全部"：不同登录方式返回的 Cookie 集合不同，
            # 扫码登录可能不返回 sgcookie，强制要求全部会导致误判
            identity_cookies = LAYER_DEFINITIONS[CookieLayer.IDENTITY].cookies
            has_identity = bool(identity_cookies & names)
            if not has_identity:
                logger.debug("cookie_checker: identity 层 Cookie 缺失 (names=%s)", names)
                return False

            # 3. 过期时间检查（兼容旧数据：无 expires 字段视为 session cookie）
            now = time.time()
            for c in cookies_list:
                expires = c.get("expires", -1)
                if expires and expires > 0 and expires < now:
                    logger.warning(
                        "cookie_checker: Cookie 已过期: %s (expires=%d, now=%d)",
                        c.get("name"), expires, now,
                    )
                    return False

            # 4. 自动同步层状态（修复状态不一致）
            # 为什么需要：登录路径只写 JSON 未更新层状态，导致 /cookies/layers 误显示无效
            states = orch.cookie_rotator.get_all_states()
            identity_state = states.get(CookieLayer.IDENTITY)
            if not identity_state or not identity_state.valid:
                logger.info("cookie_checker: Cookie 有效但层状态未初始化，自动同步")
                cookie_map = {c.get("name", ""): c.get("value", "") for c in cookies_list}
                orch.cookie_rotator.sync_state_from_cookies(cookie_map)

            # 5. 检查 collector 的会话失效标志
            # 为什么需要：cookie 存在不代表服务端仍认可，RGV587_ERROR 表示
            # 服务端已注销会话，此时 cookie 虽在本地但已失效
            try:
                from xianyu_hunter.web.deps import get_container
                container = get_container()
                if container.collector and getattr(container.collector, 'last_session_invalid', False):
                    logger.warning("cookie_checker: collector 检测到 RGV587_ERROR，会话已失效")
                    # 主动失效 identity 层，让 /cookies/layers 也能反映真实状态
                    orch.cookie_rotator.invalidate_layer(CookieLayer.IDENTITY)
                    return False
            except Exception:
                pass

            return True
        except Exception as e:
            logger.warning("cookie_checker 失败: %s", e)
            return False

    # WAF 状态提供器：基于验证码处理统计推断风控状态
    def waf_provider() -> WAFStatus:
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


@router.post("/session/start")
async def start_session(request: dict = Body(default_factory=dict)) -> JSONResponse:
    """启动会话管理（TokenRenewer 后台续期）

    Request body (可选):
        {"cookie_provider_name": "_m_h5_tk"}  - Cookie 名称（默认 _m_h5_tk）

    启动后 TokenRenewer 会定期检查 token 年龄，过期前自动续期。
    续期失败会触发 session 层 Cookie 失效。
    """
    orch = get_orchestrator()

    if orch.is_session_active:
        return JSONResponse(content={
            "ok": False,
            "error": "会话已处于活跃状态，请先停止当前会话",
        })

    # 默认从 CookieStore 读取 _m_h5_tk
    cookie_name = request.get("cookie_provider_name", "_m_h5_tk")

    def cookie_provider() -> str | None:
        """从 CookieStore 读取 token 值

        为什么用闭包而非直接传值：token 会随续期更新，
        provider 函数每次调用都读取最新值。
        """
        try:
            from xianyu_hunter.web.services.cookie_store import get_cookie_store
            store = get_cookie_store()
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

    # 续期回调：通过浏览器导航触发 token 刷新
    async def renew_callback() -> bool:
        """通过浏览器导航到 m.taobao.com 触发 token 续期

        为什么用导航而非 API：导航是用户自然行为，
        风控压力低于直接调用 getTimestamp API。
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
                return True
            finally:
                await page.close()
        except Exception as e:
            logger.warning("token 续期回调失败: %s", e)
            return False

    try:
        await orch.start_session(cookie_provider=cookie_provider, renew_callback=renew_callback)
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
async def check_health() -> JSONResponse:
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

    try:
        report = await orch.check_health()
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


@router.get("/freq/delay")
def get_request_delay(action: str = "browse") -> dict:
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
@router.post("/cookies/update")
def update_cookies(request: dict = Body(...)) -> JSONResponse:
    """登录成功后分层更新 Cookie

    Request body:
        {"cookies": {"unb": "123", "_m_h5_tk": "tk_123", ...}}

    自动将 Cookie 分类到 identity/session/tracking 三层并原子更新。
    更新顺序：identity → session → tracking，保证依赖关系。
    """
    cookies = request.get("cookies", {})
    if not cookies:
        return JSONResponse(content={"ok": False, "error": "cookies 为空"})

    orch = get_orchestrator()

    # 设置 writer：优先使用 CookieStore JSON 持久化
    # 为什么不用浏览器写入：跨线程调用 Playwright add_cookies 存在死锁风险
    # CookieStore JSON 已经是浏览器启动时的 Cookie 来源，保持一致
    from xianyu_hunter.web.services.cookie_store import get_cookie_store
    cookie_store = get_cookie_store()

    def json_writer(cookies_list: list[dict]) -> int:
        cookie_store.export_cookies(cookies_list, method="orchestrator_api")
        return len(cookies_list)

    orch.set_cookie_writer(json_writer)

    # 如果浏览器上下文可用，异步写入浏览器（best-effort，非阻塞）
    try:
        from xianyu_hunter.web.deps import get_container
        container = get_container()
        if container.browser and container.browser._context:
            import asyncio
            cookies_copy = [
                {"name": c["name"], "value": c["value"], "domain": c.get("domain", ".goofish.com"),
                 "path": c.get("path", "/")}
                for c in cookies_list
            ]
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 不等待结果，fire-and-forget 避免死锁
                    asyncio.ensure_future(
                        container.browser._context.add_cookies(cookies_copy)
                    )
            except Exception:
                pass
    except Exception:
        pass

    try:
        written = orch.on_login_success(cookies)
        return JSONResponse(content={
            "ok": True,
            "written": written,
            "message": f"已分层更新 {written} 个 Cookie",
        })
    except Exception as e:
        logger.error("Cookie 分层更新失败: %s", e)
        return JSONResponse(content={
            "ok": False,
            "error": f"Cookie 更新失败: {e}",
            "hint": "可能是依赖层未先更新（session 层需 identity 层先有效）",
        })


@router.get("/cookies/layers")
def get_cookie_layers() -> dict:
    """获取 Cookie 各层状态

    返回三层（identity/session/tracking）的有效性、更新时间、Cookie 数量。
    """
    orch = get_orchestrator()
    states = orch.cookie_rotator.get_all_states()

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
    orch.cookie_rotator.invalidate_layer(layer)

    return JSONResponse(content={
        "ok": True,
        "message": f"层 {layer_name} 已标记失效",
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
