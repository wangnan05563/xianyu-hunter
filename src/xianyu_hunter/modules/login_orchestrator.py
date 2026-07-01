"""登录协调器（设计文档 §4 架构核心）

串联所有反爬模块，提供统一的登录/会话管理入口。

职责：
1. 登录策略选择 — 调用 LoginStrategySelector 评估最优登录路径
2. 指纹管理 — 为 launch 模式生成一致的 FingerprintProfile
3. 会话生命周期 — 启动/停止 TokenRenewer + SessionHealthChecker
4. Cookie 管理 — 通过 CookieRotator 分层管理 Cookie
5. 风控对抗 — 集成 FreqDisguise + CaptchaHandler
6. 状态查询 — 提供统一的会话状态 API

使用方式：
    orchestrator = LoginOrchestrator()
    orchestrator.initialize(use_cdp=False)

    # 获取推荐登录策略
    evaluation = orchestrator.evaluate_strategy()

    # 登录成功后启动会话管理
    await orchestrator.start_session(cookie_provider, renew_callback)

    # 获取会话状态
    status = orchestrator.get_session_status()

    # 停止会话
    await orchestrator.stop_session()
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from xianyu_hunter.infra.logger import get_logger
from xianyu_hunter.modules.awsc_spoof import get_awsc_spoof_script, is_awsc_spoof_needed
from xianyu_hunter.modules.captcha_handler import CaptchaHandler, CaptchaDetection
from xianyu_hunter.modules.cookie_rotator import CookieLayer, CookieRotator
from xianyu_hunter.modules.fingerprint import FingerprintProfile, build_stealth_script
from xianyu_hunter.modules.freq_disguise import ActionType, FreqDisguise
from xianyu_hunter.modules.login_strategy import LoginStrategy, LoginStrategySelector, StrategyEvaluation
from xianyu_hunter.modules.session_health import HealthAction, SessionHealthChecker, WAFStatus
from xianyu_hunter.modules.token_renewer import RenewResult, RenewerConfig, TokenRenewer

logger = get_logger()


@dataclass
class SessionStatus:
    """会话状态摘要"""
    active: bool = False
    strategy: str = ""                    # 当前使用的登录策略
    fingerprint_profile: str = ""         # 当前指纹 profile 名称
    token_age_sec: float | None = None
    token_expired: bool | None = None
    health_score: int | None = None
    health_action: str = ""
    waf_status: str = ""
    cookie_layers: dict[str, bool] = field(default_factory=dict)
    freq_stats: dict[str, Any] = field(default_factory=dict)
    captcha_stats: dict[str, int] = field(default_factory=dict)
    started_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "active": self.active,
            "strategy": self.strategy,
            "fingerprint_profile": self.fingerprint_profile,
            "token_age_sec": self.token_age_sec,
            "token_expired": self.token_expired,
            "health_score": self.health_score,
            "health_action": self.health_action,
            "waf_status": self.waf_status,
            "cookie_layers": self.cookie_layers,
            "freq_stats": self.freq_stats,
            "captcha_stats": self.captcha_stats,
            "started_at": self.started_at,
            "uptime_sec": time.time() - self.started_at if self.active else 0,
        }


class LoginOrchestrator:
    """登录协调器

    串联所有反爬模块，提供统一的登录/会话管理入口。
    不直接执行登录操作（由 route handler 完成），
    而是提供策略选择、指纹管理、会话监控等协调功能。
    """

    def __init__(self):
        # 模块实例
        self._strategy_selector = LoginStrategySelector()
        self._fingerprint_profile: FingerprintProfile | None = None
        self._cookie_rotator = CookieRotator()
        self._token_renewer = TokenRenewer()
        self._health_checker = SessionHealthChecker()
        self._freq_disguiser = FreqDisguise()
        self._captcha_handler = CaptchaHandler()

        # 会话状态
        self._session_active = False
        self._started_at: float = 0.0
        self._current_strategy: LoginStrategy | None = None
        self._use_cdp: bool = False

    # ============== 初始化 ==============

    def initialize(self, use_cdp: bool = False) -> None:
        """初始化协调器

        Args:
            use_cdp: 是否使用 CDP 模式（真实浏览器，无需指纹注入）
        """
        self._use_cdp = use_cdp

        if not use_cdp:
            # launch 模式需要生成指纹 profile
            self._fingerprint_profile = FingerprintProfile.random()
            logger.info(
                "LoginOrchestrator 初始化: mode=launch, profile={}",
                self._fingerprint_profile.name,
            )
        else:
            self._fingerprint_profile = None
            logger.info("LoginOrchestrator 初始化: mode=cdp, 无需指纹注入")

    # ============== 策略选择 ==============

    def evaluate_strategy(self) -> StrategyEvaluation:
        """评估并推荐登录策略"""
        return self._strategy_selector.evaluate()

    # ============== 指纹管理 ==============

    def get_fingerprint_profile(self) -> FingerprintProfile | None:
        """获取当前指纹 profile"""
        return self._fingerprint_profile

    def get_stealth_scripts(self) -> list[str]:
        """获取需要注入的 stealth 脚本列表

        CDP 模式返回空列表（无需注入）。
        launch 模式返回 [fingerprint_stealth, awsc_spoof]。
        """
        if self._use_cdp or self._fingerprint_profile is None:
            return []

        scripts = [
            build_stealth_script(self._fingerprint_profile),
        ]

        # launch 模式需要 AWSC 伪装
        if is_awsc_spoof_needed(use_cdp=self._use_cdp):
            scripts.append(get_awsc_spoof_script())

        return scripts

    def get_user_agent(self) -> str | None:
        """获取当前指纹 profile 的 User-Agent"""
        if self._fingerprint_profile:
            return self._fingerprint_profile.ua
        return None

    # ============== Cookie 管理 ==============

    @property
    def cookie_rotator(self) -> CookieRotator:
        """获取 CookieRotator 实例"""
        return self._cookie_rotator

    def set_cookie_writer(self, writer: Callable[[list[dict]], int]) -> None:
        """设置 Cookie 写入函数"""
        self._cookie_rotator.set_writer(writer)

    def on_login_success(self, cookies: dict[str, str]) -> int:
        """登录成功后更新 Cookie

        自动分类 Cookie 到对应层并原子更新。
        """
        # 分离 identity 和 session 层 Cookie
        identity_cookies = {}
        session_cookies = {}
        tracking_cookies = {}

        from xianyu_hunter.modules.cookie_rotator import _COOKIE_TO_LAYER

        for name, value in cookies.items():
            layer = _COOKIE_TO_LAYER.get(name, CookieLayer.TRACKING)
            if layer == CookieLayer.IDENTITY:
                identity_cookies[name] = value
            elif layer == CookieLayer.SESSION:
                session_cookies[name] = value
            else:
                tracking_cookies[name] = value

        written = 0

        # 按顺序更新：identity → session → tracking
        if identity_cookies:
            written += self._cookie_rotator.atomic_update(identity_cookies)
        if session_cookies:
            written += self._cookie_rotator.atomic_update(session_cookies)
        if tracking_cookies:
            written += self._cookie_rotator.atomic_update(tracking_cookies)

        logger.info("登录成功，Cookie 已更新: identity={}, session={}, tracking={}",
                    len(identity_cookies), len(session_cookies), len(tracking_cookies))
        return written

    # ============== 会话生命周期 ==============

    async def start_session(
        self,
        cookie_provider: Callable[[], str | None],
        renew_callback: Callable[[], Awaitable[bool]] | None = None,
    ) -> None:
        """启动会话管理

        启动 TokenRenewer 后台续期循环。
        SessionHealthChecker 需要单独配置检查器后调用 check()。

        Args:
            cookie_provider: 返回当前 _m_h5_tk 值的函数
            renew_callback: token 续期回调（如发起 getTimestamp API 请求）
        """
        if self._session_active:
            logger.warning("会话已处于活跃状态")
            return

        self._session_active = True
        self._started_at = time.time()

        # 配置 TokenRenewer
        self._token_renewer.set_cookie_provider(cookie_provider)
        if renew_callback:
            self._token_renewer.set_renew_callback(renew_callback)

        # 设置续期失败回调：标记 Cookie 层失效
        def on_renew_fail():
            # manual=False：系统失效可被 /cookies/layers 自动同步恢复（cookie 实际有效时）
            self._cookie_rotator.invalidate_layer(CookieLayer.SESSION, manual=False)
            logger.warning("Token 续期失败，session 层已标记失效")

        self._token_renewer.set_renew_fail_callback(on_renew_fail)

        # 启动后台续期
        await self._token_renewer.start()

        logger.info("会话管理已启动")

    # ============== 默认会话启动（登录后自动调用） ==============

    def _default_cookie_provider(self) -> str | None:
        """默认 token provider：从 CookieStore 读取 _m_h5_tk

        为什么抽到协调器上：登录入口（unified_login/browser_login/
        browser_import/cookie_inject）都会调起会话，需要统一实现避免分散。
        cookie_store 延迟导入避免 LoginOrchestrator 引入 web 层编译期依赖。
        """
        try:
            from xianyu_hunter.web.services.cookie_store import get_cookie_store
            store = get_cookie_store()
            store.invalidate_cache()
            data = store._read_json()
            if not data or not data.get("cookies"):
                return None
            from xianyu_hunter.modules.cookie_rotator import is_m5tk_expired
            expired_seen = False
            for c in data["cookies"]:
                if c.get("name") == "_m_h5_tk":
                    value = c.get("value", "")
                    if value and not is_m5tk_expired(value):
                        return value
                    expired_seen = True
            if expired_seen:
                logger.debug("默认 cookie_provider 读取到过期 _m_h5_tk，等待重新登录或浏览器刷新")
            return None
        except Exception as e:
            logger.debug("默认 cookie_provider 读取失败: {}", e)
            return None

    async def _default_renew_callback(self) -> bool:
        """默认 token 续期回调：通过浏览器导航到 m.taobao.com 触发

        为什么用导航而非 API：导航是用户自然行为，
        风控压力低于直接调用 getTimestamp API。
        浏览器不可用时返回 False（TokenRenewer 续期失败会触发 on_renew_fail）。

        为什么续期后要回写 Cookie：导航触发的 Set-Cookie 会更新 Worker 浏览器
        内存中的 _m_h5_tk 等 token，但 CookieStore JSON 仍是登录时的旧值。
        不回写会导致健康检查误判 token 过期、实时搜索从 JSON 补注入旧 token。
        回写后形成完整闭环：登录（全量）→ 续期（增量同步）→ 失效重新登录。
        """
        page = None
        try:
            from xianyu_hunter.web.deps import get_container
            container = get_container()
            if not container.browser or not container.browser._context:
                logger.debug("默认 renew_callback: 浏览器不可用")
                return False
            page = await container.browser.new_page()
            try:
                await page.goto("https://h5.m.taobao.com/", wait_until="domcontentloaded", timeout=10000)
            finally:
                await page.close()

            # 导航成功后提取完整 Cookie 回写 CookieStore，保持 JSON 与浏览器内存一致
            # 只提取 goofish/taobao 域，避免写入无关域的 Cookie
            try:
                cookies = await container.browser.get_cookies(["goofish.com", "taobao.com"])
                if cookies:
                    from xianyu_hunter.web.services.cookie_store import get_cookie_store
                    get_cookie_store().export_cookies(cookies, method="renew")
                    logger.debug("token 续期后已同步 {} 个 cookie 到 CookieStore", len(cookies))
            except Exception as e:
                # 回写失败不影响续期成功状态（token 已在浏览器内存中刷新）
                logger.warning("token 续期后回写 CookieStore 失败: {}", e)
            return True
        except Exception as e:
            logger.debug("默认 token 续期回调失败: {}", e)
            return False

    async def start_session_default(self) -> bool:
        """使用默认 cookie_provider + renew_callback 启动会话

        用于登录成功后自动启动会话管理（TokenRenewer 后台续期）。
        失败仅记录日志，不抛异常（避免影响登录成功的返回路径）。

        Returns:
            True 启动成功或会话已活跃；False 启动失败
        """
        if self._session_active:
            return True
        try:
            await self.start_session(
                cookie_provider=self._default_cookie_provider,
                renew_callback=self._default_renew_callback,
            )
            return True
        except Exception as e:
            logger.error("自动启动会话失败: {}", e)
            return False

    async def stop_session(self) -> None:
        """停止会话管理"""
        if not self._session_active:
            return

        await self._token_renewer.stop()
        self._session_active = False
        logger.info("会话管理已停止")

    @property
    def is_session_active(self) -> bool:
        """会话是否活跃"""
        return self._session_active

    # ============== 健康检查 ==============

    @property
    def health_checker(self) -> SessionHealthChecker:
        """获取 SessionHealthChecker 实例"""
        return self._health_checker

    def configure_health_checkers(
        self,
        cookie_checker: Callable[[], bool] | None = None,
        api_checker: Callable[[], Awaitable[bool]] | None = None,
        page_checker: Callable[[], Awaitable[bool]] | None = None,
        waf_provider: Callable[[], WAFStatus] | None = None,
    ) -> None:
        """配置健康检查器

        各检查器可选，未设置的维度默认通过。
        """
        if cookie_checker:
            self._health_checker.set_cookie_checker(cookie_checker)
        if api_checker:
            self._health_checker.set_api_checker(api_checker)
        if page_checker:
            self._health_checker.set_page_checker(page_checker)
        if waf_provider:
            self._health_checker.set_waf_status_provider(waf_provider)

    async def check_health(self):
        """执行健康检查"""
        return await self._health_checker.check()

    # ============== 频率伪装 ==============

    @property
    def freq_disguiser(self) -> FreqDisguise:
        """获取 FreqDisguise 实例"""
        return self._freq_disguiser

    def get_request_delay(self, action: ActionType) -> float:
        """获取请求延迟（秒）

        在执行操作前调用，等待返回的秒数后再发起请求。
        """
        return self._freq_disguiser.next_interval(action)

    def should_insert_noise(self) -> bool:
        """是否应插入噪声请求"""
        return self._freq_disguiser.should_insert_noise()

    async def apply_freq_delay(self, action: ActionType) -> float:
        """应用频率伪装延迟（业务模块集成入口）

        统一封装"获取延迟 + sleep"，让 collector/buyer 等业务模块
        一行调用即可完成频率伪装。统计计数器在 next_interval 内部累加，
        确保统计数据准确反映实际请求节奏。

        噪声请求判断未在此处自动调用：should_insert_noise 会累加 _noise_count，
        若调用方不执行噪声请求会导致统计虚高。需要噪声请求时调用方应显式调用
        should_insert_noise() 并自行执行。

        Returns:
            delay_sec: 实际等待秒数
        """
        delay = self._freq_disguiser.next_interval(action)
        await asyncio.sleep(delay)
        return delay

    def record_freq_request(self, action: ActionType) -> None:
        """仅记录请求统计（不 sleep）

        用于抢单等时间敏感场景：统计计数器累加，但不引入额外延迟。
        """
        self._freq_disguiser.record_request(action)

    # ============== 验证码处理 ==============

    @property
    def captcha_handler(self) -> CaptchaHandler:
        """获取 CaptchaHandler 实例"""
        return self._captcha_handler

    def configure_captcha_handler(
        self,
        detector: Callable[[], Awaitable[CaptchaDetection]] | None = None,
        auto_solver: Callable[[CaptchaDetection], Awaitable[bool]] | None = None,
        manual_handler: Callable[[CaptchaDetection], Awaitable[bool]] | None = None,
    ) -> None:
        """配置验证码处理器"""
        if detector:
            self._captcha_handler.set_detector(detector)
        if auto_solver:
            self._captcha_handler.set_auto_solver(auto_solver)
        if manual_handler:
            self._captcha_handler.set_manual_handler(manual_handler)

    # ============== 状态查询 ==============

    def get_session_status(self) -> SessionStatus:
        """获取会话状态摘要"""
        # Token 状态
        token_status = self._token_renewer.get_status()

        # 健康状态
        last_report = self._health_checker.get_last_report()

        # Cookie 层状态
        cookie_states = self._cookie_rotator.get_all_states()

        return SessionStatus(
            active=self._session_active,
            strategy=self._current_strategy.value if self._current_strategy else "",
            fingerprint_profile=self._fingerprint_profile.name if self._fingerprint_profile else "",
            token_age_sec=token_status.get("token_age_sec"),
            token_expired=token_status.get("token_expired"),
            health_score=last_report.score if last_report else None,
            health_action=last_report.action.value if last_report else "",
            waf_status=last_report.waf_status.value if last_report else "",
            cookie_layers={
                layer.value: state.valid for layer, state in cookie_states.items()
            },
            freq_stats=self._freq_disguiser.get_stats(),
            captcha_stats=self._captcha_handler.get_stats(),
            started_at=self._started_at,
        )

    def set_current_strategy(self, strategy: LoginStrategy) -> None:
        """设置当前使用的登录策略"""
        self._current_strategy = strategy
        logger.info("当前登录策略: {}", strategy.value)


# ============== 单例 ==============

_orchestrator: LoginOrchestrator | None = None


def get_orchestrator() -> LoginOrchestrator:
    """获取 LoginOrchestrator 单例"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = LoginOrchestrator()
    return _orchestrator


