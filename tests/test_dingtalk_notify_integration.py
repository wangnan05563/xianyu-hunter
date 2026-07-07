"""钉钉通知端到端集成测试

验证修复后的完整链路：
1. wire_notifier 能识别 dingtalk 渠道（旧版 Bug #1：只判断 serverchan/pushplus/bark）
2. NotifierHub 能用 yaml 明文凭据创建 DingTalkNotifier（旧版 Bug #2：只从 keyring 读取）
3. TaskWorker 评估通过后能触发 EVAL_PASSED 事件（旧版 Bug #3：从未 publish）
"""
from __future__ import annotations

import asyncio
from contextlib import suppress
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xianyu_hunter.domain.events import Event, EventType
from xianyu_hunter.infra.event_bus import EventBus
from xianyu_hunter.infra.yaml_config import (
    AppConfig,
    NotifierChannelsConfig,
    NotifierConfig,
    QuietHoursConfig,
)
from xianyu_hunter.modules.notifier.dingtalk import DingTalkNotifier
from xianyu_hunter.modules.notifier.hub import NotifierHub


def _make_config_with_dingtalk() -> AppConfig:
    """构造 dingtalk 渠道开启 + 明文凭据齐全的 AppConfig"""
    return AppConfig.model_validate({
        "notifier": {
            "default_channels": ["dingtalk"],
            "channels": {
                "serverchan": False,
                "pushplus": False,
                "bark": False,
                "telegram": False,
                "wecom": False,
                "dingtalk": True,
                "webhook": False,
                "ntfy": False,
            },
            "quiet_hours": {"enabled": False},
            "subscribed_events": ["EVAL_PASSED", "BUY_SUCCEEDED"],
        },
        "dingtalk_webhook": "https://oapi.dingtalk.com/robot/send?access_token=test_token",
        "dingtalk_secret": "SECtest_secret_for_integration",
    })


def test_wire_notifier_recognizes_dingtalk_channel():
    """Bug #1 回归：wire_notifier 必须把 dingtalk 加入 enabled 列表

    旧版只判断 serverchan/pushplus/bark，dingtalk 即使在 channels 中开启也不会被加入
    """
    from xianyu_hunter.container import Container

    cfg = _make_config_with_dingtalk()
    # 用最小依赖构造 Container（绕过 build_default_container 的 browser/repo 等重依赖）
    container = Container.__new__(Container)
    container.config = cfg
    container.repo = MagicMock()
    container.event_bus = EventBus()
    # 初始 hub 为默认空 hub
    container.notifier_hub = NotifierHub()

    container.wire_notifier()

    # 验证 dingtalk 渠道被启用
    channel_names = [n.name for n in container.notifier_hub.notifiers]
    assert "dingtalk" in channel_names, (
        f"dingtalk 应被 wire_notifier 识别并启用，实际启用渠道: {channel_names}"
    )


def test_yaml_credentials_fallback_creates_configured_dingtalk():
    """Bug #2 回归：yaml 明文凭据应作为 keyring fallback 创建已配置的 notifier

    旧版 DingTalkNotifier 只从 keyring 读取，yaml 明文被忽略
    """
    cfg = _make_config_with_dingtalk()

    # 模拟 wire_notifier 中的 yaml_credentials 构造逻辑
    yaml_credentials = {
        "dingtalk": {
            "webhook_url": cfg.dingtalk_webhook,
            "secret": cfg.dingtalk_secret,
        }
    }

    # 模拟 keyring 中无凭据（验证 yaml fallback 生效）
    with patch("xianyu_hunter.modules.notifier.dingtalk.get_secret", return_value=None):
        hub = NotifierHub(
            channels=["dingtalk"],
            yaml_credentials=yaml_credentials,
            warn_unconfigured=False,
        )

    assert len(hub.notifiers) == 1, "应成功创建 1 个 dingtalk notifier"
    notifier = hub.notifiers[0]
    assert isinstance(notifier, DingTalkNotifier)
    assert notifier.is_configured is True, "yaml 明文凭据应让 is_configured 返回 True"
    assert notifier.webhook_url == cfg.dingtalk_webhook
    assert notifier.secret == cfg.dingtalk_secret


