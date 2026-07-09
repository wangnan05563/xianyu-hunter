# tests/test_tunnel_service.py
"""TunnelService 单元测试：验证 provider 委托与生命周期管理"""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def tunnel_service():
    """构造 TunnelService 实例，mock 掉 provider 创建"""
    from xianyu_hunter.web.services.tunnel_service import TunnelService
    svc = TunnelService(local_port=8001)
    # mock provider：避免触发真实二进制下载与进程启动
    mock_provider = MagicMock()
    mock_provider.status = "stopped"
    mock_provider.public_url = None
    mock_provider.start.return_value = "https://abc123.trycloudflare.com"
    svc._provider = mock_provider
    svc._provider_name = "cloudflare"
    return svc


def test_tunnel_service_initial_state():
    """新创建的 TunnelService（无 provider）应处于 stopped 状态"""
    from xianyu_hunter.web.services.tunnel_service import TunnelService
    svc = TunnelService()
    assert svc.status == "stopped"
    assert svc.public_url is None


def test_tunnel_service_start_assigns_url(tunnel_service):
    """启动后应返回 provider 分配的公网 URL"""
    url = tunnel_service.start()
    assert url.startswith("https://")
    tunnel_service._provider.start.assert_called_once()


def test_tunnel_service_stop_clears_state(tunnel_service):
    """停止后应委托 provider.stop"""
    tunnel_service.stop()
    tunnel_service._provider.stop.assert_called_once()


def test_tunnel_service_status_reflects_provider(tunnel_service):
    """status 应委托给 provider"""
    tunnel_service._provider.status = "running"
    assert tunnel_service.status == "running"

    tunnel_service._provider.status = "stopped"
    assert tunnel_service.status == "stopped"


def test_tunnel_service_public_url_reflects_provider(tunnel_service):
    """public_url 应委托给 provider"""
    tunnel_service._provider.public_url = "https://test.trycloudflare.com"
    assert tunnel_service.public_url == "https://test.trycloudflare.com"
