"""MU2 登录流程多用户接入测试

验证登录成功后调用 identify_or_create + issue_session + export_cookies(user_id)，
并将 session_token 通过 make_auth_response 写入 xh_token cookie。

注意：_session 通过模块属性访问（ul._session），不能用 `from ... import _session`。
因为 _reset_session() 用 `global _session; _session = {...}` 重新绑定模块属性，
直接 import 会拿到旧 dict 的悬空引用。
"""
import asyncio
import json
import subprocess
import sys
from http.cookies import SimpleCookie
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import xianyu_hunter.web.routes.unified_login as ul
from xianyu_hunter.web.routes.unified_login import (
    _background_wait,
    _background_wait_qr,
    _finalize_multi_user_login,
    _reset_session,
)


@pytest.fixture(autouse=True)
def reset_session_fixture():
    """每个测试前后重置登录会话，避免状态泄漏"""
    _reset_session()
    yield
    _reset_session()


def _write_status_file(path: Path, status: str, cookie_count: int = 2) -> None:
    """写入子进程状态文件

    同时写 status 和 state 两个键：
    - _background_wait 读 data.get("status")
    - _background_wait_qr 读 data.get("state")
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"status": status, "state": status, "cookie_count": cookie_count}),
        encoding="utf-8",
    )


# ============================================================
# _finalize_multi_user_login 单元测试
# ============================================================
def test_finalize_multi_user_login_calls_identify_issue_export():
    """登录成功后调用 identify_or_create + issue_session + export_cookies(user_id)"""
    fake_cookies = [
        {"name": "unb", "value": "12345678", "domain": ".goofish.com"},
        {"name": "cookie2", "value": "a" * 32, "domain": ".taobao.com"},
    ]

    with patch(
        "xianyu_hunter.web.routes.unified_login.get_cookie_store"
    ) as mock_store, patch(
        "xianyu_hunter.web.services.user_manager.get_user_manager"
    ) as mock_mgr:
        store = MagicMock()
        # 登录子进程把 Cookie 写入 default 文件，_finalize 读取它
        store._read_json.return_value = {"cookies": fake_cookies}
        mock_store.return_value = store

        mgr = MagicMock()
        mgr.identify_or_create.return_value = "12345678"
        mgr.issue_session.return_value = "session_token_abc"
        mock_mgr.return_value = mgr

        token = _finalize_multi_user_login()

    # 返回 session_token
    assert token == "session_token_abc"
    # identify_or_create 被调用一次
    mgr.identify_or_create.assert_called_once_with(fake_cookies)
    # issue_session 用 user_id 调用
    mgr.issue_session.assert_called_once_with("12345678")
    # export_cookies 被调用两次：一次按 user_id 存储，一次写入 default 兜底
    assert store.export_cookies.call_count == 2
    # 第一次调用是 user_id 维度
    first_kwargs = store.export_cookies.call_args_list[0].kwargs
    assert first_kwargs.get("user_id") == "12345678"
    assert first_kwargs.get("method") == "login"
    # 第二次调用是 default 维度兜底
    second_kwargs = store.export_cookies.call_args_list[1].kwargs
    assert second_kwargs.get("user_id") == "default"
    assert second_kwargs.get("method") == "login"


def test_finalize_multi_user_login_stores_session_token_in_session():
    """成功后 session_token 和 current_user_id 写入 _session"""
    fake_cookies = [{"name": "unb", "value": "12345678"}]

    with patch(
        "xianyu_hunter.web.routes.unified_login.get_cookie_store"
    ) as mock_store, patch(
        "xianyu_hunter.web.services.user_manager.get_user_manager"
    ) as mock_mgr:
        store = MagicMock()
        store._read_json.return_value = {"cookies": fake_cookies}
        mock_store.return_value = store

        mgr = MagicMock()
        mgr.identify_or_create.return_value = "12345678"
        mgr.issue_session.return_value = "session_token_xyz"
        mock_mgr.return_value = mgr

        _finalize_multi_user_login()

    assert ul._session.get("session_token") == "session_token_xyz"
    assert ul._session.get("current_user_id") == "12345678"


def test_finalize_multi_user_login_returns_none_on_empty_cookies():
    """无 Cookie 数据时返回 None（降级单用户模式）"""
    with patch(
        "xianyu_hunter.web.routes.unified_login.get_cookie_store"
    ) as mock_store, patch(
        "xianyu_hunter.web.services.user_manager.get_user_manager"
    ) as mock_mgr:
        store = MagicMock()
        store._read_json.return_value = {"cookies": []}
        mock_store.return_value = store

        mgr = MagicMock()
        mock_mgr.return_value = mgr

        token = _finalize_multi_user_login()

    assert token is None
    # 失败时不调用 identify_or_create
    mgr.identify_or_create.assert_not_called()


def test_finalize_multi_user_login_returns_none_on_exception():
    """异常时返回 None（降级单用户模式，不抛异常）"""
    with patch(
        "xianyu_hunter.web.routes.unified_login.get_cookie_store"
    ) as mock_store:
        store = MagicMock()
        # _read_json 抛异常模拟数据库故障
        store._read_json.side_effect = RuntimeError("db down")
        mock_store.return_value = store

        token = _finalize_multi_user_login()

    assert token is None


# ============================================================
# _background_wait / _background_wait_qr 集成测试
# ============================================================
def test_background_wait_calls_finalize_on_browser_success():
    """浏览器登录成功后调用 _finalize_multi_user_login"""
    import tempfile

    status_file = Path(tempfile.gettempdir()) / "test_mu2_browser_success.json"
    _write_status_file(status_file, "success", cookie_count=3)

    proc = MagicMock(spec=subprocess.Popen)
    # proc.wait 立即返回（不阻塞）
    proc.wait.return_value = None
    proc.poll.return_value = 0
    proc.communicate.return_value = (b"", b"")

    with patch(
        "xianyu_hunter.web.routes.unified_login._verify_cookies", return_value=True
    ), patch(
        "xianyu_hunter.web.routes.unified_login._trigger_userinfo_refresh"
    ), patch(
        "xianyu_hunter.web.routes.unified_login._trigger_session_start"
    ), patch(
        "xianyu_hunter.web.routes.unified_login._finalize_multi_user_login"
    ) as mock_finalize:
        mock_finalize.return_value = "session_token_browser"

        _background_wait(proc, status_file, "browser")

    mock_finalize.assert_called_once()


def test_background_wait_skips_finalize_on_failure():
    """浏览器登录失败时不调用 _finalize_multi_user_login"""
    import tempfile

    status_file = Path(tempfile.gettempdir()) / "test_mu2_browser_fail.json"
    _write_status_file(status_file, "error")

    proc = MagicMock(spec=subprocess.Popen)
    proc.wait.return_value = None
    proc.poll.return_value = 1
    proc.communicate.return_value = (b"", b"login failed")

    with patch(
        "xianyu_hunter.web.routes.unified_login._trigger_userinfo_refresh"
    ), patch(
        "xianyu_hunter.web.routes.unified_login._trigger_session_start"
    ), patch(
        "xianyu_hunter.web.routes.unified_login._finalize_multi_user_login"
    ) as mock_finalize:
        _background_wait(proc, status_file, "browser")

    mock_finalize.assert_not_called()


def test_background_wait_qr_calls_finalize_on_success():
    """QR 登录成功后调用 _finalize_multi_user_login"""
    import tempfile

    out_dir = Path(tempfile.gettempdir()) / "test_mu2_qr_success"
    status_file = out_dir / "status.json"
    qr_png = out_dir / "qr.png"
    _write_status_file(status_file, "success", cookie_count=2)
    # 创建 qr.png 让 QR 轮询阶段检测到二维码就绪，跳出轮询循环
    qr_png.write_bytes(b"fake_qr_png")

    proc = MagicMock(spec=subprocess.Popen)
    # QR 轮询阶段：proc.poll() 返回 None 表示子进程运行中（否则会提前 return）
    proc.poll.return_value = None
    # proc.wait 立即返回（不阻塞测试）
    proc.wait.return_value = None

    with patch(
        "xianyu_hunter.web.routes.unified_login._verify_cookies", return_value=True
    ), patch(
        "xianyu_hunter.web.routes.unified_login._trigger_userinfo_refresh"
    ), patch(
        "xianyu_hunter.web.routes.unified_login._trigger_session_start"
    ), patch(
        "xianyu_hunter.web.routes.unified_login._finalize_multi_user_login"
    ) as mock_finalize, patch(
        "xianyu_hunter.web.routes.unified_login.time.sleep"
    ):
        mock_finalize.return_value = "session_token_qr"

        _background_wait_qr(proc, out_dir)

    mock_finalize.assert_called_once()


# ============================================================
# login_status 端点测试
# ============================================================
def test_login_status_sets_session_token_cookie_on_success():
    """登录成功状态响应中 xh_token cookie 为 session_token"""
    # 直接设置模块级 _session 字段（fixture 已重置，无锁竞争）
    ul._session["status"] = "success"
    ul._session["method"] = "browser"
    ul._session["session_token"] = "session_token_xyz"
    ul._session["cookies_injected"] = True  # 跳过注入流程
    ul._session["started_at"] = 0.0  # 避免 elapsed 计算异常

    with patch(
        "xianyu_hunter.web.routes.unified_login._ensure_session_cookies_injected",
        new_callable=AsyncMock,
    ):
        result = asyncio.run(ul.login_status())

    # make_auth_response 返回 JSONResponse，需用 SimpleCookie 解析 set-cookie header
    assert result.status_code == 200
    set_cookie = result.headers.get("set-cookie", "")
    cookie = SimpleCookie()
    cookie.load(set_cookie)
    assert "xh_token" in cookie
    assert cookie["xh_token"].value == "session_token_xyz"


def test_login_status_no_cookie_when_not_success():
    """非成功状态不设置 xh_token cookie"""
    ul._session["status"] = "running"
    ul._session["method"] = "browser"

    result = asyncio.run(ul.login_status())

    # 非成功时返回 dict（不是 JSONResponse）
    assert isinstance(result, dict)
    assert result["status"] == "running"


def test_login_status_allows_slow_packaged_helper_startup(tmp_path):
    """打包 exe 冷启动时 pending/starting 阶段可能超过 15 秒，不应误杀。"""
    status_file = tmp_path / "browser_login_pending.json"
    status_file.write_text(
        json.dumps(
            {
                "status": "pending",
                "message": "初始化...",
                "ts": ul.time.time() - 30,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    proc = MagicMock(spec=subprocess.Popen)
    proc.poll.return_value = None

    ul._session["status"] = "running"
    ul._session["method"] = "browser"
    ul._session["message"] = "正在启动浏览器窗口..."
    ul._session["status_file"] = str(status_file)
    ul._session["proc"] = proc
    ul._session["started_at"] = ul.time.time() - 30

    result = asyncio.run(ul.login_status())

    assert isinstance(result, dict)
    assert result["status"] == "running"
    assert result["phase"] == "pending"
    proc.kill.assert_not_called()


def test_login_status_still_times_out_stale_waiting_heartbeat(tmp_path):
    """进入等待登录后，心跳长期不更新仍应判定为无响应。"""
    status_file = tmp_path / "browser_login_waiting.json"
    status_file.write_text(
        json.dumps(
            {
                "status": "waiting",
                "message": "请在浏览器窗口中登录闲鱼",
                "ts": ul.time.time() - 45,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    proc = MagicMock(spec=subprocess.Popen)
    proc.poll.return_value = None

    ul._session["status"] = "running"
    ul._session["method"] = "browser"
    ul._session["message"] = "请在浏览器窗口中登录闲鱼"
    ul._session["status_file"] = str(status_file)
    ul._session["proc"] = proc
    ul._session["started_at"] = ul.time.time() - 45

    result = asyncio.run(ul.login_status())

    assert isinstance(result, dict)
    assert result["status"] == "error"
    assert "无响应" in result["message"]
    proc.kill.assert_called_once()


def test_packaged_browser_login_uses_launcher_script_dispatch(monkeypatch, tmp_path):
    """打包模式下不能把 browser_login.py 当作普通脚本参数直接传给主 exe。"""
    script_path = tmp_path / "scripts" / "browser_login.py"
    script_path.parent.mkdir()
    script_path.write_text("raise SystemExit(0)", encoding="utf-8")
    status_dir = tmp_path / "status"
    status_dir.mkdir()
    exe_path = str(tmp_path / "xianyu-hunter.exe")

    proc = MagicMock(spec=subprocess.Popen)
    proc.pid = 12345
    proc.poll.return_value = None

    class DummyThread:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            pass

    monkeypatch.setattr(ul, "_BROWSER_LOGIN_SCRIPT", script_path)
    monkeypatch.setattr(ul.tempfile, "gettempdir", lambda: str(status_dir))
    monkeypatch.setattr(sys, "executable", exe_path)
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    with patch("xianyu_hunter.web.routes.unified_login.subprocess.Popen", return_value=proc) as popen, patch(
        "xianyu_hunter.web.routes.unified_login.threading.Thread", DummyThread
    ):
        result = ul._start_browser_login()

    assert result.status_code == 200
    cmd = popen.call_args.args[0]
    assert cmd[:3] == [exe_path, "--xh-run-script", "browser_login"]
    assert str(script_path) not in cmd[:3]


# ============================================================
# _reset_session 清理测试
# ============================================================
def test_reset_session_clears_multi_user_fields():
    """_reset_session 清除 session_token 和 current_user_id"""
    ul._session["session_token"] = "old_token"
    ul._session["current_user_id"] = "old_user"

    _reset_session()

    assert ul._session.get("session_token") is None
    assert ul._session.get("current_user_id") is None
    assert ul._session["status"] == "idle"
