"""统一 Cookie 存储 - 用 JSON 文件替代 SQLite 读取做 Cookie 验证

设计原则：
- 浏览器 Cookie 写入 SQLite 是异步的，直接读取 SQLite 不可靠
- 方案：登录子进程成功后，将 Cookie 导出到 JSON 文件（立即可见）
- 本模块负责：JSON 文件读写、Cookie 有效性验证、同步到 browser-data SQLite

使用方式：
1. 登录子进程成功后调用 `cookie_store.export_and_sync(cookies)` 写入 JSON + 同步 SQLite
2. Web 后端调用 `cookie_store.has_valid_cookies()` 验证 Cookie 是否存在
3. Worker 启动时从 browser-data SQLite 读取（Playwright 原生方式）
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path

from xianyu_hunter.infra.yaml_config import get_config
from xianyu_hunter.web.services.cookie_db import batch_upsert_cookies, init_cookie_table

logger = logging.getLogger(__name__)

# JSON 格式的 Cookie 存储文件（与 browser-data 同级）
_COOKIE_JSON_FILE = Path("data") / "cookies.json"

# 闲鱼登录关键 Cookie 名称
_GOOFISH_KEY_COOKIES = {"_m_h5_tk", "_m_h5_tk_enc", "unb", "sgcookie", "cookie2", "lg2"}

# 缓存 TTL（秒）
_CACHE_TTL = 30.0


class CookieStore:
    """单例 Cookie 存储管理器

    两种数据源：
    1. JSON 文件（主数据源）：登录子进程写入，立即可见
    2. browser-data SQLite（从数据源）：Worker 读取用，异步同步
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: dict | None = None
        self._cache_ts: float = 0.0
        _COOKIE_JSON_FILE.parent.mkdir(parents=True, exist_ok=True)

    # ---------- 公共 API ----------

    def has_valid_cookies(self) -> bool:
        """检查是否有有效的闲鱼 Cookie（JSON 优先，SQLite 兜底）"""
        data = self._read_json()
        if data and data.get("cookies"):
            names = {c["name"] for c in data["cookies"]}
            if _GOOFISH_KEY_COOKIES & names:
                return True
        # 兜底：JSON 为空时检查 SQLite
        return self._check_sqlite()

    def validate_cookies_with_expiry(self) -> tuple[bool, str]:
        """检查 Cookie 是否有效（含过期时间判断）

        为什么需要此方法：has_valid_cookies 只检查 Cookie 是否存在，
        无法识别已过期的 Cookie。此方法补充过期时间判断，供健康检查使用。

        Returns:
            (is_valid, reason) 元组。reason 为失败原因或 "ok"
        """
        data = self._read_json()
        if not data or not data.get("cookies"):
            return False, "no_cookie_data"

        cookies_list = data["cookies"]
        names = {c.get("name", "") for c in cookies_list}

        # 检查关键 Cookie 是否存在
        if not (_GOOFISH_KEY_COOKIES & names):
            return False, "no_key_cookies"

        # 过期时间检查（兼容旧数据：无 expires 字段视为 session cookie，不过期）
        # Playwright 的 expires 为 Unix 时间戳（秒），-1 或 0 表示 session cookie
        now = time.time()
        for c in cookies_list:
            expires = c.get("expires", -1)
            if expires and expires > 0 and expires < now:
                return False, f"cookie_expired:{c.get('name')}"

        return True, "ok"

    def get_cookie_info(self) -> dict:
        """获取 Cookie 摘要信息（供 /api/auth/me 使用）"""
        data = self._read_json()
        if not data or not data.get("cookies"):
            return {"logged_in": False, "source": "none"}
        names = {c["name"] for c in data["cookies"]}
        if not (_GOOFISH_KEY_COOKIES & names):
            return {"logged_in": False, "source": "json_no_key"}
        return {
            "logged_in": True,
            "source": "json",
            "cookie_count": len(data["cookies"]),
            "exported_at": data.get("exported_at", 0),
            "method": data.get("method", "unknown"),
        }

    def get_cookie_expiry(self) -> float | None:
        """获取最早过期的闲鱼关键 Cookie 的过期时间

        用于定时同步判断是否即将过期。
        返回 Unix 时间戳（秒），无 Cookie 或 session cookie 返回 None。
        """
        data = self._read_json()
        if not data or not data.get("cookies"):
            return None
        # 只看闲鱼关键 Cookie 的过期时间
        key_cookies = [
            c for c in data["cookies"]
            if c.get("name") in _GOOFISH_KEY_COOKIES
        ]
        if not key_cookies:
            return None
        # 取最早的过期时间（排除 session cookie 的 -1/0）
        expiries = [
            c.get("expires", -1) for c in key_cookies
            if c.get("expires", -1) and c.get("expires", -1) > 0
        ]
        return min(expiries) if expiries else None

    def export_cookies(self, cookies: list[dict], method: str = "unknown") -> bool:
        """导出 Cookie 到 JSON 文件（登录成功后由子进程调用）

        Args:
            cookies: Playwright cookie 对象列表
            method: 登录方式标识（browser/qr/cookie/import）
        """
        if not cookies:
            return False
        data = {
            "exported_at": time.time(),
            "method": method,
            "cookie_count": len(cookies),
            "cookies": [
                {
                    "name": c.get("name", ""),
                    "value": c.get("value", ""),
                    "domain": c.get("domain", ""),
                    "path": c.get("path", "/"),
                    # 保存过期时间用于健康检查的有效性判断
                    # Playwright 的 expires 为 Unix 时间戳（秒），-1 表示 session cookie
                    "expires": c.get("expires", -1),
                }
                for c in cookies
            ],
        }
        success = self._write_json(data)
        # 同步到 browser-data SQLite（Worker 使用）
        if success:
            self._sync_to_sqlite(cookies)
        return success

    def sync_to_sqlite(self, cookies: list[dict]) -> bool:
        """外部调用：将 Cookie 同步到 browser-data SQLite

        Args:
            cookies: Playwright cookie 对象列表
        """
        return self._sync_to_sqlite(cookies)

    # ---------- 内部方法 ----------

    def _read_json(self) -> dict | None:
        """读取 JSON Cookie 文件（带缓存）"""
        with self._lock:
            if self._cache and (time.time() - self._cache_ts) < _CACHE_TTL:
                return self._cache
        if not _COOKIE_JSON_FILE.exists():
            return None
        try:
            data = json.loads(_COOKIE_JSON_FILE.read_text(encoding="utf-8"))
            with self._lock:
                self._cache = data
                self._cache_ts = time.time()
            return data
        except (json.JSONDecodeError, OSError):
            return None

    def _write_json(self, data: dict) -> bool:
        """原子写入 JSON Cookie 文件"""
        try:
            tmp = _COOKIE_JSON_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(_COOKIE_JSON_FILE)
            with self._lock:
                self._cache = data
                self._cache_ts = time.time()
            logger.info("Cookie 已导出到 JSON: %d 个, method=%s", data.get("cookie_count", 0), data.get("method"))
            return True
        except OSError as e:
            logger.error("写入 Cookie JSON 失败: %s", e)
            return False

    def _check_sqlite(self) -> bool:
        """兜底方案：检查 browser-data SQLite 中是否有闲鱼 Cookie"""
        cfg = get_config()
        user_data_dir = Path(cfg.browser.user_data_dir)
        if not user_data_dir.is_absolute():
            user_data_dir = Path.cwd() / user_data_dir
        cookie_db = user_data_dir / "Default" / "Network" / "Cookies"
        if not cookie_db.exists():
            return False
        try:
            with sqlite3.connect(f"file:{cookie_db}?mode=ro", uri=True) as conn:
                conn.execute("PRAGMA query_only=ON")
                # 检查 cookies 表是否存在（Playwright 创建的空库可能无表）
                table_exists = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='cookies'"
                ).fetchone()
                if not table_exists:
                    return False
                rows = conn.execute(
                    "SELECT name FROM cookies WHERE host_key LIKE ? OR host_key LIKE ?",
                    ("%goofish%", "%taobao%"),
                ).fetchall()
                names = {n for (n,) in rows}
                return bool(_GOOFISH_KEY_COOKIES & names)
        except sqlite3.OperationalError:
            # 文件被锁定，返回 False（下次重试）
            return False
        except Exception:
            return False

    def _sync_to_sqlite(self, cookies: list[dict]) -> bool:
        """将 Cookie 同步写入 browser-data SQLite 数据库"""
        cfg = get_config()
        user_data_dir = Path(cfg.browser.user_data_dir)
        if not user_data_dir.is_absolute():
            user_data_dir = Path.cwd() / user_data_dir
        cookie_db = user_data_dir / "Default" / "Network" / "Cookies"
        cookie_db.parent.mkdir(parents=True, exist_ok=True)

        now_utc = int(time.time()) + 11644473600  # Chrome 时间戳（Windows epoch）

        try:
            with sqlite3.connect(str(cookie_db)) as conn:
                init_cookie_table(conn)
                # 过滤无效 cookie 并转换为 cookie_db 所需的字典格式
                cookie_data_list = [
                    {
                        "host_key": c.get("domain", ""),
                        "name": c.get("name", ""),
                        "value": c.get("value", ""),
                        "path": c.get("path", "/"),
                        "expires_utc": now_utc + 86400 * 365,
                        "is_secure": 1,
                        "is_httponly": 1,
                        "creation_utc": now_utc,
                        "last_access_utc": now_utc,
                    }
                    for c in cookies
                    if c.get("name") and c.get("value") and c.get("domain")
                ]
                synced = batch_upsert_cookies(conn, cookie_data_list)
                conn.commit()
            logger.info("Cookie 已同步到 SQLite: %d/%d 个", synced, len(cookies))
            return synced > 0
        except sqlite3.OperationalError as e:
            logger.warning("SQLite 同步失败（文件锁定）: %s", e)
            return False
        except Exception as e:
            logger.error("SQLite 同步失败: %s", e)
            return False


# 全局单例
_store: CookieStore | None = None
_store_lock = threading.Lock()


def get_cookie_store() -> CookieStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = CookieStore()
        return _store