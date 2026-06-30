# tests/test_api_tunnel.py
"""Tunnel API 端点测试"""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from xianyu_hunter.web.app import create_app
    return TestClient(create_app())


def test_tunnel_status_initial(client):
    """GET /api/tunnel/status 未启动时返回 stopped"""
    with patch("xianyu_hunter.web.routes.api_tunnel.get_tunnel_service") as mock_get:
        svc = MagicMock()
        svc.status = "stopped"
        svc.public_url = None
        mock_get.return_value = svc
        resp = client.get("/api/tunnel/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "stopped"
    assert data["public_url"] is None


def test_tunnel_start(client):
    """POST /api/tunnel/start 启动隧道并返回公网 URL"""
    with patch("xianyu_hunter.web.routes.api_tunnel.get_tunnel_service") as mock_get:
        svc = MagicMock()
        svc.start.return_value = "https://test.trycloudflare.com"
        svc.status = "running"
        svc.public_url = "https://test.trycloudflare.com"
        mock_get.return_value = svc
        resp = client.post("/api/tunnel/start")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"
    assert data["public_url"] == "https://test.trycloudflare.com"


def test_tunnel_stop(client):
    """POST /api/tunnel/stop 停止隧道"""
    with patch("xianyu_hunter.web.routes.api_tunnel.get_tunnel_service") as mock_get:
        svc = MagicMock()
        svc.status = "stopped"
        svc.public_url = None
        mock_get.return_value = svc
        resp = client.post("/api/tunnel/stop")
    assert resp.status_code == 200
    assert resp.json()["status"] == "stopped"
