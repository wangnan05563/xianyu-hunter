"""ntfy 推送适配器（跨平台 / 自由开源 / HTTP 极简）

项目地址：https://github.com/binwiederhier/ntfy
官方公共实例：https://ntfy.sh（可直接使用，也可自托管）

API 文档：https://docs.ntfy.sh/publish/
- 端点：POST {server}  (JSON 模式)
- Body：{"topic": "...", "title": "...", "message": "...", "priority": 4, "markdown": true}
- 鉴权（可选）：Authorization: Bearer tk_xxx

为什么选 ntfy：
1. 完全免费、无配额、无需注册账号
2. 全平台原生客户端（Android / iOS / Web / CLI）
3. 可自托管，也可使用官方公共实例
4. HTTP 极简：curl -d "msg" ntfy.sh/topic 即可推送
5. 填补 Bark（仅 iOS）的跨平台推送缺口
"""
from __future__ import annotations

import aiohttp

from xianyu_hunter.domain.events import Event
from xianyu_hunter.infra.secrets import (
    KEY_NTFY_SERVER,
    KEY_NTFY_TOPIC,
    KEY_NTFY_TOKEN,
    get_secret,
)
from xianyu_hunter.modules.notifier.base import BaseNotifier
from xianyu_hunter.modules.notifier.templates import render

# 官方公共实例：直接可用，无需自建
DEFAULT_SERVER = "https://ntfy.sh"


class NtfyNotifier(BaseNotifier):
    """ntfy 推送（跨平台）"""

    name = "ntfy"

    def __init__(
        self,
        server: str | None = None,
        topic: str | None = None,
        token: str | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        # 末尾去掉斜杠避免拼出双斜杠 URL
        self.server = (server or get_secret(KEY_NTFY_SERVER) or DEFAULT_SERVER).rstrip("/")
        self.topic = topic or get_secret(KEY_NTFY_TOPIC) or ""
        # token 可选：公共实例上的私有 topic 需要鉴权，自托管实例也可配置
        self.token = token or get_secret(KEY_NTFY_TOKEN) or ""

    @property
    def is_configured(self) -> bool:
        # topic 是唯一必填项；server 有默认值，token 可选
        return bool(self.topic)

    async def _do_send(self, event: Event) -> str:
        if not self.topic:
            raise ValueError("ntfy topic 未配置（keyring 缺失或为空）")
        title, body = render(event)
        url = self.server
        headers = {"Content-Type": "application/json"}
        if self.token:
            # Bearer token 鉴权（自托管或公共实例私有 topic）
            headers["Authorization"] = f"Bearer {self.token}"
        payload = {
            "topic": self.topic,
            "title": title,
            "message": body,
            # priority: 1=min, 2=low, 3=default, 4=high, 5=urgent
            # 评估通过/抢单成功都属于重要事件，使用 high 让设备有响铃提醒
            "priority": 4,
            "tags": ["shopping_cart", "bell"],
            "markdown": True,
        }
        async with aiohttp.ClientSession(timeout=self._client_timeout()) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                text = await resp.text()
                if resp.status != 200:
                    raise aiohttp.ClientResponseError(
                        request_info=resp.request_info,
                        history=resp.history,
                        status=resp.status,
                        message=text[:200],
                    )
                return text
