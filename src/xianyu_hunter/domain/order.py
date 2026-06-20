"""领域模型：订单"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class OrderStatus(str, Enum):
    PENDING_PAY = "pending_pay"  # 已拍下，待支付
    PAID = "paid"                 # 已支付
    CANCELLED = "cancelled"       # 已取消
    FAILED = "failed"             # 失败（人工处理）


@dataclass
class OrderSnapshot:
    """订单快照"""
    item_id: str
    order_no: str = ""
    price: float = 0.0
    status: OrderStatus = OrderStatus.PENDING_PAY
    seller_id: str = ""
    screenshot: str = ""
    error: str = ""
    # 与 OrderRow 对齐：补全任务关联与时间节点字段
    task_id: str = ""
    confirmed_at: datetime | None = None
    paid_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class BuyOutcome(str, Enum):
    """一次 buy() 调用的结果状态"""
    SUCCESS = "success"            # 落单成功（待支付）
    SKIPPED_DUPLICATE = "skipped_duplicate"  # 同任务内已下过单，幂等跳过
    FAILED = "failed"              # 落单失败（按钮找不到/库存不足/价格变动等）


@dataclass
class BuyResult:
    """buy() 调用结果

    Attributes:
        outcome: SUCCESS / SKIPPED_DUPLICATE / FAILED
        order: 落单成功时的订单快照（含 order_no / price / status）
        error: 失败原因（仅 FAILED 时有值）
        screenshot: 失败时截屏路径（便于排查）
    """
    outcome: BuyOutcome
    order: OrderSnapshot | None = None
    error: str = ""
    screenshot: str = ""


class BuyerError(Exception):
    """落单流程中的可控异常基类"""
    pass


class PriceMismatchError(BuyerError):
    """拍下时价格与预期不符（页面涨价/规格错乱）"""
    pass


class OutOfStockError(BuyerError):
    """商品已下架/无库存"""
    pass


class ButtonNotFoundError(BuyerError):
    """找不到「立即购买」按钮（页面结构变化）"""
    pass
