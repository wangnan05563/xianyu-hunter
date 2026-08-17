"""企业微信机器人推送适配器

API 文档：https://developer.work.weixin.qq.com/document/path/91770
- 端点：POST {webhook_url}
- 参数：msgtype=markdown, markdown.content
- 企业微信 markdown 仅支持子集：标题#/链接[]()/加粗**/行内代码`/引用>/字体颜色
  不支持：无序列表 -、图片 ![]、斜体 _、分割线 ---
  故需将 render() 的通用 markdown 降级转换后再发送
"""
from __future__ import annotations

import re

import aiohttp

from xianyu_hunter.domain.events import Event
from xianyu_hunter.infra.secrets import KEY_WECOM_WEBHOOK, get_secret
from xianyu_hunter.modules.notifier.base import BaseNotifier
from xianyu_hunter.modules.notifier.templates import render


def _to_wecom_markdown(body: str) -> str:
    """将通用 markdown 降级为企业微信兼容的子集

    - 无序列表 `- item` → 项目符号 `• item`
    - 图片 `![alt](url)` → 移除（企业微信不支持图片语法）
    - 斜体 `_text_` → 纯文本 `text`
    - 分割线 `---` → 移除（用空行替代视觉分隔）
    """
    lines = []
    for line in body.split("\n"):
        line = re.sub(r"^- (.+)$", r"• \1", line)
        line = re.sub(r"!\[[^\]]*\]\([^\)]*\)", "", line)
        line = re.sub(r"_([^_]+)_", r"\1", line)
        line = re.sub(r"^-{3,}$", "", line)
        lines.append(line)
    result = "\n".join(lines)
    # 压缩连续 3+ 换行为 2 个（分割线移除后可能产生多余空行）
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result


class WeComNotifier(BaseNotifier):
    """企业微信机器人推送（markdown 格式）"""

    name = "wecom"

    def __init__(self, webhook_url: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.webhook_url = webhook_url or get_secret(KEY_WECOM_WEBHOOK) or ""

    @property
    def is_configured(self) -> bool:
        return bool(self.webhook_url)

    async def _do_send(self, event: Event) -> str:
        if not self.webhook_url:
            raise ValueError("企业微信 webhook_url 未配置（keyring 缺失或为空）")
        title, body = render(event)
        # 标题加粗 + body 降级为企业微信兼容的 markdown 子集
        content = f"**{title}**\n\n{_to_wecom_markdown(body)}"
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
