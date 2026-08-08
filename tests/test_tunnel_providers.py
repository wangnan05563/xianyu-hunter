import json
from pathlib import Path
from subprocess import CompletedProcess
from subprocess import TimeoutExpired
from unittest.mock import MagicMock, patch

import pytest

from xianyu_hunter.web.services import tunnel_providers
from xianyu_hunter.web.services.tunnel_providers import CloudflareProvider


def test_setup_create_passes_origin_cert_as_tunnel_option() -> None:
    provider = CloudflareProvider(local_port=8000)
    output = (
        "Created tunnel 12345678-1234-1234-1234-123456789abc "
        "with credentials file C:\\Users\\tester\\.cloudflared\\12345678.json"
    )

    with (
        patch.object(provider, "_ensure_binary", return_value=Path("cloudflared.exe")),
        patch(
            "xianyu_hunter.web.services.tunnel_providers.subprocess.run",
            return_value=CompletedProcess([], 0, stdout=output, stderr=""),
        ) as run,
    ):
        provider.setup_create("my-tunnel", cert_file=r"C:\Users\tester\.cloudflared\cert.pem")

    assert run.call_args.args[0] == [
        "cloudflared.exe",
        "--no-autoupdate",
        "tunnel",
        "--origincert",
        r"C:\Users\tester\.cloudflared\cert.pem",
        "create",
        "my-tunnel",
    ]


def test_setup_create_parses_credentials_written_to_output() -> None:
    provider = CloudflareProvider(local_port=8000)
    output = (
        "Tunnel credentials written to "
        r"C:\Users\hspcadmin\.cloudflared\5338bc40-7e25-47bb-943e-a4b4c782466c.json. "
        "cloudflared chose this file based on where your origin certificate was found. "
        "Keep this file secret. To revoke these credentials, delete the tunnel. "
        "Created tunnel xianyuhunter.com with id 5338bc40-7e25-47bb-943e-a4b4c782466c"
    )

    with (
        patch.object(provider, "_ensure_binary", return_value=Path("cloudflared.exe")),
        patch(
            "xianyu_hunter.web.services.tunnel_providers.subprocess.run",
            return_value=CompletedProcess([], 0, stdout=output, stderr=""),
        ),
    ):
        result = provider.setup_create("xianyuhunter.com")

    assert result == {
        "tunnel_id": "5338bc40-7e25-47bb-943e-a4b4c782466c",
        "credentials_file": (
            r"C:\Users\hspcadmin\.cloudflared\5338bc40-7e25-47bb-943e-a4b4c782466c.json"
        ),
        "tunnel_name": "xianyuhunter.com",
    }


def test_setup_route_dns_passes_configured_origin_cert_as_tunnel_option() -> None:
    provider = CloudflareProvider(
        local_port=8000,
        cert_file=r"C:\Users\tester\.cloudflared\cert.pem",
    )

    with (
        patch.object(provider, "_ensure_binary", return_value=Path("cloudflared.exe")),
        patch(
            "xianyu_hunter.web.services.tunnel_providers.subprocess.run",
            return_value=CompletedProcess([], 0, stdout="", stderr=""),
        ) as run,
    ):
        provider.setup_route_dns("my-tunnel", "app.example.com")

    assert run.call_args.args[0] == [
        "cloudflared.exe",
        "--no-autoupdate",
        "tunnel",
        "--origincert",
        r"C:\Users\tester\.cloudflared\cert.pem",
        "route",
        "dns",
        "my-tunnel",
        "app.example.com",
    ]


def test_tailscale_start_uses_logged_in_dns_name_and_background_funnel() -> None:
    provider = tunnel_providers.TailscaleProvider(local_port=8001)
    status_output = json.dumps({
        "BackendState": "Running",
        "Self": {"DNSName": "xianyu-hunter.example.ts.net."},
    })

    with (
        patch.object(provider, "_ensure_binary", return_value=Path("tailscale.exe")),
        patch(
            "xianyu_hunter.web.services.tunnel_providers.subprocess.run",
            return_value=CompletedProcess([], 0, stdout=status_output, stderr=""),
        ) as run,
        patch(
            "xianyu_hunter.web.services.tunnel_providers.subprocess.Popen",
        ) as popen,
    ):
        # start() 用 Popen 非阻塞读取 funnel 输出，需 mock 进程的 stdout 行
        mock_proc = MagicMock()
        mock_proc.stdout.readline.return_value = "Funnel started on https://xianyu-hunter.example.ts.net"
        mock_proc.poll.return_value = None
        popen.return_value = mock_proc
        public_url = provider.start()

    assert public_url == "https://xianyu-hunter.example.ts.net"
    assert run.call_args_list[0].args[0] == ["tailscale.exe", "status", "--json"]
    assert popen.call_args.args[0] == [
        "tailscale.exe",
        "funnel",
        "--bg",
        "--yes",
        "http://127.0.0.1:8001",
    ]


