"""LoginStrategySelector 单元测试"""
from __future__ import annotations

import os
import socket
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from xianyu_hunter.modules.login_strategy import (
    LoginStrategy,
    LoginStrategySelector,
    StrategyEvaluation,
    get_strategy_selector,
)


# ============== 策略枚举测试 ==============


def test_login_strategy_values() -> None:
    """策略枚举值正确"""
    assert LoginStrategy.CDP_CONNECT.value == "cdp_connect"
    assert LoginStrategy.REUSE_USERDATA.value == "reuse_userdata"
    assert LoginStrategy.BROWSER_IMPORT.value == "browser_import"
    assert LoginStrategy.QR_SCAN.value == "qr_scan"
    assert LoginStrategy.COOKIE_INJECT.value == "cookie_inject"


# ============== CDP 检测测试 ==============


def test_cdp_available_when_port_open() -> None:
    """CDP 端口开放时检测为可用"""
    selector = LoginStrategySelector(cdp_port=19999)

    mock_socket = MagicMock()
    mock_socket.__enter__ = MagicMock(return_value=mock_socket)
    mock_socket.__exit__ = MagicMock(return_value=False)

    with patch("socket.create_connection", return_value=mock_socket):
        assert selector._check_cdp_available() is True


def test_cdp_unavailable_when_port_closed() -> None:
    """CDP 端口关闭时检测为不可用"""
    selector = LoginStrategySelector(cdp_port=19999)
    with patch("socket.create_connection", side_effect=ConnectionRefusedError):
        assert selector._check_cdp_available() is False


def test_cdp_unavailable_on_timeout() -> None:
    """CDP 连接超时检测为不可用"""
    selector = LoginStrategySelector(cdp_port=19999)
    with patch("socket.create_connection", side_effect=socket.timeout):
        assert selector._check_cdp_available() is False


# ============== Cookie 检测测试 ==============


def test_user_data_cookies_available_via_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """JSON 文件有有效 Cookie 时检测为可用"""
    selector = LoginStrategySelector()
    monkeypatch.setattr(selector, "_check_user_data_cookies", lambda: True)
    assert selector._check_user_data_cookies() is True


def test_user_data_cookies_not_available_empty_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """JSON 文件无关键 Cookie 时检测为不可用"""
    selector = LoginStrategySelector()
    monkeypatch.setattr(selector, "_check_user_data_cookies", lambda: False)
    assert selector._check_user_data_cookies() is False


# ============== 浏览器导入检测测试 ==============