def test_yaml_credentials_empty_keyring_disabled_dingtalk_skipped():
    """无 yaml 凭据且 keyring 也无凭据时，dingtalk 应被跳过（不应崩溃）"""
    with patch("xianyu_hunter.modules.notifier.dingtalk.get_secret", return_value=None):
        hub = NotifierHub(
            channels=["dingtalk"],
            yaml_credentials={},  # 空 yaml 凭据
            warn_unconfigured=False,
        )
    assert len(hub.notifiers) == 0, "无凭据时不应创建 notifier"


@pytest.mark.asyncio
async def test_eval_passed_event_triggers_dingtalk_send():
    """Bug #3 回归：EVAL_PASSED 事件应触发 DingTalkNotifier.send

    完整链路：EventBus.publish(EVAL_PASSED) → NotifierHub.send → DingTalkNotifier._do_send
    """
    cfg = _make_config_with_dingtalk()
    yaml_credentials = {
        "dingtalk": {
            "webhook_url": cfg.dingtalk_webhook,
            "secret": cfg.dingtalk_secret,
        }
    }

    with patch("xianyu_hunter.modules.notifier.dingtalk.get_secret", return_value=None):
        hub = NotifierHub(
            channels=["dingtalk"],
            yaml_credentials=yaml_credentials,
            warn_unconfigured=False,
        )

    # mock DingTalkNotifier._do_send 避免真实 HTTP 调用
    mock_response = '{"errcode":0,"errmsg":"ok"}'
    with patch.object(
        DingTalkNotifier, "_do_send", new=AsyncMock(return_value=mock_response)
    ):
        bus = EventBus()
        # NotifierHub.attach 订阅 EVAL_PASSED
        hub.attach(bus, events={EventType.EVAL_PASSED})

        # 启动 EventBus 消费循环
        bus_task = asyncio.create_task(bus.run_forever())
        try:
            # 发布 EVAL_PASSED 事件
            await bus.publish(Event(
                type=EventType.EVAL_PASSED,
                task_id="test_task",
                item_id="test_item",
                payload={"item_title": "测试商品", "score": 75},
            ))
            # 用轮询替代固定 sleep：等待 _do_send 被调用，最长等 2s
            # 比 sleep(0.1) 更健壮，CI 慢机器也不会 flaky
            for _ in range(40):
                if DingTalkNotifier._do_send.called:
                    break
                await asyncio.sleep(0.05)
        finally:
            # 用公开 API 替代私有属性 _running
            bus.stop()
            # run_forever 内部 wait_for(timeout=1.0) 轮询，stop() 后最多 1s 退出
            try:
                await asyncio.wait_for(bus_task, timeout=2.0)
            except asyncio.TimeoutError:
                bus_task.cancel()
                with suppress(asyncio.CancelledError):
                    await bus_task

        # 验证 _do_send 被调用过
        assert DingTalkNotifier._do_send.called, (
            "EVAL_PASSED 事件应触发 DingTalkNotifier._do_send 调用"
        )


def test_worker_eval_passed_publishes_event():
    """Bug #3 单元测试：TaskWorker 评估通过后应通过 EventBus publish_nowait EVAL_PASSED

    旧版 worker 不持有 event_bus，评估通过后只写数据库 events 表，NotifierHub 永远收不到
    """
    from xianyu_hunter.domain.task import Task, TaskConfig, TaskMode
    from xianyu_hunter.modules.worker import TaskWorker

    # 构造最小依赖的 worker
    task = Task(id="t1", name="测试任务", keyword="测试", mode=TaskMode.NOTIFY_ONLY)
    mock_bus = MagicMock()
    worker = TaskWorker(
        task=task,
        collector=MagicMock(),
        dedup=MagicMock(),
        price_strategy=MagicMock(),
        evaluator=MagicMock(),
        config=TaskConfig(),
        repo=None,
        event_bus=mock_bus,
    )
    assert worker.event_bus is mock_bus, "TaskWorker 应保留 event_bus 引用"


