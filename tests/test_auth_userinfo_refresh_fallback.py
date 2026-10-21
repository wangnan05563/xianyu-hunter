"""回归测试：auth_helper 刷新失败可观测 + /me 昵称本地兜底（T01633 / T01634）

背景：
1. 打包版 auth_helper 的 info 子进程与 Worker 常驻浏览器共用同一个 browser-data
   profile，Chromium 的 ProcessSingleton 让第二个实例以 RESULT_CODE_PROFILE_IN_USE
   退出，Playwright 只抛 TargetClosedError("...has been closed")。
   结果是 userinfo.json 永不生成、/me 的昵称恒为空，且失败被静默吞掉。
2. 昵称抓取失败时 /me 只能返回裸 user_id（如 135379349），可读性极差。
   Cookie 里的 tracknick 是登录时下发的账号名，可作为零成本兜底。

修复口径：
- auth_helper：共享 profile 启动失败时回退一次性临时 profile + 注入本地 Cookie
- /me：兜底链 custom_alias > users.nickname > userinfo nick > tracknick > user_id
- /me：暴露 nick_sync_state / nick_sync_error，让前端显示"昵称未同步"而非静默空值
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from xianyu_hunter.web.routes import auth_query
from xianyu_hunter.web.services.cookie_store import get_cookie_store

_REPO = Path(__file__).resolve().parents[1]
_REAL_UID = "135379349"


def _load_auth_helper():
    """scripts/ 不是包，按文件路径动态加载 auth_helper 模块"""
    spec = importlib.util.spec_from_file_location(
        "_xh_auth_helper_for_test", _REPO / "scripts" / "auth_helper.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_cookies(tmp_path: Path, user_id: str = "default", tracknick: str = "dosufo") -> None:
    payload = {
        "exported_at": 1_700_000_000,
        "method": "login",
        "cookies": [
            {"name": "unb", "value": _REAL_UID, "expires": -1},
            {"name": "tracknick", "value": tracknick, "expires": -1},
            {"name": "cookie2", "value": "16bdf26a711c", "expires": -1},
        ],
    }
    (tmp_path / f"cookies_{user_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


class _FakeAuthManager:
    """模拟 AuthManager：可配置 userinfo 缓存与刷新状态"""

    USERINFO_TTL = 300.0

    def __init__(self, info: dict | None = None, refresh: dict | None = None) -> None:
        self._info = info or {
            "logged_in": False, "user_id": "", "nick": "", "avatar_url": "", "fetched_at": 0,
        }
        self._refresh = refresh or {"state": "never", "error": "", "at": 0.0}

    def get_userinfo(self) -> dict:
        return self._info

    def get_refresh_status(self) -> dict:
        return self._refresh

    def trigger_refresh_userinfo_async(self, delay: float = 0.0) -> None:
        pass


class _EmptyUserManager:
    """users 表里没有该用户（昵称从未同步过）"""

    def get_user(self, user_id: str):
        return None

    def merge_duplicate_accounts(self, user_id: str):
        return []


def _make_request() -> dict:
    from fastapi import Request

    return Request(scope={
        "type": "http", "http_version": "1.1", "method": "GET", "scheme": "http",
        "server": ("127.0.0.1", 8001), "path": "/api/auth/me",
        "raw_path": b"/api/auth/me", "query_string": b"", "root_path": "", "headers": [],
    })


def _run_me(monkeypatch, tmp_path: Path, am: _FakeAuthManager | None = None) -> dict:
    from fastapi.responses import JSONResponse

    monkeypatch.setattr(auth_query, "_resolve_current_user_id", lambda request: None)
    monkeypatch.setattr(auth_query, "_check_cookies", lambda user_id="default": True)
    monkeypatch.setattr(auth_query, "get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(auth_query, "get_auth_manager", lambda: am or _FakeAuthManager())
    monkeypatch.setattr(auth_query, "scan_and_notify", lambda container, auth_state=None, user_id=None: None)
    monkeypatch.setattr(
        "xianyu_hunter.web.services.user_manager.get_user_manager",
        lambda: _EmptyUserManager(),
    )
    result = auth_query.auth_me(_make_request(), container=None)
    if isinstance(result, JSONResponse):
        return json.loads(result.body)
    return result


# ---------------- T01634：tracknick 本地兜底 ----------------

def test_account_name_from_cookies_url_decodes_tracknick(monkeypatch, tmp_path):
    """tracknick 是 URL 编码值，取用前需解码"""
    _write_cookies(tmp_path, "default", tracknick="%E5%8D%97%E5%B1%BF")
    monkeypatch.setattr(auth_query, "get_data_dir", lambda: tmp_path)
    store = get_cookie_store()
    store.invalidate_cache()
    assert auth_query._account_name_from_cookies(store, "default") == "南屿"


def test_account_name_from_cookies_ignores_placeholder(monkeypatch, tmp_path):
    """占位值 null/undefined/空串不应被当作账号名"""
    _write_cookies(tmp_path, "default", tracknick="null")
    monkeypatch.setattr(auth_query, "get_data_dir", lambda: tmp_path)
    store = get_cookie_store()
    store.invalidate_cache()
    assert auth_query._account_name_from_cookies(store, "default") == ""


def test_me_falls_back_to_tracknick_when_nick_missing(monkeypatch, tmp_path):
    """浏览器抓取失败（userinfo 全空）时，local_username 落到 Cookie 账号名而非裸 ID"""
    _write_cookies(tmp_path, "default", tracknick="dosufo")
    data = _run_me(monkeypatch, tmp_path)
    assert data["user_id"] == _REAL_UID
    assert data["local_username"] == "dosufo"
    assert data["display_name_source"] == "cookie_account"
    # 兜底名不是闲鱼昵称，nick 字段必须保持为空
    assert data["nick"] == ""


def test_me_prefers_real_nick_over_tracknick(monkeypatch, tmp_path):
    """拿到真实昵称时不使用 Cookie 账号名兜底"""
    _write_cookies(tmp_path, "default", tracknick="dosufo")
    am = _FakeAuthManager(info={
        "logged_in": True, "user_id": _REAL_UID, "nick": "南屿轻舟",
        "avatar_url": "", "fetched_at": 1_700_000_000,
    })
    data = _run_me(monkeypatch, tmp_path, am)
    assert data["local_username"] == "南屿轻舟"
    assert data["display_name_source"] == "userinfo_nick"
    assert data["nick"] == "南屿轻舟"


def test_me_falls_back_to_user_id_without_tracknick(monkeypatch, tmp_path):
    """Cookie 里没有 tracknick 时退化为裸 user_id（保持旧行为）"""
    payload = {"cookies": [{"name": "unb", "value": _REAL_UID, "expires": -1}]}
    (tmp_path / "cookies_default.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    data = _run_me(monkeypatch, tmp_path)
    assert data["local_username"] == _REAL_UID
    assert data["display_name_source"] == "user_id"


# ---------------- T01633：刷新失败可观测 ----------------

def test_me_exposes_nick_sync_failure(monkeypatch, tmp_path):
    """auth_helper 刷新失败时 /me 必须带出失败原因，供前端提示"昵称未同步\""""
    _write_cookies(tmp_path, "default")
    am = _FakeAuthManager(refresh={
        "state": "failed",
        "error": "auth_helper 退出码 1: BrowserType.launch_persistent_context: "
                 "Target page, context or browser has been closed",
        "at": 1_700_000_000.0,
    })
    data = _run_me(monkeypatch, tmp_path, am)
    assert data["nick_sync_state"] == "failed"
    assert "has been closed" in data["nick_sync_error"]


