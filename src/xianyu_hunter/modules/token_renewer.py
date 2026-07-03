"""_m_h5_tk 轻量续期器（设计文档 §4.4）

核心问题：_m_h5_tk 有效期仅 15-22 分钟，现有方案通过导航页面触发续期，
但导航本身可能触发风控，且不可靠。

解决方案：使用最轻量的 MTOP 接口（getTimestamp）做心跳续期，
响应仅 237 字节，不产生业务日志，风控压力最小。

续期策略对比：
| 方式                | 风控压力 | 成功率 | 延迟    |
|---------------------|----------|--------|---------|
| getTimestamp API    | 极低     | 90%    | <100ms  |
| 导航 /personal      | 中       | 95%    | 2-5s    |
| 导航首页            | 高       | 98%    | 3-8s    |
| 重新登录            | 最高     | 100%   | 30-60s  |

_m_h5_tk 格式：{token}_{timestamp}
- token: 用于 MTOP 签名计算
- timestamp: 服务端下发时间（毫秒）
- TTL: 15-22 分钟（服务端动态调整）
"""
from __future__ import annotations

import asyncio
import time
from contextlib import suppress
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Awaitable

from xianyu_hunter.infra.logger import get_logger

logger = get_logger()


class RenewResult(str, Enum):
    """续期结果"""
    SUCCESS = "success"
    SKIPPED = "skipped"          # 未到续期时间，跳过
    FAILED = "failed"            # 续期失败
    SESSION_EXPIRED = "expired"  # 会话已失效，需重新登录


@dataclass
class TokenInfo:
    """_m_h5_tk token 信息"""
    raw_value: str           # 完整的 _m_h5_tk 值
    token: str               # 下划线前的部分（用于签名）
    issued_at: float         # token 下发时间戳（秒）
    obtained_at: float       # 我们获取到的时间（秒）

    @classmethod
    def from_cookie_value(cls, value: str) -> "TokenInfo":
        """从 Cookie 值解析 token 信息

        _m_h5_tk 格式：{token}_{timestamp}
        timestamp 是毫秒级，需转换为秒
        """
        now = time.time()
        if "_" in value:
            parts = value.split("_", 1)
            token = parts[0]
            try:
                # timestamp 是毫秒级
                issued_at = int(parts[1]) / 1000.0
            except (ValueError, IndexError):
                issued_at = now
        else:
            token = value
            issued_at = now
        return cls(
            raw_value=value,
            token=token,
            issued_at=issued_at,
            obtained_at=now,
        )

    def age_seconds(self) -> float:
        """token 年龄（秒）"""
        return time.time() - self.issued_at

    def is_expired(self, ttl_sec: int = 1200) -> bool:
        """是否已过期（默认 TTL=20分钟）"""
        return self.age_seconds() > ttl_sec


@dataclass
class RenewerConfig:
    """续期器配置"""
    # 过期前 10 分钟续期（TTL=20min，10min 时触发）
    renew_before_expiry_sec: int = 600
    # 每 2 分钟检查一次
    check_interval_sec: int = 120
    # token 默认 TTL（闲鱼 15-22 分钟，取保守值 20 分钟）
    token_ttl_sec: int = 1200
    # 连续失败上限
    max_renew_attempts: int = 3
    # 续期失败后的重试间隔
    retry_interval_sec: int = 30


