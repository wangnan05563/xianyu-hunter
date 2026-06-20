"""NotifierHub：多渠道聚合 + 订阅 EventBus + 免打扰时段

Hub 独立于 EventBus 内部：构造时不绑定，调用 attach() 时才订阅。
这样测试时可单独使用 hub.send()，无需 EventBus。

P3-F-10 集成：
- 构造时接受 QuietHoursConfig
- send() 时检查当前是否在免打扰时段：
  - 不在 → 正常 fan-out 推送
  - 在 + critical_only=True + severity != critical → 静默（计入 suppressed_count）
  - 在 + critical_only=False → 仍正常推送（兼容老配置）
- 暴露 suppressed_count() / last_suppressed_at() 给前端展示

为什么静默也返回 NotifyResult(success=True)：
- 调用方基于 success 判定"是否触达用户"；静默的语义是"用户主动选择不被打扰"
- 不算推送失败，避免触发推送失败的告警链
"""
from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING

from xianyu_hunter.domain.events import Event, EventType, severity_of
from xianyu_hunter.infra.logger import get_logger
from xianyu_hunter.modules.notifier.models import NotifyResult
from xianyu_hunter.modules.notifier.quiet_hours import is_quiet_now
from xianyu_hunter.modules.notifier.registry import NotifierRegistry

if TYPE_CHECKING:
    from xianyu_hunter.infra.event_bus import EventBus
    from xianyu_hunter.infra.yaml_config import QuietHoursConfig

logger = get_logger()


# Hub 默认只关心需要触达用户的事件类型
DEFAULT_NOTIFY_EVENTS: set[EventType] = {
    EventType.EVAL_PASSED,
    EventType.BUY_SUCCEEDED,
}


class NotifierHub:
    """多渠道 Notifier 聚合器

    职责：
    1. 维护一组 Notifier 实例（每渠道一个）
    2. fan-out 推送：把同一事件并发送到所有渠道
    3. 可选 attach 到 EventBus，自动消费事件
    4. P3-F-10：quiet hours 静默（critical 仍可达）
    """

    def __init__(
        self,
        channels: list[str] | None = None,
        registry: NotifierRegistry | None = None,
        quiet_hours: "QuietHoursConfig | None" = None,
    ):
        # channels 为 None 时不创建任何 Notifier（hub 仅作容器使用）
        self._registry = registry or NotifierRegistry.default()
        self._notifiers: list = []
        for name in channels or []:
            try:
                self._notifiers.append(self._registry.create(name))
            except KeyError as e:
                logger.error(f"NotifierHub 初始化失败: {e}")
        # P3-F-10：免打扰配置 + 状态
        self._quiet_hours = quiet_hours
        self._suppressed_lock = threading.Lock()
        self._suppressed_count: int = 0  # 进程内累计被静默的事件数
        self._suppressed_last_at = None    # 最近一次静默的时间

    @property
    def notifiers(self) -> list:
        """对外暴露 Notifier 列表（便于测试和监控）"""
        return list(self._notifiers)

    @property
    def quiet_hours_config(self) -> "QuietHoursConfig | None":
        return self._quiet_hours

    def set_quiet_hours(self, cfg: "QuietHoursConfig | None") -> None:
        """热更新 quiet hours 配置（API 端可调）"""
        self._quiet_hours = cfg

    def is_suppressed_now(self) -> bool:
        """当前是否处于静默状态（UI 用来显示"勿扰中"徽章）"""
        if self._quiet_hours is None:
            return False
        return is_quiet_now(self._quiet_hours)

    def suppressed_count(self) -> int:
        """累计被静默的事件数（UI 显示"勿扰期间累计 N 条"）"""
        with self._suppressed_lock:
            return self._suppressed_count

    def suppressed_last_at(self):
        with self._suppressed_lock:
            return self._suppressed_last_at

    def reset_suppressed(self) -> None:
        """重置累计计数（UI 端"清空勿扰计数"按钮）"""
        with self._suppressed_lock:
            self._suppressed_count = 0
            self._suppressed_last_at = None

    async def send(self, event: Event) -> list[NotifyResult]:
        """fan-out 推送：同一事件并发到所有已配置渠道

        P3-F-10：quiet hours 判定
        - 不在静默窗口：照常推送
        - 在静默窗口 + critical_only=False：照常推送
        - 在静默窗口 + severity == critical：照常推送（critical 永远可达）
        - 在静默窗口 + 其他：静默（计入 suppressed_count，返回 success=True 占位结果）
        """
        # 推导 severity：调用方显式传优先，否则按 type 查表
        sev = event.severity or severity_of(event.type)

        if self._quiet_hours and is_quiet_now(self._quiet_hours):
            suppressed = (
                self._quiet_hours.critical_only and sev != "critical"
            )
            if suppressed:
                with self._suppressed_lock:
                    self._suppressed_count += 1
                    self._suppressed_last_at = event.timestamp
                logger.info(
                    f"[quiet-hours] 静默事件 {event.type.value} "
                    f"(severity={sev}) 累计 {self._suppressed_count}"
                )
                # 返回 success=True 的占位结果，调用方不会误报警
                return [NotifyResult(
                    success=True,
                    channel="quiet_suppressed",
                    attempts=0,
                    response=f"quiet hours ({self._quiet_hours.start}-{self._quiet_hours.end})",
                )]

        if not self._notifiers:
            logger.warning("NotifierHub 未配置任何渠道，事件被丢弃")
            return []

        results = await asyncio.gather(
            *(n.send(event) for n in self._notifiers),
            return_exceptions=False,  # Notifier 内部已捕获异常，不会抛
        )
        # 日志：成功/失败汇总
        ok = sum(1 for r in results if r.success)
        logger.info(
            f"推送 {event.type.value} → {ok}/{len(results)} 渠道成功"
        )
        return list(results)

    def attach(self, bus: "EventBus", events: set[EventType] | None = None) -> None:
        """订阅 EventBus 中指定类型的事件

        推送会被异步执行（bus 自身负责调度）。
        """
        target_events = events or DEFAULT_NOTIFY_EVENTS

        async def _on_event(event: Event) -> None:
            await self.send(event)

        for evt_type in target_events:
            bus.subscribe(evt_type, _on_event)
        logger.info(
            f"NotifierHub 订阅 {len(target_events)} 种事件: "
            f"{[e.value for e in target_events]}"
        )
