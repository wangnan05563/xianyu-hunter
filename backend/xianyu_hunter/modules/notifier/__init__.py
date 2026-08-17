"""Notifier 模块：多渠道推送（设计文档 §3.7）

包含：
- INotifier 协议（base.py）
- ServerChan / PushPlus / Bark 三渠道适配器
- NotifierHub 多渠道聚合与重试
- NotifyResult 推送结果模型
- 模板渲染（EVAL_PASSED / ORDER_PLACED）
"""
from xianyu_hunter.modules.notifier.base import (
    BaseNotifier,
    INotifier,
    NotifyResult,
)
from xianyu_hunter.modules.notifier.hub import NotifierHub
from xianyu_hunter.modules.notifier.registry import (
    NotifierRegistry,
    create_notifier,
)

__all__ = [
    "BaseNotifier",
    "INotifier",
    "NotifyResult",
    "NotifierHub",
    "NotifierRegistry",
    "create_notifier",
]
