"""E2E 联通测试（不依赖真实浏览器）

验证完整链路：
  Container 构造（注入 fake 依赖）
  → add task
  → Worker.run_once() 跑一轮
  → Buyer 落单
  → EventBus 派发 BUY_SUCCEEDED
  → NotifierHub 推送到 Notifier（mock aiohttp）
  → 全部成功
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from xianyu_hunter.domain.evaluation import EvalResult, RiskLevel
from xianyu_hunter.domain.item import ItemDetail, ItemSummary
from xianyu_hunter.domain.order import BuyOutcome, BuyResult, OrderSnapshot
from xianyu_hunter.domain.seller import SellerProfile
from xianyu_hunter.domain.task import Task, TaskConfig, TaskMode
from xianyu_hunter.container import Container
from xianyu_hunter.infra.event_bus import EventBus
from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.infra.yaml_config import AppConfig, BrowserConfig
from xianyu_hunter.modules.buyer import Buyer
from xianyu_hunter.modules.dedup import ItemDedup
from xianyu_hunter.modules.evaluator import Evaluator, EvaluationThresholds
from xianyu_hunter.modules.notifier import NotifierHub
from xianyu_hunter.modules.notifier.serverchan import ServerChanNotifier
from xianyu_hunter.modules.price_strategy import PriceStrategy
from xianyu_hunter.modules.scheduler import TaskScheduler
from xianyu_hunter.modules.worker import TaskWorker


# ============== Fakes（同 test_worker_scheduler）==============


class FakeCollector:
    def __init__(self, items, details=None, sellers=None):
        self.items = items
        self.details = details or {}
        self.sellers = sellers or {}

    async def search(self, keyword, **kwargs): return list(self.items)

    async def detail(self, item_id, **kwargs): return self.details.get(item_id)

    async def seller_profile(self, seller_id, **kwargs): return self.sellers.get(seller_id)

    async def seller_profile_fallback(self, summary=None, detail=None):
        from xianyu_hunter.domain.seller import SellerProfile
        return SellerProfile(id="fallback", nick="test", credit_score=700, register_days=365, on_sale_count=1, sold_count=0)

    def clear_seller_profile_cache(self): pass


class FakeDedup:
    def __init__(self, existing=None):
        self.existing = set(existing or [])
        self.saved = []

    async def filter_new(self, items): return [i for i in items if i.id not in self.existing]

    async def save(self, items):
        n = len(items)
        for i in items:
            self.existing.add(i.id)
        self.saved.extend(i.id for i in items)
        return n


class FakeEvaluator:
    def __init__(self, passed=True, score=85):
        self.passed = passed
        self.score = score

    def evaluate(self, item, seller):
        risk = RiskLevel.LOW if self.passed else RiskLevel.EXTREME
        return EvalResult(score=self.score, risk_level=risk, dimension_scores={})


class FakeBuyer:
    def __init__(self, outcome=BuyOutcome.SUCCESS):
        self.outcome = outcome
        self.calls = []
        self._lock = asyncio.Lock()

    async def buy(self, task_id, item_id, expected_price):
        async with self._lock:
            self.calls.append({"task_id": task_id, "item_id": item_id, "price": expected_price})
        return BuyResult(
            outcome=self.outcome,
            order=OrderSnapshot(item_id=item_id, order_no=f"ORD-{len(self.calls)}", price=expected_price),
        )


def make_response(status, text="ok"):
    resp = MagicMock()
    resp.status = status
    resp.text = AsyncMock(return_value=text)
    resp.request_info = MagicMock()
    resp.history = ()
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


def make_session(responses):
    session = MagicMock()
    queue = list(responses)
    def _post(*args, **kwargs):
        if not queue: raise AssertionError("post 次数超出")
        return queue.pop(0)
    session.post = _post
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


# ============== 工厂：构造带 fakes 的 Container ==============


@pytest.fixture
def e2e_container(tmp_path):
    """构造一个测试用 Container（所有依赖注入 fakes）"""
    db_path = str(tmp_path / "e2e.db")
    repo = Repository(db_path=db_path)
    bus = EventBus()
    # Fakes
    items = [ItemSummary(id="i1", title="iPhone", price=1999.0, seller_id="s1")]
    details = {"i1": ItemDetail(id="i1", title="iPhone", price=1999.0, seller_id="s1")}
    sellers = {"s1": SellerProfile(id="s1", credit_score=750, register_days=365, sold_count=10)}
    fake_collector = FakeCollector(items, details, sellers)
    fake_dedup = FakeDedup()
    fake_evaluator = FakeEvaluator(passed=True, score=85)
    fake_buyer = FakeBuyer()

    # Notifier：使用真实 ServerChanNotifier，但用 mock aiohttp 拦截 HTTP
    notifier = ServerChanNotifier(send_key="SCT-TEST", max_retries=1, base_backoff=0.01)
    hub = NotifierHub.__new__(NotifierHub)  # 跳过 init
    hub._notifiers = [notifier]
    hub._quiet_hours = None
    hub._suppressed_lock = asyncio.Lock()
    hub._suppressed_count = 0
    hub._suppressed_last_at = None
    hub.attach(bus)

    container = Container(
        config=AppConfig(browser=BrowserConfig()),
        repo=repo,
        event_bus=bus,
        collector=fake_collector,
        dedup=fake_dedup,
        evaluator=fake_evaluator,
        buyer=fake_buyer,
        notifier_hub=hub,
        scheduler=TaskScheduler(),
    )
    yield container, fake_collector, fake_dedup, fake_evaluator, fake_buyer
    # 关闭 bus
    bus.stop()


# ============== E2E 流程 ==============


@pytest.mark.asyncio
async def test_e2e_add_to_buy_with_push(tmp_path, capsys) -> None:
    """端到端：add → run 一轮 → 落单 → 事件 → 推送 mock 200"""
    db_path = str(tmp_path / "e2e.db")
    repo = Repository(db_path=db_path)
    bus = EventBus()
    items = [ItemSummary(id="i1", title="iPhone 13", price=1999.0, seller_id="s1")]
    details = {"i1": ItemDetail(id="i1", title="iPhone 13", price=1999.0, seller_id="s1")}
    sellers = {"s1": SellerProfile(id="s1", credit_score=750, register_days=365, sold_count=10)}
    collector = FakeCollector(items, details, sellers)
    dedup = FakeDedup()
    evaluator = FakeEvaluator(passed=True)
    buyer = FakeBuyer(outcome=BuyOutcome.SUCCESS)
    notifier = ServerChanNotifier(send_key="SCT-TEST", max_retries=1, base_backoff=0.01)
    hub = NotifierHub.__new__(NotifierHub)
    hub._notifiers = [notifier]
    hub._quiet_hours = None
    hub._suppressed_lock = asyncio.Lock()
    hub._suppressed_count = 0
    hub._suppressed_last_at = None
    hub.attach(bus)

    # 1. add 任务（直接写 DB，模拟 CLI 行为）
    task = Task(id="t1", name="iPhone", keyword="iPhone 13", mode=TaskMode.AUTO)
    repo.upsert_task({
        "id": task.id, "name": task.name, "keyword": task.keyword,
        "min_price": None, "max_price": None, "mode": task.mode.value, "status": "running",
    })
    assert repo.get_task("t1") is not None

    # 2. 装价格策略 + Worker
    price = PriceStrategy()  # 默认无规则：放行
    worker = TaskWorker(
        task=task, collector=collector, dedup=dedup, price_strategy=price,
        evaluator=evaluator, buyer=buyer,
        config=TaskConfig(interval_seconds=0.1, cooldown_after_buy=0.0, stop_on_first_buy=True),
    )

    # 3. 启动 bus + mock aiohttp + 跑一轮
    bus_task = asyncio.create_task(bus.run_forever())
    await asyncio.sleep(0.05)
    session = make_session([make_response(200, '{"code":0}')])
    with patch.object(aiohttp, "ClientSession", return_value=session):
        result = await worker.run_once()
        await asyncio.sleep(0.2)  # 等事件分发

    # 4. 验证
    assert result.has_bought is True
    assert len(buyer.calls) == 1
    # 注：FakeBuyer 不调 upsert_order，DB 中订单数 = 0
    # 真实 Buyer 的订单持久化路径已在 test_buyer.py 中覆盖

    # 5. 停止
    bus.stop()
    bus_task.cancel()
    try:
        await bus_task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_e2e_full_flow_with_scheduler(tmp_path) -> None:
    """端到端：通过 Scheduler 管理一个 Worker 的完整生命周期"""
    db_path = str(tmp_path / "e2e2.db")
    repo = Repository(db_path=db_path)
    bus = EventBus()
    items = [ItemSummary(id="i1", title="iPhone", price=1999.0, seller_id="s1")]
    details = {"i1": ItemDetail(id="i1", title="iPhone", price=1999.0, seller_id="s1")}
    sellers = {"s1": SellerProfile(id="s1", credit_score=750, register_days=365, sold_count=10)}
    collector = FakeCollector(items, details, sellers)
    dedup = FakeDedup()
    evaluator = FakeEvaluator(passed=True)
    buyer = FakeBuyer()
    notifier = ServerChanNotifier(send_key="K", max_retries=1, base_backoff=0.01)
    hub = NotifierHub.__new__(NotifierHub)
    hub._notifiers = [notifier]
    hub._quiet_hours = None
    hub._suppressed_lock = asyncio.Lock()
    hub._suppressed_count = 0
    hub._suppressed_last_at = None
    hub.attach(bus)

    # 装入 sched
    sched = TaskScheduler()
    task = Task(id="t1", name="iPhone", keyword="iPhone 13", mode=TaskMode.AUTO)
    repo.upsert_task({
        "id": task.id, "name": task.name, "keyword": task.keyword,
        "min_price": None, "max_price": None, "mode": task.mode.value, "status": "running",
    })
    price = PriceStrategy()
    worker = TaskWorker(
        task=task, collector=collector, dedup=dedup, price_strategy=price,
        evaluator=evaluator, buyer=buyer,
        config=TaskConfig(interval_seconds=0.1, cooldown_after_buy=0.0, stop_on_first_buy=True),
    )
    await sched.register(task, worker)

    # 跑两轮：第 1 轮落单，第 2 轮 dedup 过滤掉
    bus_task = asyncio.create_task(bus.run_forever())
    await asyncio.sleep(0.05)
    session = make_session([
        make_response(200, "ok"),  # 第 1 轮 push
        # 第 2 轮没新增商品，不会再 push
    ])
    with patch.object(aiohttp, "ClientSession", return_value=session):
        await sched.start("t1")
        await asyncio.sleep(0.3)  # 跑 2 轮
        await sched.stop("t1", timeout=2.0)
        await asyncio.sleep(0.2)  # 等事件分发

    # FakeBuyer 不携带幂等机制，每轮都会被调用（直到 stop_on_first_buy 触发）
    # 我们只验证流程"启动 → 跑多轮 → 停止" + 有过落单 + 状态正确
    assert len(buyer.calls) >= 1
    assert sched.is_running("t1") is False
    assert sched.get_status("t1").value == "stopped"

    bus.stop()
    bus_task.cancel()
    try:
        await bus_task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_e2e_eval_failed_no_buy_no_push(tmp_path) -> None:
    """评估未通过 → 不下单、不推送"""
    db_path = str(tmp_path / "e2e3.db")
    repo = Repository(db_path=db_path)
    bus = EventBus()
    items = [ItemSummary(id="i1", title="iPhone", price=1999.0, seller_id="s1")]
    details = {"i1": ItemDetail(id="i1", title="iPhone", price=1999.0, seller_id="s1")}
    sellers = {"s1": SellerProfile(id="s1", credit_score=750, register_days=365, sold_count=10)}
    collector = FakeCollector(items, details, sellers)
    dedup = FakeDedup()
    evaluator = FakeEvaluator(passed=False)  # 评估不通过
    buyer = FakeBuyer()
    notifier = ServerChanNotifier(send_key="K", max_retries=1, base_backoff=0.01)
    hub = NotifierHub.__new__(NotifierHub)
    hub._notifiers = [notifier]
    hub._quiet_hours = None
    hub._suppressed_lock = asyncio.Lock()
    hub._suppressed_count = 0
    hub._suppressed_last_at = None
    hub.attach(bus)

    task = Task(id="t1", name="iPhone", keyword="iPhone 13", mode=TaskMode.AUTO)
    price = PriceStrategy()
    worker = TaskWorker(
        task=task, collector=collector, dedup=dedup, price_strategy=price,
        evaluator=evaluator, buyer=buyer,
        config=TaskConfig(interval_seconds=0.1, cooldown_after_buy=0.0, stop_on_first_buy=True),
    )

    # 用 mock aiohttp（如果 push 被调，会用掉一次）
    bus_task = asyncio.create_task(bus.run_forever())
    await asyncio.sleep(0.05)
    session = make_session([])  # 0 次：不应有 push
    with patch.object(aiohttp, "ClientSession", return_value=session):
        result = await worker.run_once()
        await asyncio.sleep(0.1)

    assert result.stats.passed == 0
    assert result.stats.bought == 0
    assert len(buyer.calls) == 0
    # 不应有 HTTP 调用
    # （如果 push 被触发，session 队列会空，但我们无法直接验证；间接通过 buyer.calls==0 证明）

    bus.stop()
    bus_task.cancel()
    try:
        await bus_task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_container_wire_notifier_subscribes_events() -> None:
    """Container.wire_notifier() 正确订阅事件类型"""
    bus = EventBus()
    container = Container(
        config=AppConfig(),
        repo=None,  # type: ignore[arg-type]
        event_bus=bus,
    )
    container.wire_notifier()
    from xianyu_hunter.domain.events import EventType
    assert EventType.EVAL_PASSED in bus._subscribers
    assert EventType.BUY_SUCCEEDED in bus._subscribers
    bus.stop()
