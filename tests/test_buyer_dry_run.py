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
    """演练：返回 DRY_RUN_STOPPED；报告订单 type=dry_run 落库；幂等标记不置位"""
    b, repo = buyer
    # _do_buy 返回 None 表示已在中止点停下（_execute_buy_flow 的演练分支行为）
    b._do_buy = AsyncMock(return_value=None)
    b._last_dry_run_timings = {"navigate_sec": 1.2, "total_sec": 3.4}
    result = asyncio.run(b.buy(task_id="t1", item_id="i1", expected_price=100.0, dry_run=True))
    assert result.outcome == BuyOutcome.DRY_RUN_STOPPED
    assert result.dry_run_timings == {"navigate_sec": 1.2, "total_sec": 3.4}
    # 演练报告落抢单记录（type=dry_run），真实订单（type=real）零写入
    assert len(repo.orders) == 1
    report = repo.orders[0]
    assert report["type"] == "dry_run"
    assert report["status"] == "dry_run"
    assert report["price"] == 100.0
    assert "硬停止" in report["error"]
    # 演练动作写入事件时间线（payload 含各段耗时）
    events = [e for e in repo.events if e.get("stage") == "buy_dry_run"]
    assert events and "timings" in events[0]["payload"]


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
    # 各段耗时已收集（FR-C3-3 报告数据源），submit 段标记 skipped
    assert b._last_dry_run_timings["submit_order_sec"] is None
    # mock 链路即时完成，total 可能为 0.0，仅断言字段存在且为数值
    assert isinstance(b._last_dry_run_timings["total_sec"], float)


def test_dry_run_guard_in_source():
    """FR-C3-4 CI 守卫（变异测试）：下单调用点必须被 dry_run 守卫保护

    若有人移除 _execute_buy_flow 中的 dry_run 中止块（守卫缺失），
    本测试失败——保证「演练全程 0 真实订单」的断言永远由代码结构保证。
    """
    import inspect
    from pathlib import Path

    source = Path(inspect.getfile(Buyer)).read_text(encoding="utf-8")
    # 定位 _execute_buy_flow 函数体
    flow_start = source.index("async def _execute_buy_flow")
    # 函数体截断到下一个同层方法（_validate_price_or_raise）
    flow_end = source.index("def _validate_price_or_raise", flow_start)
    flow_body = source[flow_start:flow_end]

    # 守卫必须存在：dry_run 检查 + 硬中止 return
    assert "if dry_run:" in flow_body, "dry_run 守卫缺失：_execute_buy_flow 必须包含 if dry_run: 中止块"
    assert "return None" in flow_body, "dry_run 守卫必须硬中止（return None）"
    # 守卫必须位于提交订单调用之前（行号比较，防止守卫被移到下单之后）
    guard_line = source[: flow_start + flow_body.index("if dry_run:")].count("\n")
    submit_line = source[: flow_start + flow_body.index("_click_submit_order")].count("\n")
    assert guard_line < submit_line, "dry_run 守卫必须位于 _click_submit_order 调用之前"
