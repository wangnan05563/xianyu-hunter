"""回归测试：invalid CookieStatus 也必须返回真实字段（O-08-11 P1 修复）

背景：修复前 _make_invalid_status 不设置 cookie_count / key_cookies_found /
layers_status / security_flags，导致前端在 Cookie 失效时显示"Cookie 数 0 个"和
"各层缺失"，与 JSON 实际有 15 个 cookie 矛盾，严重误导用户（明明有 cookie 却报 0 个）。

本测试锁定该修复：invalid 仅表示 key cookie（如 _m_h5_tk）过期或服务端会话失效，
绝不等于"没有 cookie"。这些字段是前端展示 /api/auth/cookie/health 的核心依据。
"""
from __future__ import annotations

import time

from xianyu_hunter.web.services.cookie_status import (
    _GOOFISH_KEY_COOKIES,
    _make_invalid_status,
)


def _sample_cookies() -> list[dict]:
    """构造含 identity + session 关键 cookie 的样例（token 已过期场景）"""
    # 取一个真实 key cookie 名，避免硬编码与配置漂移
    key_name = next(iter(_GOOFISH_KEY_COOKIES))
    # 内嵌 30 分钟前的时间戳 → 触发 m5tk 过期判定
    expired_token = f"deadbeef_{int(time.time() * 1000) - 30 * 60 * 1000}"
    return [
        {"name": key_name, "value": expired_token, "expires": -1, "secure": True},
        {"name": "cna", "value": "trackval", "expires": -1},
        {"name": "unb", "value": "135379349", "expires": -1, "httpOnly": True},
    ]


def test_invalid_status_returns_real_fields_not_blank():
    """P1 修复核心：invalid 也要返回真实 cookie_count / 层状态 / 安全标记 / key cookie"""
    cookies = _sample_cookies()
    names = {c["name"] for c in cookies}
    status = _make_invalid_status(
        "default",
        "cookie_expired:_m_h5_tk",
        {"cookies": cookies, "exported_at": time.time()},
        cookies,
        names,
    )

    # 仍是 invalid（key cookie 过期）
    assert status.is_valid is False

    # 真实 cookie 数量，而非 0
    assert status.cookie_count == len(cookies), "invalid 时 cookie_count 不应为 0"

    # 层状态按实际 cookie 计算（identity/session/tracking 全覆盖）
    assert set(status.layers_status) == {"identity", "session", "tracking"}
    assert any(status.layers_status.values()), "至少应有一层被识别为存在"

    # 安全标记按实际 cookie 计算（样例含 secure + httpOnly）
    assert status.security_flags.get("has_secure") is True
    assert status.security_flags.get("has_httponly") is True

    # key cookie 被正确识别，而非空列表
    assert status.key_cookies_found == sorted(_GOOFISH_KEY_COOKIES & names)
    assert status.key_cookies_found, "invalid 时应识别到 key cookie"


def test_invalid_status_no_data_has_zero_count_and_empty_layers():
    """边界：确实没有任何 cookie 时，字段才为 0 / 空（与"有 cookie 但失效"区分）"""
    status = _make_invalid_status("default", "no_cookie_data", None, [], set())

    assert status.is_valid is False
    assert status.cookie_count == 0
    assert status.layers_status == {}
    assert status.key_cookies_found == []
