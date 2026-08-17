"""领域模型：事件"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class EventType(str, Enum):
    # 主系统 22 种事件（与前端 NotifierChannels/constants.ts eventTypes 对齐）
    # 任务生命周期
    TASK_STARTED = "task.started"
    TASK_STOPPED = "task.stopped"
    TASK_PAUSED = "task.paused"
    TASK_ERROR = "task.error"
    TASK_SEARCH_DONE = "task.search_done"
    # 商品与评估
    ITEM_DISCOVERED = "item.discovered"
    ITEM_FOUND = "item.found"  # 旧枚举兼容
    EVAL_PASSED = "eval.passed"
    EVAL_REJECTED = "eval.rejected"
    EVAL_SCORED = "eval.scored"
    # 购买
    BUY_REQUESTED = "buy.requested"
    BUY_SUCCEEDED = "buy.succeeded"
    BUY_FAILED = "buy.failed"
    # 通知
    NOTIFY_SENT = "notify.sent"
    TUNNEL_STARTED = "tunnel.started"
    # 安全
    WAF_TRIGGERED = "waf.triggered"
    WAF_BLOCKED = "waf.blocked"
    # 认证
    LOGIN_EXPIRED = "login.expired"
    AUTH_EXPIRED = "auth.expired"
    # 系统
    SYSTEM_ERROR = "system.error"
    # 维护（DB 实际存储的事件类型）
    MAINTENANCE_DATABASE = "maintenance.database"
    MAINTENANCE_LOGS = "maintenance.logs"
    MAINTENANCE_CACHE = "maintenance.cache"
    # ============== 智能客服模块事件（13 项）==============
    # 命名约定：chatbot.<域>.<动作>，与主系统 item.<动作> 风格一致
    CHATBOT_SESSION_CREATED = "chatbot.session.created"
    CHATBOT_SESSION_ENDED = "chatbot.session.ended"
    CHATBOT_MESSAGE_SAVED = "chatbot.message.saved"
    CHATBOT_FEEDBACK_RECEIVED = "chatbot.feedback.received"
    CHATBOT_FAQ_HIT = "chatbot.faq.hit"
    CHATBOT_INTENT_CLASSIFIED = "chatbot.intent.classified"
    CHATBOT_TOOL_CALLED = "chatbot.tool.called"
    CHATBOT_ESCALATED = "chatbot.escalated"
    CHATBOT_DEGRADED = "chatbot.degraded"
    CHATBOT_KB_REBUILT = "chatbot.kb.rebuilt"
    CHATBOT_KB_UPDATED = "chatbot.kb.updated"
    CHATBOT_KB_FAILED = "chatbot.kb.failed"
    CHATBOT_CONFIG_CHANGED = "chatbot.config.changed"


# P3-F-10：事件严重度
# - critical: 必须送达（如买成功、风控触发、登录过期、任务异常）—— 即便免打扰也要推送
# - important: 重要但可延迟（如评估通过、买失败）—— 免打扰期内可降级为摘要
# - info: 仅参考（如发现商品、任务启动）—— 免打扰期内静默
EVENT_SEVERITY: dict[EventType, str] = {
    EventType.BUY_SUCCEEDED: "critical",   # 买成功需要用户拍板付款
    EventType.WAF_TRIGGERED: "critical",  # 风控触发
    EventType.WAF_BLOCKED: "critical",    # 风控拦截（请求被阻断，可能影响任务执行）
    EventType.LOGIN_EXPIRED: "critical",  # 登录过期需立即重扫
    EventType.AUTH_EXPIRED: "important",  # 会话过期，可延迟但需尽快处理
    EventType.TASK_ERROR: "critical",     # 任务异常
    EventType.SYSTEM_ERROR: "critical",    # 系统级错误需立即告警
    EventType.BUY_FAILED: "important",    # 买失败但任务继续
    EventType.EVAL_PASSED: "important",   # 评估通过 → 用户确认是否抢
    EventType.EVAL_REJECTED: "info",      # 评估拒绝（量大，淹没）
    EventType.EVAL_SCORED: "info",        # 评估打分（量大，仅参考）
    EventType.ITEM_DISCOVERED: "info",
    EventType.ITEM_FOUND: "info",          # 旧枚举兼容
    EventType.NOTIFY_SENT: "info",
    EventType.TUNNEL_STARTED: "critical",  # 隧道启动是用户主动操作，需穿透免打扰送达
    EventType.BUY_REQUESTED: "info",
    EventType.TASK_STARTED: "info",
    EventType.TASK_STOPPED: "info",       # 任务正常停止
    EventType.TASK_PAUSED: "info",
    EventType.TASK_SEARCH_DONE: "info",   # 搜索完成（量大，仅参考）
    EventType.MAINTENANCE_DATABASE: "info",  # 维护类事件，仅参考
    EventType.MAINTENANCE_LOGS: "info",
    EventType.MAINTENANCE_CACHE: "info",
}


def severity_of(event_type: EventType) -> str:
    """获取事件严重度（critical / important / info）"""
    return EVENT_SEVERITY.get(event_type, "info")


# ============== 智能客服模块事件严重度扩展 ==============
# P1-9 修订：用 setdefault() 幂等写入，避免模块加载污染主字典定义
# 为什么不直接写入上方 EVENT_SEVERITY 字典：
#   1. 保持主字典定义简洁，便于主系统维护
#   2. setdefault 幂等：重复执行（如热重载）不会覆盖已有值
#   3. 模块解耦：chatbot 事件严重度与 chatbot 模块同源，便于独立演进
EVENT_SEVERITY.setdefault(EventType.CHATBOT_ESCALATED, "critical")    # 转人工需立即关注
EVENT_SEVERITY.setdefault(EventType.CHATBOT_KB_FAILED, "critical")    # KB 构建失败影响服务
EVENT_SEVERITY.setdefault(EventType.CHATBOT_DEGRADED, "important")    # 降级需关注但服务继续
EVENT_SEVERITY.setdefault(EventType.CHATBOT_FEEDBACK_RECEIVED, "important")  # 负反馈可能触发转人工
EVENT_SEVERITY.setdefault(EventType.CHATBOT_KB_REBUILT, "important")  # KB 重建成功
EVENT_SEVERITY.setdefault(EventType.CHATBOT_KB_UPDATED, "info")       # KB 增量更新
EVENT_SEVERITY.setdefault(EventType.CHATBOT_CONFIG_CHANGED, "info")   # 配置变更
EVENT_SEVERITY.setdefault(EventType.CHATBOT_SESSION_CREATED, "info")  # 会话创建
EVENT_SEVERITY.setdefault(EventType.CHATBOT_SESSION_ENDED, "info")    # 会话结束
EVENT_SEVERITY.setdefault(EventType.CHATBOT_MESSAGE_SAVED, "info")    # 消息保存
EVENT_SEVERITY.setdefault(EventType.CHATBOT_FAQ_HIT, "info")          # FAQ 命中
EVENT_SEVERITY.setdefault(EventType.CHATBOT_INTENT_CLASSIFIED, "info")  # 意图分类
EVENT_SEVERITY.setdefault(EventType.CHATBOT_TOOL_CALLED, "info")      # 工具调用


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
    # 全局流水号：标识触发本事件所属的请求/任务链路
    # 默认空字符串，EventBus._dispatch 时若为空则从 ContextVar 自动注入
    request_id: str = ""

    def __post_init__(self) -> None:
        # 未显式指定 severity 时从 type 推导，确保免打扰决策可用
        if not self.severity:
            self.severity = severity_of(self.type)
