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
    """默认全部新；可通过 existing 控制

    签名与真实 ItemDedup 一致（filter_new/save 均为同步方法，均接受 task_id），
    避免 worker.py 同步调用时报 'coroutine has no len()' 或 'unexpected keyword argument'
    """
    def __init__(self, existing: set[str] | None = None):
        self.existing = existing or set()
        self.saved: list[str] = []

    def filter_new(self, items: list[ItemSummary], task_id: str | None = None) -> list[ItemSummary]:
        return [i for i in items if i.id not in self.existing]

    def save(self, items: list[ItemSummary], task_id: str | None = None) -> int:
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


# ============== 公共 fixture ==============


@pytest.fixture(autouse=True)
def _skip_cookie_check(monkeypatch):
    """跳过 scheduler._check_resume_allowed 的 Cookie 校验

    P0-① 在 scheduler.start/resume 中新增的 Cookie 校验会调用
    get_cookie_store().has_valid_cookies()，测试环境无真实 cookie 会误判失效
    导致所有 scheduler 测试抛 ResumeBlockedError。本测试聚焦 worker/scheduler
    调度逻辑，Cookie 校验由专门测试覆盖。
    """
    monkeypatch.setattr(
        TaskScheduler, "_check_resume_allowed", lambda self, task_id: None
    )


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

        def seller_profile_fallback(self, summary: ItemSummary, detail: ItemDetail | None) -> SellerProfile:
            # worker.py 在 detail/seller_profile 异常时会调用降级方法构建基础画像
            return SellerProfile(
                id=summary.seller_id,
                credit_score=0,
                register_days=0,
                sold_count=0,
            )

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

    sch.start("t1")  # start 是同步方法，无需 await
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
    worker, _, dedup, _, _ = make_worker(buyer=buyer, config=config)
    sch = TaskScheduler()
    await sch.register(worker.task, worker)
    sch.start("t1")  # start 是同步方法，无需 await
    await asyncio.sleep(0.15)
    # 跑过几轮：每个商品都被 buy 过
    sch.pause("t1")  # pause 是同步方法，无需 await
    paused_calls = len(buyer.calls)
    # 清空已去重集合：第 1 轮 save 后 existing 包含所有商品 ID，
    # 后续轮次 filter_new 返回空列表不再触发 buy。
    # 清空后 resume 的第 1 轮才能重新触发 buy，验证恢复语义
    dedup.existing.clear()
    await asyncio.sleep(0.3)
    # 暂停后不增加
    assert len(buyer.calls) == paused_calls
    sch.resume("t1")  # resume 是同步方法，无需 await
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
    sch.start("t1")  # start 是同步方法，无需 await
    t1 = sch._workers["t1"].loop_task
    sch.start("t1")  # start 是同步方法，无需 await  # 第二次 start 应 no-op
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
    # start_all 内部通过 asyncio.create_task 启动后台循环，保持同步签名
    sch.start_all()
    assert sch.is_running("t1") and sch.is_running("t2")
    await asyncio.sleep(0.2)
    await sch.stop_all()
    assert not sch.is_running("t1") and not sch.is_running("t2")


@pytest.mark.asyncio
async def test_start_all_continues_when_one_task_fails() -> None:
    """回归测试：start_all 容错单个任务启动失败

    复现线上 bug：服务重启时 Cookie 失效，_check_resume_allowed 抛 ResumeBlockedError，
    原 start_all 不捕获异常导致整个调度器循环静默失败，所有任务都不会运行。
    修复后 start_all 容错：单个任务失败记录 warning 日志，其他任务正常启动。
    """
    from unittest.mock import patch
    from xianyu_hunter.modules.scheduler import ResumeBlockedError

    buyer1 = FakeBuyer()
    buyer2 = FakeBuyer()
    w1, _, _, _, _ = make_worker(buyer=buyer1)
    w2, _, _, _, _ = make_worker(buyer=buyer2)
    w2.task.id = "t2"
    w2.task.name = "Mac"

    sch = TaskScheduler()
    await sch.register(w1.task, w1)
    await sch.register(w2.task, w2)

    # mock _check_resume_allowed：对 t1 抛 ResumeBlockedError，对 t2 通过
    def _fake_check(task_id: str) -> None:
        if task_id == "t1":
            raise ResumeBlockedError("Cookie 已失效，请重新登录后再恢复任务")

    with patch.object(sch, "_check_resume_allowed", side_effect=_fake_check):
        sch.start_all()

    # t1 启动失败（ResumeBlockedError），t2 应正常启动
    assert not sch.is_running("t1"), "t1 启动失败，不应运行"
    assert sch.is_running("t2"), "t2 应正常启动，不受 t1 失败影响"

    # 清理：停止 t2
    await sch.stop("t2")


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
    sch.start("t1")  # start 是同步方法，无需 await
    with pytest.raises(RuntimeError, match="仍在运行"):
        await sch.unregister("t1")
    await sch.stop("t1")