def test_tailscale_start_rejects_logged_out_backend() -> None:
    provider = tunnel_providers.TailscaleProvider(local_port=8001)
    status_output = json.dumps({"BackendState": "NeedsLogin"})

    with (
        patch.object(provider, "_ensure_binary", return_value=Path("tailscale.exe")),
        patch(
            "xianyu_hunter.web.services.tunnel_providers.subprocess.run",
            return_value=CompletedProcess([], 0, stdout=status_output, stderr=""),
        ),
        pytest.raises(RuntimeError, match="登录 Tailscale"),
    ):
        provider.start()


def test_tailscale_start_explains_first_funnel_authorization_timeout() -> None:
    provider = tunnel_providers.TailscaleProvider(local_port=8001)
    status_output = json.dumps({
        "BackendState": "Running",
        "Self": {"DNSName": "xianyu-hunter.example.ts.net."},
    })

    with (
        patch.object(provider, "_ensure_binary", return_value=Path("tailscale.exe")),
        patch(
            "xianyu_hunter.web.services.tunnel_providers.subprocess.run",
            return_value=CompletedProcess([], 0, stdout=status_output, stderr=""),
        ),
        patch(
            "xianyu_hunter.web.services.tunnel_providers.subprocess.Popen",
        ) as popen,
        pytest.raises(RuntimeError, match="首次启用 Funnel.*授权"),
    ):
        # 模拟首次启用 Funnel：tailscale 输出一次性授权链接后不退出
        mock_proc = MagicMock()
        mock_proc.stdout.readline.return_value = (
            "Please visit: https://login.tailscale.com/f/funnel?node=abc123"
        )
        mock_proc.poll.return_value = None
        popen.return_value = mock_proc
        provider.start()


def test_tailscale_status_reads_persistent_funnel_configuration() -> None:
    provider = tunnel_providers.TailscaleProvider(local_port=8001)
    provider._binary_path = Path("tailscale.exe")
    status_output = json.dumps({
        "AllowFunnel": {"xianyu-hunter.example.ts.net:443": True},
    })

    with patch(
        "xianyu_hunter.web.services.tunnel_providers.subprocess.run",
        return_value=CompletedProcess([], 0, stdout=status_output, stderr=""),
    ):
        assert provider.status == "running"

    assert provider.public_url == "https://xianyu-hunter.example.ts.net"


def test_tailscale_stop_disables_only_https_funnel() -> None:
    provider = tunnel_providers.TailscaleProvider(local_port=8001)
    provider._binary_path = Path("tailscale.exe")
    provider._public_url = "https://xianyu-hunter.example.ts.net"

    with patch(
        "xianyu_hunter.web.services.tunnel_providers.subprocess.run",
        return_value=CompletedProcess([], 0, stdout="", stderr=""),
    ) as run:
        provider.stop()

    assert run.call_args.args[0] == [
        "tailscale.exe",
        "funnel",
        "off",
    ]
    assert provider.public_url is None


def test_tailscale_stop_path_prefix_clears_binary_path() -> None:
    """path_prefix 模式下 stop 不调用 funnel off，但清除 _binary_path 使 status 返回 stopped"""
    provider = tunnel_providers.TailscaleProvider(local_port=8001, path_prefix="/xianyu/")
    provider._binary_path = Path("tailscale.exe")
    provider._public_url = "https://xianyu-hunter.example.ts.net/xianyu/"

    with patch(
        "xianyu_hunter.web.services.tunnel_providers.subprocess.run",
    ) as run:
        provider.stop()

    # path_prefix 模式不应调用 funnel off（避免影响其他应用）
    run.assert_not_called()
    assert provider.public_url is None
    # 修复后：_binary_path 被清除，status 应短路返回 "stopped"
    assert provider.status == "stopped"


def test_tailscale_is_registered_provider() -> None:
    provider = tunnel_providers.create_provider("tailscale", local_port=8001)
    assert isinstance(provider, tunnel_providers.TailscaleProvider)
