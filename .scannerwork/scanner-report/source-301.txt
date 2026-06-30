"""浏览器 Cookie 导入集成测试

端到端测试覆盖：
- 多 Profile 场景（Profile 1 含闲鱼 Cookie，应优先选择）
- CDP 导入端到端（mock Playwright）
- v10 加密端到端解密（mock AESGCM）
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from xianyu_hunter.web.services.browser_profile import discover_profiles


def _create_full_browser_env(tmp_path: Path, browser: str = "edge") -> Path:
    """创建完整的模拟浏览器环境（含 Profile + Cookie DB）

    返回 LOCALAPPDATA 应指向的目录
    """
    # 真实路径结构：LOCALAPPDATA/Microsoft/Edge/User Data/...
    user_data = tmp_path / "Microsoft" / "Edge" / "User Data"
    user_data.mkdir(parents=True)

    # Local State
    info_cache = {"Default": {"name": "Default"}, "Profile 1": {"name": "Profile 1"}}
    (user_data / "Local State").write_text(
        json.dumps({"profile": {"info_cache": info_cache}}), encoding="utf-8"
    )

    # Default Profile（无闲鱼 Cookie）
    default_db = user_data / "Default" / "Network" / "Cookies"
    default_db.parent.mkdir(parents=True)
    conn = sqlite3.connect(str(default_db))
    conn.execute("""
        CREATE TABLE cookies (
            host_key TEXT, name TEXT, encrypted_value BLOB,
            value TEXT, path TEXT, expires_utc INTEGER,
            is_secure INTEGER, is_httponly INTEGER
        )
    """)
    conn.execute(
        "INSERT INTO cookies (host_key, name, value) VALUES ('.example.com', 'other', 'val')"
    )
    conn.commit()
    conn.close()

    # Profile 1（含闲鱼 Cookie）
    profile1_db = user_data / "Profile 1" / "Network" / "Cookies"
    profile1_db.parent.mkdir(parents=True)
    conn = sqlite3.connect(str(profile1_db))
    conn.execute("""
        CREATE TABLE cookies (
            host_key TEXT, name TEXT, encrypted_value BLOB,
            value TEXT, path TEXT, expires_utc INTEGER,
            is_secure INTEGER, is_httponly INTEGER
        )
    """)
    conn.execute(
        "INSERT INTO cookies (host_key, name, value) VALUES ('.goofish.com', '_m_h5_tk', 'plain_token')"
    )
    conn.commit()
    conn.close()

    # discover_profiles 会用 LOCALAPPDATA/Microsoft/Edge/User Data
    return tmp_path


def test_import_multi_profile_e2e(tmp_path: Path):
    """多 Profile 场景：Profile 1 含闲鱼 Cookie，应优先选择"""
    browser_env = _create_full_browser_env(tmp_path, "edge")

    with patch.dict("os.environ", {"LOCALAPPDATA": str(browser_env)}):
        profiles = discover_profiles("edge")

    assert len(profiles) == 2
    # Profile 1 含闲鱼 Cookie，应排在前
    assert profiles[0].name == "Profile 1"
    assert profiles[0].has_xianyu_cookie is True
    assert profiles[1].name == "Default"
    assert profiles[1].has_xianyu_cookie is False


def test_import_cdp_e2e():
    """CDP 导入端到端（mock Playwright）"""
    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_context.cookies.return_value = [
        {"name": "_m_h5_tk", "value": "cdp_token", "domain": ".goofish.com", "path": "/"},
        {"name": "unb", "value": "12345", "domain": ".taobao.com", "path": "/"},
        {"name": "other", "value": "xyz", "domain": ".example.com", "path": "/"},
    ]
    mock_browser.contexts = [mock_context]

    with patch("xianyu_hunter.web.routes.browser_import_cdp._check_cdp_reachable", return_value=True), \
         patch("playwright.sync_api.sync_playwright") as mock_pw, \
         patch("xianyu_hunter.web.routes.browser_import_cdp.get_cookie_store") as mock_store:
        mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = mock_browser
        mock_store.return_value.export_cookies.return_value = True

        from xianyu_hunter.web.routes.browser_import_cdp import import_via_cdp
        response = import_via_cdp(port=9222)

    data = json.loads(response.body)
    assert data["ok"] is True
    assert data["imported_count"] == 2  # 过滤掉 other
    assert data["source"] == "cdp"


def test_import_v10_e2e():
    """v10 加密端到端解密（mock AESGCM）"""
    from xianyu_hunter.web.routes.browser_import import decrypt_cookie_value

    # 模拟 v10 解密
    enc_val = b"v10" + b"\x00" * 12 + b"ciphertext" + b"\x00" * 16
    with patch("cryptography.hazmat.primitives.ciphers.aead.AESGCM") as mock_aesgcm:
        mock_instance = mock_aesgcm.return_value
        mock_instance.decrypt.return_value = b"decrypted_value"
        result = decrypt_cookie_value(enc_val, None, b"\x00" * 32)

    assert result == "decrypted_value"
