"""ntfy 通知渠道单元测试

ntfy：免费跨平台推送（Android/iOS/Web/CLI），填补 Bark 仅 iOS 的缺口。
公共实例 https://ntfy.sh 直接可用，也可自托管。

测试覆盖：
- 注册表包含 ntfy
- 工厂创建 NtfyNotifier
- is_configured 行为
- 推送成功（payload 字段正确性）
- 推送带 token 时携带 Authorization header
- 未配置 topic 时失败
- 4xx 响应触发重试后失败
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xianyu_hunter.domain.events import Event, EventType
from xianyu_hunter.modules.notifier import NotifierRegistry, create_notifier
from xianyu_hunter.modules.notifier.ntfy import DEFAULT_SERVER, NtfyNotifier


# ============== 工具：构造 mock aiohttp 响应 ==============

def make_response(status: int, text: str = "ok") -> MagicMock:
    """构造 aiohttp 响应 mock"""
    resp = MagicMock()
    resp.status = status
    resp.text = AsyncMock(return_value=text)
    resp.request_info = MagicMock()
    resp.history = ()
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


def make_session(responses: list[MagicMock]) -> MagicMock:
    """构造 ClientSession mock"""
    session = MagicMock()
    queue = list(responses)

    def _post(*args, **kwargs):
        if not queue:
            raise AssertionError("post() 调用次数超出预期")
        return queue.pop(0)

    session.post = MagicMock(side_effect=_post)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


def make_eval_event() -> Event:
    """构造评估通过事件"""
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


# ============== 注册表测试 ==============

def test_registry_includes_ntfy() -> None:
    """注册表应包含 ntfy"""
    registry = NotifierRegistry.default()
    channels = registry.available()
    assert "ntfy" in channels


def test_create_ntfy_notifier() -> None:
    """工厂能创建 NtfyNotifier"""
    notifier = create_notifier("ntfy", topic="my-topic", token="tk_xxx")
    assert isinstance(notifier, NtfyNotifier)
    assert notifier.name == "ntfy"


# ============== is_configured 测试 ==============

def test_is_configured_with_topic() -> None:
    """配置了 topic 时 is_configured 为 True"""
    notifier = NtfyNotifier(topic="my-topic")
    assert notifier.is_configured is True


def test_is_configured_without_topic() -> None:
    """未配置 topic 时 is_configured 为 False"""
    # 通过显式传空字符串覆盖 keyring（避免依赖测试环境 keyring 状态）
    notifier = NtfyNotifier(topic="", server="", token="")
    assert notifier.is_configured is False


def test_default_server_used_when_not_provided() -> None:
    """未传 server 时使用默认 https://ntfy.sh"""
    notifier = NtfyNotifier(topic="t", server="")
    assert notifier.server == DEFAULT_SERVER


def test_custom_server_strips_trailing_slash() -> None:
    """自托管 server 末尾斜杠应被去除（避免拼出双斜杠 URL）"""
    notifier = NtfyNotifier(topic="t", server="https://ntfy.example.com/")
    assert notifier.server == "https://ntfy.example.com"


# ============== 推送成功测试 ==============

@pytest.mark.asyncio
async def test_ntfy_send_success() -> None:
    """ntfy 推送成功（公共实例无 token）"""
    notifier = NtfyNotifier(topic="my-topic")
    resp = make_response(200, '{"event_id":"abc123"}')
    session = make_session([resp])

    with patch("aiohttp.ClientSession", return_value=session):
        result = await notifier.send(make_eval_event())

    assert result.success is True
    assert result.channel == "ntfy"
    # 验证请求 URL 和 payload
    args, kwargs = session.post.call_args
    assert args[0] == "https://ntfy.sh"
    payload = kwargs["json"]
    assert payload["topic"] == "my-topic"
    # title 含商品标题，message 是 markdown body（含卖家/评分等）
    assert "iPhone 13" in payload["title"]
    assert "测试卖家" in payload["message"]
    assert "85" in payload["message"]
    # 重要事件使用 high 优先级（让设备有响铃提醒）
    assert payload["priority"] == 4
    assert payload["markdown"] is True
    # 未配置 token 时不应带 Authorization
    assert "Authorization" not in kwargs["headers"]


@pytest.mark.asyncio
async def test_ntfy_send_with_token() -> None:
    """配置 token 时应携带 Authorization: Bearer 头"""
    notifier = NtfyNotifier(topic="my-topic", token="tk_abc123")
    resp = make_response(200, '{"event_id":"abc"}')
    session = make_session([resp])

    with patch("aiohttp.ClientSession", return_value=session):
        result = await notifier.send(make_eval_event())

    assert result.success is True
    _, kwargs = session.post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer tk_abc123"


@pytest.mark.asyncio
async def test_ntfy_send_with_custom_server() -> None:
    """自托管 server 时 URL 应指向自定义地址"""
    notifier = NtfyNotifier(
        topic="my-topic",
        server="https://ntfy.my-home-lab.com",
    )
    resp = make_response(200, '{"event_id":"abc"}')
    session = make_session([resp])

    with patch("aiohttp.ClientSession", return_value=session):
        await notifier.send(make_eval_event())

    args, _ = session.post.call_args
    assert args[0] == "https://ntfy.my-home-lab.com"


# ============== 失败场景测试 ==============

@pytest.mark.asyncio
async def test_ntfy_missing_topic_raises() -> None:
    """未配置 topic 应报错"""
    notifier = NtfyNotifier(topic="", server="", token="")
    result = await notifier.send(make_eval_event())
    assert result.success is False
    assert "topic" in result.error


@pytest.mark.asyncio
async def test_ntfy_4xx_response_fails() -> None:
    """4xx 响应应触发重试后失败（默认重试 3 次）"""
    notifier = NtfyNotifier(topic="my-topic")
    # 模拟 3 次 4xx 响应（BaseNotifier 默认重试 3 次）
    responses = [make_response(400, "Bad Request") for _ in range(3)]
    session = make_session(responses)

    with patch("aiohttp.ClientSession", return_value=session):
        result = await notifier.send(make_eval_event())

    assert result.success is False
    assert result.attempts == 3


@pytest.mark.asyncio
async def test_ntfy_5xx_retries_then_succeeds() -> None:
    """5xx 响应应触发重试，第 2 次成功"""
    notifier = NtfyNotifier(topic="my-topic")
    fail_resp = make_response(503, "Service Unavailable")
    ok_resp = make_response(200, '{"event_id":"abc"}')
    session = make_session([fail_resp, ok_resp])

    with patch("aiohttp.ClientSession", return_value=session):
        result = await notifier.send(make_eval_event())

    assert result.success is True
    assert result.attempts == 2
