"""钉钉机器人推送适配器

API 文档：https://open.dingtalk.com/document/dingstart/custom-bot-send-message-type
- 端点：POST {webhook_url}（含签名参数 timestamp&sign）
- **关键限制**：钉钉官方明确说明 webhook 方式**不支持 image 消息类型**（只支持
  text/markdown/actionCard/link/feedCard 5 种）。
- 本项目当前方案：只发 actionCard 主消息，**商品图作为 markdown 链接嵌入正文末尾**
  （用户点击链接在新窗口打开原图）。这是权衡了"国内匿名图床几乎都不可用"之后的
  最稳方案：零外部依赖、绝对稳定。

  历史方案回顾（v1→v6 全部失败，根因都是 webhook 不支持 image 或图床不可用）：
  - v1 纯 text：markdown 语法原样显示 ❌
  - v2 markdown：markdown 渲染，但 ![alt](url) 防盗链失败 ❌
  - v3 actionCard：同上，markdown 内的图片显示占位 ❌
  - v4 actionCard + link（picUrl）：link 副消息同样无法加载图（webp/防盗链）❌
  - v5 actionCard + image（base64）：errcode 400802 / 460101 ❌
  - v6 actionCard + link（公共图床 URL）：0x0.st / catbox.moe 国内访问 503 ❌
  - v7 actionCard + markdown 链接跳转 ✅ 当前方案
- 签名：HmacSHA256(secret, timestamp) → base64 → URL 编码
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import re
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
from xianyu_hunter.modules.notifier.templates import _get, GOOFISH_ITEM_URL, render

_logger = logging.getLogger(__name__)


def _to_dingtalk_markdown(body: str) -> str:
    """将通用 markdown 降级为钉钉 ActionCard 兼容的子集

    - 斜体 `_text_` → 纯文本 `text`（钉钉 markdown 不识别下划线斜体）
    - 分割线 `---` → 保留（ActionCard 渲染为浅色分割线）
    - 标题/加粗/引用/链接/`<font color>` 全部保留
    """
    lines = []
    for line in body.split("\n"):
        line = re.sub(r"_([^_]+)_", r"\1", line)
        lines.append(line)
    return "\n".join(lines)


class DingTalkNotifier(BaseNotifier):
    """钉钉机器人推送（markdown 格式）"""

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
        # body 已经按钉钉 markdown 优化（首行 # 标题、<font> 颜色、引用、风险项翻译等），
        # 只需做最小降级（移除 _ 斜体）
        text = _to_dingtalk_markdown(body)

        # 商品详情 URL（用于 actionCard 按钮跳转）
        # 兼容扁平 / item 子对象两种 payload 格式（同 render()）
        item_obj = event.payload.get("item") if isinstance(event.payload.get("item"), dict) else None
        action_url = str((event.payload or {}).get("action_url") or "").strip()
        action_title = str((event.payload or {}).get("action_title") or "").strip()
        item_url = action_url or _get(event.payload or {}, "url", item_obj, "")
        if not item_url and event.item_id:
            item_url = GOOFISH_ITEM_URL.format(item_id=event.item_id)

        # 构造主消息（actionCard 富文本卡片）
        # 商品图作为 markdown 链接已嵌入 text 末尾（由 templates._eval_passed 渲染）
        card_title = title[:64] if title else "闲鱼猎人"
        card_payload: dict = {
            "msgtype": "actionCard",
            "actionCard": {
                "title": card_title,
                "text": text,
                "singleTitle": action_title or ("查看商品详情" if item_url else "打开闲鱼猎人"),
                "singleURL": item_url or "https://www.goofish.com",
            },
        }

        async with aiohttp.ClientSession(timeout=self._client_timeout()) as session:
            resp = await self._post_message(session, card_payload)
            if "errcode" in resp and resp.get("errcode") != 0:
                raise RuntimeError(
                    f"钉钉消息发送失败 errcode={resp.get('errcode')}: "
                    f"{resp.get('errmsg', 'unknown')}"
                )
            return json.dumps({"main": resp}, ensure_ascii=False)

    async def _post_message(
        self, session: aiohttp.ClientSession, payload: dict
    ) -> dict:
        """POST 消息到钉钉 webhook，返回响应 JSON

        异常情况：
        - HTTP 状态非 200：抛 ClientResponseError
        - HTTP 200 但 errcode != 0：返回原 dict（含 errcode/errmsg），由调用方决定是否抛
        - 返回 body 非 JSON：返回 {"raw": text_resp}
        """
        url = self.webhook_url
        if self.secret:
            timestamp = int(round(time.time() * 1000))
            sign = self._sign(timestamp)
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}timestamp={timestamp}&sign={sign}"

        async with session.post(url, json=payload) as resp:
            text_resp = await resp.text()
            if resp.status != 200:
                raise aiohttp.ClientResponseError(
                    request_info=resp.request_info,
                    history=resp.history,
                    status=resp.status,
                    message=text_resp[:200],
                )
            try:
                return json.loads(text_resp)
            except (ValueError, TypeError):
                return {"raw": text_resp}
