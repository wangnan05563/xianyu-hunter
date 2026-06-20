"""领域模型：事件"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class EventType(str, Enum):
    ITEM_DISCOVERED = "item.discovered"
    EVAL_PASSED = "eval.passed"
    EVAL_REJECTED = "eval.rejected"
    BUY_REQUESTED = "buy.requested"
    BUY_SUCCEEDED = "buy.succeeded"
    BUY_FAILED = "buy.failed"
    NOTIFY_SENT = "notify.sent"
    WAF_TRIGGERED = "waf.triggered"
    LOGIN_EXPIRED = "login.expired"
    TASK_STARTED = "task.started"
    TASK_PAUSED = "task.paused"
    TASK_ERROR = "task.error"


# P3-F-10：事件严重度
# - critical: 必须送达（如买成功、风控触发、登录过期、任务异常）—— 即便免打扰也要推送
# - important: 重要但可延迟（如评估通过、买失败）—— 免打扰期内可降级为摘要
# - info: 仅参考（如发现商品、任务启动）—— 免打扰期内静默
EVENT_SEVERITY: dict[EventType, str] = {
    EventType.BUY_SUCCEEDED: "critical",   # 买成功需要用户拍板付款
    EventType.WAF_TRIGGERED: "critical",  # 风控触发
    EventType.LOGIN_EXPIRED: "critical",  # 登录过期需立即重扫
    EventType.TASK_ERROR: "critical",     # 任务异常
    EventType.BUY_FAILED: "important",    # 买失败但任务继续
    EventType.EVAL_PASSED: "important",   # 评估通过 → 用户确认是否抢
    EventType.EVAL_REJECTED: "info",      # 评估拒绝（量大，淹没）
    EventType.ITEM_DISCOVERED: "info",
    EventType.NOTIFY_SENT: "info",
    EventType.BUY_REQUESTED: "info",
    EventType.TASK_STARTED: "info",
    EventType.TASK_PAUSED: "info",
}


def severity_of(event_type: EventType) -> str:
    """获取事件严重度（critical / important / info）"""
    return EVENT_SEVERITY.get(event_type, "info")


@dataclass
class Event:
    """领域事件，跨模块传递的最小单元"""
    type: EventType
    task_id: str = ""
    item_id: str = ""
    payload: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # P3-F-10：严重度（critical/important/info），免打扰时段决策依据
    # 默认从 type 推导；调用方可显式覆盖（如强制把某条评估通过标 important）
    severity: str = ""

    def __post_init__(self) -> None:
        # 未显式指定 severity 时从 type 推导，确保免打扰决策可用
        if not self.severity:
            self.severity = severity_of(self.type)
