"""反爬登录 API 路由测试

验证 /api/anticrawl/* 端点的注册和基本功能：
1. 路由注册完整性
2. 各端点响应格式
3. LoginOrchestrator 集成正确性
4. Cookie 健康检查修复验证
"""
from __future__ import annotations

import time

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


# ============== 辅助函数 ==============

def _make_mock_cookie_data(expires_offset: float = 3600, include_identity: bool = True,
                           include_token: bool = True, extra_expired: list[str] | None = None):
    """构造模拟的 Cookie JSON 数据

    Args:
        expires_offset: Cookie 过期时间偏移（秒），正数表示未来过期
        include_identity: 是否包含 identity 层 Cookie
        include_token: 是否包含 _m_h5_tk
        extra_expired: 额外需要标记为已过期的 Cookie 名称列表
    """
    now = time.time()
    cookies = []
    if include_token:
        cookies.append({"name": "_m_h5_tk", "value": "token_123", "domain": ".goofish.com",
                        "path": "/", "expires": now + expires_offset})
        cookies.append({"name": "_m_h5_tk_enc", "value": "enc_123", "domain": ".goofish.com",
                        "path": "/", "expires": now + expires_offset})
    if include_identity:
        cookies.append({"name": "unb", "value": "123456", "domain": ".goofish.com",
                        "path": "/", "expires": now + expires_offset})
        cookies.append({"name": "cookie2", "value": "abc", "domain": ".goofish.com",
                        "path": "/", "expires": now + expires_offset})
        cookies.append({"name": "sgcookie", "value": "sg", "domain": ".goofish.com",
                        "path": "/", "expires": now + expires_offset})
    # 额外的已过期 Cookie
    if extra_expired:
        for name in extra_expired:
            cookies.append({"name": name, "value": "expired_val", "domain": ".goofish.com",
                            "path": "/", "expires": now - 100})
    return {
        "exported_at": now,
        "method": "browser",
        "cookie_count": len(cookies),
        "cookies": cookies,
    }


