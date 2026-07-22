from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


# scripts 目录不是 Python 包（无 __init__.py），无法用 `from scripts import browser_login`
# 通过 importlib 从文件路径直接加载模块，避免改动 scripts 目录结构
def _load_browser_login_module():
    project_root = Path(__file__).resolve().parent.parent
    module_path = project_root / "scripts" / "browser_login.py"
    spec = importlib.util.spec_from_file_location("browser_login", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


browser_login = _load_browser_login_module()


def test_login_launch_args_disable_system_proxy_when_not_configured() -> None:
    args = browser_login._build_login_launch_args(SimpleNamespace(proxy_server=""))

    assert "--no-proxy-server" in args
    assert not any(arg.startswith("--proxy-server=") for arg in args)


def test_login_launch_args_use_configured_proxy_when_present() -> None:
    args = browser_login._build_login_launch_args(
        SimpleNamespace(proxy_server="http://127.0.0.1:7890")
    )

    assert "--proxy-server=http://127.0.0.1:7890" in args
    assert "--no-proxy-server" not in args


def test_login_resource_filter_allows_ali_login_cdn_images() -> None:
    assert not browser_login._should_abort_login_resource(
        "https://g.alicdn.com/secdev/sufei_data/login.png",
        "image",
    )
    assert not browser_login._should_abort_login_resource(
        "https://img.alicdn.com/tfs/login-qrcode.png",
        "image",
    )


def test_login_resource_filter_allows_ali_tracking_cookie_domains() -> None:
    assert not browser_login._should_abort_login_resource(
        "https://arms-retcode.aliyuncs.com/r.png",
        "image",
    )
    assert not browser_login._should_abort_login_resource(
        "https://ynuf.aliapp.org/service/um.json",
        "manifest",
    )


def test_login_resource_filter_still_blocks_unrelated_images() -> None:
    assert browser_login._should_abort_login_resource(
        "https://cdn.example.com/tracker/banner.png",
        "image",
    )


def test_recoverable_profile_launch_error_detects_edge_exit_code() -> None:
    err = RuntimeError(
        "BrowserType.launch_persistent_context: Target page, context or browser "
        "has been closed\n<process did exit: exitCode=21, signal=null>"
    )

    assert browser_login._is_recoverable_profile_launch_error(err)


def test_quarantine_browser_profile_moves_existing_profile(tmp_path: Path) -> None:
    profile = tmp_path / "browser-data"
    default_dir = profile / "Default"
    default_dir.mkdir(parents=True)
    (default_dir / "Preferences").write_text("old", encoding="utf-8")

    backup = browser_login._quarantine_browser_profile(profile)

    assert backup is not None
    assert backup.exists()
    assert (backup / "Default" / "Preferences").read_text(encoding="utf-8") == "old"
    assert profile.exists()
    assert not any(profile.iterdir())


@pytest.mark.asyncio
async def test_launch_context_retries_with_rebuilt_profile_after_edge_profile_crash(
    tmp_path: Path,
) -> None:
    profile = tmp_path / "browser-data"
    (profile / "Default").mkdir(parents=True)
    (profile / "Default" / "Preferences").write_text("old", encoding="utf-8")

    context = object()
    launch_calls: list[str] = []

    class FakeChromium:
        async def launch_persistent_context(self, **kwargs):
            launch_calls.append(kwargs["user_data_dir"])
            if len(launch_calls) == 1:
                raise RuntimeError(
                    "BrowserType.launch_persistent_context: Target page, context "
                    "or browser has been closed\nexitCode=21"
                )
            return context

    pw = SimpleNamespace(chromium=FakeChromium())
    status_updates: list[dict] = []

    result = await browser_login._launch_login_context_with_recovery(
        pw,
        {"user_data_dir": str(profile)},
        profile,
        set_status=lambda **kw: status_updates.append(kw),
    )

    assert result is context
    assert launch_calls == [str(profile), str(profile)]
    assert any(profile.parent.glob("browser-data.bak-*"))
    assert status_updates[-1]["status"] == "starting"


@pytest.mark.asyncio
async def test_launch_context_uses_recovery_profile_when_quarantine_denied(
    monkeypatch,
    tmp_path: Path,
) -> None:
    profile = tmp_path / "browser-data"
    profile.mkdir()

    context = object()
    launch_calls: list[str] = []

    class FakeChromium:
        async def launch_persistent_context(self, **kwargs):
            launch_calls.append(kwargs["user_data_dir"])
            if len(launch_calls) == 1:
                raise RuntimeError(
                    "BrowserType.launch_persistent_context: Target page, context "
                    "or browser has been closed\nexitCode=21"
                )
            return context

    monkeypatch.setattr(
        browser_login,
        "_quarantine_browser_profile",
        lambda _profile: (_ for _ in ()).throw(PermissionError("locked")),
    )

    result = await browser_login._launch_login_context_with_recovery(
        SimpleNamespace(chromium=FakeChromium()),
        {"user_data_dir": str(profile)},
        profile,
        set_status=lambda **_kw: None,
    )

    assert result is context
    assert launch_calls[0] == str(profile)
    assert launch_calls[1] != str(profile)
    assert Path(launch_calls[1]).name.startswith("browser-data.recovery-")


@pytest.mark.asyncio
async def test_collect_settled_cookies_keeps_waiting_while_cookie_count_grows(monkeypatch) -> None:
    cookie_batches = [
        [{"name": f"c{i}", "value": "v", "domain": ".goofish.com"} for i in range(40)],
        [{"name": f"c{i}", "value": "v", "domain": ".goofish.com"} for i in range(40)],
        [{"name": f"c{i}", "value": "v", "domain": ".goofish.com"} for i in range(75)],
        [{"name": f"c{i}", "value": "v", "domain": ".goofish.com"} for i in range(75)],
    ]
    context = AsyncMock()
    context.cookies.side_effect = cookie_batches
    monkeypatch.setattr(browser_login.asyncio, "sleep", AsyncMock())

    cookies = await browser_login._collect_settled_cookies(
        context,
        min_wait=0,
        max_wait=10,
        interval=1,
        stable_rounds=1,
    )

    assert len(cookies) == 75
    assert context.cookies.await_count == 4


@pytest.mark.asyncio
async def test_prepare_login_cookie_export_updates_running_status(monkeypatch) -> None:
    context = AsyncMock()
    page = AsyncMock()
    route_handler = AsyncMock()
    timings: dict[str, float] = {}
    status_updates: list[dict] = []

    monkeypatch.setattr(browser_login.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(
        browser_login,
        "_collect_settled_cookies",
        AsyncMock(return_value=[{"name": "unb", "value": "2209384756290"}]),
    )

    cookies = await browser_login._prepare_login_cookie_export(
        context,
        page,
        route_handler,
        timings,
        set_status=lambda **kw: status_updates.append(kw),
    )

    assert cookies == [{"name": "unb", "value": "2209384756290"}]
    assert status_updates[0]["status"] == "running"
    assert "保存 Cookie" in status_updates[0]["message"]
    assert len(status_updates) >= 4
