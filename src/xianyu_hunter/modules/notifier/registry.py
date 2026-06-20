"""Notifier 注册表 + 工厂

按设计文档 §3.7，使用字典映射 name → class 便于扩展。
P1-3：新增 Telegram / 企业微信 / 钉钉 / Webhook 4 个渠道。
"""
from __future__ import annotations

from xianyu_hunter.modules.notifier.base import INotifier
from xianyu_hunter.modules.notifier.bark import BarkNotifier
from xianyu_hunter.modules.notifier.dingtalk import DingTalkNotifier
from xianyu_hunter.modules.notifier.pushplus import PushPlusNotifier
from xianyu_hunter.modules.notifier.serverchan import ServerChanNotifier
from xianyu_hunter.modules.notifier.telegram import TelegramNotifier
from xianyu_hunter.modules.notifier.wecom import WeComNotifier
from xianyu_hunter.modules.notifier.webhook import WebhookNotifier


class NotifierRegistry:
    """Notifier 渠道注册表

    使用方式：
        registry = NotifierRegistry.default()
        notifier = registry.create("serverchan")
    """

    _registry: dict[str, type[INotifier]] = {
        "serverchan": ServerChanNotifier,
        "pushplus": PushPlusNotifier,
        "bark": BarkNotifier,
        # P1-3：新增 4 个渠道
        "telegram": TelegramNotifier,
        "wecom": WeComNotifier,
        "dingtalk": DingTalkNotifier,
        "webhook": WebhookNotifier,
    }

    @classmethod
    def default(cls) -> "NotifierRegistry":
        """获取默认注册表（单例等价物）"""
        return cls()

    def create(self, name: str, **kwargs) -> INotifier:
        """根据渠道名创建 Notifier 实例"""
        if name not in self._registry:
            raise KeyError(
                f"未知渠道 {name}，可用: {list(self._registry.keys())}"
            )
        cls_ = self._registry[name]
        return cls_(**kwargs)

    def available(self) -> list[str]:
        """返回所有已注册渠道名"""
        return list(self._registry.keys())


def create_notifier(name: str, **kwargs) -> INotifier:
    """便捷工厂：NotifierRegistry.default().create(name, **kwargs)"""
    return NotifierRegistry.default().create(name, **kwargs)
