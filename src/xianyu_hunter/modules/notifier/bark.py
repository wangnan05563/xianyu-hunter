"""Bark 推送适配器（iOS）

API 文档：https://github.com/Finb/Bark
- 端点：POST {server}/{key}/{title}/{body}
  或 GET 形式亦可
"""
from __future__ import annotations

from urllib.parse import quote

import aiohttp

from xianyu_hunter.domain.events import Event
from xianyu_hunter.infra.secrets import (
    KEY_BARK_KEY,
    KEY_BARK_SERVER,
    get_secret,
)
from xianyu_hunter.modules.notifier.base import BaseNotifier
from xianyu_hunter.modules.notifier.templates import render

DEFAULT_SERVER = "https://api.day.app"


class BarkNotifier(BaseNotifier):
    """Bark 推送（iOS）"""

    name = "bark"

    def __init__(
        self,
        server: str | None = None,
        key: str | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.server = (server or get_secret(KEY_BARK_SERVER) or DEFAULT_SERVER).rstrip("/")
        self.key = key or get_secret(KEY_BARK_KEY) or ""

    async def _do_send(self, event: Event) -> str:
        if not self.key:
            raise ValueError("Bark key 未配置（keyring 缺失或为空）")
        title, body = render(event)
        # 用 POST 形式避免标题/正文 URL 编码问题
        url = f"{self.server}/{self.key}"
        # title 单独作为 query 传，body 作为 JSON 字段
        async with aiohttp.ClientSession(timeout=self._client_timeout()) as session:
            async with session.post(
                url,
                params={"title": quote(title, safe="")},
                json={"body": body, "group": "XianyuHunter"},
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