class TokenRenewer:
    """_m_h5_tk 主动续期器

    使用方式：
        renewer = TokenRenewer(config)
        renewer.set_cookie_provider(lambda: get_current_m5tk_cookie())
        renewer.set_renew_callback(renew_via_api_callback)
        renewer.start()  # 启动后台续期循环
        ...
        await renewer.stop()   # 停止

    续期回调签名：
        async def renew_callback() -> bool:
            '''执行续期，返回是否成功'''
            ...
    """

    # 最轻量的 MTOP 接口，响应仅 237 字节
    TIMESTAMP_API = "mtop.taobao.mtop.common.getTimestamp"

    def __init__(self, config: RenewerConfig | None = None):
        self.config = config or RenewerConfig()
        self._cookie_provider: Callable[[], str | None] | None = None
        self._renew_callback: Callable[[], Awaitable[bool]] | None = None
        self._renew_fail_callback: Callable[[], None] | None = None
        self._task: asyncio.Task | None = None
        self._running = False
        self._consecutive_failures = 0
        self._session_expired_warned = False
        self._session_expired_checks = 0
        self._last_renew_at: float = 0.0
        self._last_renew_result: RenewResult = RenewResult.SKIPPED
        # 会话失效后回调触发间隔（以 _session_expired_checks 计）
        # 为什么不只在首次触发：首次触发后若 on_renew_fail 的恢复尝试未成功，
        # 后续持续失效将不再有任何恢复机会。周期性触发让上层能定期重试恢复
        self._renew_fail_callback_interval = 5
        self._stats: dict[str, int] = {
            "total_checks": 0,
            "total_renewed": 0,
            "total_skipped": 0,
            "total_failed": 0,
        }

    # ============== 配置 ==============

    def set_cookie_provider(self, provider: Callable[[], str | None]) -> None:
        """设置 Cookie 提供器

        provider 应返回当前 _m_h5_tk 的值，无则返回 None
        """
        self._cookie_provider = provider

    def set_renew_callback(self, callback: Callable[[], Awaitable[bool]]) -> None:
        """设置续期回调

        callback 应执行实际的续期操作（如发起 API 请求或导航页面），
        返回 True 表示成功。
        """
        self._renew_callback = callback

    def set_renew_fail_callback(self, callback: Callable[[], None]) -> None:
        """设置续期失败回调（如触发重新登录）"""
        self._renew_fail_callback = callback

    # ============== 生命周期 ==============

    def start(self) -> None:
        """启动后台续期循环"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._renew_loop())
        logger.info("TokenRenewer 已启动，检查间隔={}s", self.config.check_interval_sec)

    async def stop(self) -> None:
        """停止续期循环"""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            # shutdown 中 await 已取消的子任务，使用 suppress 避免 CancelledError 中断 cleanup
            with suppress(asyncio.CancelledError):
                await self._task
        self._task = None
        logger.info("TokenRenewer 已停止")

    @property
    def is_running(self) -> bool:
        return self._running

    # ============== 核心逻辑 ==============

    async def _renew_loop(self) -> None:
        """后台续期循环"""
        while self._running:
            result = RenewResult.SKIPPED
            try:
                result = await self.check_and_renew()
            except asyncio.CancelledError:
                # 任务被取消时重新抛出，符合 asyncio 任务取消标准模式（S7497）
                raise
            except Exception as e:
                logger.error("续期循环异常: {}", e)
            delay = self.config.check_interval_sec
            if result == RenewResult.SESSION_EXPIRED:
                self._session_expired_checks += 1
                delay = min(600, self.config.check_interval_sec * (2 ** min(self._session_expired_checks - 1, 3)))
                logger.debug(
                    "TokenRenewer 会话失效状态未恢复，第 {} 次检查后退避 {}s",
                    self._session_expired_checks,
                    delay,
                )
            else:
                self._session_expired_checks = 0
            await asyncio.sleep(delay)

    async def check_and_renew(self) -> RenewResult:
        """检查 token 年龄，必要时续期

        Returns:
            RenewResult: 续期结果
        """
        self._stats["total_checks"] += 1

        # 1. 获取当前 token
        if not self._cookie_provider:
            logger.warning("未设置 cookie_provider，跳过续期检查")
            self._last_renew_result = RenewResult.SKIPPED
            self._stats["total_skipped"] += 1
            return RenewResult.SKIPPED

        cookie_value = self._cookie_provider()
        if not cookie_value:
            if self._session_expired_warned:
                logger.debug("无法获取 _m_h5_tk，会话仍处于失效状态，等待重新登录")
            else:
                logger.warning("无法获取 _m_h5_tk，可能未登录")
                self._session_expired_warned = True
            self._last_renew_result = RenewResult.SESSION_EXPIRED
            self._stats["total_failed"] += 1
            # Cookie 缺失时触发恢复：首次立即触发，之后按间隔周期性触发
            # 周期性触发让上层 on_renew_fail 能定期重试恢复（同步 cookie / 自动重登）
            if self._renew_fail_callback and (
                self._session_expired_checks == 0
                or self._session_expired_checks % self._renew_fail_callback_interval == 0
            ):
                self._renew_fail_callback()
            return RenewResult.SESSION_EXPIRED

        token_info = TokenInfo.from_cookie_value(cookie_value)
        age = token_info.age_seconds()

        # 2. 判断是否需要续期
        # 过期前 renew_before_expiry_sec 秒触发
        should_renew_at = self.config.token_ttl_sec - self.config.renew_before_expiry_sec
        if age < should_renew_at:
            # 未到续期时间
            self._session_expired_warned = False
            self._last_renew_result = RenewResult.SKIPPED
            self._stats["total_skipped"] += 1
            return RenewResult.SKIPPED

        # 3. 已过期？
        if token_info.is_expired(self.config.token_ttl_sec):
            if self._session_expired_warned:
                logger.debug("_m_h5_tk 仍处于过期状态（age={:.0f}s），等待重新登录", age)
            else:
                logger.warning("_m_h5_tk 已过期（age={:.0f}s），需重新登录", age)
                self._session_expired_warned = True
            self._last_renew_result = RenewResult.SESSION_EXPIRED
            self._stats["total_failed"] += 1
            # token 过期时触发恢复：首次立即触发，之后按间隔周期性触发
            if self._renew_fail_callback and (
                self._session_expired_checks == 0
                or self._session_expired_checks % self._renew_fail_callback_interval == 0
            ):
                self._renew_fail_callback()
            return RenewResult.SESSION_EXPIRED

        # 4. 执行续期
        self._session_expired_warned = False
        logger.info("_m_h5_tk age={:.0f}s，触发续期", age)
        result = await self._do_renew()
        self._last_renew_at = time.time()
        self._last_renew_result = result

        if result == RenewResult.SUCCESS:
            self._consecutive_failures = 0
            self._stats["total_renewed"] += 1
        elif result == RenewResult.FAILED:
            self._consecutive_failures += 1
            self._stats["total_failed"] += 1
            if self._consecutive_failures >= self.config.max_renew_attempts:
                if self._consecutive_failures == self.config.max_renew_attempts:
                    logger.error(
                        "连续 {} 次续期失败，触发重新登录",
                        self._consecutive_failures,
                    )
                    if self._renew_fail_callback:
                        self._renew_fail_callback()
                else:
                    logger.debug(
                        "连续续期失败已超过阈值（{} 次），等待状态恢复",
                        self._consecutive_failures,
                    )

        return result

    async def _do_renew(self) -> RenewResult:
        """执行实际续期操作"""
        if not self._renew_callback:
            logger.warning("未设置 renew_callback，无法续期")
            return RenewResult.FAILED

        try:
            success = await self._renew_callback()
            if success:
                logger.info("_m_h5_tk 续期成功")
                return RenewResult.SUCCESS
            else:
                logger.warning("_m_h5_tk 续期失败（回调返回 False）")
                return RenewResult.FAILED
        except Exception as e:
            logger.error("_m_h5_tk 续期异常: {}", e)
            return RenewResult.FAILED

    # ============== 状态查询 ==============

    def get_status(self) -> dict[str, Any]:
        """获取续期器状态"""
        cookie_value = self._cookie_provider() if self._cookie_provider else None
        token_info = TokenInfo.from_cookie_value(cookie_value) if cookie_value else None

        return {
            "running": self._running,
            "token_age_sec": token_info.age_seconds() if token_info else None,
            "token_expired": token_info.is_expired(self.config.token_ttl_sec) if token_info else None,
            "last_renew_at": self._last_renew_at,
            "last_renew_result": self._last_renew_result.value,
            "consecutive_failures": self._consecutive_failures,
            "stats": dict(self._stats),
            "config": {
                "check_interval_sec": self.config.check_interval_sec,
                "renew_before_expiry_sec": self.config.renew_before_expiry_sec,
                "token_ttl_sec": self.config.token_ttl_sec,
                "max_renew_attempts": self.config.max_renew_attempts,
            },
        }
