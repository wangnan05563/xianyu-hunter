"""自定义 Webhook 推送适配器

支持任意自定义 Webhook URL，POST JSON 格式：
{
  "title": "...",
  "body": "...",
  "event": {...原始事件对象...},
  "timestamp": "ISO 格式"
}

可选 Bearer Token 认证。
"""
from __future__ import annotations

from datetime import datetime, timezone

import aiohttp

from xianyu_hunter.domain.events import Event
from xianyu_hunter.infra.secrets import KEY_WEBHOOK_TOKEN, KEY_WEBHOOK_URL, get_secret
from xianyu_hunter.modules.notifier.base import BaseNotifier
from xianyu_hunter.modules.notifier.templates import render


class WebhookNotifier(BaseNotifier):
    """自定义 Webhook 推送"""

    name = "webhook"

    def __init__(
        self,
        webhook_url: str | None = None,
        token: str | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.webhook_url = webhook_url or get_secret(KEY_WEBHOOK_URL) or ""
        self.token = token or get_secret(KEY_WEBHOOK_TOKEN) or ""

    @property
    def is_configured(self) -> bool:
        return bool(self.webhook_url)

    async def _do_send(self, event: Event) -> str:
        if not self.webhook_url:
            raise ValueError("Webhook URL 未配置（keyring 缺失或为空）")
        title, body = render(event)
        payload = {
            "title": title,
            "body": body,
            "event": {
                "type": getattr(event, "type", None),
                "task_id": getattr(event, "task_id", None),
                "item_id": getattr(event, "item_id", None),
                "stage": getattr(event, "stage", None),
                "level": getattr(event, "level", None),
                "message": getattr(event, "message", None),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        async with aiohttp.ClientSession(timeout=self._client_timeout()) as session:
            async with session.post(
                self.webhook_url,
                json=payload,
                headers=headers,
            ) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    raise aiohttp.ClientResponseError(
                        request_info=resp.request_info,
                        history=resp.history,
                        status=resp.status,
                        message=text[:200],
                    )
                return text
