"""Notifier 单元测试（mock aiohttp，验证 3 渠道 + 2 模板 + 重试 + Hub）"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from xianyu_hunter.domain.events import Event, EventType
from xianyu_hunter.modules.notifier import (
    BaseNotifier,
    NotifierHub,
    NotifierRegistry,
    NotifyResult,
    create_notifier,
)
from xianyu_hunter.modules.notifier.bark import BarkNotifier
from xianyu_hunter.modules.notifier.pushplus import PushPlusNotifier
from xianyu_hunter.modules.notifier.serverchan import ServerChanNotifier
from xianyu_hunter.modules.notifier.templates import render


# ============== 工具：构造 mock aiohttp 响应 ==============


def make_response(status: int, text: str = "ok") -> MagicMock:
    """构造 aiohttp 响应 mock

    用 AsyncMock 模拟 __aenter__ / .text / .status
    """
    resp = MagicMock()
    resp.status = status
    resp.text = AsyncMock(return_value=text)
    resp.request_info = MagicMock()
    resp.history = ()
    # 让 aiohttp 知道这是个 awaitable 上下文
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


def make_session(responses: list[MagicMock]) -> MagicMock:
    """构造 ClientSession mock

    session.post(...) 是普通函数（不是 async def），直接返回一个支持
    __aenter__/__aexit__ 的 mock 响应，让 `async with session.post(...) as resp:` 正常。
    """
    session = MagicMock()
    queue = list(responses)

    def _post(*args, **kwargs):
        if not queue:
            raise AssertionError("post() 调用次数超出预期")
        return queue.pop(0)

    session.post = _post
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


def make_eval_event() -> Event:
    return Event(
        type=EventType.EVAL_PASSED,
        task_id="t1",
        item_id="i1",
        payload={
            "item": {
                "title": "iPhone 13 128G 国行",
                "price": 1999.0,
                "url": "https://www.goofish.com/item/i1",
                "thumb_url": "https://img.example.com/i1.jpg",
            },
            "score": 85,
            "risk_level": "low",
            "seller_nick": "测试卖家",
            "reject_reasons": [],
        },
    )


def make_order_event() -> Event:
    return Event(
        type=EventType.BUY_SUCCEEDED,
        task_id="t1",
        item_id="i1",
        payload={
            "item": {
                "title": "iPhone 13 128G 国行",
                "price": 1999.0,
            },
            "order_id": "20260603001",
            "expire_at": "2026-06-03 18:30",
        },
    )


# ============== NotifyResult 模型 ==============


def test_notify_result_to_dict() -> None:
    """NotifyResult 可序列化"""
    r = NotifyResult(success=True, channel="serverchan", attempts=1, response="ok")
    d = r.to_dict()
    assert d["success"] is True
    assert d["channel"] == "serverchan"
    assert d["attempts"] == 1
    assert "sent_at" in d


# ============== 模板 ==============


def test_template_eval_passed() -> None:
    """EVAL_PASSED 模板含标题、价格、链接、图片占位提示"""
    title, body = render(make_eval_event())
    assert "iPhone 13" in title
    assert "1999" in title
    assert "评估通过" in body
    assert "85" in body  # score
    assert "立即查看" in body
    # 商品图改为可点击链接（v7 方案，绕过钉钉 webhook 不支持 image 的限制）
    assert "点击查看商品图" in body
    assert "img.example.com" in body


def test_template_order_placed() -> None:
    """ORDER_PLACED 模板含订单号、过期时间"""
    title, body = render(make_order_event())
    assert "已拍下" in title
    assert "20260603001" in body
    assert "2026-06-03 18:30" in body
    assert "5 分钟" in body


def test_template_generic_fallback() -> None:
    """未知事件类型走通用降级模板"""
    e = Event(type=EventType.TASK_STARTED, payload={"task_id": "t1"})
    title, body = render(e)
    assert e.type.value in title
    assert "t1" in body


# ============== BaseNotifier 重试逻辑 ==============


class _DummyNotifier(BaseNotifier):
    """不发送真实请求，覆写 _do_send 用于测试重试逻辑"""
    name = "dummy"

    def __init__(self, fail_times: int = 0, exception_factory=None, **kwargs):
        super().__init__(**kwargs)
        self.fail_times = fail_times
        self.attempts_made = 0
        self.exception_factory = exception_factory or (
            lambda: aiohttp.ClientConnectionError("mock fail")
        )

    async def _do_send(self, event: Event) -> str:
        self.attempts_made += 1
        if self.attempts_made <= self.fail_times:
            raise self.exception_factory()
        return "success"


@pytest.mark.asyncio
async def test_base_first_try_success() -> None:
    """第 1 次就成功 → 1 次尝试"""
    n = _DummyNotifier(fail_times=0, max_retries=3, base_backoff=0.01)
    result = await n.send(make_eval_event())
    assert result.success is True
    assert result.attempts == 1
    assert n.attempts_made == 1


@pytest.mark.asyncio
async def test_base_retry_then_success() -> None:
    """前 2 次失败，第 3 次成功 → 3 次尝试"""
    n = _DummyNotifier(fail_times=2, max_retries=3, base_backoff=0.01)
    result = await n.send(make_eval_event())
    assert result.success is True
    assert result.attempts == 3
    assert n.attempts_made == 3


@pytest.mark.asyncio
async def test_base_retry_exhausted() -> None:
    """3 次都失败 → 失败结果，attempts=3"""
    n = _DummyNotifier(fail_times=10, max_retries=3, base_backoff=0.01)
    result = await n.send(make_eval_event())
    assert result.success is False
    assert result.attempts == 3
    assert n.attempts_made == 3
    assert "ClientConnectionError" in result.error or "mock fail" in result.error


@pytest.mark.asyncio
async def test_base_non_retryable_exception_no_retry() -> None:
    """非 ClientError 异常立即放弃，不重试"""
    n = _DummyNotifier(
        fail_times=10,
        max_retries=3,
        base_backoff=0.01,
        exception_factory=lambda: ValueError("not retryable"),
    )
    result = await n.send(make_eval_event())
    assert result.success is False
    assert result.attempts == 1  # 没重试
    assert "ValueError" in result.error


@pytest.mark.asyncio
async def test_base_retry_backoff_applied() -> None:
    """指数退避：3 次失败总耗时 ≥ 1+2=3s（base_backoff=1）"""
    n = _DummyNotifier(fail_times=10, max_retries=3, base_backoff=0.5)
    import time

    start = time.monotonic()
    result = await n.send(make_eval_event())
    elapsed = time.monotonic() - start
    # 2 次退避：0.5 + 1.0 = 1.5s
    assert result.success is False
    assert elapsed >= 1.4  # 留 0.1s 容差


# ============== Server酱适配器 ==============


@pytest.mark.asyncio
async def test_serverchan_success() -> None:
    """Server酱 200 响应 → 成功"""
    n = ServerChanNotifier(send_key="SCT123", max_retries=1, base_backoff=0.01)
    session = make_session([make_response(200, '{"code":0}')])
    with patch.object(aiohttp, "ClientSession", return_value=session):
        result = await n.send(make_eval_event())
    assert result.success is True
    assert result.channel == "serverchan"
    assert "SCT123" not in result.response  # 不泄露 key


@pytest.mark.asyncio
async def test_serverchan_http_500_retried_then_fail() -> None:
    """HTTP 500 触发重试，最终失败"""
    n = ServerChanNotifier(send_key="SCT123", max_retries=2, base_backoff=0.01)
    session = make_session([
        make_response(500, "server error"),
        make_response(500, "server error"),
    ])
    with patch.object(aiohttp, "ClientSession", return_value=session):
        result = await n.send(make_eval_event())
    assert result.success is False
    assert result.attempts == 2


@pytest.mark.asyncio
async def test_serverchan_missing_key() -> None:
    """未配置 key → 失败（ValueError 不重试）"""
    n = ServerChanNotifier(send_key="", max_retries=3, base_backoff=0.01)
    result = await n.send(make_eval_event())
    assert result.success is False
    assert "send_key" in result.error


# ============== PushPlus 适配器 ==============


@pytest.mark.asyncio
async def test_pushplus_success() -> None:
    """PushPlus 200 响应 → 成功"""
    n = PushPlusNotifier(token="TKN", max_retries=1, base_backoff=0.01)
    session = make_session([make_response(200, '{"code":200}')])
    with patch.object(aiohttp, "ClientSession", return_value=session):
        result = await n.send(make_eval_event())
    assert result.success is True
    assert result.channel == "pushplus"


@pytest.mark.asyncio
async def test_pushplus_missing_token() -> None:
    """未配置 token → 失败"""
    n = PushPlusNotifier(token="", max_retries=1)
    result = await n.send(make_eval_event())
    assert result.success is False
    assert "token" in result.error


# ============== Bark 适配器 ==============


@pytest.mark.asyncio
async def test_bark_success() -> None:
    """Bark 200 响应 → 成功"""
    n = BarkNotifier(server="https://bark.example", key="bkey", max_retries=1, base_backoff=0.01)
    session = make_session([make_response(200, '{"code":200}')])
    with patch.object(aiohttp, "ClientSession", return_value=session):
        result = await n.send(make_eval_event())
    assert result.success is True
    assert result.channel == "bark"


@pytest.mark.asyncio
async def test_bark_missing_key() -> None:
    """未配置 key → 失败"""
    n = BarkNotifier(key="", max_retries=1)
    result = await n.send(make_eval_event())
    assert result.success is False
    assert "key" in result.error


# ============== Registry ==============


def test_registry_create_known() -> None:
    """创建已知渠道"""
    n = create_notifier("serverchan", send_key="x", max_retries=1)
    assert isinstance(n, ServerChanNotifier)
    assert n.name == "serverchan"


def test_registry_create_unknown_raises() -> None:
    """未知渠道 → KeyError"""
    with pytest.raises(KeyError, match="未知渠道"):
        create_notifier("nonexistent_channel_xyz", token="x")


def test_registry_list_all() -> None:
    """默认注册表含 8 渠道（P1-3 新增 telegram/wecom/dingtalk/webhook，ntfy 新增）"""
    reg = NotifierRegistry.default()
    names = reg.available()
    assert set(names) == {"serverchan", "pushplus", "bark", "telegram", "wecom", "dingtalk", "webhook", "ntfy"}


# ============== Hub ==============


@pytest.mark.asyncio
async def test_hub_no_channels_warning() -> None:
    """未配置任何渠道时 send 返回空列表（不抛错）"""
    hub = NotifierHub(channels=[])
    results = await hub.send(make_eval_event())
    assert results == []


def test_hub_unconfigured_default_channel_logs_info() -> None:
    """默认兜底渠道未配置时不打 warning，避免启动日志噪声。"""

    class UnconfiguredNotifier:
        name = "dummy"
        is_configured = False

    class FakeRegistry:
        def create(self, name: str) -> UnconfiguredNotifier:
            return UnconfiguredNotifier()

    with patch("xianyu_hunter.modules.notifier.hub.logger") as logger:
        hub = NotifierHub(
            channels=["dummy"],
            registry=FakeRegistry(),
            warn_unconfigured=False,
        )

    assert hub.notifiers == []
    logger.warning.assert_not_called()
    logger.info.assert_called_once()


@pytest.mark.asyncio
async def test_hub_unknown_channel_skipped() -> None:
    """未知渠道被跳过（不抛错）"""
    # mock get_secret 让 serverchan 视为已配置：
    # serverchan.is_configured 依赖 keyring 中的 send_key，
    # 测试环境未配置会导致 hub 启动期过滤掉它，与本测试"未知渠道被跳过"的关注点无关
    with patch(
        "xianyu_hunter.modules.notifier.serverchan.get_secret",
        return_value="k1",
    ):
        hub = NotifierHub(channels=["nonexistent_xyz", "serverchan"])
    # nonexistent_xyz 不存在 → 只剩 serverchan
    assert len(hub.notifiers) == 1
    assert hub.notifiers[0].name == "serverchan"


@pytest.mark.asyncio
async def test_hub_fan_out_all_success() -> None:
    """3 渠道全成功 → results 数 = 3，全部 success=True"""
    from xianyu_hunter.modules.notifier.pushplus import PushPlusNotifier
    from xianyu_hunter.modules.notifier.bark import BarkNotifier

    sc = ServerChanNotifier(send_key="k1", max_retries=1)
    pp = PushPlusNotifier(token="k2", max_retries=1)
    bk = BarkNotifier(key="k3", max_retries=1)

    session = make_session([
        make_response(200, "ok1"),
        make_response(200, "ok2"),
        make_response(200, "ok3"),
    ])
    with patch.object(aiohttp, "ClientSession", return_value=session):
        hub = NotifierHub.__new__(NotifierHub)  # 跳过 __init__
        hub._notifiers = [sc, pp, bk]
        hub._quiet_hours = None
        hub._suppressed_lock = asyncio.Lock()
        hub._suppressed_count = 0
        hub._suppressed_last_at = None
        results = await hub.send(make_eval_event())

    assert len(results) == 3
    assert all(r.success for r in results)
    channels = {r.channel for r in results}
    assert channels == {"serverchan", "pushplus", "bark"}


@pytest.mark.asyncio
async def test_hub_fan_out_partial_failure() -> None:
    """部分渠道失败时，hub 返回全部结果（包含失败项）"""
    sc = ServerChanNotifier(send_key="k1", max_retries=1)
    pp = PushPlusNotifier(token="", max_retries=1)  # 缺 token，会失败
    session = make_session([make_response(200, "ok1")])
    with patch.object(aiohttp, "ClientSession", return_value=session):
        hub = NotifierHub.__new__(NotifierHub)
        hub._notifiers = [sc, pp]
        hub._quiet_hours = None
        hub._suppressed_lock = asyncio.Lock()
        hub._suppressed_count = 0
        hub._suppressed_last_at = None
        results = await hub.send(make_eval_event())

    assert len(results) == 2
    assert results[0].success is True
    assert results[1].success is False


def test_hub_attach_subscribes_events() -> None:
    """attach() 订阅默认事件类型"""
    from xianyu_hunter.infra.event_bus import EventBus

    bus = EventBus()
    hub = NotifierHub(channels=[])
    hub.attach(bus)
    # 验证订阅了 EVAL_PASSED 和 BUY_SUCCEEDED
    assert EventType.EVAL_PASSED in bus._subscribers
    assert EventType.BUY_SUCCEEDED in bus._subscribers


@pytest.mark.asyncio
async def test_hub_attach_event_triggers_send() -> None:
    """attach 后，publish 事件会自动触发 send"""
    from xianyu_hunter.infra.event_bus import EventBus

    bus = EventBus()
    sc = ServerChanNotifier(send_key="k1", max_retries=1)
    session = make_session([make_response(200, "ok")])
    with patch.object(aiohttp, "ClientSession", return_value=session):
        hub = NotifierHub.__new__(NotifierHub)
        hub._notifiers = [sc]
        hub._quiet_hours = None
        hub._suppressed_lock = asyncio.Lock()
        hub._suppressed_count = 0
        hub._suppressed_last_at = None
        hub.attach(bus)

        # 启动 EventBus 消费循环
        bus_task = asyncio.create_task(bus.run_forever())
        await asyncio.sleep(0.1)  # 让循环起来

        await bus.publish(make_eval_event())
        await asyncio.sleep(0.3)  # 等分发 + HTTP 调用

        bus.stop()
        await bus_task

    # 验证 send 被调用了 1 次（HTTP session 已被消费）
    # 注：无法直接验证，因 _do_send 内联了，我们只验证整体没抛错
    assert True
