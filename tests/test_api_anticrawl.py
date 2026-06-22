"""反爬登录 API 路由测试

验证 /api/anticrawl/* 端点的注册和基本功能：
1. 路由注册完整性
2. 各端点响应格式
3. LoginOrchestrator 集成正确性
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from xianyu_hunter.config import get_settings
from xianyu_hunter.web.app import app
from xianyu_hunter.modules.login_orchestrator import LoginOrchestrator, get_orchestrator
from xianyu_hunter.modules.login_strategy import LoginStrategy


client = TestClient(app)

# 认证 cookie：所有 /api/anticrawl/* 端点都需要 xh_token
_AUTH_COOKIE = {"xh_token": get_settings().web_token}


def _reset_orchestrator():
    """重置单例，确保每个测试干净启动"""
    import xianyu_hunter.modules.login_orchestrator as orch_mod
    orch_mod._orchestrator = None


class TestRouteRegistration:
    """路由注册测试"""

    def test_anticrawl_routes_registered(self):
        """所有反爬路由应正确注册"""
        paths = {getattr(r, "path", "") for r in app.routes}

        assert "/api/anticrawl/strategy" in paths
        assert "/api/anticrawl/initialize" in paths
        assert "/api/anticrawl/session/status" in paths
        assert "/api/anticrawl/session/start" in paths
        assert "/api/anticrawl/session/stop" in paths
        assert "/api/anticrawl/health" in paths
        assert "/api/anticrawl/fingerprint" in paths
        assert "/api/anticrawl/freq/stats" in paths
        assert "/api/anticrawl/freq/delay" in paths
        assert "/api/anticrawl/cookies/update" in paths
        assert "/api/anticrawl/cookies/layers" in paths
        assert "/api/anticrawl/cookies/invalidate" in paths
        assert "/api/anticrawl/strategy/set" in paths

    def test_no_double_prefix(self):
        """不应出现双重 /api 前缀"""
        paths = {getattr(r, "path", "") for r in app.routes}
        assert "/api/api/anticrawl" not in paths


class TestStrategyEndpoint:
    """策略评估端点测试"""

    def test_get_strategy_returns_evaluation(self):
        """GET /api/anticrawl/strategy 应返回策略评估"""
        _reset_orchestrator()

        resp = client.get("/api/anticrawl/strategy", cookies=_AUTH_COOKIE)
        assert resp.status_code == 200
        data = resp.json()

        assert data["ok"] is True
        assert "recommended" in data
        assert "reason" in data
        assert "available_strategies" in data
        assert "details" in data
        assert isinstance(data["available_strategies"], list)

    def test_set_current_strategy_valid(self):
        """POST /api/anticrawl/strategy/set 应接受有效策略名"""
        resp = client.post(
            "/api/anticrawl/strategy/set",
            json={"strategy": "qr_scan"},
            cookies=_AUTH_COOKIE,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["strategy"] == "qr_scan"

    def test_set_current_strategy_invalid(self):
        """POST /api/anticrawl/strategy/set 应拒绝无效策略名"""
        resp = client.post(
            "/api/anticrawl/strategy/set",
            json={"strategy": "invalid"},
            cookies=_AUTH_COOKIE,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False
        assert "error" in data
        assert "valid_strategies" in data


class TestInitializeEndpoint:
    """协调器初始化端点测试"""

    def test_initialize_launch_mode(self):
        """POST /api/anticrawl/initialize launch 模式应生成指纹"""
        _reset_orchestrator()

        resp = client.post(
            "/api/anticrawl/initialize",
            json={"use_cdp": False},
            cookies=_AUTH_COOKIE,
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["ok"] is True
        assert data["mode"] == "launch"
        assert data["fingerprint_profile"] is not None
        assert data["user_agent"] is not None
        assert data["stealth_scripts_count"] == 2  # fingerprint + awsc_spoof

    def test_initialize_cdp_mode(self):
        """POST /api/anticrawl/initialize CDP 模式应无指纹"""
        _reset_orchestrator()

        resp = client.post(
            "/api/anticrawl/initialize",
            json={"use_cdp": True},
            cookies=_AUTH_COOKIE,
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["ok"] is True
        assert data["mode"] == "cdp"
        assert data["fingerprint_profile"] is None
        assert data["stealth_scripts_count"] == 0


class TestSessionStatusEndpoint:
    """会话状态端点测试"""

    def test_get_session_status_default(self):
        """GET /api/anticrawl/session/status 未启动时应返回 inactive"""
        _reset_orchestrator()

        resp = client.get("/api/anticrawl/session/status", cookies=_AUTH_COOKIE)
        assert resp.status_code == 200
        data = resp.json()

        assert data["ok"] is True
        assert data["active"] is False
        assert "uptime_sec" in data
        assert "cookie_layers" in data
        assert "freq_stats" in data

    def test_get_session_status_after_initialize(self):
        """初始化后状态应包含指纹 profile"""
        _reset_orchestrator()

        client.post(
            "/api/anticrawl/initialize",
            json={"use_cdp": False},
            cookies=_AUTH_COOKIE,
        )

        resp = client.get("/api/anticrawl/session/status", cookies=_AUTH_COOKIE)
        data = resp.json()
        assert data["fingerprint_profile"] != ""


class TestFingerprintEndpoint:
    """指纹信息端点测试"""

    def test_get_fingerprint_launch_mode(self):
        """launch 模式应返回完整指纹信息"""
        _reset_orchestrator()

        client.post(
            "/api/anticrawl/initialize",
            json={"use_cdp": False},
            cookies=_AUTH_COOKIE,
        )

        resp = client.get("/api/anticrawl/fingerprint", cookies=_AUTH_COOKIE)
        assert resp.status_code == 200
        data = resp.json()

        assert data["ok"] is True
        assert data["mode"] == "launch"
        assert data["profile"] is not None
        assert "name" in data["profile"]
        assert "ua" in data["profile"]
        assert "gpu_vendor" in data["profile"]
        assert data["stealth_scripts_count"] == 2

    def test_get_fingerprint_cdp_mode(self):
        """CDP 模式应返回空 profile"""
        _reset_orchestrator()

        client.post(
            "/api/anticrawl/initialize",
            json={"use_cdp": True},
            cookies=_AUTH_COOKIE,
        )

        resp = client.get("/api/anticrawl/fingerprint", cookies=_AUTH_COOKIE)
        data = resp.json()
        assert data["ok"] is True
        assert data["mode"] == "cdp"
        assert data["profile"] is None


class TestFreqStatsEndpoint:
    """频率伪装统计端点测试"""

    def test_get_freq_stats(self):
        """GET /api/anticrawl/freq/stats 应返回统计信息"""
        resp = client.get("/api/anticrawl/freq/stats", cookies=_AUTH_COOKIE)
        assert resp.status_code == 200
        data = resp.json()

        assert data["ok"] is True
        assert "total_requests" in data
        assert "noise_requests" in data
        assert "noise_ratio" in data

    def test_get_request_delay_valid(self):
        """GET /api/anticrawl/freq/delay 应返回延迟"""
        resp = client.get(
            "/api/anticrawl/freq/delay",
            params={"action": "search"},
            cookies=_AUTH_COOKIE,
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["ok"] is True
        assert data["action"] == "search"
        assert "delay_sec" in data
        assert isinstance(data["delay_sec"], (int, float))

    def test_get_request_delay_invalid(self):
        """无效操作类型应返回错误"""
        resp = client.get(
            "/api/anticrawl/freq/delay",
            params={"action": "invalid"},
            cookies=_AUTH_COOKIE,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False
        assert "valid_actions" in data


class TestCookieLayersEndpoint:
    """Cookie 层管理端点测试"""

    def test_get_cookie_layers_default(self):
        """GET /api/anticrawl/cookies/layers 应返回三层状态"""
        _reset_orchestrator()

        resp = client.get("/api/anticrawl/cookies/layers", cookies=_AUTH_COOKIE)
        assert resp.status_code == 200
        data = resp.json()

        assert data["ok"] is True
        assert "identity" in data["layers"]
        assert "session" in data["layers"]
        assert "tracking" in data["layers"]
        # 默认应全部无效
        assert data["layers"]["identity"]["valid"] is False

    def test_invalidate_cookie_layer_valid(self):
        """POST /api/anticrawl/cookies/invalidate 应接受有效层名"""
        resp = client.post(
            "/api/anticrawl/cookies/invalidate",
            json={"layer": "session"},
            cookies=_AUTH_COOKIE,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True

    def test_invalidate_cookie_layer_invalid(self):
        """无效层名应返回错误"""
        resp = client.post(
            "/api/anticrawl/cookies/invalidate",
            json={"layer": "invalid"},
            cookies=_AUTH_COOKIE,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False
        assert "valid_layers" in data

    def test_invalidate_identity_cascades(self):
        """失效 identity 层应级联失效 session 层"""
        _reset_orchestrator()

        # 先设置 identity 有效
        orch = get_orchestrator()
        orch.set_cookie_writer(lambda c: len(c))
        orch.on_login_success({"unb": "123", "cookie2": "abc"})
        orch.on_login_success({"_m_h5_tk": "tk", "_m_h5_tk_enc": "enc"})

        # 失效 identity
        resp = client.post(
            "/api/anticrawl/cookies/invalidate",
            json={"layer": "identity"},
            cookies=_AUTH_COOKIE,
        )
        data = resp.json()
        assert data["ok"] is True
        assert data["cascaded"] is True

        # 验证 session 也失效
        layers = client.get(
            "/api/anticrawl/cookies/layers",
            cookies=_AUTH_COOKIE,
        ).json()["layers"]
        assert layers["identity"]["valid"] is False
        assert layers["session"]["valid"] is False


class TestCookiesUpdateEndpoint:
    """Cookie 更新端点测试"""

    def test_update_cookies_empty(self):
        """空 cookies 应返回错误"""
        resp = client.post(
            "/api/anticrawl/cookies/update",
            json={"cookies": {}},
            cookies=_AUTH_COOKIE,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False

    def test_update_cookies_identity_only(self):
        """仅 identity 层 Cookie 应成功更新"""
        _reset_orchestrator()

        cookies = {"unb": "123456", "cookie2": "abc"}
        resp = client.post(
            "/api/anticrawl/cookies/update",
            json={"cookies": cookies},
            cookies=_AUTH_COOKIE,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["written"] > 0


class TestHealthEndpoint:
    """健康检查端点测试"""

    def test_health_without_checkers(self):
        """未配置检查器时应返回提示"""
        _reset_orchestrator()

        resp = client.get("/api/anticrawl/health", cookies=_AUTH_COOKIE)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False
        assert "未配置" in data["error"]


class TestSessionStartStop:
    """会话启动/停止端点测试"""

    def test_stop_session_when_not_active(self):
        """未启动时停止应返回错误"""
        _reset_orchestrator()

        resp = client.post("/api/anticrawl/session/stop", cookies=_AUTH_COOKIE)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False
        assert "未启动" in data["error"]

    def test_start_then_stop_session(self):
        """启动后停止应成功"""
        _reset_orchestrator()

        # 启动会话（使用 mock cookie_provider）
        resp = client.post("/api/anticrawl/session/start", cookies=_AUTH_COOKIE)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True

        # 停止会话
        resp = client.post("/api/anticrawl/session/stop", cookies=_AUTH_COOKIE)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
