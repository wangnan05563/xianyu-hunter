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
import re
import sqlite3
import threading
import time
from pathlib import Path

from xianyu_hunter.infra.yaml_config import get_config
from xianyu_hunter.web.services.cookie_db import batch_upsert_cookies, delete_cookies_by_domain, init_cookie_table

logger = logging.getLogger(__name__)

# JSON 格式的 Cookie 存储目录（与 browser-data 同级）
# MU2 改造：按 user_id 隔离，每个用户一个独立 JSON 文件
_COOKIE_JSON_DIR = Path("data")

# user_id 白名单：仅允许字母数字下划线短横线，长度 1-64
# 防止路径遍历：user_id 后续会从 JWT/数据库解析，恶意 user_id（如 ../../etc/passwd）
# 会被拼入文件名造成 data 目录外写入，必须在此入口拦截
_USER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _cookie_json_path(user_id: str = "default") -> Path:
    """按 user_id 生成 Cookie JSON 文件路径

    为什么用 Path 多参数构造而非模块级常量拼接：
    测试通过 monkeypatch 替换模块 Path 为 lambda *args: tmp_path / args[-1]，
    多参数构造使 lambda 取 args[-1]（文件名）落到 tmp_path 下，便于测试隔离。
    """
    if not _USER_ID_RE.match(user_id):
        raise ValueError(f"invalid user_id: {user_id!r}")
    return Path("data", f"cookies_{user_id}.json")

# 闲鱼登录关键 Cookie 名称
_GOOFISH_KEY_COOKIES = {"_m_h5_tk", "_m_h5_tk_enc", "unb", "sgcookie", "cookie2", "lg2"}

# 缓存 TTL（秒）
_CACHE_TTL = 30.0

# 已知的测试数据特征（来自测试用例的默认值）
# 这些值不应被当作真实 Cookie 返回给用户或写入 JSON 存储
_TEST_COOKIE_VALUES: dict[str, set[str]] = {
    "unb": {"123456", "123"},        # 测试用例默认用户ID
    "cookie2": {"abc"},              # 测试用例默认会话ID
    "_m_h5_tk": {"abc"},             # 测试用例默认令牌
    "_m_h5_tk_enc": {"enc", "enc_123", "abc123enc456"},  # 测试用例默认加密令牌
    "sgcookie": {"sg", "sg_token"},  # 测试用例默认 sgcookie
}

# 真实 Cookie 的格式特征（用于拦截黑名单之外的测试数据）
# 为什么用正则而非精确匹配：测试代码可能使用 real_token_123、fake_token 等任意字符串，
# 精确匹配无法覆盖；用格式校验能识别所有不符合真实格式的值
# 注意：只对格式明确固定的 Cookie 添加校验，避免误伤真实数据
_COOKIE_FORMAT_PATTERNS: dict[str, re.Pattern] = {
    # _m_h5_tk: 32位hex + 下划线 + 13位毫秒时间戳（如 c7b2c44645275604a525e6287fea2c3a_1782530783399）
    # 大小写都接受：真实浏览器可能返回大写 hex
    "_m_h5_tk": re.compile(r"^[0-9a-fA-F]{32}_\d{13}$"),
    # unb: 8位以上纯数字用户ID（测试值 123456 只有6位）
    "unb": re.compile(r"^\d{8,}$"),
    # cookie2: 32位以上十六进制会话ID（大小写都接受）
    "cookie2": re.compile(r"^[0-9a-fA-F]{32,}$"),
    # sgcookie: 真实值通常以 E100 开头且长度 >= 20（URL编码的加密字符串）
    # 测试值 "sg"(2), "sg_token"(8) 等短字符串会被拦截
    "sgcookie": re.compile(r"^.{20,}$"),
    # _m_h5_tk_enc: 加密令牌，真实值长度 >= 16（测试值 enc/enc_123 等较短）
    "_m_h5_tk_enc": re.compile(r"^.{16,}$"),
}


