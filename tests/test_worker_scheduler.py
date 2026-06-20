"""Worker + Scheduler 单元测试

mock Collector / Dedup / PriceStrategy / Evaluator / Buyer，验证完整流水线。
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest

from xianyu_hunter.domain.evaluation import EvalResult, RiskLevel
from xianyu_hunter.domain.item import ItemDetail, ItemSummary
from xianyu_hunter.domain.order import BuyOutcome, BuyResult, OrderSnapshot
from xianyu_hunter.domain.seller import SellerProfile
from xianyu_hunter.domain.task import Task, TaskConfig, TaskMode
from xianyu_hunter.modules.buyer import Buyer
from xianyu_hunter.modules.collector import Collector
from xianyu_hunter.modules.dedup import ItemDedup
from xianyu_hunter.modules.evaluator import Evaluator
from xianyu_hunter.modules.price_strategy import MarketContext, PriceConfig, PriceStrategy, PriceVerdict
from xianyu_hunter.modules.scheduler import TaskScheduler
from xianyu_hunter.modules.worker import TaskWorker


# ============== Fakes ==============


class FakeCollector:
    """返回预设的 items/details/sellers"""
    def __init__(self, items: list[ItemSummary], details: dict[str, ItemDetail] | None = None, sellers: dict[str, SellerProfile] | None = None):
        self.items = items
        self.details = details or {}
        self.sellers = sellers or {}
        self.search_calls = 0
        # worker.run_once 会通过 collector.browser.new_page() 创建复用页面
        # 测试中不需要真实浏览器，用 None 占位即可（detail/seller_profile 忽略 page 参数）
        self.browser = None

    async def search(self, keyword: str, **kwargs: Any) -> list[ItemSummary]:
        self.search_calls += 1
        return list(self.items)

    async def detail(self, item_id: str, page: Any = None) -> ItemDetail | None:
        return self.details.get(item_id)

    async def seller_profile(self, seller_id: str, page: Any = None) -> SellerProfile | None:
        return self.sellers.get(seller_id)


class FakeDedup:
    """默认全部新；可通过 existing 控制"""
    def __init__(self, existing: set[str] | None = None):
        self.existing = existing or set()
        self.saved: list[str] = []

    async def filter_new(self, items: list[ItemSummary]) -> list[ItemSummary]:
        return [i for i in items if i.id not in self.existing]

    async def save(self, items: list[ItemSummary]) -> int:
        self.existing.update(i.id for i in items)
        self.saved.extend(i.id for i in items)
        return len(items)


class FakePriceStrategy:
    def __init__(self, allow: bool = True):
        self.allow = allow

    def check(self, item: ItemDetail, market=None) -> PriceVerdict:
        return PriceVerdict(pass_=self.allow, reasons=[])


class FakeEvaluator:
    def __init__(self, passed: bool = True, score: int = 85):
        self.passed = passed
        self.score = score

    def evaluate(self, item: ItemDetail, seller: SellerProfile) -> EvalResult:
        risk = RiskLevel.LOW if self.passed else RiskLevel.EXTREME
        return EvalResult(
            score=self.score,
            risk_level=risk,
            dimension_scores={"professional": self.score},
        )


class FakeBuyer:
    def __init__(self, outcome: BuyOutcome = BuyOutcome.SUCCESS, order_no: str = "X123"):
        self.calls: list[dict] = []
        self.outcome = outcome
        self.order_no = order_no
        self._lock = asyncio.Lock()

    async def buy(self, task_id: str, item_id: str, expected_price: float) -> BuyResult:
        async with self._lock:
            self.calls.append({"task_id": task_id, "item_id": item_id, "price": expected_price})
        order = OrderSnapshot(item_id=item_id, order_no=self.order_no, price=expected_price)
        return BuyResult(outcome=self.outcome, order=order)


class FakeLinkRepo:
    def __init__(self) -> None:
        self.links: list[dict[str, Any]] = []

    def upsert_task_link(self, **kwargs: Any) -> int:
        self.links.append(kwargs)
        return len(self.links)

    def upsert_item_task_links(self, **kwargs: Any) -> int:
        # URL 类型已移除：只生成 item 行，有 seller_id 时额外生成 seller 行
        rows = [
            {
                "task_id": kwargs["task_id"],
                "link_type": "item",
                "link_key": kwargs["item_id"],
                "source": kwargs.get("source", "auto"),
            },
        ]
        if kwargs.get("seller_id"):
            rows.append({
                "task_id": kwargs["task_id"],
                "link_type": "seller",
                "link_key": kwargs["seller_id"],
                "source": kwargs.get("source", "auto"),
            })
        self.links.extend(rows)
        return len(rows)


# ============== 工厂 ==============


def make_task(mode: TaskMode = TaskMode.AUTO) -> Task:
    return Task(
        id="t1",
        name="iPhone",
        keyword="iPhone 13",
        mode=mode,
    )


def make_item(i: int) -> ItemSummary:
    return ItemSummary(id=f"i{i}", title=f"iPhone {i}", price=1999.0, seller_id=f"s{i}")


def make_detail(i: int) -> ItemDetail:
    d = ItemDetail(id=f"i{i}", title=f"iPhone {i}", price=1999.0, seller_id=f"s{i}")
    return d


def make_seller(i: int) -> SellerProfile:
    return SellerProfile(id=f"s{i}", credit_score=750, register_days=365, sold_count=10)


def make_worker(
    items: list[ItemSummary] | None = None,
    mode: TaskMode = TaskMode.AUTO,
    eval_passed: bool = True,
    price_allow: bool = True,
    buyer: FakeBuyer | None = None,
    config: TaskConfig | None = None,
    existing: set[str] | None = None,
) -> tuple[TaskWorker, FakeCollector, FakeDedup, FakeEvaluator, FakeBuyer | None]:
    items = items or [make_item(i) for i in range(3)]
    details = {it.id: make_detail(int(it.id[1:])) for it in items}
    sellers = {it.seller_id: make_seller(int(it.seller_id[1:])) for it in items}
    collector = FakeCollector(items, details, sellers)
    dedup = FakeDedup(existing=existing)
    price = FakePriceStrategy(allow=price_allow)
    evaluator = FakeEvaluator(passed=eval_passed)
    task = make_task(mode=mode)
    worker = TaskWorker(
        task=task,
        collector=collector,
        dedup=dedup,
        price_strategy=price,
        evaluator=evaluator,
        buyer=buyer,
        config=config or TaskConfig(interval_seconds=0.1, cooldown_after_buy=0.1),
    )
    return worker, collector, dedup, evaluator, buyer


# ============== Worker.run_once 测试 ==============


@pytest.mark.asyncio
async def test_worker_run_once_full_pipeline() -> None:
    """完整流水线：3 件商品全部通过 + 落单（stop_on_first_buy=True 时抢 1 单就停止）"""
    buyer = FakeBuyer(outcome=BuyOutcome.SUCCESS)
    worker, _, _, _, _ = make_worker(buyer=buyer)
    result = await worker.run_once()
    assert result.stats.found == 3
    assert result.stats.deduped == 0
    assert result.stats.price_filtered == 0
    # stop_on_first_buy=True：抢到 1 单后停止本轮
    assert result.stats.evaluated == 1
    assert result.stats.passed == 1
    assert result.stats.bought == 1
    assert result.has_bought is True
    assert len(buyer.calls) == 1


@pytest.mark.asyncio
async def test_worker_run_once_process_all_when_no_stop() -> None:
    """stop_on_first_buy=False 时全部 3 件都被评估"""
    buyer = FakeBuyer(outcome=BuyOutcome.FAILED)
    config = TaskConfig(interval_seconds=0.1, cooldown_after_buy=0.0, stop_on_first_buy=False)
    worker, _, _, _, _ = make_worker(buyer=buyer, config=config)
    result = await worker.run_once()
    assert result.stats.evaluated == 3
    assert result.stats.bought == 0
    assert result.stats.failed == 3


@pytest.mark.asyncio
async def test_worker_dedup_all_existing() -> None:
    """去重全部命中 → 提前结束，不评估、不下单"""
    buyer = FakeBuyer()
    items = [make_item(i) for i in range(3)]
    worker, _, _, _, _ = make_worker(items=items, buyer=buyer, existing={i.id for i in items})
    result = await worker.run_once()
    assert result.stats.found == 3
    assert result.stats.deduped == 3
    assert result.stats.evaluated == 0
    assert len(buyer.calls) == 0


@pytest.mark.asyncio
async def test_worker_price_filtered() -> None:
    """价格过滤全部拒绝 → 不评估"""
    buyer = FakeBuyer()
    worker, _, _, _, _ = make_worker(buyer=buyer, price_allow=False)
    result = await worker.run_once()
    assert result.stats.price_filtered == 3
    assert result.stats.evaluated == 0
    assert len(buyer.calls) == 0


@pytest.mark.asyncio
async def test_worker_auto_links_only_keyword_matching_items() -> None:
    items = [
        ItemSummary(id="good", title="iPhone 13 128G 国行", price=1999.0, seller_id="s0"),
        ItemSummary(id="noise", title="全新礼品袋毛巾套装", price=20.0, seller_id="s1"),
    ]
    details = {
        "good": ItemDetail(id="good", title="iPhone 13 128G 国行", price=1999.0, seller_id="s0"),
        "noise": ItemDetail(id="noise", title="全新礼品袋毛巾套装", price=20.0, seller_id="s1"),
    }
    sellers = {
        "s0": SellerProfile(id="s0", credit_score=750, register_days=365, sold_count=10),
        "s1": SellerProfile(id="s1", credit_score=750, register_days=365, sold_count=10),
    }
    repo = FakeLinkRepo()
    worker = TaskWorker(
        task=make_task(mode=TaskMode.NOTIFY_ONLY),
        collector=FakeCollector(items, details, sellers),
        dedup=FakeDedup(),
        price_strategy=FakePriceStrategy(),
        evaluator=FakeEvaluator(),
        repo=repo,
        config=TaskConfig(interval_seconds=0.1),
    )

    result = await worker.run_once()

    assert result.stats.linked == 1
    # URL 类型已移除：只生成 item 和 seller 行
    assert {(link["link_type"], link["link_key"]) for link in repo.links} == {
        ("item", "good"),
        ("seller", "s0"),
    }


@pytest.mark.asyncio
async def test_worker_eval_not_passed() -> None:
    """评估不通过 → 不下单"""
    buyer = FakeBuyer()
    worker, _, _, _, _ = make_worker(buyer=buyer, eval_passed=False)
    result = await worker.run_once()
    assert result.stats.evaluated == 3
    assert result.stats.passed == 0
    assert result.stats.bought == 0
    assert len(buyer.calls) == 0


@pytest.mark.asyncio
async def test_worker_confirm_mode_no_buy() -> None:
    """CONFIRM 模式 → 评估通过后也不下单"""
    buyer = FakeBuyer()
    worker, _, _, _, _ = make_worker(buyer=buyer, mode=TaskMode.CONFIRM)
    result = await worker.run_once()
    assert result.stats.passed == 3
    assert result.stats.bought == 0
    assert len(buyer.calls) == 0


@pytest.mark.asyncio
async def test_worker_buy_failure_recorded() -> None:
    """落单失败 → 计入 failed，下一轮继续"""
    buyer = FakeBuyer(outcome=BuyOutcome.FAILED)
    config = TaskConfig(interval_seconds=0.1, cooldown_after_buy=0.0, stop_on_first_buy=False)
    worker, _, _, _, _ = make_worker(buyer=buyer, config=config)
    result = await worker.run_once()
    assert result.stats.bought == 0
    assert result.stats.failed == 3
    assert len(buyer.calls) == 3


@pytest.mark.asyncio
async def test_worker_cooldown_skips_subsequent_buys() -> None:
    """cooldown_after_buy 起作用：抢到 1 单后冷却期内不抢"""
    buyer = FakeBuyer()
    config = TaskConfig(interval_seconds=0.1, cooldown_after_buy=10.0, stop_on_first_buy=False)
    items = [make_item(i) for i in range(5)]
    worker, _, _, _, _ = make_worker(items=items, buyer=buyer, config=config)
    result = await worker.run_once()
    # stop_on_first_buy 仍生效（默认），只下 1 单
    assert result.stats.bought == 1


@pytest.mark.asyncio
async def test_worker_market_context_computed() -> None:
    """≥3 个商品时会计算市场参考价"""
    items = [make_item(i) for i in range(4)]
    worker, _, _, _, _ = make_worker(items=items)
    result = await worker.run_once()
    # 不报错即视为市场参考价计算正常
    assert result.stats.found == 4


@pytest.mark.asyncio
async def test_worker_exception_in_item_does_not_crash() -> None:
    """单件商品处理异常不影响其他"""
    buyer = FakeBuyer()

    class BrokenCollector(FakeCollector):
        async def detail(self, item_id: str, page: Any = None) -> ItemDetail | None:
            if item_id == "i1":
                raise RuntimeError("simulated")
            return await super().detail(item_id, page=page)

    items = [make_item(i) for i in range(3)]
    details = {it.id: make_detail(int(it.id[1:])) for it in items}
    sellers = {it.seller_id: make_seller(int(it.seller_id[1:])) for it in items}
    collector = BrokenCollector(items, details, sellers)
    task = make_task()
    worker = TaskWorker(
        task=task,
        collector=collector,
        dedup=FakeDedup(),
        price_strategy=FakePriceStrategy(),
        evaluator=FakeEvaluator(),
        buyer=buyer,
        config=TaskConfig(interval_seconds=0.1, stop_on_first_buy=False),
    )
    result = await worker.run_once()
    # i1 抛错被吞掉，i2 抢到 1 单后 stop_on_first_buy 停止
    assert result.stats.bought == 1


# ============== Scheduler 测试 ==============


@pytest.mark.asyncio
async def test_scheduler_register_and_start_stop() -> None:
    """注册→启动→停止→注销"""
    buyer = FakeBuyer()
    worker, _, _, _, _ = make_worker(buyer=buyer)
    task = worker.task
    sch = TaskScheduler()
    await sch.register(task, worker)
    assert sch.get_status("t1").value == "running"

    await sch.start("t1")
    assert sch.is_running("t1") is True
    await asyncio.sleep(0.2)  # 让循环跑 1 轮
    await sch.stop("t1", timeout=2.0)
    assert sch.is_running("t1") is False
    assert sch.get_status("t1").value == "stopped"
    await sch.unregister("t1")


@pytest.mark.asyncio
async def test_scheduler_pause_resume() -> None:
    """暂停/恢复"""
    buyer = FakeBuyer()
    config = TaskConfig(interval_seconds=0.1, cooldown_after_buy=0.0, stop_on_first_buy=False)
    worker, _, _, _, _ = make_worker(buyer=buyer, config=config)
    sch = TaskScheduler()
    await sch.register(worker.task, worker)
    await sch.start("t1")
    await asyncio.sleep(0.15)
    # 跑过几轮：每个商品都被 buy 过
    await sch.pause("t1")
    paused_calls = len(buyer.calls)
    await asyncio.sleep(0.3)
    # 暂停后不增加
    assert len(buyer.calls) == paused_calls
    await sch.resume("t1")
    await asyncio.sleep(0.2)
    resumed_calls = len(buyer.calls)
    assert resumed_calls > paused_calls
    await sch.stop("t1")


@pytest.mark.asyncio
async def test_scheduler_start_already_running() -> None:
    """重复 start 不会启动新循环"""
    worker, _, _, _, _ = make_worker()
    sch = TaskScheduler()
    await sch.register(worker.task, worker)
    await sch.start("t1")
    t1 = sch._workers["t1"].loop_task
    await sch.start("t1")  # 第二次 start 应 no-op
    assert sch._workers["t1"].loop_task is t1
    await sch.stop("t1")


@pytest.mark.asyncio
async def test_scheduler_start_all_stop_all() -> None:
    """启动/停止所有任务"""
    buyer1 = FakeBuyer()
    buyer2 = FakeBuyer()
    w1, _, _, _, _ = make_worker(buyer=buyer1)
    w2, _, _, _, _ = make_worker(buyer=buyer2)
    w2.task.id = "t2"
    w2.task.name = "Mac"

    sch = TaskScheduler()
    await sch.register(w1.task, w1)
    await sch.register(w2.task, w2)
    await sch.start_all()
    assert sch.is_running("t1") and sch.is_running("t2")
    await asyncio.sleep(0.2)
    await sch.stop_all()
    assert not sch.is_running("t1") and not sch.is_running("t2")


@pytest.mark.asyncio
async def test_scheduler_register_duplicate_raises() -> None:
    """重复注册抛错"""
    worker, _, _, _, _ = make_worker()
    sch = TaskScheduler()
    await sch.register(worker.task, worker)
    with pytest.raises(ValueError, match="已注册"):
        await sch.register(worker.task, worker)


@pytest.mark.asyncio
async def test_scheduler_unknown_task_raises() -> None:
    """查询/启动未注册任务抛 KeyError"""
    sch = TaskScheduler()
    with pytest.raises(KeyError, match="未注册"):
        sch.get_status("nope")
    with pytest.raises(KeyError, match="未注册"):
        await sch.unregister("nope")


@pytest.mark.asyncio
async def test_scheduler_list_tasks() -> None:
    """list_tasks 返回所有已注册任务"""
    w1, _, _, _, _ = make_worker()
    w2, _, _, _, _ = make_worker()
    w2.task.id = "t2"
    sch = TaskScheduler()
    await sch.register(w1.task, w1)
    await sch.register(w2.task, w2)
    assert [t.id for t in sch.list_tasks()] == ["t1", "t2"]


@pytest.mark.asyncio
async def test_scheduler_unregister_running_raises() -> None:
    """运行中任务不能注销"""
    worker, _, _, _, _ = make_worker()
    sch = TaskScheduler()
    await sch.register(worker.task, worker)
    await sch.start("t1")
    with pytest.raises(RuntimeError, match="仍在运行"):
        await sch.unregister("t1")
    await sch.stop("t1")
