from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from scripts import browser_login


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
