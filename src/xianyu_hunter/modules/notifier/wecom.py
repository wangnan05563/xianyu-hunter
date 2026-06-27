"""企业微信机器人推送适配器

API 文档：https://developer.work.weixin.qq.com/document/path/91770
- 端点：POST {webhook_url}
- 参数：msgtype=markdown, markdown.content
- markdown 类型支持加粗/链接/列表/字体颜色，可读性优于 text
"""
from __future__ import annotations

import aiohttp

from xianyu_hunter.domain.events import Event
from xianyu_hunter.infra.secrets import KEY_WECOM_WEBHOOK, get_secret
from xianyu_hunter.modules.notifier.base import BaseNotifier
from xianyu_hunter.modules.notifier.templates import render


class WeComNotifier(BaseNotifier):
    """企业微信机器人推送（markdown 格式）"""

    name = "wecom"

    def __init__(self, webhook_url: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.webhook_url = webhook_url or get_secret(KEY_WECOM_WEBHOOK) or ""

    async def _do_send(self, event: Event) -> str:
        if not self.webhook_url:
            raise ValueError("企业微信 webhook_url 未配置（keyring 缺失或为空）")
        title, body = render(event)
        # 标题加粗，body 本身已是 markdown（render 输出 ###/**/- 等语法）
        content = f"**{title}**\n\n{body}"
        async with aiohttp.ClientSession(timeout=self._client_timeout()) as session:
            async with session.post(
                self.webhook_url,
                json={
                    "msgtype": "markdown",
                    "markdown": {"content": content},
                },
            ) as resp:
                text = await resp.text()
                if resp.status != 200:
                    raise aiohttp.ClientResponseError(
                        request_info=resp.request_info,
                        history=resp.history,
                        status=resp.status,
                        message=text[:200],
                    )
                return text
