"""浏览器 Profile 发现与遍历

职责：发现浏览器所有 Profile，找出含闲鱼 Cookie 的 Profile。
不做解密，只做检测（查询 _m_h5_tk 是否存在）。

优先级排序：
1. 含闲鱼 Cookie 的 Profile 排在前
2. 同等条件下 Default 排在前
3. 其余按 Profile N 数字升序
"""
from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# 浏览器 User Data 根目录映射
_BROWSER_USER_DATA = {
    "edge": lambda lad: Path(lad) / "Microsoft" / "Edge" / "User Data",
    "chrome": lambda lad: Path(lad) / "Google" / "Chrome" / "User Data",
}

# 闲鱼关键 Cookie 名称（用于检测 Profile 是否登录过闲鱼）
_XIANYU_COOKIE_NAMES = {"_m_h5_tk", "_m_h5_tk_enc", "unb", "sgcookie", "cookie2"}

# Profile 目录名匹配（Default 或 Profile N）
_PROFILE_PATTERN = re.compile(r"^(Default|Profile\s+\d+)$")


@dataclass
class BrowserProfile:
    """浏览器单个 Profile 的元信息"""
    name: str           # "Default" / "Profile 1" / "Profile 2"
    user_data_dir: Path # User Data 根目录
    cookies_db: Path    # .../Default|Profile N/Network/Cookies
    local_state: Path   # .../Local State（AES 密钥）
    has_xianyu_cookie: bool  # 是否含 _m_h5_tk 等闲鱼 Cookie


def discover_profiles(browser: str) -> list[BrowserProfile]:
    """遍历 User Data 下所有 Profile 目录

    Args:
        browser: "edge" 或 "chrome"

    Returns:
        按优先级排序的 Profile 列表（含闲鱼 Cookie 的在前）
    """
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if not local_app_data:
        return []

    user_data_dir = _BROWSER_USER_DATA.get(browser.lower(), lambda _: None)(local_app_data)
    if not user_data_dir or not user_data_dir.exists():
        return []

    local_state = user_data_dir / "Local State"
    profile_names = _read_profile_names(local_state)

    # 兜底：Local State 无 info_cache 时扫描目录
    if not profile_names:
        profile_names = _scan_profile_dirs(user_data_dir)

    profiles: list[BrowserProfile] = []
    for name in profile_names:
        profile_dir = user_data_dir / name
        cookies_db = profile_dir / "Network" / "Cookies"
        if not cookies_db.exists():
            continue
        has_xianyu = _check_xianyu_cookie(cookies_db)
        profiles.append(BrowserProfile(
            name=name,
            user_data_dir=user_data_dir,
            cookies_db=cookies_db,
            local_state=local_state,
            has_xianyu_cookie=has_xianyu,
        ))

    # 排序：含闲鱼 Cookie 的在前，Default 次之，其余按名称
    profiles.sort(key=lambda p: (
        not p.has_xianyu_cookie,  # False(含闲鱼) 排前
        p.name != "Default",      # Default 排前
        p.name,                   # 其余按名称
    ))
    return profiles


def _read_profile_names(local_state: Path) -> list[str]:
    """从 Local State 的 profile.info_cache 读取 Profile 名称"""
    if not local_state.exists():
        return []
    try:
        data = json.loads(local_state.read_text(encoding="utf-8"))
        info_cache = data.get("profile", {}).get("info_cache", {})
        return list(info_cache.keys())
    except Exception as e:
        logger.debug("读取 Local State info_cache 失败: %s", e)
        return []


def _scan_profile_dirs(user_data_dir: Path) -> list[str]:
    """兜底：扫描 User Data 下匹配 Default|Profile N 的目录"""
    names = []
    if not user_data_dir.exists():
        return names
    for entry in user_data_dir.iterdir():
        if entry.is_dir() and _PROFILE_PATTERN.match(entry.name):
            names.append(entry.name)
    return names


def _check_xianyu_cookie(cookies_db: Path) -> bool:
    """检测 Profile 是否含闲鱼 Cookie（只看 name，不解密）"""
    try:
        # immutable=1 完全绕过文件锁，适合只读检测
        conn = sqlite3.connect(f"file:{cookies_db}?immutable=1", uri=True)
        try:
            placeholders = ",".join("?" for _ in _XIANYU_COOKIE_NAMES)
            row = conn.execute(
                f"""SELECT 1 FROM cookies
                    WHERE (host_key LIKE '%goofish%' OR host_key LIKE '%taobao%')
                      AND name IN ({placeholders})
                    LIMIT 1""",
                tuple(_XIANYU_COOKIE_NAMES),
            ).fetchone()
            return row is not None
        finally:
            conn.close()
    except Exception as e:
        logger.debug("检测闲鱼 Cookie 失败 (%s): %s", cookies_db, e)
        return False
