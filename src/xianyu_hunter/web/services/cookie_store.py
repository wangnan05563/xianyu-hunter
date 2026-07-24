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
import os
import re
import sqlite3
import threading
import time
from pathlib import Path

from xianyu_hunter.infra.yaml_config import get_config
from xianyu_hunter.paths import get_browser_data_dir, get_data_dir
from xianyu_hunter.web.services.cookie_db import batch_upsert_cookies, delete_cookies_by_domain, init_cookie_table

logger = logging.getLogger(__name__)

# JSON 格式的 Cookie 存储目录（与 browser-data 同级）
# MU2 改造：按 user_id 隔离，每个用户一个独立 JSON 文件
# 走 paths.py 统一入口：PyInstaller 打包后写入 %APPDATA%，开发模式写入项目根/data
_COOKIE_JSON_DIR = get_data_dir()

# user_id 白名单：仅允许字母数字下划线短横线，长度 1-64
# 防止路径遍历：user_id 后续会从 JWT/数据库解析，恶意 user_id（如 ../../etc/passwd）
# 会被拼入文件名造成 data 目录外写入，必须在此入口拦截
_USER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _cookie_json_path(user_id: str = "default") -> Path:
    """按 user_id 生成 Cookie JSON 文件路径

    为什么用 Path 多参数构造而非 _COOKIE_JSON_DIR / 拼接：
    测试通过 monkeypatch 替换模块 Path 为 lambda *args: tmp_path / args[-1]，
    多参数构造使 lambda 取 args[-1]（文件名）落到 tmp_path 下，便于测试隔离。
    """
    if not _USER_ID_RE.match(user_id):
        raise ValueError(f"invalid user_id: {user_id!r}")
    return Path(_COOKIE_JSON_DIR, f"cookies_{user_id}.json")