def sync_cookie_layers_from_json() -> bool:
    """从 CookieStore JSON 同步 CookieRotator 层状态

    在所有登录路径（browser_login / auth_helper / cookie_inject / browser_import）
    成功写入 JSON 后调用，确保层状态与 JSON 实际内容一致。

    为什么需要此函数：on_login_success 从未被调用，导致登录后层状态保持初始 False，
    /cookies/layers 显示失效。此函数作为统一补救入口，替代 on_login_success 的职责。

    与 /cookies/layers 端点的同步逻辑一致：
    1. 重新读 JSON 构造 cookie_map（export_cookies 内部已过滤测试数据）
    2. 过滤已过期的 cookie（expires > 0 且 < now），避免过期 cookie 误标层为 valid

    Returns:
        True 表示同步成功，False 表示同步失败或无数据
    """
    try:
        import time as _time
        from xianyu_hunter.web.services.cookie_store import get_cookie_store
        from xianyu_hunter.modules.cookie_rotator import is_m5tk_expired
        store = get_cookie_store()
        # 必须先清除缓存再读取：浏览器登录子进程是独立 Python 进程，
        # 写入 cookies.json 后只更新子进程自己的缓存，主进程的 30 秒 TTL 缓存仍是旧数据。
        # 不清除缓存会读到旧的空数据/失效数据，导致层状态无法及时更新
        store.invalidate_cache()
        data = store._read_json()
        if not data or not data.get("cookies"):
            return False
        # 过滤过期 cookie：与 /cookies/layers 端点保持一致
        # expires <= 0 视为 session cookie（不过期），expires > 0 且 < now 视为已过期
        # _m_h5_tk 特殊处理：cookie.expires=-1 无法判断真实过期，需检查内嵌 timestamp，
        # 否则登录后旧 token 仍会同步给 CookieRotator，与 TokenRenewer 失效标记振荡
        now = _time.time()
        cookie_map = {
            c.get("name", ""): c.get("value", "")
            for c in data["cookies"]
            if c.get("name") and c.get("value")
            and not (c.get("expires", -1) and c.get("expires", -1) > 0 and c.get("expires", -1) < now)
            and not (c.get("name") == "_m_h5_tk" and is_m5tk_expired(c.get("value", "")))
        }
        if not cookie_map:
            return False
        get_orchestrator().cookie_rotator.sync_state_from_cookies(cookie_map)
        return True
    except Exception as e:
        logger.warning("同步 Cookie 层状态失败: {}", e)
        return False
