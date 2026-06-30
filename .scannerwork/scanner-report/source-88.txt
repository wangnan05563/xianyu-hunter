"""Notifier 数据模型

NotifyResult 描述一次推送尝试的最终结果（含重试）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class NotifyResult:
    """单次推送结果

    Attributes:
        success: 是否最终成功（重试后可能为 True）
        channel: 渠道名（serverchan/pushplus/bark）
        attempts: 总尝试次数（含重试）
        response: 渠道返回的原始响应（HTTP body 或错误）
        error: 失败时的异常信息
        sent_at: 推送完成时间
    """
    success: bool
    channel: str
    attempts: int = 1
    response: str = ""
    error: str = ""
    # 与项目其他时间字段统一使用 UTC
    sent_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "channel": self.channel,
            "attempts": self.attempts,
            "response": self.response,
            "error": self.error,
            "sent_at": self.sent_at.isoformat(),
        }
