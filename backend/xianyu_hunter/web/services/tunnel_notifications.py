"""内网穿透启动通知：桥接同步隧道生命周期与异步 NotifierHub。"""
from __future__ import annotations

import asyncio
import logging
import threading

from xianyu_hunter.domain.events import Event, EventType

logger = logging.getLogger(__name__)

_PROVIDER_LABELS = {
    "cloudflare": "Cloudflare Tunnel",
    "cpolar": "cpolar",
    "tailscale": "Tailscale Funnel",
}


def send_tunnel_started_notification(
    provider_name: str,
    public_url: str,
    local_port: int,
) -> None:
    """在线程内调用异步 NotifierHub，向所有已启用渠道发送启动通知。"""
    from xianyu_hunter.web.deps import get_container

    event = Event(
        type=EventType.TUNNEL_STARTED,
        payload={
            "provider": provider_name,
            "provider_label": _PROVIDER_LABELS.get(provider_name, provider_name),
            "public_url": public_url,
            "local_port": local_port,
            "action_url": public_url,
            "action_title": "立即打开闲鱼猎人",
        },
    )
    try:
        asyncio.run(get_container().notifier_hub.send(event))
    except Exception:
        logger.exception("发送内网穿透启动通知失败")


def notify_tunnel_started(provider_name: str, public_url: str, local_port: int) -> None:
    """异步调度启动通知，不阻塞 API 或开机自启动线程。"""
    threading.Thread(
        target=send_tunnel_started_notification,
        args=(provider_name, public_url, local_port),
        daemon=True,
        name="tunnel-start-notification",
    ).start()


def _send_autostart_failed_notification(error_message: str) -> None:
    """自启动失败时发送通知，复用 notify_tunnel_started 的子线程 + asyncio.run 模式。

    用 SYSTEM_ERROR 事件类型：severity=critical，穿透免打扰，
    确保用户不看 DB 事件也能通过通知渠道获知自启动失败原因。
    """
    threading.Thread(
        target=_do_send_autostart_failed,
        args=(error_message,),
        daemon=True,
        name="tunnel-autostart-fail-notify",
    ).start()


def _do_send_autostart_failed(error_message: str) -> None:
    """实际执行通知发送（在子线程中调用 asyncio.run 桥接异步 NotifierHub）。"""
    from xianyu_hunter.web.deps import get_container

    event = Event(
        type=EventType.SYSTEM_ERROR,
        payload={
            "error": error_message,
            "stage": "tunnel",
            "action_url": "",
            "action_title": "",
        },
    )
    try:
        asyncio.run(get_container().notifier_hub.send(event))
    except Exception:
        logger.exception("发送内网穿透自启动失败通知时出错")
