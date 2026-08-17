"""PushPlus 推送适配器

API 文档：https://www.pushplus.plus/doc/
- 端点：POST https://www.pushplus.plus/send
- 参数：token, title, content, template (markdown)
"""
from __future__ import annotations

import aiohttp

from xianyu_hunter.domain.events import Event
from xianyu_hunter.infra.secrets import KEY_PUSHPLUS, get_secret
from xianyu_hunter.modules.notifier.base import BaseNotifier
from xianyu_hunter.modules.notifier.templates import render

API_URL = "https://www.pushplus.plus/send"
TEMPLATE_MARKDOWN = "markdown"


class PushPlusNotifier(BaseNotifier):
    """PushPlus 推送（支持微信公众号）"""

    name = "pushplus"

    def __init__(self, token: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.token = token or get_secret(KEY_PUSHPLUS) or ""

    @property
    def is_configured(self) -> bool:
        return bool(self.token)

    async def _do_send(self, event: Event) -> str:
        if not self.token:
            raise ValueError("PushPlus token 未配置（keyring 缺失或为空）")
        title, body = render(event)
        payload = {
            "token": self.token,
            "title": title,
            "content": body,
            "template": TEMPLATE_MARKDOWN,
        }
        async with aiohttp.ClientSession(timeout=self._client_timeout()) as session:
            async with session.post(API_URL, json=payload) as resp:
                text = await resp.text()
                if resp.status != 200:
                    raise aiohttp.ClientResponseError(
                        request_info=resp.request_info,
                        history=resp.history,
                        status=resp.status,
                        message=text[:200],
                    )
                return text