def is_test_cookie(name: str, value: str) -> bool:
    """检测 Cookie 是否为测试数据

    两层过滤策略：
    1. 黑名单匹配：拦截测试用例的已知默认值（unb=123456 等）
    2. 格式校验：对有关键格式特征的 Cookie 名称校验值是否符合真实格式
       （如 _m_h5_tk 必须是 hex_timestamp 格式，real_token_123 这类会被拦截）

    真实的闲鱼 Cookie 有明确的格式特征：
    - unb: 8位以上纯数字用户ID
    - cookie2: 32位以上的十六进制会话ID
    - _m_h5_tk: 格式为 token_timestamp 的安全令牌（32位hex_13位时间戳）
    """
    if not value:
        return True
    # 第一层：黑名单精确匹配
    test_values = _TEST_COOKIE_VALUES.get(name)
    if test_values and value in test_values:
        return True
    # 第二层：格式校验（仅对有已知格式的 Cookie 名称生效）
    # 为什么需要这一层：测试代码可能使用任意字符串如 real_token_123，
    # 不在黑名单中但也不符合真实格式，必须拦截以防污染 JSON 存储
    pattern = _COOKIE_FORMAT_PATTERNS.get(name)
    if pattern and not pattern.match(value):
        logger.warning("Cookie %s 值不符合真实格式，识别为测试数据: %s", name, value)
        return True
    return False


