# tests/test_tunnel_service.py
"""TunnelService 单元测试：验证 cloudflare-tunnel 生命周期管理"""
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


@pytest.fixture
def tunnel_service():
    """构造 TunnelService 实例，mock 掉二进制路径检查"""
    from xianyu_hunter.web.services.tunnel_service import TunnelService
    with patch.object(TunnelService, "_ensure_binary", return_value=Path("/fake/cloudflared")):
        return TunnelService(local_port=8000)


def test_tunnel_service_initial_state(tunnel_service):
    """新创建的 TunnelService 应处于 stopped 状态"""
    assert tunnel_service.status == "stopped"
    assert tunnel_service.public_url is None


def test_tunnel_service_start_assigns_url(tunnel_service):
    """启动后应分配 HTTPS 公网域名"""
    with patch.object(tunnel_service, "_run_cloudflared") as mock_run:
        mock_run.return_value = "https://abc123.quicktunnel.cfargotunnel.com"
        url = tunnel_service.start()
    assert url.startswith("https://")
    assert ".cfargotunnel.com" in url
    assert tunnel_service.status == "running"


def test_tunnel_service_stop_clears_state(tunnel_service):
    """停止后应清除 URL 与进程"""
    tunnel_service._process = MagicMock()
    tunnel_service._public_url = "https://test.cfargotunnel.com"
    tunnel_service.stop()
    assert tunnel_service.status == "stopped"
    assert tunnel_service.public_url is None


def test_tunnel_service_status_reflects_process(tunnel_service):
    """status 应反映进程存活状态"""
    tunnel_service._process = MagicMock()
    tunnel_service._process.poll.return_value = None  # 进程运行中
    assert tunnel_service.status == "running"

    tunnel_service._process.poll.return_value = 0  # 进程已退出
    assert tunnel_service.status == "stopped"
