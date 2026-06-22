"""实时搜索登录 Cookie 完整性检查测试"""
from __future__ import annotations

from xianyu_hunter.web.routes.api_task_links import _missing_live_search_cookie_names


def test_live_search_cookie_check_passes_with_required_identity_cookies() -> None:
    names = {"cookie2", "sgcookie", "unb", "_m_h5_tk"}

    assert _missing_live_search_cookie_names(names) == []


def test_live_search_cookie_check_reports_missing_identity_cookies() -> None:
    names = {"cookie2", "_m_h5_tk", "_tb_token_"}

    assert _missing_live_search_cookie_names(names) == ["sgcookie", "unb"]
