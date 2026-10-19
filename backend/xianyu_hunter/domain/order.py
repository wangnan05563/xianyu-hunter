"""领域模型：订单"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class OrderStatus(str, Enum):
    """orders.status 的唯一字面值来源（T02585 状态口径同源）

    写入路径：buyer 落单写 PENDING_PAY（演练写 DRY_RUN）→ 人工接管写 TAKEOVER_PENDING
    → 确认支付写 SUCCEEDED；CANCELLED / FAILED 为终态。
    新增状态必须先加到这里，再同时改读写两端：散落的字符串会让统计卡片、
    超时告警与筛选静默命中 0 行（原 PAID="paid" 与前端 pending、统计里的
    submitting/paying 都属于从未被写入过的死字面值）。
    """

    PENDING_PAY = "pending_pay"      # 已拍下，待支付（唯一可被接管的起始态）
    TAKEOVER_PENDING = "takeover_pending"  # 用户已点接管，等待在 App 内完成支付
    SUCCEEDED = "succeeded"          # 接管确认后支付完成
    CANCELLED = "cancelled"          # 已取消
    FAILED = "failed"                # 失败（人工处理）
    DRY_RUN = "dry_run"              # 演练报告条目（无真实订单号）


# 「待支付」桶：语义上只有一个字面值，集中定义供统计与告警共用，
# 避免每个查询各写一份 IN 列表
PENDING_STATUSES: tuple[str, ...] = (OrderStatus.PENDING_PAY.value,)

# 契约测试与文档用：完整合法取值集合
ORDER_STATUS_VALUES: frozenset[str] = frozenset(s.value for s in OrderStatus)


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
    # 演练中止（PRD FR-C3-2）：订单确认页已打开（支付页打开前）硬中止，
    # 未创建真实订单。与 FAILED 区分：演练是预期行为，不应计入失败统计
    DRY_RUN_STOPPED = "dry_run_stopped"


@dataclass
class BuyResult:
    """buy() 调用结果

    Attributes:
        outcome: SUCCESS / SKIPPED_DUPLICATE / FAILED / DRY_RUN_STOPPED
        order: 落单成功时的订单快照（含 order_no / price / status）
        error: 失败原因（仅 FAILED 时有值）；演练中止时为中止说明
        screenshot: 失败时截屏路径（便于排查）
        dry_run_timings: 演练各段耗时（秒）——导航/点击购买/等待确认页/总计
            （FR-C3-3 演练报告数据源，仅 DRY_RUN_STOPPED 时有值）
    """
    outcome: BuyOutcome
    order: OrderSnapshot | None = None
    error: str = ""
    screenshot: str = ""
    dry_run_timings: dict | None = None


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


class ItemSoldError(BuyerError):
    """商品已售出，不可抢购（与 ButtonNotFoundError 区分，便于返回明确错误）"""
    pass
