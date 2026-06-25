"""browser_profile 模块单元测试"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from xianyu_hunter.web.services.browser_profile import (
    BrowserProfile,
    discover_profiles,
)


def _create_cookie_db(db_path: Path, has_xianyu: bool = True) -> None:
    """创建测试用的 Cookie 数据库"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE cookies (
            host_key TEXT, name TEXT, encrypted_value BLOB,
            value TEXT, path TEXT, expires_utc INTEGER,
            is_secure INTEGER, is_httponly INTEGER
        )
    """)
    if has_xianyu:
        conn.execute(
            "INSERT INTO cookies (host_key, name) VALUES ('.goofish.com', '_m_h5_tk')"
        )
    else:
        conn.execute(
            "INSERT INTO cookies (host_key, name) VALUES ('.example.com', 'other')"
        )
    conn.commit()
    conn.close()


def _create_local_state(user_data_dir: Path, profiles: list[str]) -> None:
    """创建测试用的 Local State 文件"""
    user_data_dir.mkdir(parents=True, exist_ok=True)
    info_cache = {p: {"name": p} for p in profiles}
    (user_data_dir / "Local State").write_text(
        json.dumps({"profile": {"info_cache": info_cache}}), encoding="utf-8"
    )


def test_discover_profiles_default_only(tmp_path: Path):
    """只有 Default 目录时能正确发现"""
    user_data = tmp_path / "Microsoft" / "Edge" / "User Data"
    _create_local_state(user_data, ["Default"])
    _create_cookie_db(user_data / "Default" / "Network" / "Cookies", has_xianyu=True)

    with patch.dict("os.environ", {"LOCALAPPDATA": str(tmp_path)}):
        profiles = discover_profiles("edge")

    assert len(profiles) == 1
    assert profiles[0].name == "Default"
    assert profiles[0].has_xianyu_cookie is True


def test_discover_profiles_multiple(tmp_path: Path):
    """Default + Profile 1/2 都能被发现"""
    user_data = tmp_path / "Microsoft" / "Edge" / "User Data"
    _create_local_state(user_data, ["Default", "Profile 1", "Profile 2"])
    _create_cookie_db(user_data / "Default" / "Network" / "Cookies", has_xianyu=False)
    _create_cookie_db(user_data / "Profile 1" / "Network" / "Cookies", has_xianyu=True)
    _create_cookie_db(user_data / "Profile 2" / "Network" / "Cookies", has_xianyu=False)

    with patch.dict("os.environ", {"LOCALAPPDATA": str(tmp_path)}):
        profiles = discover_profiles("edge")

    assert len(profiles) == 3
    names = [p.name for p in profiles]
    assert "Default" in names
    assert "Profile 1" in names
    assert "Profile 2" in names


def test_discover_profiles_priority(tmp_path: Path):
    """含闲鱼 Cookie 的 Profile 排在前"""
    user_data = tmp_path / "Microsoft" / "Edge" / "User Data"
    _create_local_state(user_data, ["Default", "Profile 1"])
    _create_cookie_db(user_data / "Default" / "Network" / "Cookies", has_xianyu=False)
    _create_cookie_db(user_data / "Profile 1" / "Network" / "Cookies", has_xianyu=True)

    with patch.dict("os.environ", {"LOCALAPPDATA": str(tmp_path)}):
        profiles = discover_profiles("edge")

    # Profile 1 含闲鱼 Cookie，应排在前
    assert profiles[0].name == "Profile 1"
    assert profiles[0].has_xianyu_cookie is True
    assert profiles[1].name == "Default"
    assert profiles[1].has_xianyu_cookie is False


def test_discover_profiles_no_xianyu(tmp_path: Path):
    """无闲鱼 Cookie 的 Profile 也返回，但 has_xianyu_cookie 为 False"""
    user_data = tmp_path / "Microsoft" / "Edge" / "User Data"
    _create_local_state(user_data, ["Default"])
    _create_cookie_db(user_data / "Default" / "Network" / "Cookies", has_xianyu=False)

    with patch.dict("os.environ", {"LOCALAPPDATA": str(tmp_path)}):
        profiles = discover_profiles("edge")

    assert len(profiles) == 1
    assert profiles[0].has_xianyu_cookie is False


def test_discover_profiles_fallback_scan(tmp_path: Path):
    """Local State 无 info_cache 时，兜底扫描目录"""
    user_data = tmp_path / "Microsoft" / "Edge" / "User Data"
    user_data.mkdir(parents=True)
    # 不写 Local State，只创建目录
    _create_cookie_db(user_data / "Default" / "Network" / "Cookies", has_xianyu=True)

    with patch.dict("os.environ", {"LOCALAPPDATA": str(tmp_path)}):
        profiles = discover_profiles("edge")

    assert len(profiles) >= 1
    assert any(p.name == "Default" for p in profiles)