class CookieStore:
    """单例 Cookie 存储管理器

    两种数据源：
    1. JSON 文件（主数据源）：登录子进程写入，立即可见
    2. browser-data SQLite（从数据源）：Worker 读取用，异步同步
    """

    def __init__(self) -> None:
        # 用 RLock（可重入锁）：update_cookie_values 需要在持锁状态下调用
        # _read_json/_write_json（它们各自也加锁），Lock 不可重入会死锁
        self._lock = threading.RLock()
        # MU2 改造：缓存按 user_id 分桶 {user_id: (data, timestamp)}
        # 为什么删除旧的单值 _cache_ts：多用户场景下各用户缓存独立过期，
        # 单一时间戳无法表达"每个用户各自的缓存写入时刻"
        self._cache: dict[str, tuple[dict, float]] = {}
        _COOKIE_JSON_DIR.mkdir(parents=True, exist_ok=True)

    # ---------- 公共 API ----------

    def has_valid_cookies(self, user_id: str = "default") -> bool:
        """检查是否有有效的闲鱼 Cookie（JSON 优先，SQLite 兜底）"""
        data = self._read_json(user_id)
        if data and data.get("cookies"):
            names = {c["name"] for c in data["cookies"]}
            if _GOOFISH_KEY_COOKIES & names:
                return True
        # 兜底：JSON 为空时检查 SQLite
        # 为什么只对 default 用户走 SQLite 兜底：browser-data SQLite 是全局共享的，
        # 不按 user_id 隔离。多用户场景下其他用户不应通过全局 SQLite 判断登录态，
        # 否则 user_a 登录后 user_b 也会被误判为已登录
        if user_id == "default":
            return self._check_sqlite()
        return False

    def validate_cookies_with_expiry(self, user_id: str = "default") -> tuple[bool, str]:
        """检查 Cookie 是否有效（含过期时间判断）

        为什么需要此方法：has_valid_cookies 只检查 Cookie 是否存在，
        无法识别已过期的 Cookie。此方法补充过期时间判断，供健康检查使用。

        Returns:
            (is_valid, reason) 元组。reason 为失败原因或 "ok"
        """
        data = self._read_json(user_id)
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

    def get_cookie_info(self, user_id: str = "default") -> dict:
        """获取 Cookie 摘要信息（供 /api/auth/me 使用）"""
        data = self._read_json(user_id)
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

    def get_cookie_expiry(self, user_id: str = "default") -> float | None:
        """获取最早过期的闲鱼关键 Cookie 的过期时间

        用于定时同步判断是否即将过期。
        返回 Unix 时间戳（秒），无 Cookie 或 session cookie 返回 None。
        """
        data = self._read_json(user_id)
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

    def export_cookies(self, cookies: list[dict], method: str = "unknown", user_id: str = "default") -> bool:
        """导出 Cookie 到 JSON 文件（登录成功后由子进程调用）

        Args:
            cookies: Playwright cookie 对象列表
            method: 登录方式标识（browser/qr/cookie/import）
            user_id: 用户标识，用于多用户隔离存储
        """
        if not cookies:
            return False
        # 过滤掉测试数据，避免测试用例的默认值污染 JSON 存储
        # 真实登录不会产生 unb=123456 / cookie2=abc 这样的值
        filtered = [
            c for c in cookies
            if not is_test_cookie(c.get("name", ""), c.get("value", ""))
        ]
        if not filtered:
            logger.warning("export_cookies: 所有 Cookie 被识别为测试数据，跳过写入")
            return False
        if len(filtered) < len(cookies):
            logger.warning(
                "export_cookies: 过滤掉 %d 个测试 Cookie（%d → %d）",
                len(cookies) - len(filtered), len(cookies), len(filtered),
            )
        data = {
            "exported_at": time.time(),
            "method": method,
            "cookie_count": len(filtered),
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
                for c in filtered
            ],
        }
        success = self._write_json(data, user_id)
        # 同步到 browser-data SQLite（Worker 使用）
        # 为什么传 filtered 而非原始 cookies：测试数据已被 is_test_cookie 过滤，
        # 若同步原始 cookies 会把测试数据写入 SQLite，造成 JSON 与 SQLite 内容不一致
        if success:
            self._sync_to_sqlite(filtered)
        return success

    def sync_to_sqlite(self, cookies: list[dict]) -> bool:
        """外部调用：将 Cookie 同步到 browser-data SQLite

        Args:
            cookies: Playwright cookie 对象列表
        """
        return self._sync_to_sqlite(cookies)

    def update_cookie_values(self, updates: dict[str, str], user_id: str = "default") -> bool:
        """合并更新指定 Cookie 的值（不覆盖整个 JSON，不同步 SQLite）

        用于 MTOP Set-Cookie 回写场景：登录后 token 刷新产生新 _m_h5_tk 等，
        需要将新值回写到 JSON，避免重启后浏览器从 JSON 加载旧 token。

        与 export_cookies 的区别：
        - export_cookies 覆盖写整个 JSON（登录场景，全量替换）+ 同步 SQLite
        - update_cookie_values 合并写指定字段（token 刷新场景，增量更新），
          不同步 SQLite（SQLite 由 Worker 浏览器自行管理，避免锁竞争）

        并发安全：整个"读-改-写"事务在 self._lock（RLock）内完成，
        避免与并发 export_cookies/update_cookie_values 交错导致数据丢失。

        Args:
            updates: {cookie_name: new_value} 字典，仅更新已存在的 cookie
            user_id: 用户标识，用于多用户隔离存储

        Returns:
            True 表示有 cookie 被更新，False 表示无更新（JSON 无数据或无匹配）
        """
        if not updates:
            return False
        # 持锁完成整个事务：防止并发 update 或 export_cookies 交错导致丢失更新
        with self._lock:
            data = self._read_json(user_id)
            if not data or not data.get("cookies"):
                return False
            updated = False
            for c in data["cookies"]:
                name = c.get("name", "")
                if name in updates and c.get("value") != updates[name]:
                    c["value"] = updates[name]
                    updated = True
            if updated:
                data["exported_at"] = time.time()
                # 避免重复追加：method 字段只标记一次 mtop_refresh，防止无限增长
                existing_method = data.get("method", "unknown")
                if "mtop_refresh" not in existing_method:
                    data["method"] = existing_method + "+mtop_refresh"
                success = self._write_json(data, user_id)
                if success:
                    logger.info("已合并更新 %d 个 Cookie 值到 JSON: %s",
                                len(updates), sorted(updates.keys()))
                return success
            return False

    def upsert_cookie_values(self, upserts: dict[str, dict], user_id: str = "default") -> bool:
        """Upsert Cookie 值（更新已存在的 + 添加不存在的）

        用于浏览器内存兜底回写场景：/cookies/layers 从浏览器内存读取 cookie 后，
        JSON 中可能缺少某些 cookie（如 _m_h5_tk 未持久化），需要既能更新又能添加。

        与 update_cookie_values 的区别：
        - update_cookie_values：只更新已存在的 cookie（token 刷新场景）
        - upsert_cookie_values：更新 + 添加（浏览器兜底回写场景）

        Args:
            upserts: {cookie_name: {value, domain, path, expires}} 字典
            user_id: 用户标识，用于多用户隔离存储

        Returns:
            True 表示有 cookie 被更新或添加
        """
        if not upserts:
            return False
        with self._lock:
            data = self._read_json(user_id)
            if not data or not data.get("cookies"):
                return False
            existing_names = {c.get("name", "") for c in data["cookies"]}
            changed = False
            # 更新已存在的
            for c in data["cookies"]:
                name = c.get("name", "")
                if name in upserts and c.get("value") != upserts[name].get("value"):
                    c["value"] = upserts[name].get("value", c.get("value", ""))
                    changed = True
            # 添加不存在的
            for name, props in upserts.items():
                if name not in existing_names and props.get("value"):
                    data["cookies"].append({
                        "name": name,
                        "value": props["value"],
                        "domain": props.get("domain", ".goofish.com"),
                        "path": props.get("path", "/"),
                        "expires": props.get("expires", -1),
                    })
                    changed = True
            if changed:
                data["exported_at"] = time.time()
                existing_method = data.get("method", "unknown")
                if "browser_sync" not in existing_method:
                    data["method"] = existing_method + "+browser_sync"
                success = self._write_json(data, user_id)
                if success:
                    logger.info("已 upsert %d 个 Cookie 到 JSON: %s",
                                len(upserts), sorted(upserts.keys()))
                return success
            return False

    # ---------- 内部方法 ----------

    def invalidate_cache(self, user_id: str | None = None) -> None:
        """清除内存缓存，强制下次 _read_json 重新读取文件

        为什么需要此方法：浏览器登录子进程是独立 Python 进程，
        写入 cookies.json 后只更新子进程自己的缓存，主进程的缓存仍是旧数据。
        主进程在调用 sync_cookie_layers_from_json 等"读后同步"操作前必须先清除缓存，
        否则会读到 30 秒 TTL 内的旧缓存，导致层状态无法及时更新。

        Args:
            user_id: 指定用户则只清除该用户缓存，不传则清除全部用户缓存
        """
        with self._lock:
            # 兼容旧代码：外部可能直接赋值 _cache = None 来清缓存
            if self._cache is None:
                self._cache = {}
                return
            if user_id:
                self._cache.pop(user_id, None)
            else:
                self._cache.clear()

    def _read_json(self, user_id: str = "default") -> dict | None:
        """读取指定用户的 JSON Cookie 文件（带缓存）"""
        with self._lock:
            # 兼容旧代码：外部可能直接赋值 _cache = None 来清缓存
            if self._cache is None:
                self._cache = {}
            cached = self._cache.get(user_id)
            if cached and (time.time() - cached[1]) < _CACHE_TTL:
                return cached[0]
        path = _cookie_json_path(user_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            with self._lock:
                if self._cache is None:
                    self._cache = {}
                self._cache[user_id] = (data, time.time())
            return data
        except (json.JSONDecodeError, OSError):
            return None

    def _write_json(self, data: dict, user_id: str = "default") -> bool:
        """原子写入指定用户的 JSON Cookie 文件"""
        path = _cookie_json_path(user_id)
        try:
            tmp = path.with_suffix(".tmp")
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(path)
            with self._lock:
                if self._cache is None:
                    self._cache = {}
                self._cache[user_id] = (data, time.time())
            logger.info("Cookie 已导出到 JSON [%s]: %d 个, method=%s", user_id, data.get("cookie_count", 0), data.get("method"))
            return True
        except OSError as e:
            logger.error("写入 Cookie JSON 失败 [%s]: %s", user_id, e)
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
        """将 Cookie 同步写入 browser-data SQLite 数据库

        策略：先清除闲鱼/淘宝域的旧 Cookie，再写入新批次。
        原因：闲鱼反爬严格，累积历史 Cookie 会增加被识别为异常访问的风险，
        仅保留最近一次获取的真实 Cookie 数据。
        """
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
                # 先清除闲鱼/淘宝域的历史 Cookie，避免旧数据累积
                # 闲鱼 Cookie 分布在 .goofish.com 和 .taobao.com 两个域
                deleted = 0
                for domain in ("goofish", "taobao"):
                    deleted += delete_cookies_by_domain(conn, domain)
                if deleted:
                    logger.info("SQLite: 清除 %d 个历史闲鱼 Cookie", deleted)
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