# ============== 评分达标→自动抢单 多场景集成测试 ==============
#
# 覆盖 worker.run_once() 内「评估→抢单门槛检查→落单」完整链路
# 修复回归：container.py 修复前 Evaluator 用固定 thresholds 划分 risk，
# 导致 score=77、auto_buy_score=75 时 risk=MEDIUM（按 80 划分）→ 不抢单


class ScoreableFakeEvaluator:
    """可精确控制 score 与 risk 的 Evaluator 替身

    FakeEvaluator 默认 score=85 risk=LOW，无法覆盖边界场景。
    本类允许测试用例独立设置 score 和 risk_level，验证 worker 的抢单门槛判断。
    """

    def __init__(self, score: int, risk: RiskLevel):
        self.score = score
        self.risk = risk

    def evaluate(self, item: ItemDetail, seller: SellerProfile) -> EvalResult:
        return EvalResult(
            score=self.score,
            risk_level=self.risk,
            dimension_scores={"professional": self.score},
        )


def _build_worker_with_score(
    score: int,
    risk: RiskLevel,
    mode: TaskMode = TaskMode.AUTO,
    buyer: FakeBuyer | None = None,
    cooldown_after_buy: float = 0.0,
) -> TaskWorker:
    """构造指定 score/risk 的 worker，便于多场景测试"""
    items = [make_item(0)]
    details = {"i0": make_detail(0)}
    sellers = {"s0": make_seller(0)}
    collector = FakeCollector(items, details, sellers)
    dedup = FakeDedup()
    price = FakePriceStrategy(allow=True)
    evaluator = ScoreableFakeEvaluator(score=score, risk=risk)
    task = make_task(mode=mode)
    config = TaskConfig(
        interval_seconds=0.1,
        cooldown_after_buy=cooldown_after_buy,
        stop_on_first_buy=False,
    )
    return TaskWorker(
        task=task,
        collector=collector,
        dedup=dedup,
        price_strategy=price,
        evaluator=evaluator,
        buyer=buyer,
        config=config,
    )


@pytest.mark.asyncio
async def test_auto_buy_triggered_when_score_meets_threshold() -> None:
    """场景1：AUTO 模式 + score=80(=auto_buy_score) + LOW → 抢单成功

    这是用户问题的核心场景：评分达标且 LOW 风险时应触发抢单。
    """
    from xianyu_hunter.infra.yaml_config import get_config

    auto_buy_score = get_config().eval.auto_buy_score
    buyer = FakeBuyer(outcome=BuyOutcome.SUCCESS)
    worker = _build_worker_with_score(
        score=auto_buy_score,
        risk=RiskLevel.LOW,
        mode=TaskMode.AUTO,
        buyer=buyer,
    )
    result = await worker.run_once()
    assert result.stats.bought == 1, f"score={auto_buy_score}+LOW+AUTO 应抢单"
    assert len(buyer.calls) == 1


@pytest.mark.asyncio
async def test_auto_buy_skipped_when_score_below_threshold() -> None:
    """场景2：AUTO 模式 + score=auto_buy_score-1 + MEDIUM → 不抢单

    边界条件：恰好低于抢单门槛 1 分。
    """
    from xianyu_hunter.infra.yaml_config import get_config

    auto_buy_score = get_config().eval.auto_buy_score
    buyer = FakeBuyer(outcome=BuyOutcome.SUCCESS)
    worker = _build_worker_with_score(
        score=auto_buy_score - 1,
        risk=RiskLevel.MEDIUM,
        mode=TaskMode.AUTO,
        buyer=buyer,
    )
    result = await worker.run_once()
    assert result.stats.bought == 0, f"score={auto_buy_score - 1} 不应抢单"
    assert len(buyer.calls) == 0


@pytest.mark.asyncio
async def test_auto_buy_skipped_in_confirm_mode_even_if_score_high() -> None:
    """场景3：CONFIRM 模式 + score=95 + LOW → 不抢单（默认模式仅推送）

    TaskMode 默认 CONFIRM，这是高频失败原因：评分达标但模式不对。
    """
    buyer = FakeBuyer(outcome=BuyOutcome.SUCCESS)
    worker = _build_worker_with_score(
        score=95,
        risk=RiskLevel.LOW,
        mode=TaskMode.CONFIRM,
        buyer=buyer,
    )
    result = await worker.run_once()
    assert result.stats.bought == 0, "CONFIRM 模式不应自动抢单"
    assert len(buyer.calls) == 0


@pytest.mark.asyncio
async def test_auto_buy_skipped_in_notify_only_mode() -> None:
    """场景4：NOTIFY_ONLY 模式 + score=95 + LOW → 不抢单"""
    buyer = FakeBuyer(outcome=BuyOutcome.SUCCESS)
    worker = _build_worker_with_score(
        score=95,
        risk=RiskLevel.LOW,
        mode=TaskMode.NOTIFY_ONLY,
        buyer=buyer,
    )
    result = await worker.run_once()
    assert result.stats.bought == 0, "NOTIFY_ONLY 模式不应抢单"
    assert len(buyer.calls) == 0


