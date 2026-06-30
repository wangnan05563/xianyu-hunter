"""钉钉机器人推送适配器

API 文档：https://open.dingtalk.com/document/robots/custom-robot-access
- 端点：POST {webhook_url}（含签名参数 timestamp&sign）
- 参数：msgtype=text, text.content
- 签名：HmacSHA256(secret, timestamp) → base64 → URL 编码
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time
from urllib.parse import quote

import aiohttp

from xianyu_hunter.domain.events import Event
from xianyu_hunter.infra.secrets import (
    KEY_DINGTALK_SECRET,
    KEY_DINGTALK_WEBHOOK,
    get_secret,
)
from xianyu_hunter.modules.notifier.base import BaseNotifier
from xianyu_hunter.modules.notifier.templates import render


class DingTalkNotifier(BaseNotifier):
    """钉钉机器人推送"""

    name = "dingtalk"

    def __init__(
        self,
        webhook_url: str | None = None,
        secret: str | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.webhook_url = webhook_url or get_secret(KEY_DINGTALK_WEBHOOK) or ""
        self.secret = secret or get_secret(KEY_DINGTALK_SECRET) or ""

    @property
    def is_configured(self) -> bool:
        return bool(self.webhook_url)

    def _sign(self, timestamp: int) -> str:
        """生成钉钉机器人签名

        算法：HmacSHA256(secret, f"{timestamp}\n{secret}") → base64 → URL 编码
        """
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            self.secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        return quote(base64.b64encode(hmac_code).decode("utf-8"), safe="")

    async def _do_send(self, event: Event) -> str:
        if not self.webhook_url:
            raise ValueError("钉钉 webhook_url 未配置（keyring 缺失或为空）")
        title, body = render(event)
        content = f"{title}\n\n{body}"

        # 构造请求 URL（含签名）
        url = self.webhook_url
        if self.secret:
            timestamp = int(round(time.time() * 1000))
            sign = self._sign(timestamp)
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}timestamp={timestamp}&sign={sign}"

        async with aiohttp.ClientSession(timeout=self._client_timeout()) as session:
            async with session.post(
                url,
                json={
                    "msgtype": "text",
                    "text": {"content": content},
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