# 闲鱼登录关键 Cookie 名称 / 缓存 TTL / 测试值过滤 / 格式正则
# 配置化（cookie_management 节点）：统一管理散落在 cookie_store / cookie_rotator /
# browser_import / cookie_inject / _search 等模块的硬编码常量，
# 避免名单漂移导致 75+ cookie 丢失。模块级一次性加载，热更新需重启进程
_CFG_COOKIE = get_config().cookie_management
_GOOFISH_KEY_COOKIES: set[str] = set(_CFG_COOKIE.key_cookies)
_CACHE_TTL: float = _CFG_COOKIE.cache_ttl_sec
# 已知的测试数据特征（来自测试用例的默认值）
# 这些值不应被当作真实 Cookie 返回给用户或写入 JSON 存储
_TEST_COOKIE_VALUES: dict[str, set[str]] = {
    k: set(v) for k, v in _CFG_COOKIE.test_cookie_values.items()
}
# 真实 Cookie 的格式特征（用于拦截黑名单之外的测试数据）
# 为什么用正则而非精确匹配：测试代码可能使用 real_token_123、fake_token 等任意字符串，
# 精确匹配无法覆盖；用格式校验能识别所有不符合真实格式的值
# 注意：只对格式明确固定的 Cookie 添加校验，避免误伤真实数据
_COOKIE_FORMAT_PATTERNS: dict[str, re.Pattern] = {
    k: re.compile(v) for k, v in _CFG_COOKIE.cookie_format_patterns.items()
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
        # 只记录长度而非完整 value：Cookie value 是敏感会话凭证，
        # 完整记录会泄露到日志文件，存在信息泄露风险
        logger.warning("Cookie %s 值不符合真实格式，识别为测试数据 (len=%d)", name, len(value))
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

        # 过期时间检查：仅检查关键 Cookie（identity + session 层）
        # 为什么不检查所有 Cookie：x5secdata/cna/tfstk 等追踪层或安全令牌 Cookie
        # 过期时间很短（几小时），过期不影响闲鱼核心登录态，但会导致健康检查误判。
        # 与 /api/anticrawl/health 的 cookie_checker 保持一致（api_anticrawl.py:105-120）
        # 兼容旧数据：无 expires 字段视为 session cookie，不过期
        # Playwright 的 expires 为 Unix 时间戳（秒），-1 或 0 表示 session cookie
        # 延迟导入避免 cookie_store → cookie_rotator 循环依赖
        from xianyu_hunter.modules.cookie_rotator import is_m5tk_expired

        now = time.time()
        for c in cookies_list:
            name = c.get("name")
            if name not in _GOOFISH_KEY_COOKIES:
                continue

            # _m_h5_tk 特殊处理：使用内嵌 timestamp 判断过期，而非 expires 字段。
            # 原因：is_m5tk_expired 文档明确记载 "_m_h5_tk 的 cookie expires 字段
            # 通常是 -1（session cookie），无法用 cookie.expires 判断过期"。
            # cookie_rotator / _default_cookie_provider 等全链路均使用 is_m5tk_expired，
            # 健康检查若用 expires 字段会导致与全链路不一致：
            # - expires 已过期但内嵌 timestamp 仍有效时误报 cookie_expired
            # - expires=-1 但 token 实已过期时漏报
            if name == "_m_h5_tk":
                value = c.get("value", "")
                if value and is_m5tk_expired(value):
                    return False, f"cookie_expired:{name}"
                continue

            expires = c.get("expires", -1)
            if expires and expires > 0 and expires < now:
                return False, f"cookie_expired:{name}"

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

    def merge_cookies(self, cookies: list[dict], method: str = "merge", user_id: str = "default") -> bool:
        """合并写入 Cookie 到 JSON（保留原有 cookie，新值覆盖同名 cookie）

        为什么需要合并写：用户从浏览器 DevTools 复制 cookie 时可能只粘贴部分
        cookie（如仅 4 个身份 cookie），若用 export_cookies 覆盖写入，会丢失
        原有 22 个完整 cookie 集（包括 cna/tracknick/_tb_token_/t/tfstk 等
        详情页 SPA 渲染必需的会话/追踪 cookie），导致详情页采集失败。

        合并策略：以 cookie 名为 key 合并，相同 name 的新值覆盖旧值，旧文件中
        其他 cookie 全部保留。
        """
        if not cookies:
            return False
        filtered = [
            c for c in cookies
            if not is_test_cookie(c.get("name", ""), c.get("value", ""))
        ]
        if not filtered:
            logger.warning("merge_cookies: 所有 Cookie 被识别为测试数据，跳过写入")
            return False
        if len(filtered) < len(cookies):
            logger.warning(
                "merge_cookies: 过滤掉 %d 个测试 Cookie（%d → %d）",
                len(cookies) - len(filtered), len(cookies), len(filtered),
            )

        with self._lock:
            existing = self._read_json(user_id)
            # 用 name 做 key：同名 cookie 覆盖，旧文件中其他 cookie 全部保留
            merged_by_name: dict[str, dict] = {}
            if existing and existing.get("cookies"):
                for c in existing["cookies"]:
                    name = c.get("name", "")
                    if name:
                        merged_by_name[name] = c
            for new_c in filtered:
                merged_by_name[new_c.get("name", "")] = new_c

            merged_cookies = list(merged_by_name.values())
            existing_count = len(existing["cookies"]) if existing and existing.get("cookies") else 0
            logger.info(
                "merge_cookies: 注入 %d 个，原有 %d 个，合并后 %d 个",
                len(filtered), existing_count, len(merged_cookies),
            )

            data = {
                "exported_at": time.time(),
                "method": method,
                "cookie_count": len(merged_cookies),
                "cookies": [
                    {
                        "name": c.get("name", ""),
                        "value": c.get("value", ""),
                        "domain": c.get("domain", ""),
                        "path": c.get("path", "/"),
                        # 保存过期时间用于健康检查的有效性判断
                        "expires": c.get("expires", -1),
                    }
                    for c in merged_cookies
                ],
            }
            success = self._write_json(data, user_id)

        # _sync_to_sqlite 移到锁外执行：sqlite3.connect + 批量写入可能耗时数百毫秒，
        # 持锁会阻塞其他 CookieStore 操作（has_valid_cookies/get_cookie_info 等）。
        # merged_cookies 在锁内计算完成，锁外传给 _sync_to_sqlite 不会读到中间态。
        # 与 export_cookies 的模式保持一致（export_cookies 也是锁外调用 _sync_to_sqlite）
        if success:
            # 同步全部合并后的 cookie（不仅仅是新注入的），
            # 确保 SQLite 与 JSON 状态一致
            self._sync_to_sqlite(merged_cookies)
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
            if not self._apply_upsert_to_cookies(data["cookies"], upserts):
                return False
            data["exported_at"] = time.time()
            data["method"] = self._merge_method(data.get("method", "unknown"), "browser_sync")
            success = self._write_json(data, user_id)
            if success:
                logger.info(
                    "已 upsert %d 个 Cookie 到 JSON: %s",
                    len(upserts),
                    sorted(upserts.keys()),
                )
            return success

    def _apply_upsert_to_cookies(
        self,
        cookies: list[dict],
        upserts: dict[str, dict],
    ) -> bool:
        """应用 upsert 变更到 cookies 列表，返回是否有变更

        拆分为「更新已存在」+「添加不存在」两个职责，避免单函数嵌套过深。
        """
        existing_names = {c.get("name", "") for c in cookies}
        changed = False
        changed |= self._update_existing_cookies(cookies, upserts)
        changed |= self._append_missing_cookies(cookies, upserts, existing_names)
        return changed

    def _update_existing_cookies(self, cookies: list[dict], upserts: dict[str, dict]) -> bool:
        """将 upserts 中已存在 cookie 的值同步到列表，返回是否发生变更"""
        changed = False
        for c in cookies:
            name = c.get("name", "")
            if name in upserts and c.get("value") != upserts[name].get("value"):
                c["value"] = upserts[name].get("value", c.get("value", ""))
                changed = True
        return changed

    def _append_missing_cookies(
        self,
        cookies: list[dict],
        upserts: dict[str, dict],
        existing_names: set[str],
    ) -> bool:
        """将 upserts 中不存在的 cookie 追加到列表，返回是否发生追加"""
        changed = False
        for name, props in upserts.items():
            if name in existing_names or not props.get("value"):
                continue
            cookies.append(self._build_cookie_entry(name, props))
            changed = True
        return changed

    @staticmethod
    def _build_cookie_entry(name: str, props: dict) -> dict:
        """构造单条 cookie 字典，缺省字段使用 .goofish.com 域与根路径"""
        return {
            "name": name,
            "value": props["value"],
            "domain": props.get("domain", ".goofish.com"),
            "path": props.get("path", "/"),
            "expires": props.get("expires", -1),
        }

    @staticmethod
    def _merge_method(existing_method: str, new_tag: str) -> str:
        """合并 method 标记：若 new_tag 已存在则不重复拼接"""
        if new_tag in existing_method:
            return existing_method
        return f"{existing_method}+{new_tag}"

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
                # double-check: 读文件期间不持锁，其他线程可能已通过 _write_json
                # 写入更新的数据并更新缓存。若此时直接覆盖会用刚读到的旧文件数据
                # 覆盖较新的缓存，造成缓存回退。这里重新检查缓存，若已被更新则用缓存值
                cached = self._cache.get(user_id)
                if cached and (time.time() - cached[1]) < _CACHE_TTL:
                    return cached[0]
                self._cache[user_id] = (data, time.time())
            return data
        except (json.JSONDecodeError, OSError):
            return None

    def _write_json(self, data: dict, user_id: str = "default") -> bool:
        """原子写入指定用户的 JSON Cookie 文件"""
        path = _cookie_json_path(user_id)
        try:
            # 使用 pid + thread id 生成唯一 tmp 文件名，避免并发写入竞争同一个 .tmp 路径
            # 为什么不用固定 .tmp：两个并发的 _write_json(user_id="default") 会
            # 同时写 cookies_default.tmp 造成数据损坏，即便最终 replace 是原子的
            tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
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
        user_data_dir = get_browser_data_dir(cfg.browser.user_data_dir)
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
        user_data_dir = get_browser_data_dir(cfg.browser.user_data_dir)
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
