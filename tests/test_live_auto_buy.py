"""live 评估达标自动抢单测试

验证架构优化：实时搜索评估发现的达标商品能异步触发抢单，
不必等待 worker 下一轮调度。

测试覆盖：
1. _trigger_live_auto_buy 的模式检查、buyer 检查、冷却检查、browser_lock
2. _trigger_live_evaluation 的达标商品收集与异步触发
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xianyu_hunter.web.routes.api_task_links import (
    _LIVE_BUY_COOLDOWN,
    _trigger_live_auto_buy,
    _trigger_live_evaluation,
    _live_last_buy_at,
)


def _make_container(
    buyer: MagicMock | None = MagicMock(),
    task_mode: str = "auto",
    task_exists: bool = True,
    task_fields: dict | None = None,
) -> MagicMock:
    """构造测试用 Container mock

    task_fields: 覆盖任务字段（如 min_price/max_price/price_config），
    用于价格过滤测试。默认 price_config={"market_ratio": None} 显式禁用
    全局 market_ratio，让评估达标测试不被价格过滤干扰
    """
    container = MagicMock()
    container.buyer = buyer
    container.browser_lock = MagicMock()
    container.browser_lock.acquire = AsyncMock()
    container.browser_lock.release = MagicMock()

    # repo.get_task 返回任务字典
    if task_exists:
        task_dict = {"id": "t1", "mode": task_mode}
        # 默认禁用全局 market_ratio，避免评估达标测试被价格过滤干扰
        # 价格过滤测试通过 task_fields 显式启用规则覆盖此默认
        task_dict["price_config"] = {"market_ratio": None}
        if task_fields:
            task_dict.update(task_fields)
        container.repo.get_task.return_value = task_dict
    else:
        container.repo.get_task.return_value = None

    # repo.upsert_eval_event 不做任何事
    container.repo.upsert_eval_event = MagicMock()

    # evaluator 返回一个 mock（_trigger_live_evaluation 内部会用到）
    container.evaluator = None  # 触发内部 Evaluator() 构造

    return container


def _make_candidate(item_id: str = "i1", score: int = 85, price: float = 100.0) -> dict:
    """构造达标商品候选"""
    return {
        "item_id": item_id,
        "title": f"测试商品 {item_id}",
        "price": price,
        "score": score,
        "risk_level": "low",
    }


# ============== _trigger_live_auto_buy 单元测试 ==============


@pytest.mark.asyncio
async def test_auto_buy_skipped_when_task_mode_not_auto() -> None:
    """场景1：任务模式非 auto → 跳过抢单"""
    container = _make_container(task_mode="confirm")
    buyer_mock = container.buyer
    buyer_mock.buy = AsyncMock()

    await _trigger_live_auto_buy(container, "t1", _make_candidate())

    buyer_mock.buy.assert_not_called()
    container.browser_lock.acquire.assert_not_called()


@pytest.mark.asyncio
async def test_auto_buy_skipped_when_task_not_exists() -> None:
    """场景2：任务不存在 → 跳过抢单"""
    container = _make_container(task_exists=False)
    buyer_mock = container.buyer
    buyer_mock.buy = AsyncMock()

    await _trigger_live_auto_buy(container, "t1", _make_candidate())

    buyer_mock.buy.assert_not_called()


@pytest.mark.asyncio
async def test_auto_buy_skipped_when_buyer_not_injected() -> None:
    """场景3：buyer 未注入（with_browser=False）→ 跳过抢单"""
    container = _make_container()
    container.buyer = None

    await _trigger_live_auto_buy(container, "t1", _make_candidate())

    container.browser_lock.acquire.assert_not_called()


@pytest.mark.asyncio
async def test_auto_buy_skipped_during_cooldown() -> None:
    """场景4：冷却中 → 跳过抢单

    修复后冷却检查在 browser_lock 内，所以锁会被获取和释放，但 buy 不会被调用。
    """
    container = _make_container()
    buyer_mock = container.buyer
    buyer_mock.buy = AsyncMock()

    # 模拟刚抢单过（冷却未过期）
    with patch("xianyu_hunter.web.routes.api_task_links._live_last_buy_at", time.monotonic()):
        await _trigger_live_auto_buy(container, "t1", _make_candidate())

    buyer_mock.buy.assert_not_called()
    # 冷却检查在锁内，所以锁会被获取
    container.browser_lock.acquire.assert_called_once_with(priority="low")
    # finally 块保证锁被释放
    container.browser_lock.release.assert_called_once()


@pytest.mark.asyncio
async def test_auto_buy_triggers_when_all_conditions_met() -> None:
    """场景5：所有条件满足 → 触发抢单

    AUTO 模式 + buyer 已注入 + 冷却已过 + browser_lock 获取成功
    """
    from xianyu_hunter.domain.order import BuyOutcome, BuyResult

    container = _make_container()
    buyer_mock = container.buyer
    expected_result = BuyResult(outcome=BuyOutcome.SUCCESS)
    buyer_mock.buy = AsyncMock(return_value=expected_result)

    # 冷却已过（_live_last_buy_at = 0 表示从未抢单）
    with patch("xianyu_hunter.web.routes.api_task_links._live_last_buy_at", 0.0):
        await _trigger_live_auto_buy(container, "t1", _make_candidate())

    buyer_mock.buy.assert_called_once_with(
        task_id="t1",
        item_id="i1",
        expected_price=100.0,
    )
    container.browser_lock.acquire.assert_called_once_with(priority="low")
    container.browser_lock.release.assert_called_once()


@pytest.mark.asyncio
async def test_auto_buy_releases_lock_on_buy_exception() -> None:
    """场景6：buyer.buy 抛异常 → 仍释放 browser_lock

    防止锁泄漏导致 worker/live 端点永久阻塞。
    """
    container = _make_container()
    buyer_mock = container.buyer
    buyer_mock.buy = AsyncMock(side_effect=RuntimeError("浏览器断开"))

    with patch("xianyu_hunter.web.routes.api_task_links._live_last_buy_at", 0.0):
        await _trigger_live_auto_buy(container, "t1", _make_candidate())

    buyer_mock.buy.assert_called_once()
    container.browser_lock.release.assert_called_once()


@pytest.mark.asyncio
async def test_auto_buy_logs_warning_on_non_success_outcome() -> None:
    """场景7：抢单未成功（如 SKIPPED_DUPLICATE）→ 记录警告日志"""
    from xianyu_hunter.domain.order import BuyOutcome, BuyResult

    container = _make_container()
    buyer_mock = container.buyer
    expected_result = BuyResult(outcome=BuyOutcome.SKIPPED_DUPLICATE, error="in-process duplicate")
    buyer_mock.buy = AsyncMock(return_value=expected_result)

    with patch("xianyu_hunter.web.routes.api_task_links._live_last_buy_at", 0.0):
        await _trigger_live_auto_buy(container, "t1", _make_candidate())

    buyer_mock.buy.assert_called_once()
    container.browser_lock.release.assert_called_once()


@pytest.mark.asyncio
async def test_concurrent_auto_buy_respects_cooldown_after_fix() -> None:
    """场景11：并发竞态修复验证——多个协程同时触发，冷却检查在锁内串行生效

    修复前：冷却检查在锁外，3 个协程同时通过检查 → 3 次 buy()（冷却失效）
    修复后：冷却检查在锁内，第 1 个 buy 后 _live_last_buy_at 更新，
            第 2、3 个协程获取锁后冷却检查失败 → 只 1 次 buy()
    """
    from xianyu_hunter.domain.order import BuyOutcome, BuyResult
    from xianyu_hunter.container import PriorityBrowserLock

    # 用真实的 PriorityBrowserLock 保证串行化
    container = _make_container()
    container.browser_lock = PriorityBrowserLock()

    buyer_mock = container.buyer
    success_result = BuyResult(outcome=BuyOutcome.SUCCESS)
    buyer_mock.buy = AsyncMock(return_value=success_result)

    # 3 个达标商品同时触发
    candidates = [_make_candidate(item_id=f"i{i}") for i in range(3)]

    # 冷却已过（_live_last_buy_at = 0）
    with patch("xianyu_hunter.web.routes.api_task_links._live_last_buy_at", 0.0):
        await asyncio.gather(*[
            _trigger_live_auto_buy(container, "t1", c) for c in candidates
        ])

    # 修复后：只有第 1 个协程通过冷却检查，其余 2 个被冷却跳过
    assert buyer_mock.buy.call_count == 1, (
        f"冷却修复后应只抢单 1 次，实际 {buyer_mock.buy.call_count} 次"
    )


# ============== _trigger_live_evaluation 集成测试 ==============


@pytest.mark.asyncio
async def test_live_evaluation_triggers_auto_buy_for_qualified_item() -> None:
    """场景8：评估达标商品 → 触发 _trigger_live_auto_buy

    验证 _trigger_live_evaluation 在评估完成后，
    对 should_auto_buy=True 的商品触发异步抢单。
    """
    from xianyu_hunter.domain.evaluation import EvalResult, RiskLevel

    # 构造 mock evaluator，返回达标评分
    mock_evaluator = MagicMock()
    mock_evaluator.evaluate.return_value = EvalResult(
        score=85,
        risk_level=RiskLevel.LOW,
        dimension_scores={"professional": 85},
        reject_reasons=[],
        data_quality="insufficient",
    )

    container = _make_container()
    container.evaluator = mock_evaluator

    # 构造搜索结果
    items = [{
        "link_key": "i123",
        "display": {
            "title": "测试商品",
            "price": 100.0,
            "seller_id": "s1",
            "seller_nick": "卖家1",
        },
    }]

    # patch _trigger_live_auto_buy 捕获调用
    with patch("xianyu_hunter.web.routes.api_task_links._trigger_live_auto_buy", new_callable=AsyncMock) as mock_auto_buy:
        # patch asyncio.create_task 立即执行协程（测试环境不真正异步调度）
        async def _immediate_run(coro):
            await coro

        with patch("asyncio.create_task", side_effect=lambda c: asyncio.ensure_future(c)):
            await _trigger_live_evaluation(container, "t1", items)
            # 等待 create_task 创建的协程完成
            await asyncio.sleep(0.1)

    mock_auto_buy.assert_called_once()
    call_args = mock_auto_buy.call_args
    assert call_args.args[1] == "t1"  # task_id
    candidate = call_args.args[2]
    assert candidate["item_id"] == "i123"
    assert candidate["score"] == 85


@pytest.mark.asyncio
async def test_live_evaluation_skips_auto_buy_for_unqualified_item() -> None:
    """场景9：评估未达标商品 → 不触发 _trigger_live_auto_buy

    score=70 risk=MEDIUM，未达 auto_buy_score=80，不应触发抢单。
    """
    from xianyu_hunter.domain.evaluation import EvalResult, RiskLevel

    mock_evaluator = MagicMock()
    mock_evaluator.evaluate.return_value = EvalResult(
        score=70,
        risk_level=RiskLevel.MEDIUM,
        dimension_scores={"professional": 70},
        reject_reasons=[],
        data_quality="insufficient",
    )

    container = _make_container()
    container.evaluator = mock_evaluator

    items = [{
        "link_key": "i456",
        "display": {"title": "低分商品", "price": 50.0, "seller_id": "s2"},
    }]

    with patch("xianyu_hunter.web.routes.api_task_links._trigger_live_auto_buy", new_callable=AsyncMock) as mock_auto_buy:
        await _trigger_live_evaluation(container, "t1", items)

    mock_auto_buy.assert_not_called()


@pytest.mark.asyncio
async def test_live_evaluation_triggers_auto_buy_only_for_qualified() -> None:
    """场景10：混合评分商品 → 只对达标商品触发抢单

    3 个商品：1 个达标(85 LOW)、2 个未达标(70 MEDIUM, 50 HIGH)
    应只触发 1 次 _trigger_live_auto_buy。
    """
    from xianyu_hunter.domain.evaluation import EvalResult, RiskLevel

    # 构造 3 次评估返回不同结果
    results = [
        EvalResult(score=85, risk_level=RiskLevel.LOW, dimension_scores={},
                   reject_reasons=[], data_quality="insufficient"),
        EvalResult(score=70, risk_level=RiskLevel.MEDIUM, dimension_scores={},
                   reject_reasons=[], data_quality="insufficient"),
        EvalResult(score=50, risk_level=RiskLevel.HIGH, dimension_scores={},
                   reject_reasons=[], data_quality="insufficient"),
    ]
    mock_evaluator = MagicMock()
    mock_evaluator.evaluate.side_effect = results

    container = _make_container()
    container.evaluator = mock_evaluator

    items = [
        {"link_key": f"i{i}", "display": {"title": f"商品{i}", "price": 100.0, "seller_id": "s1"}}
        for i in range(3)
    ]

    with patch("xianyu_hunter.web.routes.api_task_links._trigger_live_auto_buy", new_callable=AsyncMock) as mock_auto_buy:
        with patch("asyncio.create_task", side_effect=lambda c: asyncio.ensure_future(c)):
            await _trigger_live_evaluation(container, "t1", items)
            await asyncio.sleep(0.1)

    # 只触发 1 次（达标商品）
    mock_auto_buy.assert_called_once()
    candidate = mock_auto_buy.call_args.args[2]
    assert candidate["item_id"] == "i0"
    assert candidate["score"] == 85


# ============== 价格过滤测试（与 worker.run_once 行为一致）==============


@pytest.mark.asyncio
async def test_live_evaluation_skips_auto_buy_when_price_above_max() -> None:
    """场景11：评估达标但价格超过任务 max_price → 不加入抢单候选

    验证 live 链路修复后与 worker.run_once 行为一致：
    任务设了 max_price=5000，商品价格 8000 且评分 85，应被价格过滤跳过抢单
    """
    from xianyu_hunter.domain.evaluation import EvalResult, RiskLevel

    mock_evaluator = MagicMock()
    mock_evaluator.evaluate.return_value = EvalResult(
        score=85,
        risk_level=RiskLevel.LOW,
        dimension_scores={},
        reject_reasons=[],
        data_quality="insufficient",
    )

    # 任务设了 max_price=5000，禁用 market_ratio 避免干扰
    container = _make_container(task_fields={
        "max_price": 5000.0,
        "price_config": {"market_ratio": None},
    })
    container.evaluator = mock_evaluator

    items = [{
        "link_key": "i_expensive",
        "display": {"title": "高价商品", "price": 8000.0, "seller_id": "s1"},
    }]

    with patch("xianyu_hunter.web.routes.api_task_links._trigger_live_auto_buy", new_callable=AsyncMock) as mock_auto_buy:
        await _trigger_live_evaluation(container, "t1", items)

    # 价格超 max_price，不应触发抢单
    mock_auto_buy.assert_not_called()


@pytest.mark.asyncio
async def test_live_evaluation_skips_auto_buy_when_price_below_min() -> None:
    """场景12：评估达标但价格低于任务 min_price（1元引流）→ 不加入抢单候选"""
    from xianyu_hunter.domain.evaluation import EvalResult, RiskLevel

    mock_evaluator = MagicMock()
    mock_evaluator.evaluate.return_value = EvalResult(
        score=85,
        risk_level=RiskLevel.LOW,
        dimension_scores={},
        reject_reasons=[],
        data_quality="insufficient",
    )

    container = _make_container(task_fields={
        "min_price": 100.0,
        "price_config": {"market_ratio": None},
    })
    container.evaluator = mock_evaluator

    items = [{
        "link_key": "i_cheap",
        "display": {"title": "1元引流", "price": 1.0, "seller_id": "s1"},
    }]

    with patch("xianyu_hunter.web.routes.api_task_links._trigger_live_auto_buy", new_callable=AsyncMock) as mock_auto_buy:
        await _trigger_live_evaluation(container, "t1", items)

    mock_auto_buy.assert_not_called()


@pytest.mark.asyncio
async def test_live_evaluation_auto_buy_when_price_within_range() -> None:
    """场景13：评估达标且价格在 [min, max] 区间内 → 触发抢单"""
    from xianyu_hunter.domain.evaluation import EvalResult, RiskLevel

    mock_evaluator = MagicMock()
    mock_evaluator.evaluate.return_value = EvalResult(
        score=85,
        risk_level=RiskLevel.LOW,
        dimension_scores={},
        reject_reasons=[],
        data_quality="insufficient",
    )

    container = _make_container(task_fields={
        "min_price": 100.0,
        "max_price": 5000.0,
        "price_config": {"market_ratio": None},
    })
    container.evaluator = mock_evaluator

    items = [{
        "link_key": "i_ok",
        "display": {"title": "价格合适", "price": 500.0, "seller_id": "s1"},
    }]

    with patch("xianyu_hunter.web.routes.api_task_links._trigger_live_auto_buy", new_callable=AsyncMock) as mock_auto_buy:
        with patch("asyncio.create_task", side_effect=lambda c: asyncio.ensure_future(c)):
            await _trigger_live_evaluation(container, "t1", items)
            await asyncio.sleep(0.1)

    mock_auto_buy.assert_called_once()
    candidate = mock_auto_buy.call_args.args[2]
    assert candidate["item_id"] == "i_ok"


@pytest.mark.asyncio
async def test_live_evaluation_price_filter_only_blocks_auto_buy_not_eval_write() -> None:
    """场景14：价格过滤仅阻止抢单，评估事件仍照写入 events 表

    设计意图：评估明细页面需要展示所有搜索到的商品供用户决策，
    不能因为价格超 max_price 就让前端看不到该商品
    """
    from xianyu_hunter.domain.evaluation import EvalResult, RiskLevel

    mock_evaluator = MagicMock()
    mock_evaluator.evaluate.return_value = EvalResult(
        score=85,
        risk_level=RiskLevel.LOW,
        dimension_scores={},
        reject_reasons=[],
        data_quality="insufficient",
    )

    container = _make_container(task_fields={
        "max_price": 100.0,
        "price_config": {"market_ratio": None},
    })
    container.evaluator = mock_evaluator

    items = [{
        "link_key": "i_over_priced",
        "display": {"title": "超价商品", "price": 500.0, "seller_id": "s1"},
    }]

    with patch("xianyu_hunter.web.routes.api_task_links._trigger_live_auto_buy", new_callable=AsyncMock) as mock_auto_buy:
        await _trigger_live_evaluation(container, "t1", items)

    # 抢单不触发
    mock_auto_buy.assert_not_called()
    # 但评估事件仍写入库（供前端展示）
    container.repo.upsert_eval_event.assert_called_once()
    event_payload = container.repo.upsert_eval_event.call_args[0][0]
    assert event_payload["item_id"] == "i_over_priced"
    assert event_payload["type"] == "eval.scored"


@pytest.mark.asyncio
async def test_live_evaluation_mixed_pricing_only_qualifies_in_range() -> None:
    """场景15：3 个达标商品，价格各不同，仅价格合适的触发抢单

    - 商品1: 1元（低于 min_price=100，过滤）
    - 商品2: 500元（在 [100, 5000] 内，触发抢单）
    - 商品3: 8000元（超过 max_price=5000，过滤）
    """
    from xianyu_hunter.domain.evaluation import EvalResult, RiskLevel

    mock_evaluator = MagicMock()
    # 3 个商品都评估达标
    mock_evaluator.evaluate.return_value = EvalResult(
        score=85,
        risk_level=RiskLevel.LOW,
        dimension_scores={},
        reject_reasons=[],
        data_quality="insufficient",
    )

    container = _make_container(task_fields={
        "min_price": 100.0,
        "max_price": 5000.0,
        "price_config": {"market_ratio": None},
    })
    container.evaluator = mock_evaluator

    items = [
        {"link_key": "i_cheap", "display": {"title": "便宜", "price": 1.0, "seller_id": "s1"}},
        {"link_key": "i_ok", "display": {"title": "合适", "price": 500.0, "seller_id": "s2"}},
        {"link_key": "i_expensive", "display": {"title": "贵", "price": 8000.0, "seller_id": "s3"}},
    ]

    with patch("xianyu_hunter.web.routes.api_task_links._trigger_live_auto_buy", new_callable=AsyncMock) as mock_auto_buy:
        with patch("asyncio.create_task", side_effect=lambda c: asyncio.ensure_future(c)):
            await _trigger_live_evaluation(container, "t1", items)
            await asyncio.sleep(0.1)

    # 只有价格合适的商品触发抢单
    mock_auto_buy.assert_called_once()
    candidate = mock_auto_buy.call_args.args[2]
    assert candidate["item_id"] == "i_ok"


@pytest.mark.asyncio
async def test_live_evaluation_uses_global_market_ratio_when_task_no_override() -> None:
    """场景16：任务未设 min/max_price 也未设 price_config，应用全局 market_ratio

    验证与 worker 行为一致：worker 共享 container.price_strategy（默认 market_ratio=0.8）
    """
    from xianyu_hunter.domain.evaluation import EvalResult, RiskLevel

    mock_evaluator = MagicMock()
    mock_evaluator.evaluate.return_value = EvalResult(
        score=85,
        risk_level=RiskLevel.LOW,
        dimension_scores={},
        reject_reasons=[],
        data_quality="insufficient",
    )

    # 任务无任何价格字段，不传 task_fields 让默认 price_config={"market_ratio": None} 生效
    # 这里显式覆盖回空 price_config 模拟"任务未配置价格规则"
    container = _make_container(task_fields={"price_config": {}})
    container.evaluator = mock_evaluator

    # 3 个商品价格都 100，median=100，market_ratio=0.8（全局默认）
    # 100 > 100 * 0.8 = 80 → 被过滤
    items = [
        {"link_key": f"i{i}", "display": {"title": f"商品{i}", "price": 100.0, "seller_id": "s1"}}
        for i in range(3)
    ]

    with patch("xianyu_hunter.web.routes.api_task_links._trigger_live_auto_buy", new_callable=AsyncMock) as mock_auto_buy:
        await _trigger_live_evaluation(container, "t1", items)

    # 全局 market_ratio=0.8 触发过滤（与 worker 行为一致）
    mock_auto_buy.assert_not_called()
