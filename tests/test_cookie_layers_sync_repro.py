"""复现用户报告的「更新Cookie后三类仍显示失效」问题。

目标：
1. 复现服务重启后 /cookies/layers 返回失效（即使 JSON 中有有效 Cookie）
2. 验证 /cookies/update 后 /cookies/layers 是否正确显示有效
3. 覆盖正常更新、异常处理、边界条件场景
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from xianyu_hunter.config import get_settings
from xianyu_hunter.web.app import app
from xianyu_hunter.modules.login_orchestrator import get_orchestrator
from xianyu_hunter.modules.cookie_rotator import CookieLayer
from xianyu_hunter.web.services.cookie_store import get_cookie_store


client = TestClient(app)
_AUTH_COOKIE = {"xh_token": get_settings().web_token}
_COOKIE_JSON = Path("data") / "cookies_default.json"


def _reset_orchestrator():
    """重置单例，确保每个测试干净启动"""
    import xianyu_hunter.modules.login_orchestrator as orch_mod
    orch_mod._orchestrator = None


def _backup_json() -> dict | None:
    """备份当前 JSON 数据，测试后恢复"""
    if _COOKIE_JSON.exists():
        return json.loads(_COOKIE_JSON.read_text(encoding="utf-8"))
    return None


def _restore_json(data: dict | None) -> None:
    """恢复 JSON 数据"""
    if data is None:
        if _COOKIE_JSON.exists():
            _COOKIE_JSON.unlink()
    else:
        _COOKIE_JSON.parent.mkdir(parents=True, exist_ok=True)
        _COOKIE_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    # 清除 CookieStore 缓存
    store = get_cookie_store()
    store._cache = None
    store._cache_ts = 0.0


def _write_mock_json(cookies: list[dict], method: str = "test") -> None:
    """写入 mock JSON 数据"""
    _COOKIE_JSON.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "exported_at": time.time(),
        "method": method,
        "cookie_count": len(cookies),
        "cookies": cookies,
    }
    _COOKIE_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    # 清除 CookieStore 缓存
    store = get_cookie_store()
    store._cache = None
    store._cache_ts = 0.0


def _real_cookie_sample() -> list[dict]:
    """构造真实格式的 Cookie 样本（非测试数据）"""
    return [
        {"name": "unb", "value": "2209384756290", "domain": ".goofish.com", "path": "/", "expires": -1},
        {"name": "cookie2", "value": "c8421f9e5b6d7a3b9c0e1f2d3a4b5c6d", "domain": ".goofish.com", "path": "/", "expires": -1},
        {"name": "sgcookie", "value": "E100zRxEj%2FbXi%2B%2FbxVSJT%2Fg%2FaDG6MgjhL", "domain": ".goofish.com", "path": "/", "expires": -1},
        {"name": "_m_h5_tk", "value": "c7b2c44645275604a525e6287fea2c3a_1782530783399", "domain": ".goofish.com", "path": "/", "expires": -1},
        {"name": "_m_h5_tk_enc", "value": "abc123enc456def789", "domain": ".goofish.com", "path": "/", "expires": -1},
        {"name": "cna", "value": "YcHJH+IsChycAXTQMyRJqgj+", "domain": ".goofish.com", "path": "/", "expires": -1},
        {"name": "tfstk", "value": "e1NjUcFrYBFsf7ReJcFrZ", "domain": ".goofish.com", "path": "/", "expires": -1},
    ]


# ============== 复现测试：服务重启后 /cookies/layers 显示失效 ==============


class TestLayersEndpointAutoSync:
    """复现问题1：服务重启后 /cookies/layers 返回失效状态

    场景：用户登录成功后，JSON 中已有有效 Cookie，但服务重启后
    /cookies/layers 端点直接从内存读取，内存状态默认 False，
    导致前端显示三类 Cookie 全部失效，即使 JSON 中有有效数据。
    """

    def setup_method(self):
        """每个测试前备份并重置状态"""
        self._backup = _backup_json()
        _reset_orchestrator()

    def teardown_method(self):
        """测试后恢复 JSON"""
        _restore_json(self._backup)
        _reset_orchestrator()

    def test_layers_returns_invalid_after_restart_with_valid_json(self):
        """复现：JSON 有有效 Cookie，但服务重启后 /cookies/layers 返回 False"""
        # 准备：JSON 中写入有效 Cookie
        _write_mock_json(_real_cookie_sample())
        _reset_orchestrator()  # 模拟服务重启：内存状态重置

        # 执行：调用 /cookies/layers
        resp = client.get("/api/anticrawl/cookies/layers", cookies=_AUTH_COOKIE)
        data = resp.json()

        # 断言：当前实现会返回 valid=False（这就是 bug）
        # 期望：应该自动同步层状态，返回 valid=True
        layers = data["layers"]
        print(f"\n[复现] 服务重启后 /cookies/layers 返回: {layers}")
        # 这个断言会失败，证明 bug 存在
        assert layers["identity"]["valid"] is True, "JSON 有 identity Cookie，应自动同步为有效"
        assert layers["session"]["valid"] is True, "JSON 有 session Cookie，应自动同步为有效"
        assert layers["tracking"]["valid"] is True, "JSON 有 tracking Cookie，应自动同步为有效"


class TestUpdateCookiesSync:
    """复现问题2：/cookies/update 后 /cookies/layers 应正确显示有效"""

    def setup_method(self):
        self._backup = _backup_json()
        _reset_orchestrator()

    def teardown_method(self):
        _restore_json(self._backup)
        _reset_orchestrator()

    def test_update_all_three_layers(self):
        """正常更新：传入三层 Cookie，应全部显示有效"""
        # 准备：清空 JSON
        _restore_json(None)

        cookies = {
            "unb": "2209384756290",
            "cookie2": "c8421f9e5b6d7a3b9c0e1f2d3a4b5c6d",
            "sgcookie": "E100zRxEj%2FbXi",
            "_m_h5_tk": "c7b2c44645275604a525e6287fea2c3a_1782530783399",
            "_m_h5_tk_enc": "abc123enc456",
            "cna": "YcHJH+IsChycAXTQ",
            "tfstk": "e1NjUcFrYBFsf",
        }

        resp = client.post(
            "/api/anticrawl/cookies/update",
            json={"cookies": cookies},
            cookies=_AUTH_COOKIE,
        )
        data = resp.json()
        assert data["ok"] is True, f"更新应成功: {data}"

        # 验证：/cookies/layers 应返回三层全部有效
        layers = client.get(
            "/api/anticrawl/cookies/layers",
            cookies=_AUTH_COOKIE,
        ).json()["layers"]

        assert layers["identity"]["valid"] is True, "identity 层应有效"
        assert layers["session"]["valid"] is True, "session 层应有效"
        assert layers["tracking"]["valid"] is True, "tracking 层应有效"

    def test_update_partial_layers_only_updates_provided(self):
        """边界条件：仅传入部分层的 Cookie，只应更新该层"""
        _restore_json(None)

        # 只传入 identity 层 Cookie
        cookies = {
            "unb": "2209384756290",
            "cookie2": "c8421f9e5b6d7a3b9c0e1f2d3a4b5c6d",
        }

        resp = client.post(
            "/api/anticrawl/cookies/update",
            json={"cookies": cookies},
            cookies=_AUTH_COOKIE,
        )
        assert resp.json()["ok"] is True

        layers = client.get(
            "/api/anticrawl/cookies/layers",
            cookies=_AUTH_COOKIE,
        ).json()["layers"]

        assert layers["identity"]["valid"] is True, "identity 层应有效"
        # session 和 tracking 未传入，应保持无效
        assert layers["session"]["valid"] is False
        assert layers["tracking"]["valid"] is False

    def test_update_empty_cookies_returns_error(self):
        """异常处理：空 cookies 应返回错误"""
        resp = client.post(
            "/api/anticrawl/cookies/update",
            json={"cookies": {}},
            cookies=_AUTH_COOKIE,
        )
        data = resp.json()
        assert data["ok"] is False
        assert "为空" in data["error"]

    def test_update_test_data_only_returns_error(self):
        """异常处理：全部测试数据应返回错误，不污染层状态"""
        _restore_json(None)

        # 全部是测试数据
        cookies = {
            "unb": "123456",
            "cookie2": "abc",
            "_m_h5_tk": "abc",
        }

        resp = client.post(
            "/api/anticrawl/cookies/update",
            json={"cookies": cookies},
            cookies=_AUTH_COOKIE,
        )
        data = resp.json()
        assert data["ok"] is False, "全测试数据应失败"

        # 层状态应保持无效（不因测试数据污染）
        layers = client.get(
            "/api/anticrawl/cookies/layers",
            cookies=_AUTH_COOKIE,
        ).json()["layers"]
        assert layers["identity"]["valid"] is False

    def test_update_mixed_test_and_real_cookies(self):
        """边界条件：测试数据 + 真实数据混合，应只写入真实数据

        验证 Bug 3 修复：update_cookies 用 fresh_data（JSON 实际内容）构造 cookie_map，
        而非 merged_list（包含测试数据）。这样测试数据被 export_cookies 过滤后，
        对应层状态不会误判为有效。
        """
        _restore_json(None)

        cookies = {
            "unb": "123456",  # 测试数据，应被过滤
            "_m_h5_tk": "c7b2c44645275604a525e6287fea2c3a_1782530783399",  # 真实
            "cna": "YcHJH+IsChycAXTQ",  # 真实
        }

        resp = client.post(
            "/api/anticrawl/cookies/update",
            json={"cookies": cookies},
            cookies=_AUTH_COOKIE,
        )
        data = resp.json()
        assert data["ok"] is True

        # identity 层应保持无效（unb=123456 被过滤，JSON 中没有 identity Cookie）
        layers = client.get(
            "/api/anticrawl/cookies/layers",
            cookies=_AUTH_COOKIE,
        ).json()["layers"]
        assert layers["identity"]["valid"] is False, "identity 层 unb 被过滤，应无效"
        # SESSION 依赖 IDENTITY：identity 无效时 session 也无效（即使 _m_h5_tk 是真实的）
        assert layers["session"]["valid"] is False
        assert layers["tracking"]["valid"] is True  # tracking 无依赖，cna 是真实的

    def test_update_after_restart_with_existing_json(self):
        """复现场景：服务重启后 JSON 有数据，/cookies/layers 应自动同步显示有效

        修复后：/cookies/layers 端点会读取 JSON 实际内容并同步层状态，
        所以服务重启后即使内存状态为 False，也会自动恢复为 True。
        """
        # 准备：JSON 中已有有效 Cookie（模拟之前登录过）
        _write_mock_json(_real_cookie_sample())
        _reset_orchestrator()  # 模拟服务重启

        # 验证：重启后 /cookies/layers 应自动同步，返回有效状态
        layers_before = client.get(
            "/api/anticrawl/cookies/layers",
            cookies=_AUTH_COOKIE,
        ).json()["layers"]
        assert layers_before["identity"]["valid"] is True, "重启后应自动同步为有效"
        assert layers_before["session"]["valid"] is True
        assert layers_before["tracking"]["valid"] is True

        # 执行：用户点击"更新Cookie"（用 JSON 中已有的 cookie 重新提交）
        cookies = {c["name"]: c["value"] for c in _real_cookie_sample()}
        resp = client.post(
            "/api/anticrawl/cookies/update",
            json={"cookies": cookies},
            cookies=_AUTH_COOKIE,
        )
        assert resp.json()["ok"] is True

        # 验证：更新后层状态保持有效
        layers_after = client.get(
            "/api/anticrawl/cookies/layers",
            cookies=_AUTH_COOKIE,
        ).json()["layers"]
        assert layers_after["identity"]["valid"] is True
        assert layers_after["session"]["valid"] is True
        assert layers_after["tracking"]["valid"] is True


class TestExportCookiesSqliteSync:
    """验证 export_cookies 内部 _sync_to_sqlite 的传参问题"""

    def setup_method(self):
        """每个测试前备份并重置状态，防止测试数据污染生产 JSON"""
        self._backup = _backup_json()
        _reset_orchestrator()

    def teardown_method(self):
        """测试后恢复 JSON，清除 CookieStore 缓存"""
        _restore_json(self._backup)
        _reset_orchestrator()

    def test_sync_to_sqlite_uses_filtered_cookies(self):
        """export_cookies 应将 filtered（过滤后）传给 _sync_to_sqlite，而非原始 cookies"""
        store = get_cookie_store()
        # 用 mock 捕获 _sync_to_sqlite 的入参
        with pytest.MonkeyPatch().context() as mp:
            captured = []
            original_sync = store._sync_to_sqlite

            def spy_sync(cookies):
                captured.append(cookies)
                return original_sync(cookies)

            mp.setattr(store, "_sync_to_sqlite", spy_sync)

            # 传入混合数据：测试数据 + 真实格式数据
            # 注意：_m_h5_tk 必须使用真实格式（32位hex_13位时间戳），
            # 否则会被 is_test_cookie 的格式校验拦截
            mixed = [
                {"name": "unb", "value": "123456", "domain": ".goofish.com", "path": "/"},
                {"name": "_m_h5_tk", "value": "c7b2c44645275604a525e6287fea2c3a_1782530783399", "domain": ".goofish.com", "path": "/"},
            ]
            store.export_cookies(mixed, method="test")

            # _sync_to_sqlite 应只收到过滤后的真实数据
            assert len(captured) == 1
            synced_names = {c["name"] for c in captured[0]}
            assert "unb" not in synced_names, "测试数据不应同步到 SQLite"
            assert "_m_h5_tk" in synced_names
