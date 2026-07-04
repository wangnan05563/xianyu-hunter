"""P1-3 通知渠道扩展单元测试

测试新增的 4 个渠道：Telegram / 企业微信 / 钉钉 / Webhook
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xianyu_hunter.domain.events import Event, EventType
from xianyu_hunter.modules.notifier import NotifierRegistry, create_notifier
from xianyu_hunter.modules.notifier.dingtalk import DingTalkNotifier, _to_dingtalk_markdown
from xianyu_hunter.modules.notifier.telegram import TelegramNotifier
from xianyu_hunter.modules.notifier.templates import _translate_reject_reason
from xianyu_hunter.modules.notifier.wecom import WeComNotifier, _to_wecom_markdown
from xianyu_hunter.modules.notifier.webhook import WebhookNotifier


# ============== 工具：构造 mock aiohttp 响应 ==============

def make_response(status: int, text: str = "ok", body: bytes | None = None) -> MagicMock:
    """构造 aiohttp 响应 mock

    - text：text() 返回的字符串（默认 "ok"）
    - body：read() 返回的字节（用于图片下载等场景）
      若同时提供 body，text() 返回 body 的字符串形式（兜底）
    """
    resp = MagicMock()
    resp.status = status
    if body is not None:
        resp.read = AsyncMock(return_value=body)
        # 部分代码可能用 text()，兜底返回 body 字符串
        resp.text = AsyncMock(return_value=body.decode("utf-8", errors="replace"))
    else:
        resp.text = AsyncMock(return_value=text)
        resp.read = AsyncMock(return_value=text.encode("utf-8") if isinstance(text, str) else text)
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


def make_session_with_get(get_responses: list[MagicMock], post_responses: list[MagicMock]) -> MagicMock:
    """构造支持 GET + POST 的 ClientSession mock（独立队列）

    钉钉 notifier v6 方案需要：
    1. session.get(thumb_url) 下载商品图
    2. session.post(payload) 发送主消息
    3. session.post(form) 上传到公共图床
    4. session.post(payload) 发送 link 副消息

    get_responses 和 post_responses 各自维护独立队列
    """
    session = MagicMock()
    get_queue = list(get_responses)
    post_queue = list(post_responses)

    def _next_get(*args, **kwargs):
        if not get_queue:
            raise AssertionError("get() 调用次数超出预期")
        return get_queue.pop(0)

    def _next_post(*args, **kwargs):
        if not post_queue:
            raise AssertionError("post() 调用次数超出预期")
        return post_queue.pop(0)

    session.get = MagicMock(side_effect=_next_get)
    session.post = MagicMock(side_effect=_next_post)
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


def patch_pil_compress_success():
    """mock PIL.Image 让压缩步骤"成功"返回固定字节

    测试中下载的 image_bytes 是不合法的（仅为模拟 webp 头），PIL 真实解码会失败。
    用这个 context manager 替换 PIL.Image，模拟 Image.open / convert / thumbnail / save 链，
    让 _prepare_image_url 走完整个下载→压缩→上传流程。

    注意：dingtalk.py 用的是 `from PIL import Image` + `Image.open(...)` 模式，
    替换 PIL.Image 后，函数内重新 import 时 Image 就指向 mock_module，
    所以这里 mock 的是 mock_module.open（不是 mock_module.Image.open）。
    """
    fake_jpg = b"\xff\xd8\xff\xe0" + b"\x00" * 50  # 模拟 JPEG 字节
    mock_img = MagicMock()
    mock_img.mode = "RGB"

    def _fake_save(buf, format=None, **kwargs):
        buf.write(fake_jpg)
        return None

    mock_img.save = _fake_save
    mock_img.convert = MagicMock(return_value=mock_img)
    mock_img.thumbnail = MagicMock(return_value=None)

    mock_module = MagicMock()
    mock_module.open = MagicMock(return_value=mock_img)

    # PIL 用延迟加载：测试运行时 PIL.Image 还不存在（没人 import），
    # create=True 让 patch 在属性缺失时自动创建
    return patch("PIL.Image", mock_module, create=True)


# ============== 注册表测试 ==============

def test_registry_includes_new_channels() -> None:
    """注册表应包含 8 个渠道（原 3 + P1-3 新增 4 + ntfy 新增 1）"""
    registry = NotifierRegistry.default()
    channels = registry.available()
    assert "telegram" in channels
    assert "wecom" in channels
    assert "dingtalk" in channels
    assert "webhook" in channels
    assert len(channels) == 8


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


def test_to_wecom_markdown_converts_lists() -> None:
    """无序列表 - 应转换为项目符号 •"""
    body = "- 卖家：张三\n- 价格：¥100"
    result = _to_wecom_markdown(body)
    assert "- " not in result
    assert "• 卖家：张三" in result
    assert "• 价格：¥100" in result


def test_to_wecom_markdown_removes_images() -> None:
    """图片语法 ![alt](url) 应被移除"""
    body = "### 评估通过\n![商品图](https://example.com/img.jpg)\n[查看](https://example.com)"
    result = _to_wecom_markdown(body)
    assert "![" not in result
    assert "[查看](https://example.com)" in result  # 普通链接保留


def test_to_wecom_markdown_removes_italics() -> None:
    """斜体 _text_ 应转为纯文本"""
    body = "系统自动发送，_请 5 分钟内确认_"
    result = _to_wecom_markdown(body)
    assert "_" not in result
    assert "请 5 分钟内确认" in result


def test_to_wecom_markdown_removes_separators() -> None:
    """分割线 --- 应被移除，多余空行压缩"""
    body = "标题\n\n---\n\n正文"
    result = _to_wecom_markdown(body)
    assert "---" not in result
    assert "\n\n\n" not in result  # 无 3+ 连续换行


@pytest.mark.asyncio
async def test_wecom_send_uses_converted_markdown() -> None:
    """发送时应使用降级转换后的 markdown（不含 - 列表 / ![] 图片 / _ 斜体）"""
    notifier = WeComNotifier(webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send")
    resp = make_response(200, '{"errcode":0}')
    session = make_session([resp])

    with patch("aiohttp.ClientSession", return_value=session):
        await notifier.send(make_eval_event())

    _, kwargs = session.post.call_args
    content = kwargs["json"]["markdown"]["content"]
    # 标题加粗
    assert content.startswith("**")
    # 不应包含企业微信不支持的语法
    assert "\n- " not in content  # 无序列表
    assert "![" not in content  # 图片
    assert "_系统自动" not in content  # 斜体（_ 已被移除）


@pytest.mark.asyncio
async def test_wecom_4xx_response_raises() -> None:
    """企业微信 4xx 响应应抛异常，重试 3 次后 result.success 为 False"""
    notifier = WeComNotifier(webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send")
    # BaseNotifier 默认重试 3 次，需提供 3 个相同 4xx 响应
    resp = make_response(400, '{"errcode":40001,"errmsg":"invalid webhook url"}')
    session = make_session([resp, resp, resp])

    with patch("aiohttp.ClientSession", return_value=session):
        result = await notifier.send(make_eval_event())

    assert result.success is False
    assert result.attempts == 3
    assert "webhook" in result.error


# ============== 钉钉推送测试 ==============

@pytest.mark.asyncio
async def test_dingtalk_send_success() -> None:
    """钉钉推送成功（含签名），单条 actionCard 策略

    策略：
    - 单条 actionCard 主消息：富文本（# 标题、<font color>、>引用、风险项翻译）
      + 商品图作为 markdown 链接嵌入末尾 + 按钮跳转
    - **钉钉 webhook 不支持 image 类型 + 公共图床国内不可用**（v1→v6 全失败）
    - 当前 v7 方案：只发 1 条消息，商品图以可点击链接形式呈现
    """
    notifier = DingTalkNotifier(
        webhook_url="https://oapi.dingtalk.com/robot/send?access_token=abc",
        secret="SECtest123",
    )
    main_resp = make_response(200, '{"errcode":0,"errmsg":"ok"}')
    session = make_session([main_resp])

    with patch("aiohttp.ClientSession", return_value=session):
        result = await notifier.send(make_eval_event())

    assert result.success is True
    assert result.channel == "dingtalk"
    # 只发 1 条 actionCard（无副消息、无 GET 下载、无图床上传）
    assert session.post.call_count == 1
    assert session.get.call_count == 0

    # —— 验证主消息（actionCard）——
    main_args, main_kwargs = session.post.call_args
    # URL 应含签名参数
    assert "timestamp=" in main_args[0]
    assert "sign=" in main_args[0]
    # msgtype 应为 actionCard
    assert main_kwargs["json"]["msgtype"] == "actionCard"
    card = main_kwargs["json"]["actionCard"]
    # 卡片标题：短标题（限 64 字符）
    assert card["title"].startswith("[闲鱼捡漏]")
    # 卡片正文：markdown
    content = card["text"]
    # 钉钉优化格式：首行用 # 标题
    assert content.startswith("# ")
    # 关键字段用 <font color> 标记
    assert '<font color="#1890FF">' in content  # 评分（蓝色）
    assert '<font color="#52C41A">' in content or '<font color="#FA8C16">' in content
    assert '<font color="#F5222D">' in content  # 价格（红色）
    # 跳转链接带颜色
    assert '[<font color="#0088FF">' in content
    # 不应包含钉钉不支持的语法
    assert "_系统自动" not in content  # 斜体已移除
    # actionCard 整体跳转按钮
    assert card["singleTitle"] == "查看商品详情"
    assert "goofish.com" in card["singleURL"] and "/item/" in card["singleURL"]
    # 商品图作为可点击链接嵌入（v7 新方案）
    assert "点击查看商品图" in content
    assert "img.example.com" in content
    # 灰色页脚
    assert '<font color="#999999">' in content


@pytest.mark.asyncio
async def test_dingtalk_send_without_thumb_skips_link() -> None:
    """无 thumb_url 时主消息正常发送（v7 单消息策略无副消息可跳过）"""
    notifier = DingTalkNotifier(
        webhook_url="https://oapi.dingtalk.com/robot/send?access_token=abc",
        secret="SECtest123",
    )
    # 构造无 thumb_url 的事件
    event = Event(
        type=EventType.EVAL_PASSED,
        task_id="t1",
        item_id="i1",
        payload={
            "item": {
                "title": "iPhone 13",
                "price": 1999.0,
                "url": "https://www.goofish.com/item/i1",
            },
            "score": 85,
            "risk_level": "low",
            "seller_nick": "测试卖家",
            "reject_reasons": [],
        },
    )
    main_resp = make_response(200, '{"errcode":0,"errmsg":"ok"}')
    session = make_session([main_resp])

    with patch("aiohttp.ClientSession", return_value=session):
        result = await notifier.send(event)

    assert result.success is True
    # 只调用 1 次 POST
    assert session.post.call_count == 1
    # 不应调用 GET（无图可下）
    assert session.get.call_count == 0
    # 且为主消息 actionCard
    assert session.post.call_args.kwargs["json"]["msgtype"] == "actionCard"
    # 无 thumb_url 时主消息不含"点击查看商品图"
    content = session.post.call_args.kwargs["json"]["actionCard"]["text"]
    assert "点击查看商品图" not in content


@pytest.mark.asyncio
async def test_dingtalk_send_renders_reject_reasons_as_blockquote() -> None:
    """风险项 reject_reasons 存在时，应渲染为 > 引用块 + 中文翻译（钉钉 markdown 原生支持）"""
    event = Event(
        type=EventType.EVAL_PASSED,
        task_id="t1",
        item_id="i1",
        payload={
            "item": {
                "title": "iPhone 13 128G 国行",
                "price": 1999.0,
                "url": "https://www.goofish.com/item/i1",
            },
            "score": 70,
            "risk_level": "medium",
            "reject_reasons": [
                "on_sale 9 (ded=1)",
                "dealer:image_theft(sellers=6,sample=10506087)",
            ],
        },
    )
    notifier = DingTalkNotifier(
        webhook_url="https://oapi.dingtalk.com/robot/send?access_token=abc",
        secret="SECtest123",
    )
    resp = make_response(200, '{"errcode":0}')
    session = make_session([resp])

    with patch("aiohttp.ClientSession", return_value=session):
        await notifier.send(event)

    _, kwargs = session.post.call_args
    content = kwargs["json"]["actionCard"]["text"]
    # 风险项用 > 引用块突出
    assert "> 📦 在售商品过多（9 件）" in content
    # dealer:image_theft 应翻译为中文
    assert "> 🖼️ 涉嫌盗图" in content
    # 风险等级 medium → 橙色
    assert '<font color="#FA8C16">medium</font>' in content


@pytest.mark.asyncio
async def test_dingtalk_send_business_error() -> None:
    """钉钉业务错误（HTTP 200 但 errcode!=0）应标记为失败"""
    notifier = DingTalkNotifier(
        webhook_url="https://oapi.dingtalk.com/robot/send?access_token=abc",
        secret="SECtest123",
    )
    # 模拟关键词不匹配
    main_resp = make_response(200, '{"errcode":310000,"errmsg":"keywords not in content"}')
    session = make_session([main_resp])

    with patch("aiohttp.ClientSession", return_value=session):
        result = await notifier.send(make_eval_event())

    assert result.success is False
    assert "errcode=310000" in result.error or "keywords" in result.error


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


def test_to_dingtalk_markdown_keeps_images() -> None:
    """图片语法 ![alt](url) 应保留（ActionCard 走钉钉图片代理）"""
    body = "# 评估通过\n![商品图](https://example.com/img.jpg)\n[查看](https://example.com)"
    result = _to_dingtalk_markdown(body)
    assert "![商品图](https://example.com/img.jpg)" in result
    assert "[查看](https://example.com)" in result  # 普通链接保留


def test_to_dingtalk_markdown_removes_italics() -> None:
    """斜体 _text_ 应转为纯文本（ActionCard markdown 不识别下划线斜体）"""
    body = "系统自动发送，_请尽快确认_"
    result = _to_dingtalk_markdown(body)
    assert "_" not in result
    assert "请尽快确认" in result


def test_to_dingtalk_markdown_keeps_separators() -> None:
    """ActionCard 支持分割线 --- → 保留"""
    body = "标题\n\n---\n\n正文"
    result = _to_dingtalk_markdown(body)
    assert "---" in result


def test_to_dingtalk_markdown_keeps_font_color() -> None:
    """<font color> 字体颜色应保留（ActionCard markdown 原生支持）"""
    body = '<font color="#F5222D">¥760.00</font>'
    result = _to_dingtalk_markdown(body)
    assert '<font color="#F5222D">¥760.00</font>' in result


def test_to_dingtalk_markdown_keeps_blockquote() -> None:
    """引用块 > 应保留（ActionCard markdown 原生支持）"""
    body = "**风险项：**\n> on_sale 9 (ded=1)\n> dealer:image_theft"
    result = _to_dingtalk_markdown(body)
    assert "> on_sale 9" in result
    assert "> dealer:image_theft" in result


# ============== 风险项翻译器测试 ==============


def test_translate_reject_reason_image_theft() -> None:
    """dealer:image_theft 应翻译为'涉嫌盗图'"""
    assert "涉嫌盗图" in _translate_reject_reason(
        "dealer:image_theft(sellers=6,sample=10506087,85381285)"
    )


def test_translate_reject_reason_new_register() -> None:
    """dealer:new_register_low_activity 应翻译为'新注册账号'"""
    assert "新注册账号" in _translate_reject_reason(
        "dealer:new_register_low_activity(days=15,sold=2,on_sale=8)"
    )


def test_translate_reject_reason_templated_text() -> None:
    """dealer:templated_text 应翻译为'文案高度模板化'"""
    assert "文案高度模板化" in _translate_reject_reason(
        "dealer:templated_text(max_sim=0.92,sample=15)"
    )


def test_translate_reject_reason_post_burst() -> None:
    """dealer:post_burst 应翻译为'短期大量发帖'"""
    assert "短期大量发帖" in _translate_reject_reason(
        "dealer:post_burst(recent=20,previous=2,ratio=10.0x)"
    )


def test_translate_reject_reason_on_sale() -> None:
    """on_sale N (ded=M) 应翻译为'在售商品过多'"""
    assert "在售商品过多" in _translate_reject_reason("on_sale 9 (ded=1)")


def test_translate_reject_reason_credit_score() -> None:
    """credit_score N moderate 应翻译为'信用分一般'"""
    assert "信用分一般" in _translate_reject_reason("credit_score 98 moderate")


def test_translate_reject_reason_register_days() -> None:
    """register_days N < M 应翻译为'注册时间过短'"""
    assert "注册时间过短" in _translate_reject_reason("register_days 30 < 90")


def test_translate_reject_reason_unknown_keeps_original() -> None:
    """未知模式应保留原值，便于排查"""
    result = _translate_reject_reason("some_unknown_signal")
    assert "some_unknown_signal" in result


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
