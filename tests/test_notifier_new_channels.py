"""P1-3 通知渠道扩展单元测试

测试新增的 4 个渠道：Telegram / 企业微信 / 钉钉 / Webhook
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xianyu_hunter.domain.events import Event, EventType
from xianyu_hunter.modules.notifier import NotifierRegistry, create_notifier
from xianyu_hunter.modules.notifier.dingtalk import DingTalkNotifier
from xianyu_hunter.modules.notifier.telegram import TelegramNotifier
from xianyu_hunter.modules.notifier.wecom import WeComNotifier
from xianyu_hunter.modules.notifier.webhook import WebhookNotifier


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
    """构造 ClientSession mock

    session.post 是 MagicMock，调用后返回支持 __aenter__/__aexit__ 的 mock 响应。
    """
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

def test_registry_includes_new_channels() -> None:
    """注册表应包含 7 个渠道（原 3 + 新 4）"""
    registry = NotifierRegistry.default()
    channels = registry.available()
    assert "telegram" in channels
    assert "wecom" in channels
    assert "dingtalk" in channels
    assert "webhook" in channels
    assert len(channels) == 7


def test_create_telegram_notifier() -> None:
    """工厂能创建 Telegram notifier"""
    notifier = create_notifier("telegram", bot_token="test", chat_id="123")
    assert isinstance(notifier, TelegramNotifier)
    assert notifier.name == "telegram"


def test_create_wecom_notifier() -> None:
    """工厂能创建企业微信 notifier"""
    notifier = create_notifier("wecom", webhook_url="https://example.com/webhook")
    assert isinstance(notifier, WeComNotifier)
    assert notifier.name == "wecom"


def test_create_dingtalk_notifier() -> None:
    """工厂能创建钉钉 notifier"""
    notifier = create_notifier("dingtalk", webhook_url="https://oapi.dingtalk.com/robot/send", secret="SEC")
    assert isinstance(notifier, DingTalkNotifier)
    assert notifier.name == "dingtalk"


def test_create_webhook_notifier() -> None:
    """工厂能创建 Webhook notifier"""
    notifier = create_notifier("webhook", webhook_url="https://example.com/hook", token="abc")
    assert isinstance(notifier, WebhookNotifier)
    assert notifier.name == "webhook"


# ============== Telegram 推送测试 ==============

@pytest.mark.asyncio
async def test_telegram_send_success() -> None:
    """Telegram 推送成功"""
    notifier = TelegramNotifier(bot_token="123:ABC", chat_id="456")
    resp = make_response(200, '{"ok":true}')
    session = make_session([resp])

    with patch("aiohttp.ClientSession", return_value=session):
        result = await notifier.send(make_eval_event())

    assert result.success is True
    assert result.channel == "telegram"
    # 验证请求参数
    session.post.assert_called_once()
    args, kwargs = session.post.call_args
    assert "123:ABC" in args[0]  # URL 含 bot token
    assert kwargs["json"]["chat_id"] == "456"
    assert "iPhone 13" in kwargs["json"]["text"]


@pytest.mark.asyncio
async def test_telegram_missing_token_raises() -> None:
    """Telegram 未配置 token 应报错"""
    notifier = TelegramNotifier(bot_token="", chat_id="456")
    result = await notifier.send(make_eval_event())
    assert result.success is False
    assert "bot_token" in result.error


@pytest.mark.asyncio
async def test_telegram_missing_chat_id_raises() -> None:
    """Telegram 未配置 chat_id 应报错"""
    notifier = TelegramNotifier(bot_token="123:ABC", chat_id="")
    result = await notifier.send(make_eval_event())
    assert result.success is False
    assert "chat_id" in result.error


# ============== 企业微信推送测试 ==============

@pytest.mark.asyncio
async def test_wecom_send_success() -> None:
    """企业微信推送成功"""
    notifier = WeComNotifier(webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send")
    resp = make_response(200, '{"errcode":0}')
    session = make_session([resp])

    with patch("aiohttp.ClientSession", return_value=session):
        result = await notifier.send(make_eval_event())

    assert result.success is True
    assert result.channel == "wecom"
    args, kwargs = session.post.call_args
    # markdown 格式：标题加粗，body 保持 markdown 语法
    assert kwargs["json"]["msgtype"] == "markdown"
    assert "iPhone 13" in kwargs["json"]["markdown"]["content"]


@pytest.mark.asyncio
async def test_wecom_missing_url_raises() -> None:
    """企业微信未配置 webhook 应报错"""
    notifier = WeComNotifier(webhook_url="")
    result = await notifier.send(make_eval_event())
    assert result.success is False
    assert "webhook" in result.error


# ============== 钉钉推送测试 ==============

@pytest.mark.asyncio
async def test_dingtalk_send_success() -> None:
    """钉钉推送成功（含签名）"""
    notifier = DingTalkNotifier(
        webhook_url="https://oapi.dingtalk.com/robot/send?access_token=abc",
        secret="SECtest123",
    )
    resp = make_response(200, '{"errcode":0}')
    session = make_session([resp])

    with patch("aiohttp.ClientSession", return_value=session):
        result = await notifier.send(make_eval_event())

    assert result.success is True
    assert result.channel == "dingtalk"
    args, kwargs = session.post.call_args
    # URL 应含签名参数
    assert "timestamp=" in args[0]
    assert "sign=" in args[0]
    assert kwargs["json"]["msgtype"] == "text"


@pytest.mark.asyncio
async def test_dingtalk_send_without_secret() -> None:
    """钉钉无 secret 时也能推送（不签名）"""
    notifier = DingTalkNotifier(
        webhook_url="https://oapi.dingtalk.com/robot/send?access_token=abc",
        secret="",
    )
    resp = make_response(200, '{"errcode":0}')
    session = make_session([resp])

    with patch("aiohttp.ClientSession", return_value=session):
        result = await notifier.send(make_eval_event())

    assert result.success is True
    args, _ = session.post.call_args
    # 无签名时 URL 不含 timestamp/sign
    assert "timestamp=" not in args[0]


def test_dingtalk_sign_algorithm() -> None:
    """钉钉签名算法正确性"""
    notifier = DingTalkNotifier(
        webhook_url="https://example.com",
        secret="SECtest",
    )
    timestamp = 1718700000000
    sign = notifier._sign(timestamp)
    # 签名应为 URL 编码的 base64 字符串
    assert isinstance(sign, str)
    assert len(sign) > 0
    # 同一输入应产生相同签名
    assert notifier._sign(timestamp) == sign


@pytest.mark.asyncio
async def test_dingtalk_missing_url_raises() -> None:
    """钉钉未配置 webhook 应报错"""
    notifier = DingTalkNotifier(webhook_url="")
    result = await notifier.send(make_eval_event())
    assert result.success is False
    assert "webhook" in result.error


# ============== Webhook 推送测试 ==============

@pytest.mark.asyncio
async def test_webhook_send_success() -> None:
    """自定义 Webhook 推送成功"""
    notifier = WebhookNotifier(webhook_url="https://example.com/hook", token="bearer123")
    resp = make_response(200, '{"ok":true}')
    session = make_session([resp])

    with patch("aiohttp.ClientSession", return_value=session):
        result = await notifier.send(make_eval_event())

    assert result.success is True
    assert result.channel == "webhook"
    args, kwargs = session.post.call_args
    assert args[0] == "https://example.com/hook"
    # 应含 Bearer token
    assert kwargs["headers"]["Authorization"] == "Bearer bearer123"
    # payload 应含 title/body/event/timestamp
    payload = kwargs["json"]
    assert "title" in payload
    assert "body" in payload
    assert "event" in payload
    assert "timestamp" in payload
    assert "iPhone 13" in payload["title"]


@pytest.mark.asyncio
async def test_webhook_send_without_token() -> None:
    """Webhook 无 token 时不带 Authorization 头"""
    notifier = WebhookNotifier(webhook_url="https://example.com/hook", token="")
    resp = make_response(200, "ok")
    session = make_session([resp])

    with patch("aiohttp.ClientSession", return_value=session):
        result = await notifier.send(make_eval_event())

    assert result.success is True
    _, kwargs = session.post.call_args
    assert "Authorization" not in kwargs["headers"]


@pytest.mark.asyncio
async def test_webhook_missing_url_raises() -> None:
    """Webhook 未配置 URL 应报错"""
    notifier = WebhookNotifier(webhook_url="")
    result = await notifier.send(make_eval_event())
    assert result.success is False
    assert "URL" in result.error


@pytest.mark.asyncio
async def test_webhook_4xx_response_fails() -> None:
    """Webhook 返回 4xx 应触发重试后失败"""
    notifier = WebhookNotifier(webhook_url="https://example.com/hook", token="")
    # 模拟 3 次 4xx 响应（重试 3 次）
    responses = [make_response(400, "Bad Request") for _ in range(3)]
    session = make_session(responses)

    with patch("aiohttp.ClientSession", return_value=session):
        result = await notifier.send(make_eval_event())

    assert result.success is False
    assert result.attempts == 3