class TestCookieCheckerFix:
    """Cookie 健康检查修复测试

    验证修复：Cookie 有效但 CookieRotator 层状态未初始化时，
    健康检查应正确判定 Cookie 有效（而非误判为无效）。

    根因：browser_login / auth_helper / browser_import / cookie_inject 等登录路径
    只调用 export_cookies 写入 JSON，未调用 on_login_success 更新层状态，
    导致 cookie_checker 依赖的 identity_state.valid 始终为 False。
    """

    def test_cookie_valid_when_layer_not_initialized(self, monkeypatch):
        """Cookie 在 JSON 中有效但层状态未初始化时应判定为有效

        复现用户报告的问题：Cookie 处于有效期内，点击检查按钮显示"Cookie无效"。
        """
        _reset_orchestrator()

        mock_data = _make_mock_cookie_data(expires_offset=3600)
        from xianyu_hunter.web.services import cookie_store as cs_module
        monkeypatch.setattr(cs_module.CookieStore, "_read_json", lambda self: mock_data)

        # 初始化协调器（配置健康检查器）
        client.post(
            "/api/anticrawl/initialize",
            json={"use_cdp": False},
            cookies=_AUTH_COOKIE,
        )

        # 不调用 on_login_success，模拟浏览器登录路径
        # CookieRotator 的 identity 层状态仍为默认 False

        resp = client.get("/api/anticrawl/health", cookies=_AUTH_COOKIE)
        data = resp.json()

        assert data["ok"] is True
        assert data["cookie_valid"] is True, "Cookie 有效期内应判定为有效"

    def test_cookie_invalid_when_expired(self, monkeypatch):
        """Cookie 已过期时应判定为无效"""
        _reset_orchestrator()

        # expires_offset 为负数表示已过期
        mock_data = _make_mock_cookie_data(expires_offset=-100)
        from xianyu_hunter.web.services import cookie_store as cs_module
        monkeypatch.setattr(cs_module.CookieStore, "_read_json", lambda self: mock_data)

        client.post(
            "/api/anticrawl/initialize",
            json={"use_cdp": False},
            cookies=_AUTH_COOKIE,
        )

        resp = client.get("/api/anticrawl/health", cookies=_AUTH_COOKIE)
        data = resp.json()

        assert data["ok"] is True
        assert data["cookie_valid"] is False, "已过期 Cookie 应判定为无效"

    def test_cookie_invalid_when_no_token(self, monkeypatch):
        """缺少 _m_h5_tk 时应判定为无效"""
        _reset_orchestrator()

        mock_data = _make_mock_cookie_data(include_token=False)
        from xianyu_hunter.web.services import cookie_store as cs_module
        monkeypatch.setattr(cs_module.CookieStore, "_read_json", lambda self: mock_data)

        client.post(
            "/api/anticrawl/initialize",
            json={"use_cdp": False},
            cookies=_AUTH_COOKIE,
        )

        resp = client.get("/api/anticrawl/health", cookies=_AUTH_COOKIE)
        data = resp.json()

        assert data["ok"] is True
        assert data["cookie_valid"] is False

    def test_cookie_invalid_when_no_identity(self, monkeypatch):
        """缺少 identity 层 Cookie 时应判定为无效"""
        _reset_orchestrator()

        mock_data = _make_mock_cookie_data(include_identity=False)
        from xianyu_hunter.web.services import cookie_store as cs_module
        monkeypatch.setattr(cs_module.CookieStore, "_read_json", lambda self: mock_data)

        client.post(
            "/api/anticrawl/initialize",
            json={"use_cdp": False},
            cookies=_AUTH_COOKIE,
        )

        resp = client.get("/api/anticrawl/health", cookies=_AUTH_COOKIE)
        data = resp.json()

        assert data["ok"] is True
        assert data["cookie_valid"] is False

    def test_cookie_invalid_when_no_data(self, monkeypatch):
        """JSON 无 Cookie 数据时应判定为无效"""
        _reset_orchestrator()

        from xianyu_hunter.web.services import cookie_store as cs_module
        monkeypatch.setattr(cs_module.CookieStore, "_read_json", lambda self: None)

        client.post(
            "/api/anticrawl/initialize",
            json={"use_cdp": False},
            cookies=_AUTH_COOKIE,
        )

        resp = client.get("/api/anticrawl/health", cookies=_AUTH_COOKIE)
        data = resp.json()

        assert data["ok"] is True
        assert data["cookie_valid"] is False

    def test_layer_state_auto_synced(self, monkeypatch):
        """Cookie 有效时层状态应自动同步"""
        _reset_orchestrator()

        mock_data = _make_mock_cookie_data(expires_offset=3600)
        from xianyu_hunter.web.services import cookie_store as cs_module
        monkeypatch.setattr(cs_module.CookieStore, "_read_json", lambda self: mock_data)

        client.post(
            "/api/anticrawl/initialize",
            json={"use_cdp": False},
            cookies=_AUTH_COOKIE,
        )

        # 健康检查前，层状态应为默认 False
        layers_before = client.get(
            "/api/anticrawl/cookies/layers",
            cookies=_AUTH_COOKIE,
        ).json()["layers"]
        assert layers_before["identity"]["valid"] is False

        # 执行健康检查（触发自动同步）
        client.get("/api/anticrawl/health", cookies=_AUTH_COOKIE)

        # 健康检查后，identity 和 session 层应已同步为有效
        layers_after = client.get(
            "/api/anticrawl/cookies/layers",
            cookies=_AUTH_COOKIE,
        ).json()["layers"]
        assert layers_after["identity"]["valid"] is True
        assert layers_after["session"]["valid"] is True

    def test_cookie_valid_with_legacy_data_no_expires(self, monkeypatch):
        """旧版数据（无 expires 字段）应兼容处理，视为 session cookie 不过期"""
        _reset_orchestrator()

        now = time.time()
        # 旧版格式：无 expires 字段
        mock_data = {
            "exported_at": now,
            "method": "browser",
            "cookie_count": 5,
            "cookies": [
                {"name": "_m_h5_tk", "value": "token_123", "domain": ".goofish.com", "path": "/"},
                {"name": "_m_h5_tk_enc", "value": "enc_123", "domain": ".goofish.com", "path": "/"},
                {"name": "unb", "value": "123456", "domain": ".goofish.com", "path": "/"},
                {"name": "cookie2", "value": "abc", "domain": ".goofish.com", "path": "/"},
                {"name": "sgcookie", "value": "sg", "domain": ".goofish.com", "path": "/"},
            ],
        }
        from xianyu_hunter.web.services import cookie_store as cs_module
        monkeypatch.setattr(cs_module.CookieStore, "_read_json", lambda self: mock_data)

        client.post(
            "/api/anticrawl/initialize",
            json={"use_cdp": False},
            cookies=_AUTH_COOKIE,
        )

        resp = client.get("/api/anticrawl/health", cookies=_AUTH_COOKIE)
        data = resp.json()

        assert data["ok"] is True
        assert data["cookie_valid"] is True, "旧版数据无 expires 字段应视为有效"
