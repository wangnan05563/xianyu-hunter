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
                "LoginOrchestrator 初始化: mode=launch, profile=%s",
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

        logger.info("登录成功，Cookie 已更新: identity=%d, session=%d, tracking=%d",
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
            self._cookie_rotator.invalidate_layer(CookieLayer.SESSION)
            logger.warning("Token 续期失败，session 层已标记失效")

        self._token_renewer.set_renew_fail_callback(on_renew_fail)

        # 启动后台续期
        await self._token_renewer.start()

        logger.info("会话管理已启动")

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
        logger.info("当前登录策略: %s", strategy.value)


# ============== 单例 ==============

_orchestrator: LoginOrchestrator | None = None


def get_orchestrator() -> LoginOrchestrator:
    """获取 LoginOrchestrator 单例"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = LoginOrchestrator()
    return _orchestrator