@pytest.mark.asyncio
async def test_worker_run_once_triggers_eval_passed_after_rules_pass():
    """I-6 验证：worker.run_once 评估通过后应实际调用 publish_nowait

    构造最小 mock 依赖跑通 run_once 主流程，断言 event_bus.publish_nowait
    被调用且事件类型为 EVAL_PASSED。验证 I-1 修复后事件触发位置正确
    """
    from xianyu_hunter.domain.evaluation import EvalResult, RiskLevel
    from xianyu_hunter.domain.item import ItemDetail, ItemSummary
    from xianyu_hunter.domain.seller import SellerProfile
    from xianyu_hunter.domain.task import Task, TaskConfig, TaskMode
    from xianyu_hunter.modules.price_strategy import PriceVerdict
    from xianyu_hunter.modules.worker import TaskWorker

    # 构造测试商品（标题包含关键词，避免被 task_links 过滤跳过）
    summary = ItemSummary(id="item_1", title="测试商品 iPhone", price=2000.0)
    detail = ItemDetail(id="item_1", title="测试商品 iPhone", price=2000.0, seller_id="seller_1")
    seller = SellerProfile(id="seller_1")

    task = Task(id="t1", name="测试任务", keyword="测试", mode=TaskMode.NOTIFY_ONLY)

    # 构造 mock collector：browser=None 跳过页面复用逻辑
    mock_collector = MagicMock()
    mock_collector.browser = None
    mock_collector.last_session_invalid = False
    mock_collector._browser_lock = MagicMock(has_high_priority_waiting=False)
    mock_collector.search = AsyncMock(return_value=[summary])
    mock_collector.detail = AsyncMock(return_value=detail)
    mock_collector.seller_profile = AsyncMock(return_value=seller)
    mock_collector.seller_profile_fallback = AsyncMock(return_value=seller)

    mock_dedup = MagicMock()
    # filter_new 与 worker.py 同步调用对齐：worker._dedup_and_limit 中
    # `new_items = self.dedup.filter_new(items)` 不带 await，
    # 若用 AsyncMock 会返回 coroutine，`len(coroutine)` 抛 TypeError
    mock_dedup.filter_new = MagicMock(return_value=[summary])
    mock_dedup.save = MagicMock()

    mock_price = MagicMock()
    mock_price.check = MagicMock(return_value=PriceVerdict(pass_=True, reasons=[]))

    eval_result = EvalResult(score=75, risk_level=RiskLevel.LOW, data_quality="full")
    mock_evaluator = MagicMock()
    mock_evaluator.evaluate = MagicMock(return_value=eval_result)

    mock_bus = MagicMock()
    mock_repo = MagicMock()

    worker = TaskWorker(
        task=task,
        collector=mock_collector,
        dedup=mock_dedup,
        price_strategy=mock_price,
        evaluator=mock_evaluator,
        config=TaskConfig(),
        repo=mock_repo,
        event_bus=mock_bus,
    )

    # mock 全局配置：禁用 AI 评估，避免触发 LLM 调用
    with patch("xianyu_hunter.modules.worker.get_settings") as mock_settings, \
         patch("xianyu_hunter.modules.worker.get_config") as mock_get_config, \
         patch(
             "xianyu_hunter.web.services.cookie_runtime_sync.inject_cookie_store_to_browser",
             new=AsyncMock(),
         ):
        mock_settings.return_value.ai_enabled = False
        mock_cfg = MagicMock()
        mock_cfg.eval.pass_score = 60
        mock_cfg.eval.ai_auto_eval = False
        mock_cfg.eval.ai_auto_deep_analyze = False
        mock_get_config.return_value = mock_cfg

        await worker.run_once()

    # 验证 publish_nowait 被调用过
    assert mock_bus.publish_nowait.called, (
        "评估通过后应调用 event_bus.publish_nowait 触发 EVAL_PASSED"
    )
    # 验证事件类型为 EVAL_PASSED
    call_args = mock_bus.publish_nowait.call_args
    event = call_args.args[0]
    assert event.type == EventType.EVAL_PASSED, (
        f"事件类型应为 EVAL_PASSED，实际: {event.type}"
    )
    assert event.task_id == "t1"
    assert event.item_id == "item_1"
    assert event.payload["score"] == 75