def test_browser_importable_on_windows_with_edge(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Windows 上有 Edge Cookie 文件时可导入"""
    selector = LoginStrategySelector()

    monkeypatch.setattr(os, "name", "nt")
    fake_localappdata = str(tmp_path)
    monkeypatch.setenv("LOCALAPPDATA", fake_localappdata)

    edge_cookie = tmp_path / "Microsoft" / "Edge" / "User Data" / "Default" / "Network" / "Cookies"
    edge_cookie.parent.mkdir(parents=True, exist_ok=True)
    edge_cookie.touch()

    assert selector._check_browser_importable() is True


def test_browser_importable_on_windows_with_chrome(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Windows 上有 Chrome Cookie 文件时可导入"""
    selector = LoginStrategySelector()

    monkeypatch.setattr(os, "name", "nt")
    fake_localappdata = str(tmp_path)
    monkeypatch.setenv("LOCALAPPDATA", fake_localappdata)

    chrome_cookie = tmp_path / "Google" / "Chrome" / "User Data" / "Default" / "Network" / "Cookies"
    chrome_cookie.parent.mkdir(parents=True, exist_ok=True)
    chrome_cookie.touch()

    assert selector._check_browser_importable() is True


def test_browser_importable_not_on_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    """非 Windows 系统不可导入"""
    selector = LoginStrategySelector()
    monkeypatch.setattr(os, "name", "posix")
    assert selector._check_browser_importable() is False


def test_browser_importable_no_browser_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Windows 上无浏览器 Cookie 文件时不可导入"""
    selector = LoginStrategySelector()

    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert selector._check_browser_importable() is False


# ============== evaluate 综合测试 ==============


def test_evaluate_recommends_cdp_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    """CDP 可用时优先推荐 CDP"""
    selector = LoginStrategySelector()
    monkeypatch.setattr(selector, "_check_cdp_available", lambda: True)

    result = selector.evaluate()

    assert result.recommended == LoginStrategy.CDP_CONNECT
    assert LoginStrategy.CDP_CONNECT in result.available_strategies
    assert result.details["cdp_available"] is True


def test_evaluate_recommends_reuse_when_cookies_exist(monkeypatch: pytest.MonkeyPatch) -> None:
    """有有效 Cookie 时推荐复用"""
    selector = LoginStrategySelector()
    monkeypatch.setattr(selector, "_check_cdp_available", lambda: False)
    monkeypatch.setattr(selector, "_check_user_data_cookies", lambda: True)

    result = selector.evaluate()

    assert result.recommended == LoginStrategy.REUSE_USERDATA
    assert LoginStrategy.CDP_CONNECT not in result.available_strategies


def test_evaluate_recommends_import_when_browser_has_cookies(monkeypatch: pytest.MonkeyPatch) -> None:
    """系统浏览器有 Cookie 时推荐导入"""
    selector = LoginStrategySelector()
    monkeypatch.setattr(selector, "_check_cdp_available", lambda: False)
    monkeypatch.setattr(selector, "_check_user_data_cookies", lambda: False)
    monkeypatch.setattr(selector, "_check_browser_importable", lambda: True)

    result = selector.evaluate()

    assert result.recommended == LoginStrategy.BROWSER_IMPORT


def test_evaluate_recommends_qr_as_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """无任何已有登录态时推荐扫码"""
    selector = LoginStrategySelector()
    monkeypatch.setattr(selector, "_check_cdp_available", lambda: False)
    monkeypatch.setattr(selector, "_check_user_data_cookies", lambda: False)
    monkeypatch.setattr(selector, "_check_browser_importable", lambda: False)

    result = selector.evaluate()

    assert result.recommended == LoginStrategy.QR_SCAN
    # 扫码和 Cookie 注入都应可用
    assert LoginStrategy.QR_SCAN in result.available_strategies
    assert LoginStrategy.COOKIE_INJECT in result.available_strategies


def test_evaluate_always_includes_cookie_inject(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cookie 注入始终可用（兜底方案）"""
    selector = LoginStrategySelector()
    monkeypatch.setattr(selector, "_check_cdp_available", lambda: False)
    monkeypatch.setattr(selector, "_check_user_data_cookies", lambda: False)
    monkeypatch.setattr(selector, "_check_browser_importable", lambda: False)

    result = selector.evaluate()
    assert LoginStrategy.COOKIE_INJECT in result.available_strategies


# ============== StrategyEvaluation 测试 ==============


def test_strategy_evaluation_to_dict() -> None:
    """to_dict 序列化正确"""
    ev = StrategyEvaluation(
        recommended=LoginStrategy.CDP_CONNECT,
        reason="test reason",
        available_strategies=[LoginStrategy.CDP_CONNECT, LoginStrategy.COOKIE_INJECT],
        details={"cdp_available": True},
    )
    d = ev.to_dict()
    assert d["recommended"] == "cdp_connect"
    assert d["reason"] == "test reason"
    assert d["available"] == ["cdp_connect", "cookie_inject"]
    assert d["details"]["cdp_available"] is True


# ============== 单例测试 ==============


def test_get_strategy_selector_singleton() -> None:
    """get_strategy_selector 返回单例"""
    s1 = get_strategy_selector()
    s2 = get_strategy_selector()
    assert s1 is s2
