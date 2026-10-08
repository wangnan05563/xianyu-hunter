"""回归测试：/api/auth/me 的身份解析以 Cookie 文件 unb 为准，不再被降级缓存带成"未登录"

背景：扫码登录成功后，悬浮 Cookie 状态面板显示正常（只读 Cookie 文件），
但顶栏账号名显示"未登录"。两处读的是不同数据源：
- /cookie/health → Cookie JSON 文件（cookies_{uid}.json / last_login_cookies.json / default）
- /me → AuthManager 的 auth_cache/userinfo.json 缓存
当 userinfo 缓存里的 user_id 是降级身份（子进程读不到 unb 时用 sha256(cookie2) 生成，
users 表无此记录）、nick 又是无效值时，/me 的 local_username 退化为裸 user_id，
前端 computeDisplayName 判空后显示"未登录"。

修复口径：/me 的身份优先级为 会话 user_id > Cookie 文件 unb > userinfo 缓存 user_id，
并用校正后的 id 去 users 表取昵称。
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse

from xianyu_hunter.web.routes import auth_query
from xianyu_hunter.web.services.cookie_store import get_cookie_store

_REAL_UID = "135379349"
_DEGRADED_UID = "74450ae57f364"  # auth_helper 读不到 unb 时的 sha256(cookie2) 降级值


def _write_cookies(tmp_path: Path, user_id: str = "default") -> None:
    payload = {
        "exported_at": 1_700_000_000,
        "method": "login",
        "cookies": [
            {"name": "unb", "value": _REAL_UID, "expires": -1},
            {"name": "cookie2", "value": "16bdf26a711c", "expires": -1},
            {"name": "_m_h5_tk", "value": "tok_1700000000", "expires": -1},
        ],
    }
    (tmp_path / f"cookies_{user_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


class _FakeAuthManager:
    USERINFO_TTL = 300.0

    def get_userinfo(self) -> dict:
        # 模拟登录后仍在生效的过期缓存：降级 uid + 无效昵称
        return {
            "logged_in": True,
            "user_id": _DEGRADED_UID,
            "nick": "Hi! 你好",
            "avatar_url": "",
            "fetched_at": 1_700_000_000,
        }

    def trigger_refresh_userinfo_async(self, delay: float = 0.0) -> None:
        pass


class _FakeUserManager:
    def __init__(self) -> None:
        self._users = {_REAL_UID: {"user_id": _REAL_UID, "nickname": "南屿轻舟", "custom_alias": ""}}

    def get_user(self, user_id: str):
        return self._users.get(user_id)

    def merge_duplicate_accounts(self, user_id: str):
        return []


def _make_request() -> Request:
    return Request(scope={
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "server": ("127.0.0.1", 8001),
        "path": "/api/auth/me",
        "raw_path": b"/api/auth/me",
        "query_string": b"",
        "root_path": "",
        "headers": [],
    })


def _run_me(monkeypatch, tmp_path: Path) -> dict:
    monkeypatch.setattr(auth_query, "_resolve_current_user_id", lambda request: None)
    monkeypatch.setattr(auth_query, "_check_cookies", lambda user_id="default": True)
    monkeypatch.setattr(auth_query, "get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(auth_query, "get_auth_manager", lambda: _FakeAuthManager())
    monkeypatch.setattr(auth_query, "scan_and_notify", lambda container, auth_state: None)
    monkeypatch.setattr(
        "xianyu_hunter.web.services.user_manager.get_user_manager",
        lambda: _FakeUserManager(),
    )
    result = auth_query.auth_me(_make_request(), container=None)
    # 已登录路径返回 JSONResponse（附带 xh_token cookie），取回其 JSON 内容
    if isinstance(result, JSONResponse):
        return json.loads(result.body)
    return result


def test_uid_from_cookies_reads_unb_with_fallback_chain(monkeypatch, tmp_path):
    """_uid_from_cookies 从 Cookie 文件（含 fallback 链）解析 unb"""
    _write_cookies(tmp_path, "default")
    monkeypatch.setattr(auth_query, "get_data_dir", lambda: tmp_path)
    store = get_cookie_store()
    store.invalidate_cache()
    assert auth_query._uid_from_cookies(store, "missing_user") == _REAL_UID


def test_uid_from_cookies_rejects_non_unb_value(monkeypatch, tmp_path):
    """无 unb（或非 8 位以上数字）时返回空串，交由上层继续兜底"""
    payload = {"cookies": [{"name": "cookie2", "value": "abc", "expires": -1}]}
    (tmp_path / "cookies_default.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    monkeypatch.setattr(auth_query, "get_data_dir", lambda: tmp_path)
    store = get_cookie_store()
    store.invalidate_cache()
    assert auth_query._uid_from_cookies(store, "default") == ""


def test_me_corrects_degraded_uid_to_cookie_unb(monkeypatch, tmp_path):
    """缓存里是降级 user_id 时，/me 用 Cookie unb 校正身份并取回库里昵称"""
    _write_cookies(tmp_path, "default")
    data = _run_me(monkeypatch, tmp_path)
    assert data["user_id"] == _REAL_UID
    assert data["local_username"] == "南屿轻舟"
    assert data["logged_in"] is True


def test_me_prefers_session_uid_over_cookie_file(monkeypatch, tmp_path):
    """会话已识别 user_id 时不被 Cookie 文件覆盖（多用户切换场景）"""
    _write_cookies(tmp_path, "default")

    def _resolve(request):
        return _REAL_UID

    monkeypatch.setattr(auth_query, "_resolve_current_user_id", _resolve)
    data = _run_me(monkeypatch, tmp_path)
    assert data["user_id"] == _REAL_UID
    assert data["local_username"] == "南屿轻舟"
