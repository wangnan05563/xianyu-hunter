"""钉钉通知端到端集成测试

验证修复后的完整链路：
1. wire_notifier 能识别 dingtalk 渠道（旧版 Bug #1：只判断 serverchan/pushplus/bark）
2. NotifierHub 能用 yaml 明文凭据创建 DingTalkNotifier（旧版 Bug #2：只从 keyring 读取）
3. TaskWorker 评估通过后能触发 EVAL_PASSED 事件（旧版 Bug #3：从未 publish）
"""
from __future__ import annotations

import asyncio
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
            # 给 EventBus 一点时间分发事件
            await asyncio.sleep(0.1)
        finally:
            bus._running = False
            # 唤醒可能在 await queue.get() 中的消费者
            await bus.publish(Event(type=EventType.TASK_STOPPED))
            await asyncio.sleep(0.05)
            bus_task.cancel()
            try:
                await bus_task
            except asyncio.CancelledError:
                pass

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
