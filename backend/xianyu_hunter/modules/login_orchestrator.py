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
from xianyu_hunter.modules.session_health import SessionHealthChecker, WAFStatus
from xianyu_hunter.modules.token_renewer import TokenRenewer

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

        # 自愈状态：续期失败后尝试恢复 cookie 层 / 自动重登
        self._renew_fail_count: int = 0
        self._auto_relogin_callback: Callable[[], Awaitable[bool]] | None = None
        self._auto_relogin_cooldown_until: float = 0.0  # 冷却时间戳，避免频繁重登
        # 重登失败计数 + 长冷却：cookie_inject 反复失败时进入长冷却，
        # 避免无意义重试；用户手动重新登录后由 on_login_success 复位
        self._relogin_fail_count: int = 0
        self._relogin_long_cooldown_until: float = 0.0
        # 保存异步恢复任务引用，避免被 GC 回收导致任务中途消失
        self._pending_recover_task: asyncio.Task | None = None

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

    def set_auto_relogin_callback(self, callback: Callable[[], Awaitable[bool]]) -> None:
        """设置自动重登回调

        续期连续失败且 cookie 同步恢复无效时触发。回调应为无副作用的异步重登流程
        （如 browser_login），返回 True 表示重登成功。

        为什么需要：session 持续失效后若无自动重登，采集/搜索将一直不可用，
        需人工介入。设置回调后系统可自愈。
        """
        self._auto_relogin_callback = callback

    def on_login_success(self, cookies: dict[str, str]) -> int:
        """登录成功后更新 Cookie

        自动分类 Cookie 到对应层并原子更新。

        复位自愈状态：用户手动登录是最高优先级的会话恢复方式，
        成功后必须复位所有失败计数和冷却时间，否则历史失败会
        持续影响后续自愈决策（如长冷却未到期导致下次自动重登被跳过）。
        """
        # 复位自愈状态：续期失败计数 + 重登失败计数 + 短/长冷却
        # 为什么在 on_login_success 而非 start_session：用户可能通过其他入口
        # （如 cookie_inject API、浏览器导入）更新 cookie 而不经 start_session，
        # on_login_success 是所有登录路径的共同后置钩子
        if self._renew_fail_count or self._relogin_fail_count:
            logger.info(
                "登录成功，复位自愈状态（原：续期失败 {} 次，重登失败 {} 次）",
                self._renew_fail_count, self._relogin_fail_count,
            )
        self._renew_fail_count = 0
        self._relogin_fail_count = 0
        self._auto_relogin_cooldown_until = 0.0
        self._relogin_long_cooldown_until = 0.0

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

    # 续期失败连续阈值：超过此次数才触发自动重登
    _RENEW_FAIL_THRESHOLD = 2
    # 自动重登冷却时间（秒），失败后避免频繁重试
    _AUTO_RELOGIN_COOLDOWN_SEC = 600
    # 自动重登连续失败阈值：触达后进入长冷却
    # 为什么设为 3：1-2 次失败可能是 cookie 短暂抖动，3 次基本可判定 JSON 中 cookie 已失效
    _RELOGIN_LONG_COOLDOWN_THRESHOLD = 3
    # 自动重登长冷却时间（秒）：30 分钟，等待用户手动扫码登录
    _RELOGIN_LONG_COOLDOWN_SEC = 1800

    def start_session(
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

        # 续期失败回调：拆分为多个原子方法，避免单函数嵌套过深
        self._token_renewer.set_renew_fail_callback(self._on_renew_fail)
        # 续期成功回调：重置失败计数，避免历史失败累计误触发自动重登
        # 为什么需要：token_renewer 自身续期成功时只清零自己的 _consecutive_failures，
        # 不通知上层；上层的 _renew_fail_count 会一直累加直至触发自动重登
        self._token_renewer.set_renew_success_callback(self._on_renew_success)

        # 启动后台续期
        self._token_renewer.start()

        logger.info("会话管理已启动")

    def _on_renew_success(self) -> None:
        """Token 续期成功回调：重置失败计数

        为什么需要：续期成功说明会话已恢复，应清零历史失败计数，
        否则下次偶发失败会立刻达到阈值触发不必要的自动重登。
        """
        if self._renew_fail_count > 0:
            logger.info("Token 续期成功，失败计数已重置（原 {} 次）", self._renew_fail_count)
            self._renew_fail_count = 0

    def _on_renew_fail(self) -> None:
        """Token 续期失败回调（同步入口）

        三步策略：
        1. 标记 session 层失效
        2. 尝试从 CookieStore JSON 同步恢复（低成本自愈）
        3. 连续失败且超过冷却时间时触发自动重登（高成本自愈）
        """
        # 手动标记失效：manual=False 让 /cookies/layers 自动同步可恢复该层
        self._invalidate_session_layer_after_renew_fail()
        if self._try_recover_session_from_json():
            return
        self._maybe_trigger_auto_relogin()

    def _invalidate_session_layer_after_renew_fail(self) -> None:
        """续期失败后标记 session 层失效并累加计数"""
        self._cookie_rotator.invalidate_layer(CookieLayer.SESSION, manual=False)
        self._renew_fail_count += 1
        logger.warning(
            "Token 续期失败（第 {} 次），session 层已标记失效",
            self._renew_fail_count,
        )

    def _try_recover_session_from_json(self) -> bool:
        """尝试从 CookieStore JSON 同步恢复 session 层

        为什么先尝试同步：浏览器登录子进程可能已刷新 cookie 但主进程缓存未更新，
        重新读 JSON 有机会恢复，成本远低于重新登录。

        为什么同步后还要异步注入浏览器：sync_cookie_layers_from_json 只更新了
        CookieRotator 的内存层状态，浏览器上下文仍是失效的旧 cookie。
        必须将 JSON 中的 cookie 注入浏览器才能形成完整恢复闭环（与
        collection_service.ensure_official_cookies 的最佳实践一致）。
        同步函数中无法 await，用 create_task 调度异步注入。

        Returns:
            True 表示恢复成功，无需触发自动重登
        """
        recovered = sync_cookie_layers_from_json()
        if not recovered:
            return False
        self._renew_fail_count = 0
        logger.info("Cookie 层同步恢复成功，session 失效已自愈")
        # 异步注入浏览器 cookie：层状态同步成功说明 JSON 有新数据，
        # 但浏览器内存仍是旧 cookie，必须注入才能让后续请求使用新 token
        try:
            loop = asyncio.get_event_loop()
            # 保存引用避免任务被 GC 回收（Python 官方文档要求）
            self._pending_recover_task = loop.create_task(self._inject_cookies_to_browser_after_recover())
        except RuntimeError:
            logger.warning("无事件循环可用，cookie 已同步层状态但未注入浏览器")
        return True

    async def _inject_cookies_to_browser_after_recover(self) -> None:
        """续期失败恢复后异步注入 cookie 到浏览器

        复用 cookie_runtime_sync 的 inject_cookie_store_to_worker_browser，
        内部已实现 add_cookies + sync_cookie_layers_from_json 完整闭环。
        """
        try:
            from xianyu_hunter.web.services.cookie_runtime_sync import inject_cookie_store_to_worker_browser
            success = await inject_cookie_store_to_worker_browser(
                log_prefix="续期失败恢复"
            )
            if success:
                logger.info("续期失败恢复后已注入 CookieStore cookie 到浏览器")
            else:
                logger.warning("续期失败恢复后注入浏览器 cookie 未通过验证")
        except asyncio.CancelledError:
            # 事件循环关闭时任务可能被取消，不应记为错误
            raise
        except Exception as e:
            logger.warning("续期失败恢复后注入浏览器 cookie 失败: {}", e)

    def _maybe_trigger_auto_relogin(self) -> None:
        """根据冷却时间和失败次数决定是否触发自动重登

        冷却 10 分钟避免重登失败后频繁重试；
        无事件循环时记录错误并提示手动重登。
        """
        if not self._should_trigger_relogin():
            return
        now = time.time()
        self._auto_relogin_cooldown_until = now + self._AUTO_RELOGIN_COOLDOWN_SEC
        logger.error(
            "续期连续失败 {} 次，cookie 同步无效，触发自动重登",
            self._renew_fail_count,
        )
        self._schedule_auto_relogin()

    def _should_trigger_relogin(self) -> bool:
        """是否应该触发自动重登：需要回调 + 连续失败次数达标 + 冷却期已过

        双层冷却：
        - 短冷却（_auto_relogin_cooldown_until, 10 分钟）：单次失败后避免立即重试
        - 长冷却（_relogin_long_cooldown_until, 30 分钟）：连续失败 3 次后，
          cookie_inject 已无效，等待用户手动介入
        """
        if not self._auto_relogin_callback:
            if self._renew_fail_count >= self._RENEW_FAIL_THRESHOLD:
                logger.error(
                    "续期连续失败 {} 次且未配置自动重登回调，请手动重新登录",
                    self._renew_fail_count,
                )
            return False
        if self._renew_fail_count < self._RENEW_FAIL_THRESHOLD:
            return False
        # 长冷却期内不再触发自动重登，避免 cookie_inject 反复失败浪费资源
        if time.time() < self._relogin_long_cooldown_until:
            remaining = int(self._relogin_long_cooldown_until - time.time())
            logger.debug(
                "自动重登处于长冷却期，剩余 {} 秒，等待用户手动登录",
                remaining,
            )
            return False
        return time.time() >= self._auto_relogin_cooldown_until

    def _schedule_auto_relogin(self) -> None:
        """通过事件循环调度异步自动重登；无循环时降级为日志告警"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            logger.error("无事件循环可用，无法触发自动重登，请手动重新登录")
            return
        loop.create_task(self._do_auto_relogin())

    async def _do_auto_relogin(self) -> None:
        """执行自动重登：调用回调并根据结果重置/保留失败计数

        可观测性设计：
        - 成功：INFO + 复位失败计数 + 复位长冷却
        - 失败/异常：ERROR + 累加 _relogin_fail_count + 触达阈值进入长冷却
          + 通过 EventBus 发布 LOGIN_EXPIRED 事件让 NotifierHub 通知用户介入
        - 为什么需要通知：自动重登是后台自愈机制，用户无感知；
          连续失败表明 cookie_inject 已无法恢复，必须人工扫码登录
        """
        try:
            success = await self._auto_relogin_callback()
        except Exception as exc:  # noqa: BLE001 - 自动重登失败需记录原始异常
            self._relogin_fail_count += 1
            logger.error(
                "自动重登异常（连续第 {} 次）: {}",
                self._relogin_fail_count, exc,
            )
            self._handle_relogin_failure()
            return
        if success:
            self._renew_fail_count = 0
            self._relogin_fail_count = 0
            self._relogin_long_cooldown_until = 0.0
            logger.info("自动重登成功，session 已恢复，失败计数与长冷却均已复位")
            return
        self._relogin_fail_count += 1
        logger.error(
            "自动重登返回失败（连续第 {} 次），等待下次重试",
            self._relogin_fail_count,
        )
        self._handle_relogin_failure()

    def _handle_relogin_failure(self) -> None:
        """重登失败统一处理：长冷却 + 通知用户

        为什么抽独立方法：异常分支和失败分支都需要相同的"长冷却+通知"处理，
        避免重复代码；同时便于单测 mock 验证通知调用
        """
        # 触达长冷却阈值：进入 30 分钟冷却，避免 cookie_inject 反复失败浪费资源
        if self._relogin_fail_count >= self._RELOGIN_LONG_COOLDOWN_THRESHOLD:
            self._relogin_long_cooldown_until = (
                time.time() + self._RELOGIN_LONG_COOLDOWN_SEC
            )
            logger.error(
                "自动重登连续失败 {} 次，进入长冷却 {} 秒，请手动重新登录",
                self._relogin_fail_count,
                self._RELOGIN_LONG_COOLDOWN_SEC,
            )
        # 通过 EventBus 发布 LOGIN_EXPIRED 事件，NotifierHub 会按渠道推送告警
        # 为什么用 publish_nowait：本方法可能在无事件循环上下文中被调用，
        # publish_nowait 只入队不阻塞，EventBus 主循环会异步消费
        try:
            from xianyu_hunter.domain.events import Event, EventType
            from xianyu_hunter.infra.event_bus import get_event_bus
            bus = get_event_bus()
            bus.publish_nowait(Event(
                type=EventType.LOGIN_EXPIRED,
                payload={
                    "reason": "auto_relogin_failed",
                    "consecutive_failures": self._relogin_fail_count,
                    "in_long_cooldown": (
                        time.time() < self._relogin_long_cooldown_until
                    ),
                    "hint": "自动重登连续失败，请打开登录页面手动扫码",
                },
            ))
        except Exception as notify_err:
            # 通知失败不影响主流程，仅记录告警
            logger.warning("自动重登失败后发送通知异常: {}", notify_err)

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

    async def _default_relogin_callback(self) -> bool:
        """默认重登回调：从 CookieStore JSON 强制重新注入 cookie 到 Worker 浏览器

        策略：续期连续失败且 JSON 同步恢复无效时，强制从 CookieStore JSON
        重新读取 cookie 并注入浏览器。这是 cookie_inject 风格的重登 ——
        无头、无需用户交互，适用于 session 失效但 JSON 中仍有有效 cookie 的场景。

        为什么复用 inject_cookie_store_to_worker_browser：该函数已封装
        add_cookies + sync_cookie_layers_from_json 完整闭环，且会按 user_id
        读取对应 cookie 文件，支持多用户隔离。

        为什么不弹出浏览器重新登录：自动重登是后台自愈机制，弹出浏览器
        需要用户交互（扫码），无人值守场景下会卡住。cookie_inject 策略
        依赖之前登录保存的 cookie，若无有效 cookie 则返回 False 等待人工介入。
        """
        try:
            from xianyu_hunter.web.services.cookie_runtime_sync import inject_cookie_store_to_worker_browser
            success = await inject_cookie_store_to_worker_browser(
                log_prefix="自动重登(cookie_inject)"
            )
            if success:
                logger.info("自动重登(cookie_inject)成功：已从 CookieStore 重新注入 cookie")
            else:
                logger.warning("自动重登(cookie_inject)失败：注入浏览器 cookie 未通过验证")
            return success
        except Exception as e:
            logger.error("自动重登(cookie_inject)异常: {}", e)
            return False

    async def _default_renew_callback(self) -> bool:
        """默认 token 续期回调：浏览器导航优先，httpx API 兜底

        策略分层：
        1. 优先用浏览器导航到 m.taobao.com（用户自然行为，风控压力低）
        2. 浏览器不可用或导航失败时，用 httpx 调用 MTOP getTimestamp API
           触发续期（无浏览器场景的唯一兜底路径）

        为什么需要 httpx 兜底：Web 进程默认 with_browser=False 省内存，
        container.browser 为 None，原实现直接返回 False，TokenRenewer 永远
        无法续期，导致 cookie_expired:_m_h5_tk 恢复机制完全失效。
        httpx 调用 getTimestamp 是无浏览器场景下唯一可行的续期路径。

        为什么续期后要回写 Cookie：导航或 API 触发的 Set-Cookie 会更新
        浏览器内存或 httpx 响应，但 CookieStore JSON 仍是旧值。不回写会
        导致健康检查误判、实时搜索补注入旧 token。回写后形成完整闭环：
        登录（全量）→ 续期（增量同步）→ 失效重新登录。
        """
        # 1. 优先尝试浏览器导航续期
        if await self._renew_via_browser():
            return True

        # 2. 浏览器路径失败，回退到 httpx API 续期
        return await self._renew_via_httpx()

    async def _renew_via_browser(self) -> bool:
        """通过浏览器导航触发续期（with_browser=True 模式）

        为什么用导航而非 API：导航是用户自然行为，
        风控压力低于直接调用 getTimestamp API。
        浏览器不可用或重启失败时返回 False（由上层回退到 httpx 兜底）。

        浏览器自愈：_context 非空但连接已断开时（进程崩溃/CDP 中断），
        new_page 会抛 TargetClosedError。此处调用 ensure_alive 先尝试重启，
        重启成功后继续导航，重启失败才降级 httpx。
        """
        page = None
        try:
            from xianyu_hunter.web.deps import get_container
            container = get_container()
            if not container.browser or not container.browser._context:
                logger.debug("renew_via_browser: 浏览器不可用")
                return False
            # ensure_alive：_context 存在但连接已断开时自动重启，
            # 避免对死浏览器调用 new_page 必然抛 TargetClosedError 后才降级
            if hasattr(container.browser, "ensure_alive"):
                if not await container.browser.ensure_alive():
                    logger.debug("renew_via_browser: 浏览器重启失败，降级 httpx")
                    return False
            page = await container.browser.new_page()
            try:
                await page.goto("https://h5.m.taobao.com/", wait_until="domcontentloaded", timeout=10000)
            finally:
                await page.close()

            # 导航成功后回写 Cookie + 同步层状态（统一入口，消除与其他续期回调的重复）
            from xianyu_hunter.web.services.cookie_runtime_sync import sync_browser_cookies_to_store_after_renew
            await sync_browser_cookies_to_store_after_renew(container, log_prefix="renew_callback(浏览器)")
            return True
        except Exception as e:
            logger.debug("浏览器续期失败: {}", e)
            return False

    async def _renew_via_httpx(self) -> bool:
        """通过 httpx 调用 MTOP getTimestamp API 触发续期（无浏览器兜底）

        使用场景：
        - with_browser=False 模式（Web 进程默认配置，省内存）
        - 浏览器进程崩溃或导航超时后的兜底

        续期流程：
        1. 从 CookieStore 读取全部 cookies，构造 Cookie header
        2. 用 MtopSigner 对 getTimestamp API 签名（appKey=COMMON，通用接口）
        3. httpx GET 请求 h5api.m.goofish.com，携带 Cookie header
        4. 解析 Set-Cookie 响应头，提取新 _m_h5_tk / _m_h5_tk_enc
        5. 回写到 CookieStore（update_cookie_values），形成闭环

        为什么 token 已过期仍尝试：getTimestamp 接口对过期 token 会下发
        新 token（Set-Cookie），这是续期而非签名校验，服务端不依赖 token 有效性。
        """
        try:
            import httpx
            from xianyu_hunter.web.services.cookie_store import get_cookie_store
            from xianyu_hunter.modules.mtop_signer import MtopSigner, MtopRequest, MtopAppKey

            store = get_cookie_store()
            store.invalidate_cache()
            data = store._read_json()
            if not data or not data.get("cookies"):
                logger.debug("renew_via_httpx: CookieStore 无数据")
                return False

            cookies_list = data["cookies"]
            # 构造 name=value; 拼接的 Cookie header，携带全部 cookie
            # 为什么携带全部而非仅 _m_h5_tk：服务端会校验 identity cookie（unb/cookie2）
            # 是否与 token 匹配，仅发 _m_h5_tk 会被识别为异常请求触发风控
            cookie_header = "; ".join(
                f"{c.get('name', '')}={c.get('value', '')}" for c in cookies_list
            )

            # 提取 _m_h5_tk 用于签名（MtopSigner 要求非空 token）
            m5tk_value = self._extract_m5tk_from_cookies(cookies_list)

            if not m5tk_value:
                logger.warning("renew_via_httpx: 无 _m_h5_tk，无法签名")
                return False

            # 构造 MTOP 签名请求
            # 为什么用 COMMON appKey：getTimestamp 是通用接口，不属于搜索/详情业务线
            signer = MtopSigner()
            signer.set_token_provider(lambda: m5tk_value)
            request = MtopRequest(
                api="mtop.taobao.mtop.common.getTimestamp",
                data={},
                method="GET",
                app_key=MtopAppKey.COMMON,
            )
            url = signer.build_url(request)

            headers = {
                "Cookie": cookie_header,
                # 模拟浏览器请求头，避免被识别为爬虫
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://h5.m.taobao.com/",
                "Origin": "https://h5.m.taobao.com",
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=headers)

            if resp.status_code != 200:
                logger.warning("renew_via_httpx: HTTP {}", resp.status_code)
                return False

            # 解析 Set-Cookie 响应头，提取 _m_h5_tk / _m_h5_tk_enc 等新值
            # httpx Headers.get_list 返回多个 Set-Cookie 头的原始列表
            set_cookies = resp.headers.get_list("set-cookie")
            updates = self._parse_set_cookie_token_updates(set_cookies)

            if not updates:
                logger.warning("renew_via_httpx: 响应无 _m_h5_tk Set-Cookie")
                return False

            # 回写到 CookieStore JSON（不同步 SQLite，避免锁竞争）
            success = store.update_cookie_values(updates)
            if success:
                logger.info("renew_via_httpx: 续期成功，已回写 {} 个 token", len(updates))
            else:
                logger.warning("renew_via_httpx: update_cookie_values 未更新任何 cookie")
            return success
        except Exception as e:
            logger.debug("httpx 续期失败: {}", e)
            return False

    def _extract_m5tk_from_cookies(self, cookies_list: list[dict]) -> str | None:
        """从 cookie 列表中提取 _m_h5_tk 值

        为什么单独提取：MtopSigner 要求 token 非空，提取逻辑独立后
        _renew_via_httpx 的认知复杂度可降至阈值以下，且便于单元测试。
        """
        for c in cookies_list:
            if c.get("name") == "_m_h5_tk":
                return c.get("value", "")
        return None

    def _parse_set_cookie_token_updates(self, set_cookies: list[str]) -> dict[str, str]:
        """解析 Set-Cookie 响应头，提取 _m_h5_tk / _m_h5_tk_enc 新值

        为什么只回写关键 token cookie：避免覆盖其他 cookie 的过期时间等元数据，
        CookieStore.update_cookie_values 仅按 name 更新 value，但仍需限制范围
        避免误覆盖其他 cookie 的内存值。
        """
        updates: dict[str, str] = {}
        for sc in set_cookies:
            # Set-Cookie 格式: name=value; Path=/; Domain=...
            # 只取第一段 name=value
            name_value = sc.split(";")[0].strip()
            if "=" not in name_value:
                continue
            name, _, value = name_value.partition("=")
            name = name.strip()
            value = value.strip()
            # 只回写关键 token cookie，避免覆盖其他 cookie 的过期时间等元数据
            if name in ("_m_h5_tk", "_m_h5_tk_enc") and value:
                updates[name] = value
        return updates

    def start_session_default(self) -> bool:
        """使用默认 cookie_provider + renew_callback 启动会话

        用于登录成功后自动启动会话管理（TokenRenewer 后台续期）。
        失败仅记录日志，不抛异常（避免影响登录成功的返回路径）。

        Returns:
            True 启动成功或会话已活跃；False 启动失败
        """
        if self._session_active:
            return True
        try:
            # 登录成功后重置自愈状态，避免历史失败计数影响新一轮会话
            self._renew_fail_count = 0
            self._auto_relogin_cooldown_until = 0.0
            # 注入默认重登回调：续期连续失败时从 CookieStore 强制重新注入 cookie
            # 仅在未配置时注入，允许外部通过 set_auto_relogin_callback 覆盖默认策略
            if self._auto_relogin_callback is None:
                self._auto_relogin_callback = self._default_relogin_callback
            # start_session 是同步函数，直接调用即可
            self.start_session(
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

    async def check_health(self, user_id: str | None = None):
        """执行健康检查"""
        return await self._health_checker.check(user_id=user_id)

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