def test_me_nick_sync_ok_has_no_error_field(monkeypatch, tmp_path):
    """刷新成功时不输出 nick_sync_error，避免前端误报"""
    _write_cookies(tmp_path, "default")
    am = _FakeAuthManager(refresh={"state": "ok", "error": "", "at": 1_700_000_000.0})
    data = _run_me(monkeypatch, tmp_path, am)
    assert data["nick_sync_state"] == "ok"
    assert "nick_sync_error" not in data


# ---------------- T01633：隔离 profile 回退 ----------------

def test_is_profile_in_use_error_recognizes_chromium_marker():
    """Chromium profile 被独占时 Playwright 抛 TargetClosedError，必须能被识别"""
    helper = _load_auth_helper()
    assert helper._is_profile_in_use_error(
        RuntimeError("BrowserType.launch_persistent_context: "
                     "Target page, context or browser has been closed")
    )
    # 非独占类错误不应误判为 profile 占用，否则会掩盖真实故障
    assert not helper._is_profile_in_use_error(RuntimeError("Executable doesn't exist"))


def test_load_local_cookies_normalizes_for_playwright(monkeypatch, tmp_path):
    """Cookie 汇总需把 sameSite/expires 收敛到 Playwright 允许取值"""
    helper = _load_auth_helper()
    payload = {
        "cookies": [
            {"name": "unb", "value": _REAL_UID, "expires": -1, "sameSite": "Unspecified"},
            {"name": "tracknick", "value": "dosufo", "expires": -1},
            {"name": "", "value": "bad"},
        ],
    }
    (tmp_path / "cookies_default.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    monkeypatch.setattr("xianyu_hunter.paths.get_data_dir", lambda: tmp_path)
    cookies = helper._load_local_cookies_for_injection()
    by_name = {c["name"]: c for c in cookies}
    assert set(by_name) == {"unb", "tracknick"}
    assert by_name["unb"]["sameSite"] == "Lax"       # Unspecified → Lax
    assert by_name["unb"]["expires"] == -1            # 会话级保持 -1
    assert by_name["unb"]["domain"] == ".goofish.com"  # 缺 domain 时补默认域


def test_load_local_cookies_merges_multiple_user_files(monkeypatch, tmp_path):
    """多用户 Cookie 文件按 (name, domain) 合并，保证 unb 不遗漏"""
    helper = _load_auth_helper()
    (tmp_path / "cookies_default.json").write_text(
        json.dumps({"cookies": [{"name": "unb", "value": _REAL_UID, "expires": -1}]}),
        encoding="utf-8",
    )
    (tmp_path / "cookies_135379349.json").write_text(
        json.dumps({"cookies": [{"name": "tracknick", "value": "dosufo", "expires": -1}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr("xianyu_hunter.paths.get_data_dir", lambda: tmp_path)
    cookies = helper._load_local_cookies_for_injection()
    assert {c["name"] for c in cookies} == {"unb", "tracknick"}
