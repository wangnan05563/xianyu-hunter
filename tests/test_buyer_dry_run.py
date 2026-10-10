# tests/test_buyer_dry_run.py
"""抢单演练模式测试（PRD FR-C3-1/FR-C3-2，REQ-011/012）

覆盖：
- dry_run 中止：不产生真实订单（orders 表零写入）、返回 DRY_RUN_STOPPED
- 演练跳过幂等：已有真实订单的商品仍可反复演练
- 演练异常不写失败订单
- _execute_buy_flow 中止点：订单确认页后、提交订单前硬停止
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from xianyu_hunter.domain.order import BuyOutcome
from xianyu_hunter.modules.buyer import Buyer


class FakeRepo:
    """内存版 Repository：只实现 Buyer.buy 用到的方法，并记录调用"""

    def __init__(self):
        self.orders: list[dict] = []
        self.events: list[dict] = []
        self._db_orders: dict[tuple[str, str], dict] = {}

    def find_order_by_task_item(self, task_id, item_id):
        return self._db_orders.get((task_id, item_id))

    def upsert_order(self, order):
        self.orders.append(order)

    def get_task(self, task_id):
        return None

    def get_item(self, item_id, user_id=None):
        return {}

    def save_event(self, event):
        self.events.append(event)
        return 1


@pytest.fixture
def buyer():
    repo = FakeRepo()
    b = Buyer(browser=MagicMock(), repository=repo, event_bus=None)
    return b, repo


def test_dry_run_stops_before_real_order(buyer):
    """演练：链路中止返回 DRY_RUN_STOPPED，orders 表零写入，幂等标记不置位"""
    b, repo = buyer
    # _do_buy 返回 None 表示已在中止点停下（_execute_buy_flow 的演练分支行为）
    b._do_buy = AsyncMock(return_value=None)
    result = asyncio.run(b.buy(task_id="t1", item_id="i1", expected_price=100.0, dry_run=True))
    assert result.outcome == BuyOutcome.DRY_RUN_STOPPED
    # 不产生真实订单
    assert repo.orders == []
    # 演练动作写入事件时间线
    assert any(e.get("stage") == "buy_dry_run" for e in repo.events)


def test_dry_run_skips_idempotency(buyer):
    """已有真实订单的商品仍可演练（幂等检查仅作用于真实下单）"""
    b, repo = buyer
    repo._db_orders[("t1", "i1")] = {"id": "o1", "order_no": "NO123"}
    b._do_buy = AsyncMock(return_value=None)
    result = asyncio.run(b.buy(task_id="t1", item_id="i1", expected_price=100.0, dry_run=True))
    assert result.outcome == BuyOutcome.DRY_RUN_STOPPED


def test_dry_run_exception_does_not_write_failed_order(buyer):
    """演练异常：不写真实失败订单（orders 表只承载真实下单结果）"""
    b, repo = buyer
    b._do_buy = AsyncMock(side_effect=RuntimeError("page crashed"))
    result = asyncio.run(b.buy(task_id="t1", item_id="i1", expected_price=100.0, dry_run=True))
    assert result.outcome == BuyOutcome.FAILED
    assert "dry_run" in result.error
    assert repo.orders == []


def test_real_buy_unchanged(buyer):
    """回归：非演练路径仍正常落单（幂等 + 持久化 + SUCCESS）"""
    b, repo = buyer
    order = {"id": "o2", "order_no": "NO456", "price": 88.0, "status": "pending_pay"}
    b._do_buy = AsyncMock(return_value=order)
    result = asyncio.run(b.buy(task_id="t1", item_id="i2", expected_price=100.0))
    assert result.outcome == BuyOutcome.SUCCESS
    assert len(repo.orders) == 1
    # 同一 (task, item) 二次真实下单被幂等拦截
    result2 = asyncio.run(b.buy(task_id="t1", item_id="i2", expected_price=100.0))
    assert result2.outcome == BuyOutcome.SKIPPED_DUPLICATE


def test_execute_buy_flow_stops_before_submit(buyer, monkeypatch):
    """中止点位置：订单确认页打开后（步骤2.5）、提交订单点击（步骤3）前硬停止"""
    b, _ = buyer
    b._navigate = AsyncMock()
    b._detect_sold = AsyncMock(return_value=False)
    b._click_buy_now = AsyncMock(return_value=True)
    b._wait_for_order_page = AsyncMock()
    submit = AsyncMock(return_value=True)
    b._click_submit_order = submit
    result = asyncio.run(b._execute_buy_flow(MagicMock(), "i1", 100.0, dry_run=True))
    assert result is None
    # 提交订单未被调用（FR-C3-2：中止点之后的所有步骤标记 skipped）
    submit.assert_not_awaited()
