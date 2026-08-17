"""Telegram Bot 推送适配器

API 文档：https://core.telegram.org/bots/api#sendmessage
- 端点：POST https://api.telegram.org/bot{token}/sendMessage
- 参数：chat_id, text, parse_mode
"""
from __future__ import annotations

import aiohttp

from xianyu_hunter.domain.events import Event
from xianyu_hunter.infra.secrets import KEY_TELEGRAM_CHAT, KEY_TELEGRAM_TOKEN, get_secret
from xianyu_hunter.modules.notifier.base import BaseNotifier
from xianyu_hunter.modules.notifier.templates import render

API_BASE = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramNotifier(BaseNotifier):
    """Telegram Bot 推送"""

    name = "telegram"

    def __init__(
        self,
        bot_token: str | None = None,
        chat_id: str | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.bot_token = bot_token or get_secret(KEY_TELEGRAM_TOKEN) or ""
        self.chat_id = chat_id or get_secret(KEY_TELEGRAM_CHAT) or ""

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    async def _do_send(self, event: Event) -> str:
        if not self.bot_token:
            raise ValueError("Telegram bot_token 未配置（keyring 缺失或为空）")
        if not self.chat_id:
            raise ValueError("Telegram chat_id 未配置（keyring 缺失或为空）")
        title, body = render(event)
        # Telegram 消息格式：标题加粗 + 换行 + 正文（Markdown）
        text = f"*{title}*\n\n{body}"
        url = API_BASE.format(token=self.bot_token)
        async with aiohttp.ClientSession(timeout=self._client_timeout()) as session:
            async with session.post(
                url,
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True,
                },
            ) as resp:
                text_resp = await resp.text()
                if resp.status != 200:
                    raise aiohttp.ClientResponseError(
                        request_info=resp.request_info,
                        history=resp.history,
                        status=resp.status,
                        message=text_resp[:200],
                    )
                return text_resp
