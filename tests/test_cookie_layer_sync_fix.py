"""验证 cookie 层状态同步修复的正确性

覆盖本次修复的 4 类缺陷：
1. sync_cookie_layers_from_json 辅助函数：从 JSON 同步层状态
2. CookieStore.update_cookie_values：MTOP token 刷新的合并写入
3. cookie_checker 不覆盖主动失效：updated_at==0.0 才同步
4. 登录路径写后钩子：层状态与 JSON 一致

测试隔离：conftest.py 的 autouse fixture 已自动隔离 CookieStore JSON 路径，
所有写入操作落到 tmp_path，不会污染生产 data/cookies.json。
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from xianyu_hunter.config import get_settings
from xianyu_hunter.web.app import app
from xianyu_hunter.modules.login_orchestrator import (
    get_orchestrator,
    sync_cookie_layers_from_json,
)
from xianyu_hunter.modules.cookie_rotator import CookieLayer
from xianyu_hunter.web.services.cookie_store import get_cookie_store

client = TestClient(app)
_AUTH_COOKIE = {"xh_token": get_settings().web_token}
_COOKIE_JSON = Path("data") / "cookies.json"


def _reset_orchestrator() -> None:
    """重置 LoginOrchestrator 单例，确保每个测试干净启动"""
    import xianyu_hunter.modules.login_orchestrator as orch_mod
    orch_mod._orchestrator = None


def _write_mock_json(cookies: list[dict], method: str = "test") -> None:
    """写入 mock JSON 数据并清除 CookieStore 缓存"""
    _COOKIE_JSON.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "exported_at": time.time(),
        "method": method,
        "cookie_count": len(cookies),
        "cookies": cookies,
    }
    _COOKIE_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    store = get_cookie_store()
    store._cache = None
    store._cache_ts = 0.0


def _real_cookie_sample() -> list[dict]:
    """构造真实格式的 Cookie 样本（通过 is_test_cookie 校验）"""
    return [
        {"name": "unb", "value": "2209384756290", "domain": ".goofish.com", "path": "/", "expires": -1},
        {"name": "cookie2", "value": "c8421f9e5b6d7a3b9c0e1f2d3a4b5c6d", "domain": ".goofish.com", "path": "/", "expires": -1},
        {"name": "sgcookie", "value": "E100zRxEj%2FbXi%2B%2FbxVSJT%2Fg%2FaDG6MgjhL", "domain": ".goofish.com", "path": "/", "expires": -1},
        {"name": "_m_h5_tk", "value": "c7b2c44645275604a525e6287fea2c3a_1782530783399", "domain": ".goofish.com", "path": "/", "expires": -1},
        {"name": "_m_h5_tk_enc", "value": "abc123enc456def789", "domain": ".goofish.com", "path": "/", "expires": -1},
        {"name": "cna", "value": "YcHJH+IsChycAXTQMyRJqgj+", "domain": ".goofish.com", "path": "/", "expires": -1},
        {"name": "tfstk", "value": "e1NjUcFrYBFsf7ReJcFrZ", "domain": ".goofish.com", "path": "/", "expires": -1},
        {"name": "tracknick", "value": "user123", "domain": ".goofish.com", "path": "/", "expires": -1},
    ]


# ============== 缺陷1: sync_cookie_layers_from_json 辅助函数 ==============


class TestSyncCookieLayersFromJson:
    """验证 sync_cookie_layers_from_json 函数的正确性"""

    def setup_method(self):
        _reset_orchestrator()

    def teardown_method(self):
        _reset_orchestrator()

    def test_sync_from_valid_json(self):
        """正常场景：JSON 有完整 Cookie，同步后三层全部 valid"""
        _write_mock_json(_real_cookie_sample())
        orch = get_orchestrator()

        # 同步前：层状态默认 False（从未初始化）
        states = orch.cookie_rotator.get_all_states()
        assert states[CookieLayer.IDENTITY].valid is False
        assert states[CookieLayer.IDENTITY].updated_at == 0.0

        # 执行同步
        result = sync_cookie_layers_from_json()
        assert result is True

        # 同步后：三层全部 valid
        states = orch.cookie_rotator.get_all_states()
        assert states[CookieLayer.IDENTITY].valid is True
        assert states[CookieLayer.SESSION].valid is True
        assert states[CookieLayer.TRACKING].valid is True
        # updated_at 应被更新为非零
        assert states[CookieLayer.IDENTITY].updated_at > 0.0

    def test_sync_with_empty_json_returns_false(self):
        """边界条件：JSON 无数据时返回 False"""
        _write_mock_json([])
        result = sync_cookie_layers_from_json()
        assert result is False

    def test_sync_with_missing_json_returns_false(self):
        """边界条件：JSON 文件不存在时返回 False"""
        if _COOKIE_JSON.exists():
            _COOKIE_JSON.unlink()
        store = get_cookie_store()
        store._cache = None
        store._cache_ts = 0.0
        result = sync_cookie_layers_from_json()
        assert result is False

    def test_sync_is_idempotent(self):
        """健壮性：多次调用幂等，不会产生副作用"""
        _write_mock_json(_real_cookie_sample())
        orch = get_orchestrator()

        # 第一次同步
        sync_cookie_layers_from_json()
        states1 = orch.cookie_rotator.get_all_states()
        ts1 = states1[CookieLayer.IDENTITY].updated_at

        # 第二次同步
        time.sleep(0.01)  # 确保时间戳可能不同
        sync_cookie_layers_from_json()
        states2 = orch.cookie_rotator.get_all_states()

        # 状态应保持一致（valid 不变）
        assert states2[CookieLayer.IDENTITY].valid is True
        assert states2[CookieLayer.SESSION].valid is True
        assert states2[CookieLayer.TRACKING].valid is True

    def test_sync_after_invalidate_restores_valid(self):
        """功能验证：主动失效后再同步，应恢复为 valid

        场景：cookie_checker 检测到 RGV587 主动失效 identity 层后，
        用户重新登录，sync_cookie_layers_from_json 应恢复 valid=True
        """
        _write_mock_json(_real_cookie_sample())
        orch = get_orchestrator()

        # 先正常同步
        sync_cookie_layers_from_json()
        # 主动失效 identity 层（模拟 RGV587 检测）
        orch.cookie_rotator.invalidate_layer(CookieLayer.IDENTITY)
        states = orch.cookie_rotator.get_all_states()
        assert states[CookieLayer.IDENTITY].valid is False
        # invalidate_layer 不重置 updated_at（保留主动失效语义）
        assert states[CookieLayer.IDENTITY].updated_at > 0.0

        # 重新同步（模拟重新登录后调用）
        sync_cookie_layers_from_json()
        states = orch.cookie_rotator.get_all_states()
        assert states[CookieLayer.IDENTITY].valid is True

    def test_sync_filters_expired_cookies(self):
        """边界条件：过期 cookie 不应标记层为 valid（I1 修复验证）

        场景：JSON 中所有 identity 层 cookie（unb/cookie2/sgcookie）都过期，
        sync 后 identity 层应保持 invalid；session 层 cookie 未过期应 valid
        """
        # 构造过期 cookie：identity 层全部过期，session 层是 session cookie（不过期）
        past = time.time() - 3600
        expired_cookies = [
            {"name": "unb", "value": "2209384756290", "domain": ".goofish.com", "path": "/", "expires": past},
            {"name": "cookie2", "value": "c8421f9e5b6d7a3b9c0e1f2d3a4b5c6d", "domain": ".goofish.com", "path": "/", "expires": past},
            {"name": "sgcookie", "value": "E100zRxEj%2FbXi%2B%2FbxVSJT%2Fg%2FaDG6MgjhL", "domain": ".goofish.com", "path": "/", "expires": past},
            {"name": "_m_h5_tk", "value": "c7b2c44645275604a525e6287fea2c3a_1782530783399", "domain": ".goofish.com", "path": "/", "expires": -1},
            {"name": "_m_h5_tk_enc", "value": "abc123enc456def789", "domain": ".goofish.com", "path": "/", "expires": -1},
        ]
        _write_mock_json(expired_cookies)
        orch = get_orchestrator()

        sync_cookie_layers_from_json()
        states = orch.cookie_rotator.get_all_states()

        # identity 层所有 cookie 都过期，应被过滤，identity 层应 invalid
        assert states[CookieLayer.IDENTITY].valid is False, "过期 identity cookie 不应标记层为 valid"
        # session 层 cookie 未过期（session cookie，expires=-1），应 valid
        assert states[CookieLayer.SESSION].valid is True


# ============== 缺陷2: cookie_checker 不覆盖主动失效 ==============


class TestCookieCheckerPreservesInvalidation:
    """验证 cookie_checker 修复后不覆盖主动失效状态

    修复前：同步条件 `not identity_state.valid` 会覆盖主动失效
    修复后：同步条件 `identity_state.updated_at == 0.0` 只在从未初始化时同步
    """

    def setup_method(self):
        _reset_orchestrator()

    def teardown_method(self):
        _reset_orchestrator()

    def test_checker_does_not_override_active_invalidation(self):
        """关键场景：identity 层被主动失效后，cookie_checker 不应覆盖

        场景：collector 检测到 RGV587_ERROR 调用 invalidate_layer(identity)，
        此时 cookie_checker 检查 JSON 仍有效，但不应同步层状态（保留失效语义）
        """
        _write_mock_json(_real_cookie_sample())
        orch = get_orchestrator()

        # 模拟：先正常同步，然后主动失效
        sync_cookie_layers_from_json()
        orch.cookie_rotator.invalidate_layer(CookieLayer.IDENTITY)

        # 验证：失效后 updated_at 仍 > 0.0（不会被 cookie_checker 视为"从未初始化"）
        states = orch.cookie_rotator.get_all_states()
        identity_state = states[CookieLayer.IDENTITY]
        assert identity_state.valid is False
        assert identity_state.updated_at > 0.0  # 关键：不是从未初始化

        # 模拟 cookie_checker 的同步条件判断
        should_sync = (not identity_state) or (identity_state.updated_at == 0.0)
        assert should_sync is False, "主动失效后不应触发同步"

    def test_checker_syncs_when_never_initialized(self):
        """对比场景：从未初始化时（updated_at==0.0），cookie_checker 应同步"""
        _write_mock_json(_real_cookie_sample())
        orch = get_orchestrator()

        # 不调用 sync_cookie_layers_from_json，直接检查状态
        states = orch.cookie_rotator.get_all_states()
        identity_state = states[CookieLayer.IDENTITY]
        assert identity_state.updated_at == 0.0  # 从未初始化

        # 模拟 cookie_checker 的同步条件判断
        should_sync = (not identity_state) or (identity_state.updated_at == 0.0)
        assert should_sync is True, "从未初始化时应触发同步"


# ============== 缺陷4: CookieStore.update_cookie_values 合并写入 ==============


class TestUpdateCookieValues:
    """验证 CookieStore.update_cookie_values 的合并写入行为"""

    def setup_method(self):
        _reset_orchestrator()

    def teardown_method(self):
        _reset_orchestrator()

    def test_update_existing_cookie_value(self):
        """正常场景：更新已存在的 cookie 值"""
        _write_mock_json(_real_cookie_sample())
        store = get_cookie_store()

        new_token = "new_token_value_1234567890_1782539999999"
        result = store.update_cookie_values({"_m_h5_tk": new_token})
        assert result is True

        # 验证：JSON 中 _m_h5_tk 已更新
        data = store._read_json()
        tk_cookie = next(c for c in data["cookies"] if c["name"] == "_m_h5_tk")
        assert tk_cookie["value"] == new_token

    def test_update_multiple_cookies(self):
        """正常场景：同时更新多个 cookie 值"""
        _write_mock_json(_real_cookie_sample())
        store = get_cookie_store()

        updates = {
            "_m_h5_tk": "new_tk_value",
            "_m_h5_tk_enc": "new_enc_value",
        }
        result = store.update_cookie_values(updates)
        assert result is True

        data = store._read_json()
        tk = next(c for c in data["cookies"] if c["name"] == "_m_h5_tk")
        enc = next(c for c in data["cookies"] if c["name"] == "_m_h5_tk_enc")
        assert tk["value"] == "new_tk_value"
        assert enc["value"] == "new_enc_value"

    def test_update_nonexistent_cookie_returns_false(self):
        """边界条件：更新不存在的 cookie 时返回 False（不创建新条目）"""
        _write_mock_json(_real_cookie_sample())
        store = get_cookie_store()

        result = store.update_cookie_values({"nonexistent_cookie": "value"})
        assert result is False

    def test_update_empty_dict_returns_false(self):
        """边界条件：空 updates 字典返回 False"""
        _write_mock_json(_real_cookie_sample())
        store = get_cookie_store()
        result = store.update_cookie_values({})
        assert result is False

    def test_update_with_missing_json_returns_false(self):
        """边界条件：JSON 不存在时返回 False"""
        if _COOKIE_JSON.exists():
            _COOKIE_JSON.unlink()
        store = get_cookie_store()
        store._cache = None
        store._cache_ts = 0.0
        result = store.update_cookie_values({"_m_h5_tk": "value"})
        assert result is False

    def test_update_preserves_other_cookies(self):
        """健壮性：更新不影响其他 cookie（合并写而非覆盖写）"""
        _write_mock_json(_real_cookie_sample())
        store = get_cookie_store()

        original_count = len(store._read_json()["cookies"])
        store.update_cookie_values({"_m_h5_tk": "new_value"})

        data = store._read_json()
        # cookie 数量不变（没有丢失任何 cookie）
        assert len(data["cookies"]) == original_count
        # 其他 cookie 仍在
        names = {c["name"] for c in data["cookies"]}
        assert "unb" in names
        assert "cookie2" in names
        assert "sgcookie" in names

    def test_update_same_value_returns_false(self):
        """健壮性：值未变化时不触发写入（避免不必要的 IO）"""
        _write_mock_json(_real_cookie_sample())
        store = get_cookie_store()

        # 读取当前值
        data = store._read_json()
        current_tk = next(c for c in data["cookies"] if c["name"] == "_m_h5_tk")["value"]

        # 用相同的值更新
        result = store.update_cookie_values({"_m_h5_tk": current_tk})
        assert result is False  # 无变化，不写入

    def test_update_updates_exported_at_timestamp(self):
        """功能验证：更新后 exported_at 时间戳被刷新"""
        _write_mock_json(_real_cookie_sample())
        store = get_cookie_store()

        original_ts = store._read_json()["exported_at"]
        time.sleep(0.01)
        store.update_cookie_values({"_m_h5_tk": "new_value"})

        new_ts = store._read_json()["exported_at"]
        assert new_ts > original_ts

    def test_update_method_field_not_growing(self):
        """健壮性：多次更新后 method 字段不会无限增长（C2 修复验证）"""
        _write_mock_json(_real_cookie_sample())
        store = get_cookie_store()

        # 连续更新 5 次
        for i in range(5):
            store.update_cookie_values({"_m_h5_tk": f"value_{i}"})

        data = store._read_json()
        method = data.get("method", "")
        # method 中 "mtop_refresh" 只出现一次，不会重复追加
        assert method.count("mtop_refresh") <= 1, f"method 字段重复追加: {method}"

    def test_update_concurrent_safety(self):
        """并发安全：多线程并发 update 不会丢失数据（C1 修复验证）"""
        import threading
        _write_mock_json(_real_cookie_sample())
        store = get_cookie_store()

        # 两个线程并发更新不同的 cookie
        results = []
        barrier = threading.Barrier(2)

        def update_tk():
            barrier.wait()
            results.append(store.update_cookie_values({"_m_h5_tk": "tk_from_thread1"}))

        def update_enc():
            barrier.wait()
            results.append(store.update_cookie_values({"_m_h5_tk_enc": "enc_from_thread2"}))

        t1 = threading.Thread(target=update_tk)
        t2 = threading.Thread(target=update_enc)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # 验证：两个更新都成功，且两个值都在 JSON 中（没有丢失）
        data = store._read_json()
        tk = next(c for c in data["cookies"] if c["name"] == "_m_h5_tk")
        enc = next(c for c in data["cookies"] if c["name"] == "_m_h5_tk_enc")
        assert tk["value"] == "tk_from_thread1", "thread1 的更新丢失"
        assert enc["value"] == "enc_from_thread2", "thread2 的更新丢失"


class TestUpsertCookieValues:
    """验证 CookieStore.upsert_cookie_values 的 upsert 行为"""

    def setup_method(self):
        _reset_orchestrator()

    def teardown_method(self):
        _reset_orchestrator()

    def test_upsert_updates_existing_cookie(self):
        """正常场景：更新已存在的 cookie 值"""
        _write_mock_json(_real_cookie_sample())
        store = get_cookie_store()

        result = store.upsert_cookie_values({
            "_m_h5_tk": {"value": "new_tk_value", "domain": ".goofish.com", "path": "/", "expires": -1}
        })
        assert result is True
        data = store._read_json()
        tk = next(c for c in data["cookies"] if c["name"] == "_m_h5_tk")
        assert tk["value"] == "new_tk_value"

    def test_upsert_adds_nonexistent_cookie(self):
        """关键场景：添加 JSON 中不存在的 cookie（浏览器兜底回写场景）"""
        _write_mock_json(_real_cookie_sample())
        store = get_cookie_store()

        # 确认 JSON 中没有 "t" cookie
        data = store._read_json()
        assert "t" not in {c["name"] for c in data["cookies"]}

        result = store.upsert_cookie_values({
            "t": {"value": "new_t_token", "domain": ".goofish.com", "path": "/", "expires": -1}
        })
        assert result is True

        # 验证：新 cookie 已添加
        data = store._read_json()
        t_cookie = next(c for c in data["cookies"] if c["name"] == "t")
        assert t_cookie["value"] == "new_t_token"
        assert t_cookie["domain"] == ".goofish.com"

    def test_upsert_mixed_update_and_add(self):
        """边界条件：同时更新已有 + 添加新 cookie"""
        _write_mock_json(_real_cookie_sample())
        store = get_cookie_store()

        original_count = len(store._read_json()["cookies"])

        result = store.upsert_cookie_values({
            "_m_h5_tk": {"value": "updated_tk", "domain": ".goofish.com", "path": "/", "expires": -1},
            "t": {"value": "new_t_token", "domain": ".goofish.com", "path": "/", "expires": -1},
        })
        assert result is True

        data = store._read_json()
        # cookie 数量 +1（添加了 "t"，更新了 "_m_h5_tk"）
        assert len(data["cookies"]) == original_count + 1
        tk = next(c for c in data["cookies"] if c["name"] == "_m_h5_tk")
        assert tk["value"] == "updated_tk"
        t_cookie = next(c for c in data["cookies"] if c["name"] == "t")
        assert t_cookie["value"] == "new_t_token"

    def test_upsert_preserves_other_cookies(self):
        """健壮性：upsert 不影响其他 cookie"""
        _write_mock_json(_real_cookie_sample())
        store = get_cookie_store()

        store.upsert_cookie_values({
            "t": {"value": "new_t", "domain": ".goofish.com", "path": "/", "expires": -1}
        })

        data = store._read_json()
        names = {c["name"] for c in data["cookies"]}
        assert "unb" in names
        assert "cookie2" in names
        assert "sgcookie" in names

    def test_upsert_empty_dict_returns_false(self):
        """边界条件：空 upserts 返回 False"""
        _write_mock_json(_real_cookie_sample())
        store = get_cookie_store()
        result = store.upsert_cookie_values({})
        assert result is False

    def test_upsert_with_missing_json_returns_false(self):
        """边界条件：JSON 不存在时返回 False"""
        if _COOKIE_JSON.exists():
            _COOKIE_JSON.unlink()
        store = get_cookie_store()
        store._cache = None
        store._cache_ts = 0.0
        result = store.upsert_cookie_values({
            "t": {"value": "new_t", "domain": ".goofish.com", "path": "/", "expires": -1}
        })
        assert result is False


# ============== 缺陷3: 实时搜索/官方采集补注入后层状态同步 ==============


class TestEnsureLiveSearchCookiesSync:
    """验证 _ensure_live_search_cookies 补注入后调用 sync_cookie_layers_from_json

    通过 mock 验证：补注入成功时调用 sync_cookie_layers_from_json，
    补注入失败或无需补注入时不调用。
    """

    def test_sync_called_after_successful_injection(self):
        """功能验证：补注入成功后应调用 sync_cookie_layers_from_json"""
        _write_mock_json(_real_cookie_sample())
        _reset_orchestrator()

        # 构造 mock container：浏览器缺少关键 cookie，补注入会成功
        mock_container = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()

        # get_cookies 是 async 方法；用 side_effect 模拟补注入前后状态变化：
        # 第一次调用（检测缺失）：只返回 cna，缺少 identity cookie
        # 第二次调用（补注入后复查）：返回完整 cookie，补注入成功
        cookies_before = [{"name": "cna", "value": "xxx", "domain": ".goofish.com"}]
        cookies_after = [
            {"name": "cna", "value": "xxx", "domain": ".goofish.com"},
            {"name": "unb", "value": "2209384756290", "domain": ".goofish.com"},
            {"name": "cookie2", "value": "c8421f9e5b6d7a3b9c0e1f2d3a4b5c6d", "domain": ".goofish.com"},
            {"name": "sgcookie", "value": "E100zRxEj%2FbXi%2B%2FbxVSJT%2Fg%2FaDG6MgjhL", "domain": ".goofish.com"},
            {"name": "_m_h5_tk", "value": "c7b2c44645275604a525e6287fea2c3a_1782530783399", "domain": ".goofish.com"},
            {"name": "_m_h5_tk_enc", "value": "abc123enc456def789", "domain": ".goofish.com"},
        ]
        mock_browser.get_cookies = AsyncMock(side_effect=[cookies_before, cookies_after])
        # add_cookies 也是 async 方法；实时搜索通过 BrowserManager 封装注入，避免绕过统一校验。
        mock_browser.add_cookies = AsyncMock(return_value=True)
        mock_browser._context = mock_context
        mock_container.browser = mock_browser
        mock_container.collector = None

        # 执行 _ensure_live_search_cookies（Python 3.14 用 asyncio.run）
        from xianyu_hunter.web.routes.api_task_links import _ensure_live_search_cookies

        asyncio.run(_ensure_live_search_cookies(mock_container))

        # 验证：sync_cookie_layers_from_json 被调用（通过层状态变化判断）
        orch = get_orchestrator()
        states = orch.cookie_rotator.get_all_states()
        assert states[CookieLayer.IDENTITY].valid is True, "补注入后层状态应同步为有效"


# ============== 浏览器内存兜底同步 ==============


class TestBrowserFallbackSync:
    """验证 /cookies/layers 端点的浏览器内存兜底同步

    场景：JSON 缺少某些 cookie（如 MTOP token），但浏览器内存中有，
    /cookies/layers 应从浏览器内存读取并同步层状态 + 回写 JSON。
    """

    def setup_method(self):
        _reset_orchestrator()

    def teardown_method(self):
        _reset_orchestrator()

    def test_browser_fallback_syncs_missing_session_cookies(self):
        """关键场景：JSON 缺少 session cookie，浏览器内存有，应兜底同步

        场景：JSON 中没有 _m_h5_tk（MTOP token 未持久化），但浏览器内存有，
        /cookies/layers 应从浏览器读取并同步 session 层状态
        """
        # 构造 JSON：只有 identity cookie，缺少 session cookie
        cookies_without_session = [
            {"name": "unb", "value": "2209384756290", "domain": ".goofish.com", "path": "/", "expires": -1},
            {"name": "cookie2", "value": "c8421f9e5b6d7a3b9c0e1f2d3a4b5c6d", "domain": ".goofish.com", "path": "/", "expires": -1},
            {"name": "sgcookie", "value": "E100zRxEj%2FbXi%2B%2FbxVSJT%2Fg%2FaDG6MgjhL", "domain": ".goofish.com", "path": "/", "expires": -1},
            {"name": "cna", "value": "YcHJH+IsChycAXTQMyRJqgj+", "domain": ".goofish.com", "path": "/", "expires": -1},
        ]
        _write_mock_json(cookies_without_session)
        _reset_orchestrator()

        # 构造 mock container：浏览器内存有完整 cookie（包括 session cookie）
        mock_container = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()

        browser_cookies = [
            {"name": "unb", "value": "2209384756290", "domain": ".goofish.com", "path": "/", "expires": -1},
            {"name": "cookie2", "value": "c8421f9e5b6d7a3b9c0e1f2d3a4b5c6d", "domain": ".goofish.com", "path": "/", "expires": -1},
            {"name": "sgcookie", "value": "E100zRxEj%2FbXi%2B%2FbxVSJT%2Fg%2FaDG6MgjhL", "domain": ".goofish.com", "path": "/", "expires": -1},
            {"name": "_m_h5_tk", "value": "c7b2c44645275604a525e6287fea2c3a_1782530783399", "domain": ".goofish.com", "path": "/", "expires": -1},
            {"name": "_m_h5_tk_enc", "value": "abc123enc456def789", "domain": ".goofish.com", "path": "/", "expires": -1},
        ]
        mock_browser.get_cookies = AsyncMock(return_value=browser_cookies)
        mock_browser._context = mock_context
        mock_container.browser = mock_browser

        # patch get_container 返回 mock
        with patch("xianyu_hunter.web.deps.get_container", return_value=mock_container):
            # 调用 /cookies/layers 端点
            response = client.get("/api/anticrawl/cookies/layers", cookies=_AUTH_COOKIE)

        assert response.status_code == 200
        result = response.json()

        # 验证：identity 和 session 层都应 valid（浏览器兜底同步成功）
        assert result["layers"]["identity"]["valid"] is True, "identity 层应通过浏览器兜底同步为有效"
        assert result["layers"]["session"]["valid"] is True, "session 层应通过浏览器兜底同步为有效"

    def test_browser_fallback_writes_cookies_to_json(self):
        """功能验证：浏览器兜底同步应回写缺失的 cookie 到 JSON"""
        # 构造 JSON：缺少 _m_h5_tk
        cookies_without_session = [
            {"name": "unb", "value": "2209384756290", "domain": ".goofish.com", "path": "/", "expires": -1},
            {"name": "cookie2", "value": "c8421f9e5b6d7a3b9c0e1f2d3a4b5c6d", "domain": ".goofish.com", "path": "/", "expires": -1},
            {"name": "sgcookie", "value": "E100zRxEj%2FbXi%2B%2FbxVSJT%2Fg%2FaDG6MgjhL", "domain": ".goofish.com", "path": "/", "expires": -1},
        ]
        _write_mock_json(cookies_without_session)
        _reset_orchestrator()

        mock_container = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_browser.get_cookies = AsyncMock(return_value=[
            {"name": "_m_h5_tk", "value": "new_tk_value_123", "domain": ".goofish.com", "path": "/", "expires": -1},
            {"name": "_m_h5_tk_enc", "value": "new_enc_value", "domain": ".goofish.com", "path": "/", "expires": -1},
            {"name": "unb", "value": "2209384756290", "domain": ".goofish.com", "path": "/", "expires": -1},
        ])
        mock_browser._context = mock_context
        mock_container.browser = mock_browser

        with patch("xianyu_hunter.web.deps.get_container", return_value=mock_container):
            client.get("/api/anticrawl/cookies/layers", cookies=_AUTH_COOKIE)

        # 验证：JSON 中已新增 _m_h5_tk（通过 upsert_cookie_values）
        store = get_cookie_store()
        store._cache = None  # 清除缓存
        store._cache_ts = 0.0
        data = store._read_json()
        names = {c["name"] for c in data["cookies"]}
        assert "_m_h5_tk" in names, "浏览器兜底回写应添加缺失的 _m_h5_tk 到 JSON"

    def test_browser_fallback_skips_when_no_browser(self):
        """边界条件：浏览器未启动时兜底不生效，但不影响 JSON 同步"""
        _write_mock_json(_real_cookie_sample())
        _reset_orchestrator()

        # mock container.browser = None
        mock_container = MagicMock()
        mock_container.browser = None

        with patch("xianyu_hunter.web.deps.get_container", return_value=mock_container):
            response = client.get("/api/anticrawl/cookies/layers", cookies=_AUTH_COOKIE)

        assert response.status_code == 200
        result = response.json()
        # JSON 有完整 cookie，JSON 同步应该生效（不依赖浏览器）
        assert result["layers"]["identity"]["valid"] is True
        assert result["layers"]["session"]["valid"] is True


# ============== 跨进程缓存一致性 ==============


class TestCrossProcessCacheInvalidation:
    """验证浏览器登录子进程写入 JSON 后，主进程不会读到旧缓存

    场景：浏览器登录子进程是独立 Python 进程，写入 cookies.json 后只更新
    子进程自己的 CookieStore 单例缓存，主进程的 30 秒 TTL 缓存仍是旧数据。
    修复后 sync_cookie_layers_from_json / /cookies/layers / /cookies/update
    在读取 JSON 前必须先调用 invalidate_cache() 清除旧缓存。

    若不修复：登录成功后层状态仍显示失效，且 /cookies/update 会用旧缓存覆盖
    子进程刚写入的新 cookie，导致用户报告"更新后还是失效状态"。
    """

    def setup_method(self):
        _reset_orchestrator()

    def teardown_method(self):
        _reset_orchestrator()

    def _simulate_subprocess_write(self, cookies: list[dict]) -> None:
        """模拟浏览器登录子进程写入 JSON（不通过主进程的 CookieStore）

        子进程是独立 Python 进程，只写文件不会更新主进程的 _cache/_cache_ts。
        直接调用 _write_json 会更新主进程缓存，无法复现跨进程问题，
        所以这里直接写文件并故意不清除主进程缓存（模拟真实跨进程场景）。
        """
        _COOKIE_JSON.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "exported_at": time.time(),
            "method": "browser_login_subprocess",
            "cookie_count": len(cookies),
            "cookies": cookies,
        }
        _COOKIE_JSON.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # 故意不清除主进程缓存：模拟子进程写入后主进程缓存仍是旧数据的状态
        # （这是真实跨进程场景的关键特征）

    def test_sync_invalidates_stale_cache_after_subprocess_write(self):
        """关键场景：主进程缓存空数据，子进程写入新数据，sync 应读到新数据

        复现路径：服务启动后从未读取过 JSON（缓存为空），浏览器登录子进程
        写入新 cookies.json，调用 sync_cookie_layers_from_json 应读到新数据
        而非旧缓存，层状态应正确同步为 valid。
        """
        # Step 1: 主进程首次读取（缓存空数据，此时文件不存在）
        store = get_cookie_store()
        store._cache = None
        store._cache_ts = 0.0
        if _COOKIE_JSON.exists():
            _COOKIE_JSON.unlink()
        # 触发一次读取，让缓存记录"空数据"
        store._read_json()  # 返回 None，但 _cache 仍为 None
        # 模拟主进程曾经读取过空数据：手工设置空缓存
        store._cache = {"cookies": []}
        store._cache_ts = time.time()

        # Step 2: 子进程写入新数据（不清除主进程缓存）
        self._simulate_subprocess_write(_real_cookie_sample())

        # 验证：未修复前，主进程直接 _read_json 仍读到空缓存
        # （因为 30 秒 TTL 内未过期）
        stale = store._read_json()
        assert stale is not None and len(stale.get("cookies", [])) == 0, \
            "测试前置：未 invalidate_cache 时应读到旧空缓存"

        # Step 3: 调用 sync_cookie_layers_from_json（修复后会先 invalidate_cache）
        result = sync_cookie_layers_from_json()
        assert result is True

        # 验证：层状态已正确同步为 valid（说明读到了子进程写入的新数据）
        orch = get_orchestrator()
        states = orch.cookie_rotator.get_all_states()
        assert states[CookieLayer.IDENTITY].valid is True, \
            "invalidate_cache 修复后，应读到子进程写入的新数据，identity 层应 valid"
        assert states[CookieLayer.SESSION].valid is True
        assert states[CookieLayer.TRACKING].valid is True

    def test_cookies_layers_endpoint_invalidates_stale_cache(self):
        """关键场景：/cookies/layers 端点应读到子进程写入的新数据

        用户在前端轮询 /cookies/layers 查看层状态，主进程缓存可能为旧数据，
        端点必须先 invalidate_cache 才能反映子进程的最新写入。
        """
        # Step 1: 主进程缓存空数据
        store = get_cookie_store()
        if _COOKIE_JSON.exists():
            _COOKIE_JSON.unlink()
        store._read_json()
        store._cache = {"cookies": []}
        store._cache_ts = time.time()

        # Step 2: 子进程写入新数据
        self._simulate_subprocess_write(_real_cookie_sample())

        # Step 3: 调用 /cookies/layers 端点
        response = client.get("/api/anticrawl/cookies/layers", cookies=_AUTH_COOKIE)
        assert response.status_code == 200
        result = response.json()

        # 验证：端点读到子进程写入的新数据，三层应 valid
        assert result["layers"]["identity"]["valid"] is True, \
            "/cookies/layers 端点应通过 invalidate_cache 读到子进程写入的新数据"
        assert result["layers"]["session"]["valid"] is True
        assert result["layers"]["tracking"]["valid"] is True

    def test_health_endpoint_invalidates_stale_cache(self):
        """关键场景：/health 的 cookie_checker 应读到子进程写入的新数据"""
        # Step 1: 主进程缓存空数据
        store = get_cookie_store()
        if _COOKIE_JSON.exists():
            _COOKIE_JSON.unlink()
        store._read_json()
        store._cache = {"cookies": []}
        store._cache_ts = time.time()

        # Step 2: 子进程写入新数据（不清除主进程缓存）
        self._simulate_subprocess_write(_real_cookie_sample())

        # Step 3: 初始化健康检查器并调用 /health
        client.post(
            "/api/anticrawl/initialize",
            json={"use_cdp": False},
            cookies=_AUTH_COOKIE,
        )
        response = client.get("/api/anticrawl/health", cookies=_AUTH_COOKIE)
        assert response.status_code == 200
        result = response.json()

        assert result["ok"] is True
        assert result["cookie_valid"] is True, "/health 应通过 invalidate_cache 读到最新 Cookie"

    def test_cookies_update_endpoint_invalidates_stale_cache(self):
        """关键场景：/cookies/update 端点不应丢失子进程写入的 cookie

        用户报告"点击更新Cookie后还是失效状态"的根因：主进程缓存为空（旧数据），
        合并写入时会用空缓存 + 用户传入的少量 cookie 覆盖丢失子进程刚写入的
        全量 cookie。修复后端点先 invalidate_cache 读到子进程的数据，再合并。
        """
        # Step 1: 主进程缓存空数据
        store = get_cookie_store()
        if _COOKIE_JSON.exists():
            _COOKIE_JSON.unlink()
        store._read_json()
        store._cache = {"cookies": []}
        store._cache_ts = time.time()

        # Step 2: 子进程写入完整 cookie（含 identity + session + tracking）
        self._simulate_subprocess_write(_real_cookie_sample())

        # Step 3: 用户在前端只传入少量 cookie（如刷新 _m_h5_tk）
        # 修复前：合并时会用主进程缓存的空数据作为 base，导致其他 cookie 全部丢失
        # 修复后：先 invalidate_cache 读到子进程写入的全量 cookie，再合并
        # 注意：token 必须符合真实格式（32hex_13timestamp），否则会被 is_test_cookie 过滤
        new_token = "abcdef1234567890abcdef1234567890_1782550000000"
        response = client.post(
            "/api/anticrawl/cookies/update",
            json={"cookies": {"_m_h5_tk": new_token}},
            cookies=_AUTH_COOKIE,
        )
        assert response.status_code == 200
        result = response.json()
        assert result["ok"] is True

        # 验证：JSON 中应保留子进程写入的其他 cookie（unb/cookie2/sgcookie）
        store._cache = None
        store._cache_ts = 0.0
        data = store._read_json()
        names = {c["name"] for c in data["cookies"]}
        assert "unb" in names, "修复前会用空缓存覆盖丢失 unb，修复后应保留"
        assert "cookie2" in names, "修复前会用空缓存覆盖丢失 cookie2，修复后应保留"
        assert "sgcookie" in names, "修复前会用空缓存覆盖丢失 sgcookie，修复后应保留"
        # 用户传入的新值应被合并写入
        tk = next(c for c in data["cookies"] if c["name"] == "_m_h5_tk")
        assert tk["value"] == new_token
