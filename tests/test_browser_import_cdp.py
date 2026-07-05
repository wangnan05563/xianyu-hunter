"""browser_import_cdp 模块单元测试"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.responses import JSONResponse

from xianyu_hunter.web.routes.browser_import_cdp import (
    _check_cdp_reachable,
    _collect_cookies_via_cdp,
    _filter_xianyu_cookies,
    import_via_cdp,
)


def test_filter_xianyu_cookies():
    """只保留闲鱼/淘宝/支付宝域名的 Cookie"""
    cookies = [
        {"name": "_m_h5_tk", "value": "abc", "domain": ".goofish.com"},
        {"name": "unb", "value": "123", "domain": ".taobao.com"},
        {"name": "other", "value": "xyz", "domain": ".example.com"},
        {"name": "cna", "value": "def", "domain": ".alipay.com"},
    ]
    result = _filter_xianyu_cookies(cookies)
    assert len(result) == 3
    names = [c["name"] for c in result]
    assert "_m_h5_tk" in names
    assert "unb" in names
    assert "cna" in names
    assert "other" not in names


def test_cdp_port_not_reachable():
    """CDP 端口未启动时返回 False"""
    with patch("httpx.get", side_effect=Exception("connection refused")):
        result = _check_cdp_reachable(9222)
    assert result is False


def test_cdp_port_reachable():
    """CDP 端口可达时返回 True"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    with patch("httpx.get", return_value=mock_response):
        result = _check_cdp_reachable(9222)
    assert result is True


def test_cdp_no_xianyu_cookie():
    """浏览器未登录闲鱼时返回空列表"""
    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_context.cookies.return_value = [
        {"name": "other", "value": "xyz", "domain": ".example.com"}
    ]
    mock_browser.contexts = [mock_context]

    with patch("playwright.sync_api.sync_playwright") as mock_pw:
        mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = mock_browser
        result = _collect_cookies_via_cdp(9222)

    assert result == []


def test_cdp_connect_success():
    """CDP 连接成功获取闲鱼 Cookie"""
    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_context.cookies.return_value = [
        {"name": "_m_h5_tk", "value": "abc", "domain": ".goofish.com", "path": "/"},
        {"name": "unb", "value": "123", "domain": ".taobao.com", "path": "/"},
    ]
    mock_browser.contexts = [mock_context]

    with patch("playwright.sync_api.sync_playwright") as mock_pw:
        mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = mock_browser
        result = _collect_cookies_via_cdp(9222)

    assert len(result) == 2
    assert result[0]["name"] == "_m_h5_tk"


def test_import_via_cdp_endpoint_not_reachable():
    """CDP 端点不可达时返回错误响应"""
    # 构造 mock request：多用户隔离需要 request.state.user_id，
    # 但 _check_cdp_reachable 失败时函数直接返回，不访问 request
    mock_request = MagicMock()

    with patch("xianyu_hunter.web.routes.browser_import_cdp._check_cdp_reachable", return_value=False):
        response = import_via_cdp(mock_request, port=9222)

    assert isinstance(response, JSONResponse)
    assert response.status_code == 200
    import json
    data = json.loads(response.body)
    assert data["ok"] is False
    assert "9222" in data["error"]
