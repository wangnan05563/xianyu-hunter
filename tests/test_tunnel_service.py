from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from xianyu_hunter.domain.events import EventType
from xianyu_hunter.web.services import tunnel_notifications
from xianyu_hunter.web.services.tunnel_service import TunnelService


@pytest.fixture
def tunnel_service():
    """构造 TunnelService 实例，mock 掉 provider 创建。"""
    service = TunnelService(local_port=8001)
    provider = MagicMock()
    provider.status = "stopped"
    provider.public_url = None
    provider.start.return_value = "https://abc123.trycloudflare.com"
    service._provider = provider
    service._provider_name = "cloudflare"
    # 避免 start() 读取真实配置创建新 provider 替换 mock
    service._ensure_provider = lambda: provider
    return service


def test_tunnel_service_initial_state() -> None:
    service = TunnelService()
    assert service.status == "stopped"
    assert service.public_url is None


def test_tunnel_service_start_assigns_url(tunnel_service) -> None:
    url = tunnel_service.start()
    assert url.startswith("https://")
    tunnel_service._provider.start.assert_called_once()


def test_tunnel_service_stop_clears_state(tunnel_service) -> None:
    tunnel_service.stop()
    tunnel_service._provider.stop.assert_called_once()


def test_tunnel_service_status_reflects_provider(tunnel_service) -> None:
    tunnel_service._provider.status = "running"
    assert tunnel_service.status == "running"
    tunnel_service._provider.status = "stopped"
    assert tunnel_service.status == "stopped"


def test_tunnel_service_public_url_reflects_provider(tunnel_service) -> None:
    tunnel_service._provider.public_url = "https://test.trycloudflare.com"
    assert tunnel_service.public_url == "https://test.trycloudflare.com"


@pytest.mark.parametrize(
    ("provider_name", "public_url"),
    [
        ("cloudflare", "https://example.trycloudflare.com"),
        ("cpolar", "https://example.cpolar.top"),
        ("tailscale", "https://xianyu-hunter.example.ts.net"),
    ],
)
def test_start_notifies_once_after_provider_returns_public_url(
    provider_name: str,
    public_url: str,
) -> None:
    on_started = Mock()
    provider = Mock()
    provider.start.return_value = public_url
    service = TunnelService(on_started=on_started)
    service._provider_name = provider_name

    with (
        patch.object(service, "_ensure_provider", return_value=provider),
        patch.object(service, "_resolve_port", return_value=8001),
    ):
        result = service.start()

    assert result == public_url
    on_started.assert_called_once_with(
        provider_name,
        public_url,
        8001,
    )


def test_notification_failure_does_not_fail_tunnel_start() -> None:
    def fail_notification(*_args) -> None:
        raise RuntimeError("notification unavailable")

    provider = Mock()
    provider.start.return_value = "https://xianyu-hunter.example.ts.net"
    service = TunnelService(on_started=fail_notification)
    service._provider_name = "tailscale"

    with (
        patch.object(service, "_ensure_provider", return_value=provider),
        patch.object(service, "_resolve_port", return_value=8001),
    ):
        assert service.start() == "https://xianyu-hunter.example.ts.net"


def test_notification_worker_sends_tunnel_event_to_enabled_notifiers() -> None:
    hub = Mock()
    hub.send = AsyncMock(return_value=[])
    container = Mock(notifier_hub=hub)

    with patch("xianyu_hunter.web.deps.get_container", return_value=container):
        tunnel_notifications.send_tunnel_started_notification(
            "tailscale",
            "https://xianyu-hunter.example.ts.net",
            8001,
        )

    event = hub.send.await_args.args[0]
    assert event.type == EventType.TUNNEL_STARTED
    assert event.payload["provider_label"] == "Tailscale Funnel"
    assert event.payload["public_url"] == "https://xianyu-hunter.example.ts.net"
    assert event.payload["action_url"] == "https://xianyu-hunter.example.ts.net"
