"""Task 3: 自动官方采集触发逻辑（worker.py L405-418）的边界条件测试

覆盖四个 AND 条件的逐一不满足场景、全部满足场景、异常处理、配额耗尽。
触发逻辑：
    if (eval_cfg and eval_cfg.auto_collect_official
            and self.official_collect_fn
            and stats.official_collected < eval_cfg.auto_collect_max_per_run):
        await self.official_collect_fn(detail.id, self.task.id)
        stats.official_collected += 1

设计要点：
- patch worker 模块的 get_config 控制 EvalConfig 字段
- 使用 AsyncMock mock 异步 official_collect_fn
- NOTIFY_ONLY 模式避免抢单逻辑干扰采集断言
- FakeCollector.browser=None 跳过 AI 评估/深度分析块
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from xianyu_hunter.domain.evaluation import EvalResult, RiskLevel
from xianyu_hunter.domain.item import ItemDetail, ItemSummary
from xianyu_hunter.domain.seller import SellerProfile
from xianyu_hunter.domain.task import Task, TaskConfig, TaskMode
from xianyu_hunter.infra.yaml_config import AppConfig, EvalConfig
from xianyu_hunter.modules.price_strategy import PriceVerdict
from xianyu_hunter.modules.worker import TaskWorker


# ============== Fakes ==============
#
# 复用 test_worker_scheduler.py 的 Fake 模式：不依赖真实数据库/浏览器，
# 通过 fake 对象控制 collector/dedup/price/evaluator 的返回值。


class FakeCollector:
    """返回预设的 items/details/sellers

    browser=None 让 worker 中 _has_browser=False，跳过 AI 评估/深度分析
    以及 new_page() 调用，避免引入浏览器依赖。
    """

    def __init__(
        self,
        items: list[ItemSummary],
        details: dict[str, ItemDetail] | None = None,
        sellers: dict[str, SellerProfile] | None = None,
    ):
        self.items = items
        self.details = details or {}
        self.sellers = sellers or {}
        self.browser = None
        self.last_session_invalid = False
        self._browser_lock = None

    async def search(self, keyword: str, **kwargs: Any) -> list[ItemSummary]:
        return list(self.items)

    async def detail(self, item_id: str, page: Any = None) -> ItemDetail | None:
        return self.details.get(item_id)

    async def seller_profile(self, seller_id: str, page: Any = None) -> SellerProfile | None:
        return self.sellers.get(seller_id)

    async def seller_profile_fallback(
        self, summary: ItemSummary | None = None, detail: ItemDetail | None = None
    ) -> SellerProfile | None:
        sid = getattr(summary, "seller_id", None) or getattr(detail, "seller_id", None)
        return self.sellers.get(sid or "")


class FakeDedup:
    """默认全部新；可通过 existing 控制去重"""

    def __init__(self, existing: set[str] | None = None):
        self.existing = existing or set()

    def filter_new(self, items: list[ItemSummary]) -> list[ItemSummary]:
        return [i for i in items if i.id not in self.existing]

    def save(self, items: list[ItemSummary], task_id: str | None = None) -> int:
        self.existing.update(i.id for i in items)
        return len(items)


class FakePriceStrategy:
    """价格策略替身，allow 控制是否通过"""

    def __init__(self, allow: bool = True):
        self.allow = allow

    def check(self, item: ItemDetail, market: Any = None) -> PriceVerdict:
        return PriceVerdict(pass_=self.allow, reasons=[])


class ScoreableFakeEvaluator:
    """可精确控制 score 与 risk 的 Evaluator 替身

    FakeEvaluator 默认 score=85 risk=LOW，无法覆盖不通过 pass_score 的场景。
    本类允许测试用例独立设置 score 和 risk_level，验证 worker 的 pass_score 判断。
    """

    def __init__(self, score: int = 85, risk: RiskLevel = RiskLevel.LOW):
        self.score = score
        self.risk = risk

    def evaluate(self, item: ItemDetail, seller: SellerProfile) -> EvalResult:
        return EvalResult(
            score=self.score,
            risk_level=self.risk,
            dimension_scores={"professional": self.score},
        )


# ============== 工厂函数 ==============


def make_task(mode: TaskMode = TaskMode.NOTIFY_ONLY) -> Task:
    """创建测试任务

    默认 NOTIFY_ONLY 模式：评估通过后不抢单，循环继续处理下一件商品，
    便于在多商品场景下断言 official_collect_fn 的调用次数。
    """
    return Task(id="t1", name="iPhone", keyword="iPhone 13", mode=mode)


def make_item(i: int) -> ItemSummary:
    return ItemSummary(id=f"i{i}", title=f"iPhone 13 {i}", price=1999.0, seller_id=f"s{i}")


def make_detail(i: int) -> ItemDetail:
    return ItemDetail(id=f"i{i}", title=f"iPhone 13 {i}", price=1999.0, seller_id=f"s{i}")


def make_seller(i: int) -> SellerProfile:
    return SellerProfile(id=f"s{i}", credit_score=750, register_days=365, sold_count=10)


def make_eval_config(
    auto_collect_official: bool = True,
    auto_collect_max_per_run: int = 3,
    pass_score: int = 60,
    auto_buy_score: int = 80,
    auto_collect_fail_pause_threshold: int = 3,
    auto_collect_dedup_window_minutes: int = 30,
) -> EvalConfig:
    """构造自定义 EvalConfig，用于 patch get_config

    关闭所有 AI 功能避免干扰采集逻辑测试。
    Task 9 新增 auto_collect_fail_pause_threshold 参数：
    控制连续失败多少次后暂停本轮自动采集。
    """
    return EvalConfig(
        auto_collect_official=auto_collect_official,
        auto_collect_max_per_run=auto_collect_max_per_run,
        pass_score=pass_score,
        auto_buy_score=auto_buy_score,
        auto_collect_fail_pause_threshold=auto_collect_fail_pause_threshold,
        auto_collect_dedup_window_minutes=auto_collect_dedup_window_minutes,
        ai_auto_eval=False,
        ai_auto_deep_analyze=False,
        ai_multi_run_suggestion=False,
    )


def patch_eval_config(eval_cfg: EvalConfig):
    """patch worker 模块的 get_config，返回指定 EvalConfig 的 AppConfig

    worker.run_once 内通过 `from xianyu_hunter.infra.yaml_config import get_config`
    绑定到 worker 模块命名空间，故 patch xianyu_hunter.modules.worker.get_config。
    """
    app_cfg = AppConfig(eval=eval_cfg)
    return patch("xianyu_hunter.modules.worker.get_config", return_value=app_cfg)


def build_worker(
    item_count: int = 1,
    score: int = 85,
    risk: RiskLevel = RiskLevel.LOW,
    official_collect_fn: Any | None = None,
    mode: TaskMode = TaskMode.NOTIFY_ONLY,
    price_allow: bool = True,
    repo: Any | None = None,
    event_bus: Any | None = None,
) -> TaskWorker:
    """构造带官方采集回调的 worker

    默认 NOTIFY_ONLY 模式 + stop_on_first_buy=False：评估通过后不抢单，
    循环继续处理下一件商品，便于断言 official_collect_fn 在多商品场景下的调用次数。

    Task 8/9 新增 repo / event_bus 参数：
    - repo：注入后用于去重检查（get_recently_collected_item_ids）
    - event_bus：注入后用于 EVAL_PASSED / TASK_ERROR 事件投递（publish_nowait 调用）
    """
    items = [make_item(i) for i in range(item_count)]
    details = {it.id: make_detail(int(it.id[1:])) for it in items}
    sellers = {it.seller_id: make_seller(int(it.seller_id[1:])) for it in items}
    collector = FakeCollector(items, details, sellers)
    dedup = FakeDedup()
    price = FakePriceStrategy(allow=price_allow)
    evaluator = ScoreableFakeEvaluator(score=score, risk=risk)
    task = make_task(mode=mode)
    config = TaskConfig(
        interval_seconds=0.1,
        cooldown_after_buy=0.0,
        stop_on_first_buy=False,
    )
    return TaskWorker(
        task=task,
        collector=collector,
        dedup=dedup,
        price_strategy=price,
        evaluator=evaluator,
        buyer=None,
        config=config,
        official_collect_fn=official_collect_fn,
        repo=repo,
        event_bus=event_bus,
    )


@pytest.fixture
def worker_factory():
    """可复用的 mock worker 构造工厂

    返回 build_worker 函数，测试用例通过参数定制 worker 行为：
        worker = worker_factory(item_count=3, official_collect_fn=collect_fn)
    """
    return build_worker


# ============== SubTask 3.1: 四个 AND 条件任一不满足时不触发采集 ==============


@pytest.mark.asyncio
async def test_no_trigger_when_auto_collect_official_disabled(worker_factory):
    """条件1不满足：auto_collect_official=False，其他条件满足 → 不触发采集

    验证 eval_cfg.auto_collect_official 为 False 时短路求值，
    official_collect_fn 不被调用，计数保持 0。
    """
    collect_fn = AsyncMock(return_value={"ok": True})
    worker = worker_factory(item_count=1, official_collect_fn=collect_fn)
    with patch_eval_config(make_eval_config(auto_collect_official=False)):
        result = await worker.run_once()
    collect_fn.assert_not_awaited()
    assert result.stats.official_collected == 0


@pytest.mark.asyncio
async def test_no_trigger_when_official_collect_fn_none(worker_factory):
    """条件2不满足：official_collect_fn=None，其他条件满足 → 不触发采集

    验证 self.official_collect_fn 为 None 时短路求值，
    不报错且计数保持 0（模拟 container 未注入采集回调的场景）。
    """
    worker = worker_factory(item_count=1, official_collect_fn=None)
    with patch_eval_config(make_eval_config(auto_collect_official=True)):
        result = await worker.run_once()
    # official_collect_fn 为 None 时不应报错，计数应为 0
    assert result.stats.official_collected == 0


@pytest.mark.asyncio
async def test_no_trigger_when_quota_exceeded(worker_factory):
    """条件3不满足：max_per_run=0 → stats.official_collected(0) < 0 为 False → 不触发采集

    验证配额已耗尽时不触发采集。max_per_run=0 表示本轮不允许任何采集，
    0 < 0 为 False，条件短路，official_collect_fn 不被调用。
    """
    collect_fn = AsyncMock(return_value={"ok": True})
    worker = worker_factory(item_count=1, official_collect_fn=collect_fn)
    with patch_eval_config(
        make_eval_config(auto_collect_official=True, auto_collect_max_per_run=0)
    ):
        result = await worker.run_once()
    collect_fn.assert_not_awaited()
    assert result.stats.official_collected == 0


@pytest.mark.asyncio
async def test_no_trigger_when_not_pass_score(worker_factory):
    """条件4不满足：商品评估分 < pass_score → should_pass 返回 False，continue 跳过采集块

    验证未通过 pass_score 的商品不会触发采集。score=50 < pass_score=60，
    should_pass(60) 返回 False，worker 在 continue 之前不会进入采集代码块。
    """
    collect_fn = AsyncMock(return_value={"ok": True})
    # score=50 < pass_score=60 → should_pass(60) 返回 False
    worker = worker_factory(
        item_count=1, score=50, risk=RiskLevel.MEDIUM, official_collect_fn=collect_fn
    )
    with patch_eval_config(make_eval_config(auto_collect_official=True, pass_score=60)):
        result = await worker.run_once()
    collect_fn.assert_not_awaited()
    assert result.stats.official_collected == 0
    # 商品被评估但未通过 pass_score
    assert result.stats.evaluated == 1
    assert result.stats.passed == 0


# ============== SubTask 3.2: 全部条件满足 → 触发采集并自增计数 ==============


@pytest.mark.asyncio
async def test_trigger_when_all_conditions_met(worker_factory):
    """四个条件全满足 → official_collect_fn 被调用一次，计数自增 1

    验证完整触发路径：
    - eval_cfg.auto_collect_official=True
    - self.official_collect_fn 不为 None
    - stats.official_collected(0) < max_per_run(3)
    - 商品通过 pass_score（score=85 >= 60）
    断言 official_collect_fn 以 (detail.id, task.id) 参数被 await 一次，计数为 1。
    """
    collect_fn = AsyncMock(return_value={"ok": True})
    worker = worker_factory(item_count=1, official_collect_fn=collect_fn)
    with patch_eval_config(
        make_eval_config(auto_collect_official=True, auto_collect_max_per_run=3)
    ):
        result = await worker.run_once()
    collect_fn.assert_awaited_once_with("i0", "t1")
    assert result.stats.official_collected == 1


# ============== SubTask 3.3: 采集函数抛异常 → 记录 warning 并继续 ==============


@pytest.mark.asyncio
async def test_continue_on_collect_exception(worker_factory):
    """official_collect_fn 抛 RuntimeError → 异常被捕获，计数不自增，循环继续处理下一件

    验证异常容错：第一件商品采集抛 RuntimeError，worker 内 try/except 捕获后
    计数不自增；第二件商品继续被处理且采集成功，计数变为 1。
    断言 official_collect_fn 被 await 两次（每件商品一次），但只有第二次成功。
    """
    # 第一次抛异常，第二次正常返回
    collect_fn = AsyncMock(side_effect=[RuntimeError("simulated"), {"ok": True}])
    worker = worker_factory(item_count=2, official_collect_fn=collect_fn)
    with patch_eval_config(
        make_eval_config(auto_collect_official=True, auto_collect_max_per_run=3)
    ):
        result = await worker.run_once()
    # 两件商品都尝试了采集（第一件抛异常被吞，第二件成功）
    assert collect_fn.await_count == 2
    # 只有第二件成功，计数为 1（第一件抛异常时计数不自增）
    assert result.stats.official_collected == 1


# ============== SubTask 3.4: 本轮 max_per_run 配额耗尽后停止触发 ==============


@pytest.mark.asyncio
async def test_stop_when_quota_reached(worker_factory):
    """max_per_run=2，前两件触发后，第三件即使通过 pass_score 也不再触发

    验证配额限制：3 件商品全部通过 pass_score，但 max_per_run=2 时
    只有前两件触发采集，第三件因 stats.official_collected(2) < 2 为 False 被跳过。
    断言 official_collect_fn 只被 await 两次，且第三件 i2 不在调用列表中。
    """
    collect_fn = AsyncMock(return_value={"ok": True})
    worker = worker_factory(item_count=3, official_collect_fn=collect_fn)
    with patch_eval_config(
        make_eval_config(auto_collect_official=True, auto_collect_max_per_run=2)
    ):
        result = await worker.run_once()
    # 只有前两件触发采集，第三件因配额耗尽跳过
    assert collect_fn.await_count == 2
    assert result.stats.official_collected == 2
    # 三件商品都被评估且通过，但只有前两件被采集
    assert result.stats.evaluated == 3
    assert result.stats.passed == 3
    # 验证调用参数：第三件 i2 未被调用
    called_item_ids = [call.args[0] for call in collect_fn.await_args_list]
    assert called_item_ids == ["i0", "i1"]
    assert "i2" not in called_item_ids


# ============== Task 9: 失败退避机制测试 ==============
#
# 验证连续失败计数器、暂停阈值、暂停后跳过、新一轮重置、notifier 告警。
# 配合 make_eval_config(auto_collect_fail_pause_threshold=N) 控制阈值。


@pytest.mark.asyncio
async def test_backoff_increments_failure_counter(worker_factory):
    """采集失败时计数器自增，但未达阈值不暂停

    场景：1 件商品，collect_fn 抛 RuntimeError，threshold=3（默认）
    期望：计数器=1，未暂停（1 < 3），official_collected 保持 0
    """
    collect_fn = AsyncMock(side_effect=RuntimeError("simulated"))
    worker = worker_factory(item_count=1, official_collect_fn=collect_fn)
    with patch_eval_config(
        make_eval_config(auto_collect_official=True, auto_collect_fail_pause_threshold=3)
    ):
        result = await worker.run_once()
    assert collect_fn.await_count == 1
    assert result.stats.official_collected == 0
    assert worker._consecutive_collect_failures == 1
    assert result.stats.official_collect_paused is False


@pytest.mark.asyncio
async def test_backoff_pauses_after_threshold(worker_factory):
    """连续失败达到阈值后 stats.official_collect_paused=True

    场景：3 件商品全部采集失败，threshold=3
    期望：3 件都尝试了采集（暂停发生在第 3 件失败后），计数器=3，paused=True
    """
    collect_fn = AsyncMock(side_effect=RuntimeError("simulated"))
    worker = worker_factory(item_count=3, official_collect_fn=collect_fn)
    with patch_eval_config(
        make_eval_config(auto_collect_official=True, auto_collect_fail_pause_threshold=3)
    ):
        result = await worker.run_once()
    # 3 件商品都触发了 collect_fn（暂停发生在第 3 件失败之后）
    assert collect_fn.await_count == 3
    assert worker._consecutive_collect_failures == 3
    assert result.stats.official_collect_paused is True
    assert result.stats.official_collected == 0


@pytest.mark.asyncio
async def test_backoff_skips_subsequent_collects(worker_factory):
    """暂停后后续商品不触发采集（通过 stats.official_collect_paused 短路）

    场景：3 件商品，threshold=1，第 1 件失败后立即暂停
    期望：只有第 1 件触发 collect_fn，第 2/3 件因 paused 跳过采集块
    验证商品仍走完评估流程（evaluated=3），仅采集被跳过
    """
    collect_fn = AsyncMock(side_effect=RuntimeError("simulated"))
    worker = worker_factory(item_count=3, official_collect_fn=collect_fn)
    with patch_eval_config(
        make_eval_config(auto_collect_official=True, auto_collect_fail_pause_threshold=1)
    ):
        result = await worker.run_once()
    # 只有第 1 件触发采集（失败后立即暂停，第 2/3 件跳过采集块）
    assert collect_fn.await_count == 1
    assert result.stats.official_collect_paused is True
    # 商品仍走完评估流程，不因采集暂停而中断
    assert result.stats.evaluated == 3
    assert result.stats.passed == 3
    assert result.stats.official_collected == 0


@pytest.mark.asyncio
async def test_backoff_resets_next_run(worker_factory):
    """新一轮 run_once 开始时计数器重置为 0

    场景：第 1 轮 1 件商品失败（counter=1），第 2 轮 1 件商品成功
    期望：第 2 轮开始时 counter 重置为 0，第 2 轮成功后 counter 仍为 0
    为什么不延续：新一轮可能已修复问题（Cookie 刷新/网络恢复），
    应给重新尝试的机会
    """
    # 第 1 轮失败，第 2 轮成功
    collect_fn = AsyncMock(side_effect=[RuntimeError("simulated"), {"ok": True}])
    worker = worker_factory(item_count=1, official_collect_fn=collect_fn)
    with patch_eval_config(
        make_eval_config(auto_collect_official=True, auto_collect_fail_pause_threshold=3)
    ):
        first_result = await worker.run_once()
        # 第 1 轮结束后计数器为 1
        assert worker._consecutive_collect_failures == 1
        assert first_result.stats.official_collected == 0

        # 清空 dedup 缓存：第 1 轮 finally 块的 save() 已将 i0 标记为已见，
        # 不清空则第 2 轮 filter_new 会返回空列表导致提前 return，
        # 无法验证采集块的 counter 重置逻辑
        worker.dedup.existing.clear()

        # 第 2 轮：counter 应在 run_once 开始时重置为 0
        second_result = await worker.run_once()
    # 第 2 轮成功，counter 保持 0
    assert worker._consecutive_collect_failures == 0
    assert second_result.stats.official_collected == 1
    assert second_result.stats.official_collect_paused is False


@pytest.mark.asyncio
async def test_backoff_notifier_called_on_pause(worker_factory):
    """暂停时通过 EventBus 发送 TASK_ERROR 告警

    场景：1 件商品失败，threshold=1，注入 mock event_bus
    期望：event_bus.publish_nowait 被调用 2 次：
    1. EVAL_PASSED（评估通过推送）
    2. TASK_ERROR（自动采集暂停告警，severity=critical）
    验证告警能触达用户，避免采集长期失效未察觉。
    统一走 EventBus 路径，与钉钉通知修复的架构方向一致。
    """
    from unittest.mock import MagicMock

    from xianyu_hunter.domain.events import Event, EventType

    collect_fn = AsyncMock(side_effect=RuntimeError("simulated"))
    # EventBus.publish_nowait 是同步方法，用 MagicMock（非 AsyncMock）
    event_bus = MagicMock()
    event_bus.publish_nowait = MagicMock()
    worker = worker_factory(
        item_count=1, official_collect_fn=collect_fn, event_bus=event_bus
    )
    with patch_eval_config(
        make_eval_config(auto_collect_official=True, auto_collect_fail_pause_threshold=1)
    ):
        result = await worker.run_once()
    # publish_nowait 被调用 2 次：
    # 1. EVAL_PASSED（评估通过推送）
    # 2. TASK_ERROR（自动采集暂停告警）
    assert event_bus.publish_nowait.call_count == 2
    # 第一次是 EVAL_PASSED
    eval_event = event_bus.publish_nowait.call_args_list[0].args[0]
    assert isinstance(eval_event, Event)
    assert eval_event.type == EventType.EVAL_PASSED
    # 第二次是 TASK_ERROR
    called_event = event_bus.publish_nowait.call_args_list[1].args[0]
    assert isinstance(called_event, Event)
    assert called_event.type == EventType.TASK_ERROR
    assert called_event.severity == "critical"
    assert called_event.task_id == "t1"
    assert "auto_collect_paused" in called_event.payload.get("reason", "")
    assert result.stats.official_collect_paused is True