@pytest.mark.asyncio
async def test_auto_buy_skipped_when_buyer_not_injected() -> None:
    """场景5：AUTO 模式 + score 达标 + LOW + buyer=None → 不抢单

    模拟 with_browser=False 场景：Web 进程不启动浏览器，container.buyer=None。
    worker 应跳过落单而非抛 AttributeError。
    """
    worker = _build_worker_with_score(
        score=95,
        risk=RiskLevel.LOW,
        mode=TaskMode.AUTO,
        buyer=None,
    )
    result = await worker.run_once()
    assert result.stats.bought == 0, "buyer 未注入时不应抢单"


@pytest.mark.asyncio
async def test_auto_buy_skipped_during_cooldown() -> None:
    """场景6：AUTO 模式 + score 达标 + LOW + 冷却中 → 不抢单

    冷却期内即使评分达标也不重复抢单。
    """
    buyer = FakeBuyer(outcome=BuyOutcome.SUCCESS)
    # cooldown_after_buy=3600 模拟刚抢单后的冷却状态
    worker = _build_worker_with_score(
        score=95,
        risk=RiskLevel.LOW,
        mode=TaskMode.AUTO,
        buyer=buyer,
        cooldown_after_buy=3600.0,
    )
    # 手动设置 _last_buy_at 模拟刚抢单
    import time
    worker._last_buy_at = time.monotonic()
    result = await worker.run_once()
    assert result.stats.bought == 0, "冷却期内不应抢单"
    assert len(buyer.calls) == 0


@pytest.mark.asyncio
async def test_auto_buy_skipped_when_high_risk() -> None:
    """场景7：AUTO 模式 + score=95 + HIGH risk → 不抢单

    风险等级非 LOW 时即使分数达标也不抢单（should_auto_buy 要求 LOW）。
    """
    buyer = FakeBuyer(outcome=BuyOutcome.SUCCESS)
    worker = _build_worker_with_score(
        score=95,
        risk=RiskLevel.HIGH,
        mode=TaskMode.AUTO,
        buyer=buyer,
    )
    result = await worker.run_once()
    assert result.stats.bought == 0, "HIGH 风险不应抢单"
    assert len(buyer.calls) == 0


@pytest.mark.asyncio
async def test_auto_buy_skipped_when_extreme_risk() -> None:
    """场景8：AUTO 模式 + score=95 + EXTREME risk → 不抢单（一票否决）"""
    buyer = FakeBuyer(outcome=BuyOutcome.SUCCESS)
    worker = _build_worker_with_score(
        score=95,
        risk=RiskLevel.EXTREME,
        mode=TaskMode.AUTO,
        buyer=buyer,
    )
    result = await worker.run_once()
    assert result.stats.bought == 0, "EXTREME 风险不应抢单"
    assert len(buyer.calls) == 0


@pytest.mark.asyncio
async def test_auto_buy_high_score_above_threshold() -> None:
    """场景9：AUTO 模式 + score=100(满分) + LOW → 抢单成功"""
    buyer = FakeBuyer(outcome=BuyOutcome.SUCCESS)
    worker = _build_worker_with_score(
        score=100,
        risk=RiskLevel.LOW,
        mode=TaskMode.AUTO,
        buyer=buyer,
    )
    result = await worker.run_once()
    assert result.stats.bought == 1, "满分+LOW+AUTO 应抢单"
    assert len(buyer.calls) == 1


@pytest.mark.asyncio
async def test_real_evaluator_score_risk_consistency_in_worker_flow() -> None:
    """场景10：端到端集成——真实 Evaluator + 真实配置，验证 score↔risk 一致性

    回归 container.py 修复：确保 Evaluator 不带覆盖参数时，
    _score_to_risk 与 should_auto_buy 使用同一份 auto_buy_score。
    """
    from xianyu_hunter.infra.yaml_config import get_config
    from xianyu_hunter.modules.evaluator import Evaluator

    ev = Evaluator()
    # 模拟 evaluate() 内部赋值 self.thresholds 的过程
    ev.thresholds = ev._get_thresholds()
    ev.weights = ev._get_weights()
    ev.professional_keywords = ev._get_keywords()

    auto_buy_score = ev.thresholds.auto_buy_score
    config_auto_buy = get_config().eval.auto_buy_score
    # 关键断言：evaluator 用的阈值 == worker 用的阈值
    assert auto_buy_score == config_auto_buy, (
        f"evaluator.thresholds.auto_buy_score({auto_buy_score}) "
        f"必须等于 config.eval.auto_buy_score({config_auto_buy})"
    )

    # 边界1：刚好达标
    risk_at = ev._score_to_risk(auto_buy_score)
    assert risk_at == RiskLevel.LOW
    result_at = EvalResult(score=auto_buy_score, risk_level=risk_at)
    assert result_at.should_auto_buy(config_auto_buy) is True

    # 边界2：刚好未达标
    risk_below = ev._score_to_risk(auto_buy_score - 1)
    assert risk_below != RiskLevel.LOW
    result_below = EvalResult(score=auto_buy_score - 1, risk_level=risk_below)
    assert result_below.should_auto_buy(config_auto_buy) is False
