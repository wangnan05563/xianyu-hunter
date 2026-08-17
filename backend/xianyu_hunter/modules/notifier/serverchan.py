"""Server酱 推送适配器

API 文档：https://sct.ftqq.com/sendkey
- 端点：POST https://sctapi.ftqq.com/{send_key}.send
- 参数：title, desp (Markdown)
"""
from __future__ import annotations

import aiohttp

from xianyu_hunter.domain.events import Event
from xianyu_hunter.infra.secrets import KEY_SERVERCHAN, get_secret
from xianyu_hunter.modules.notifier.base import BaseNotifier
from xianyu_hunter.modules.notifier.templates import render

API_URL = "https://sctapi.ftqq.com/{send_key}.send"


class ServerChanNotifier(BaseNotifier):
    """Server酱推送"""

    name = "serverchan"

    def __init__(self, send_key: str | None = None, **kwargs):
        super().__init__(**kwargs)
        # 显式传入优先；否则从 keyring 拉取
        self.send_key = send_key or get_secret(KEY_SERVERCHAN) or ""

    @property
    def is_configured(self) -> bool:
        return bool(self.send_key)

    async def _do_send(self, event: Event) -> str:
        if not self.send_key:
            raise ValueError("Server酱 send_key 未配置（keyring 缺失或为空）")
        title, body = render(event)
        url = API_URL.format(send_key=self.send_key)
        async with aiohttp.ClientSession(timeout=self._client_timeout()) as session:
            async with session.post(
                url,
                data={"title": title, "desp": body},
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
