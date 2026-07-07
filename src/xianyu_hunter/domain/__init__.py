"""领域模型包

子模块列表
- item 表示商品 ItemSummary 与 ItemDetail
- seller 表示卖家画像
- task 表示监控任务
- order 表示订单快照
- events 表示领域事件
- evaluation 表示评估结果
"""
# 聚合导出核心领域模型，支持 from xianyu_hunter.domain import Task 等简洁引用
from xianyu_hunter.domain.task import Task, TaskMode, TaskStatus, TaskConfig, XIANYU_FILTER_MAP
from xianyu_hunter.domain.item import ItemSummary, ItemDetail
from xianyu_hunter.domain.seller import SellerProfile
from xianyu_hunter.domain.order import (
    OrderSnapshot,
    OrderStatus,
    BuyOutcome,
    BuyResult,
    BuyerError,
    PriceMismatchError,
    OutOfStockError,
    ButtonNotFoundError,
)
from xianyu_hunter.domain.events import Event, EventType, EVENT_SEVERITY, severity_of
from xianyu_hunter.domain.evaluation import EvalResult, RiskLevel

__all__ = [
    "Task", "TaskMode", "TaskStatus", "TaskConfig", "XIANYU_FILTER_MAP",
    "ItemSummary", "ItemDetail",
    "SellerProfile",
    "OrderSnapshot", "OrderStatus", "BuyOutcome", "BuyResult",
    "BuyerError", "PriceMismatchError", "OutOfStockError", "ButtonNotFoundError",
    "Event", "EventType", "EVENT_SEVERITY", "severity_of",
    "EvalResult", "RiskLevel",
]