@pytest.mark.asyncio
async def test_worker_run_once_no_eval_passed_when_score_below_threshold():
    """I-6 验证：评估分数低于 pass_score 时不应触发 EVAL_PASSED

    防止低分商品误触发通知
    """
    from xianyu_hunter.domain.evaluation import EvalResult, RiskLevel
    from xianyu_hunter.domain.item import ItemDetail, ItemSummary
    from xianyu_hunter.domain.seller import SellerProfile
    from xianyu_hunter.domain.task import Task, TaskConfig, TaskMode
    from xianyu_hunter.modules.price_strategy import PriceVerdict
    from xianyu_hunter.modules.worker import TaskWorker

    summary = ItemSummary(id="item_2", title="测试商品 iPhone", price=2000.0)
    detail = ItemDetail(id="item_2", title="测试商品 iPhone", price=2000.0, seller_id="seller_2")
    seller = SellerProfile(id="seller_2")

    task = Task(id="t2", name="测试任务", keyword="测试", mode=TaskMode.NOTIFY_ONLY)

    mock_collector = MagicMock()
    mock_collector.browser = None
    mock_collector.last_session_invalid = False
    mock_collector._browser_lock = MagicMock(has_high_priority_waiting=False)
    mock_collector.search = AsyncMock(return_value=[summary])
    mock_collector.detail = AsyncMock(return_value=detail)
    mock_collector.seller_profile = AsyncMock(return_value=seller)
    mock_collector.seller_profile_fallback = AsyncMock(return_value=seller)

    mock_dedup = MagicMock()
    # filter_new 与 worker.py 同步调用对齐：worker._dedup_and_limit 中
    # `new_items = self.dedup.filter_new(items)` 不带 await，
    # 若用 AsyncMock 会返回 coroutine，`len(coroutine)` 抛 TypeError
    mock_dedup.filter_new = MagicMock(return_value=[summary])
    mock_dedup.save = MagicMock()

    mock_price = MagicMock()
    mock_price.check = MagicMock(return_value=PriceVerdict(pass_=True, reasons=[]))

    # 评估分 30，低于 pass_score 60，should_pass 返回 False
    eval_result = EvalResult(score=30, risk_level=RiskLevel.HIGH, data_quality="full")
    mock_evaluator = MagicMock()
    mock_evaluator.evaluate = MagicMock(return_value=eval_result)

    mock_bus = MagicMock()
    mock_repo = MagicMock()

    worker = TaskWorker(
        task=task,
        collector=mock_collector,
        dedup=mock_dedup,
        price_strategy=mock_price,
        evaluator=mock_evaluator,
        config=TaskConfig(),
        repo=mock_repo,
        event_bus=mock_bus,
    )

    with patch("xianyu_hunter.modules.worker.get_settings") as mock_settings, \
         patch("xianyu_hunter.modules.worker.get_config") as mock_get_config, \
         patch(
             "xianyu_hunter.web.services.cookie_runtime_sync.inject_cookie_store_to_browser",
             new=AsyncMock(),
         ):
        mock_settings.return_value.ai_enabled = False
        mock_cfg = MagicMock()
        mock_cfg.eval.pass_score = 60
        mock_cfg.eval.ai_auto_eval = False
        mock_cfg.eval.ai_auto_deep_analyze = False
        mock_get_config.return_value = mock_cfg

        await worker.run_once()

    # 验证 publish_nowait 未被调用
    assert not mock_bus.publish_nowait.called, (
        "评估分数低于 pass_score 时不应触发 EVAL_PASSED 事件"
    )
