"""单日真实落单上限护栏测试（T02589 / PRD FR-A-4）

背景：抢单策略页原本文案宣称「单日抢单数量上限：在 buyer_config.py 中配置（待 UI 化）」，
但 buyer_config.py 里既没有该字段，也没有任何执行逻辑——属虚假安全护栏。
本文件锁住三件事：
1. 护栏默认为 0＝不限制（PRD §8 决策 2：不给用户未经同意的刹车）；
2. 非 0 时在提交订单前硬拦，且拦截原因写清当前用量与调整入口；
3. 演练（dry_run）既不占额度也不受额度限制；计数只算 type='real' 的订单。
"""
from __future__ import annotations

import asyncio
import tempfile
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xianyu_hunter.domain.order import BuyOutcome
from xianyu_hunter.infra.db_models import _utcnow
from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.modules.buyer import Buyer
from xianyu_hunter.modules.buyer_config import BuyerConfig


class FakeRepo:
    """只实现 Buyer.buy 用到的方法；count_real_orders_since 由测试注入用量"""

    def __init__(self, used_today: int = 0):
        self.orders: list[dict] = []
        self.events: list[dict] = []
        self._db_orders: dict[tuple[str, str], dict] = {}
        self.used_today = used_today
        self.since_calls: list = []

    def find_order_by_task_item(self, task_id, item_id):
        return self._db_orders.get((task_id, item_id))

    def count_real_orders_since(self, since):
        self.since_calls.append(since)
        return self.used_today

    def upsert_order(self, order, user_id=None):
        if user_id is not None and "user_id" not in order:
            order["user_id"] = user_id
        self.orders.append(order)

    def get_task(self, task_id, user_id=None):
        return None

    def save_event(self, event):
        self.events.append(event)
        return 1


def _buyer(used_today: int = 0, snapshot_limit: int = 0) -> tuple[Buyer, FakeRepo]:
    repo = FakeRepo(used_today=used_today)
    b = Buyer(
        browser=MagicMock(),
        repository=repo,
        event_bus=None,
        config=BuyerConfig(max_orders_per_day=snapshot_limit),
    )
    return b, repo


def _limit(value: int):
    """把 buyer.max_orders_per_day 灌进全局配置读取路径"""
    return patch(
        "xianyu_hunter.infra.yaml_config.get_config",
        return_value=SimpleNamespace(buyer=SimpleNamespace(max_orders_per_day=value)),
    )


def test_default_is_no_brake():
    """默认 0＝不限制：不让护栏在用户不知情时改变抢单行为"""
    assert BuyerConfig().max_orders_per_day == 0
    b, repo = _buyer(used_today=999)
    b._do_buy = AsyncMock(return_value={"item_id": "i1", "order_no": "NO1", "price": 1.0, "status": "pending_pay"})
    with _limit(0):
        result = asyncio.run(b.buy(task_id="t1", item_id="i1", expected_price=1.0))
    assert result.outcome == BuyOutcome.SUCCESS
    assert repo.since_calls == []  # 不限时连计数查询都不该发（省一次 DB 往返）


def test_limit_blocks_before_real_order():
    """达到上限：提交订单前硬拦，_do_buy 完全不被调用"""
    b, repo = _buyer(used_today=2)
    b._do_buy = AsyncMock()
    with _limit(2):
        result = asyncio.run(b.buy(task_id="t1", item_id="i1", expected_price=1.0))
    assert result.outcome == BuyOutcome.FAILED
    assert "单日抢单上限 2" in (result.error or "")
    assert "已真实落单 2 次" in (result.error or "")
    b._do_buy.assert_not_called()
    assert repo.orders == []


def test_limit_not_reached_still_orders():
    """未达上限照常放行（护栏只做「>=」拦截，不吃掉那一单）"""
    b, repo = _buyer(used_today=1)
    b._do_buy = AsyncMock(return_value={"item_id": "i1", "order_no": "NO1", "price": 1.0, "status": "pending_pay"})
    with _limit(2):
        result = asyncio.run(b.buy(task_id="t1", item_id="i1", expected_price=1.0))
    assert result.outcome == BuyOutcome.SUCCESS
    b._do_buy.assert_awaited_once()


def test_dry_run_neither_consumes_nor_is_blocked():
    """演练不产生真实订单：既不受上限限制，也不该被计入额度"""
    b, repo = _buyer(used_today=5)
    b._do_buy = AsyncMock(return_value=None)  # None＝已在提交前硬中止
    with _limit(2):
        result = asyncio.run(b.buy(task_id="t1", item_id="i1", expected_price=1.0, dry_run=True))
    assert result.outcome == BuyOutcome.DRY_RUN_STOPPED
    assert repo.since_calls == []


def test_config_read_failure_falls_back_to_snapshot():
    """读不到全局配置时回落构造期快照，不能把「读取失败」当成「无护栏」"""
    b, _repo = _buyer(used_today=3, snapshot_limit=1)
    b._do_buy = AsyncMock()
    with patch("xianyu_hunter.infra.yaml_config.get_config", side_effect=RuntimeError("boom")):
        result = asyncio.run(b.buy(task_id="t1", item_id="i1", expected_price=1.0))
    assert result.outcome == BuyOutcome.FAILED
    assert "单日抢单上限 1" in (result.error or "")
    b._do_buy.assert_not_called()


def test_today_boundary_matches_dashboard():
    """计数窗口起点＝UTC 自然日 0 点，与 stats_today 的「今日订单」同一口径"""
    b, repo = _buyer(used_today=0)
    b._do_buy = AsyncMock(return_value={"item_id": "i1", "order_no": "NO1", "price": 1.0, "status": "pending_pay"})
    with _limit(3):
        asyncio.run(b.buy(task_id="t1", item_id="i1", expected_price=1.0))
    assert len(repo.since_calls) == 1
    since = repo.since_calls[0]
    assert (since.hour, since.minute, since.second) == (0, 0, 0)
    assert since.date() == _utcnow().date()


@pytest.fixture
def tmp_repo() -> Repository:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        repo = Repository(str(Path(d) / "test.db"))
        yield repo
        repo.engine.dispose()


def test_count_real_orders_since_excludes_dry_run(tmp_repo: Repository):
    """repo 层：type='dry_run' 的演练报告不占真实额度，跨日记录不计入"""
    now = _utcnow()
    tmp_repo.upsert_order({
        "id": "o-real-1", "item_id": "i1", "status": "pending_pay",
        "type": "real", "created_at": now,
    })
    tmp_repo.upsert_order({
        "id": "o-real-2", "item_id": "i2", "status": "pending_pay",
        "type": "real", "created_at": now,
    })
    tmp_repo.upsert_order({
        "id": "o-dry", "item_id": "i3", "status": "dry_run",
        "type": "dry_run", "created_at": now,
    })
    tmp_repo.upsert_order({
        "id": "o-old", "item_id": "i4", "status": "pending_pay",
        "type": "real", "created_at": now - timedelta(days=2),
    })
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    assert tmp_repo.count_real_orders_since(day_start) == 2
    assert tmp_repo.count_real_orders_since(now - timedelta(days=5)) == 3
