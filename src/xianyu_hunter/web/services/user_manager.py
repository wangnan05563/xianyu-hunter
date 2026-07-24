"""用户身份与多账号会话管理。

设计：
- 单例模式（get_user_manager），全局唯一实例；
- 用户身份来源：闲鱼 Cookie 的 unb 字段，缺失降级 sha256(cookie2)[:16]；
- session_token 仅存于 cookie，库内只存 sha256 哈希；
- 会话校验结果缓存 5 分钟，避免每次请求查库。
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from sqlalchemy import text as sa_text

from xianyu_hunter.paths import get_data_dir

logger = logging.getLogger(__name__)


# 默认 SQLite 数据库路径：get_user_manager 与 migrate_to_multi_user 共用
# 为什么用 get_data_dir() 而不是 "data/xianyu.db"：
# 打包后 CWD 不确定，相对路径会写入错误位置，导致 session_token 写入与校验不一致 → 401
_DB_PATH = str(get_data_dir() / "xianyu.db")


def _utcnow_iso() -> str:
    """返回 ISO8601 格式的当前 UTC 时间"""
    return datetime.now(timezone.utc).isoformat()


class UserManager:
    """用户身份与多账号会话管理器"""

    DEFAULT_USER_ID = "default"
    SESSION_TTL_DAYS = 30
    _VERIFY_CACHE_TTL = 300.0  # 5 分钟

    def __init__(self, engine) -> None:
        self._engine = engine
        self._lock = threading.RLock()
        self._verify_cache: dict[str, tuple[str, float]] = {}  # token_hash → (user_id, ts)

    # ---------- 用户身份 ----------

    def identify_or_create(self, cookies: list[dict]) -> str:
        """从 Cookie 列表识别用户身份，不存在则创建。

        优先级：unb（8位以上数字）> sha256(cookie2)[:16] > "default"
        """
        cookie_map = {c.get("name", ""): c.get("value", "") for c in cookies}

        # 1. 优先用 unb（闲鱼用户 ID）
        unb = cookie_map.get("unb", "")
        if unb and re.match(r"^\d{8,}$", unb):
            user_id = unb
        # 2. 降级：cookie2 哈希
        elif cookie_map.get("cookie2"):
            user_id = hashlib.sha256(cookie_map["cookie2"].encode()).hexdigest()[:16]
        # 3. 最终降级
        else:
            user_id = self.DEFAULT_USER_ID

        with self._lock:
            if not self.get_user(user_id):
                now = _utcnow_iso()
                with self._engine.connect() as conn:
                    # 显式提供 avatar_url/custom_alias/updated_at：ORM 的 default 仅 Python 端生效，
                    # DB schema 层面是 NOT NULL 无 server_default，省略会触发约束失败
                    conn.execute(sa_text(
                        "INSERT INTO users (user_id, nickname, avatar_url, custom_alias, status, created_at, last_active_at, updated_at) "
                        "VALUES (:uid, '', '', '', 'active', :now, :now, :now)"
                    ), {"uid": user_id, "now": now})
                    conn.commit()
                logger.info("创建用户记录: user_id=%s", user_id)

            self.update_last_active(user_id)
        return user_id

    def get_user(self, user_id: str) -> Optional[dict]:
        """获取用户记录"""
        with self._engine.connect() as conn:
            row = conn.execute(
                sa_text("SELECT * FROM users WHERE user_id=:uid"),
                {"uid": user_id},
            ).fetchone()
        if not row:
            return None
        return dict(row._mapping)

    def update_last_active(self, user_id: str) -> None:
        """更新最近活跃时间"""
        with self._engine.connect() as conn:
            conn.execute(
                sa_text("UPDATE users SET last_active_at=:now WHERE user_id=:uid"),
                {"now": _utcnow_iso(), "uid": user_id},
            )
            conn.commit()

    def get_active_user_id(self) -> str:
        """获取最近活跃的非 default 用户 ID（供后台调度器/全局组件使用）

        为什么需要：后台调度器（cookie_sync_scheduler）和全局组件
        （login_orchestrator/cookie_runtime_sync）没有 request 上下文，
        无法从 request.state.user_id 获取当前用户。它们需要知道当前活跃用户
        才能把 cookie 写到正确的 cookies_{user_id}.json。

        降级策略：无活跃非 default 用户时返回 "default"，保持与旧行为兼容。
        """
        try:
            with self._engine.connect() as conn:
                rows = conn.execute(sa_text(
                    "SELECT user_id FROM users "
                    "WHERE status='active' AND user_id!='default' "
                    "ORDER BY last_active_at DESC LIMIT 1"
                )).fetchall()
            if rows:
                return rows[0][0]
        except Exception:
            pass
        return "default"

    def issue_session(self, user_id: str) -> str:
        """为用户签发新的 session_token。

        1. secrets.token_urlsafe(48) 生成 64 字符随机串
        2. sha256(token) 存入 user_sessions 表
        3. 同用户旧 session 标记 is_active=0（会话固定防护）
        4. 返回原始 token（仅此一次明文）
        """
        token = secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=self.SESSION_TTL_DAYS)

        with self._lock:
            with self._engine.connect() as conn:
                # 旧 session 失效
                conn.execute(sa_text(
                    "UPDATE user_sessions SET is_active=0 WHERE user_id=:uid AND is_active=1"
                ), {"uid": user_id})
                # 清除该用户所有 token 的缓存条目，避免旧 token 在缓存 TTL 内仍命中
                # 为什么在这里清缓存：issue_session 撤销了 DB 中所有旧 session，
                # 但 _verify_cache 仍持有旧 token_hash → user_id 映射，
                # 不清理会导致旧 token 在 5 分钟 TTL 内绕过会话固定防护
                self._verify_cache = {
                    thash: val for thash, val in self._verify_cache.items()
                    if val[0] != user_id
                }
                # 写入新 session（client_ip 为 NOT NULL，ORM default 仅 Python 端生效，需显式提供）
                conn.execute(sa_text(
                    "INSERT INTO user_sessions (user_id, token_hash, issued_at, expires_at, last_renewed_at, client_ip, is_active) "
                    "VALUES (:uid, :thash, :issued, :exp, :renewed, :ip, 1)"
                ), {
                    "uid": user_id,
                    "thash": token_hash,
                    "issued": now.isoformat(),
                    "exp": expires.isoformat(),
                    "renewed": now.isoformat(),
                    "ip": "",
                })
                conn.commit()

        try:
            self._log_event(user_id, "login", {})
        except Exception:
            logger.warning("记录 login 事件失败 user_id=%s", user_id, exc_info=True)
        return token

    def verify_session(self, session_token: str) -> Optional[str]:
        """校验会话 token，返回 user_id 或 None。

        流程：sha256 → 缓存命中检查 → 查库 → hmac.compare_digest 比对
        → 过期检查 → 滑动续期 → 写入缓存。
        """
        # 空 token 直接拒绝，避免无意义的 hash 计算
        if not session_token:
            return None

        token_hash = hashlib.sha256(session_token.encode()).hexdigest()

        # 整个 verify 串行化，与 revoke_session 互斥，消除"查库后缓存被撤销"
        # 与"撤销时缓存尚未写入"之间的窗口，避免撤销后 5 分钟内仍命中缓存
        with self._lock:
            # 缓存命中检查：避免每次请求都查库（TTL 5 分钟）
            cached = self._verify_cache.get(token_hash)
            if cached is not None:
                cached_user_id, cached_ts = cached
                if time.time() - cached_ts < self._VERIFY_CACHE_TTL:
                    return cached_user_id
                # 缓存过期，清除后继续查库
                del self._verify_cache[token_hash]

            with self._engine.connect() as conn:
                row = conn.execute(
                    sa_text(
                        "SELECT user_id, token_hash, expires_at "
                        "FROM user_sessions WHERE token_hash=:thash AND is_active=1"
                    ),
                    {"thash": token_hash},
                ).fetchone()

                # 未查到活跃 session，直接拒绝
                if row is None:
                    return None

                user_id, stored_hash, expires_at = row[0], row[1], row[2]

                # 防时序攻击：即使 WHERE 已匹配也要走一次 compare_digest
                if not hmac.compare_digest(token_hash, stored_hash):
                    return None

                now = datetime.now(timezone.utc)
                try:
                    expires_dt = datetime.fromisoformat(expires_at)
                except (TypeError, ValueError):
                    # expires_at 字段损坏，视为无效
                    return None

                # SQLite 可能存储 naive datetime，统一加上 UTC 时区以便比较
                if expires_dt.tzinfo is None:
                    expires_dt = expires_dt.replace(tzinfo=timezone.utc)

                # 过期 session：标记失效并拒绝
                if expires_dt < now:
                    conn.execute(
                        sa_text("UPDATE user_sessions SET is_active=0 WHERE token_hash=:thash"),
                        {"thash": token_hash},
                    )
                    conn.commit()
                    return None

                # 滑动续期：距过期不足 7 天时延长到 30 天，避免用户频繁登录
                if (expires_dt - now) < timedelta(days=7):
                    new_expires = now + timedelta(days=self.SESSION_TTL_DAYS)
                    conn.execute(
                        sa_text(
                            "UPDATE user_sessions SET expires_at=:exp, last_renewed_at=:now "
                            "WHERE token_hash=:thash"
                        ),
                        {"exp": new_expires.isoformat(), "now": now.isoformat(), "thash": token_hash},
                    )
                    conn.commit()

            # 校验通过，写入缓存供后续请求复用（在同一个锁内，与 revoke_session 互斥）
            self._verify_cache[token_hash] = (user_id, time.time())

            return user_id

    def revoke_session(self, user_id: str) -> None:
        """撤销用户所有活跃 session（退出账号时调用）。

        撤销后清除缓存条目，并记录 logout 事件（异常隔离，不阻塞业务）。
        """
        with self._engine.connect() as conn:
            conn.execute(
                sa_text("UPDATE user_sessions SET is_active=0 WHERE user_id=:uid AND is_active=1"),
                {"uid": user_id},
            )
            conn.commit()

        # 清除缓存中该用户的所有条目，避免撤销后仍命中缓存
        # 用字典推导式重建而非 in-place del：避免 list() 抑制 S7504，同时保证并发安全
        with self._lock:
            self._verify_cache = {
                thash: val for thash, val in self._verify_cache.items()
                if val[0] != user_id
            }

        # 记录 logout 事件，失败不阻塞退出流程
        try:
            self._log_event(user_id, "logout", {})
        except Exception:
            logger.warning("记录 logout 事件失败 user_id=%s", user_id, exc_info=True)

    def delete_user(self, user_id: str, delete_tasks: bool = False) -> None:
        """退出账号并清除该用户的所有相关数据。

        采用"标记 disabled"而非物理删除用户记录，符合概要设计 §6.1 状态机
        （disabled 不可恢复，需重新添加）。revoke_session 已含缓存清除和
        logout 事件记录，此处不重复记录。

        线程安全：整个方法体持锁，与 verify_session/revoke_session 互斥，
        避免删除过程中 verify_session 命中缓存。
        """
        if user_id == self.DEFAULT_USER_ID:
            raise ValueError("禁止删除 default 用户")

        with self._lock:
            # 撤销会话（RLock 可重入，内部再获锁不会死锁；含缓存清除 + logout 事件）
            self.revoke_session(user_id)

            now = _utcnow_iso()
            with self._engine.connect() as conn:
                # 清除用户级数据：cookie/菜单配置/偏好
                conn.execute(
                    sa_text("DELETE FROM user_cookies WHERE user_id=:uid"),
                    {"uid": user_id},
                )
                conn.execute(
                    sa_text("DELETE FROM user_menu_configs WHERE user_id=:uid"),
                    {"uid": user_id},
                )
                conn.execute(
                    sa_text("DELETE FROM user_preferences WHERE user_id=:uid"),
                    {"uid": user_id},
                )

                # 可选删除任务数据
                if delete_tasks:
                    conn.execute(
                        sa_text("DELETE FROM tasks WHERE user_id=:uid"),
                        {"uid": user_id},
                    )

                # 标记用户为 disabled（状态机：disabled 不可恢复，需重新添加）
                conn.execute(
                    sa_text(
                        "UPDATE users SET status='disabled', updated_at=:now "
                        "WHERE user_id=:uid"
                    ),
                    {"now": now, "uid": user_id},
                )
                conn.commit()

            # 删除 Cookie 文件，不存在时静默跳过；其他 IO 错误降级为 warning 不阻塞
            # 为什么用 _cookie_json_path 而非直接拼接：
            # 复用 cookie_store 的 _USER_ID_RE 白名单校验，统一路径遍历防御边界，
            # 避免 delete_user 接收外部 user_id 时绕过安全校验
            from xianyu_hunter.web.services.cookie_store import _cookie_json_path
            try:
                cookie_file = _cookie_json_path(user_id)
                cookie_file.unlink(missing_ok=True)
            except (OSError, ValueError):
                logger.warning("删除 Cookie 文件失败: user_id=%s", user_id, exc_info=True)

            logger.info(
                "用户已退出并清理数据: user_id=%s, delete_tasks=%s",
                user_id, delete_tasks,
            )

    def list_users(self) -> list[dict]:
        """列出所有已登录账号（含状态）。

        按 created_at 升序返回（default 用户通常最先创建）。
        不过滤 disabled 用户，展示层负责过滤。
        只读操作但仍持锁，与现有方法风格保持一致。
        """
        with self._lock:
            with self._engine.connect() as conn:
                rows = conn.execute(
                    sa_text("SELECT * FROM users ORDER BY created_at")
                ).fetchall()
            return [dict(row._mapping) for row in rows]

    def set_user_status(self, user_id: str, status: str) -> None:
        """设置账号状态（active / expired / disabled）。

        不校验 status 合法性，由 API 层负责。
        状态变更事件记录失败不阻塞业务流程（沿用 Task 4 模式）。
        """
        with self._lock:
            now = _utcnow_iso()
            with self._engine.connect() as conn:
                conn.execute(
                    sa_text(
                        "UPDATE users SET status=:status, updated_at=:now "
                        "WHERE user_id=:uid"
                    ),
                    {"status": status, "now": now, "uid": user_id},
                )
                conn.commit()
                # disabled 用户的 token 应立即失效，清除缓存避免 5 分钟窗口内仍可访问
                # 为什么仅 disabled 分支清缓存：active/expired 是正常状态流转，
                # 用户 token 仍应可用；disabled 是终止态（不可恢复），必须即时吊销缓存
                if status == "disabled":
                    self._verify_cache = {
                        thash: val for thash, val in self._verify_cache.items()
                        if val[0] != user_id
                    }

        # 事件记录与业务解耦：_log_event 失败不阻塞状态变更
        try:
            self._log_event(user_id, "status_change", {"status": status})
        except Exception:
            logger.warning(
                "记录 status_change 事件失败 user_id=%s", user_id, exc_info=True
            )

    def probe_all_accounts(self, validator: "Callable[[str], tuple[bool, str]]") -> None:
        """探测所有账号 Cookie 有效性，更新账号状态。

        通过依赖注入 validator 函数解耦 CookieStore（MU2 接入时直接传入
        CookieStore.validate_cookies_with_expiry 即可），使核心探测逻辑
        在 MU1 阶段可独立测试，无需等待 CookieStore 改造。

        状态机：
        - active + invalid → expired + cookie_expired 事件
        - expired + valid → active + cookie_recovered 事件
        - disabled 跳过（不可恢复，避免无谓探测）
        - 其他组合（active 仍 active / expired 仍 expired）不处理，避免
          status_change 事件抖动污染审计日志。

        线程安全：整个方法体持锁，与 set_user_status/list_users 互斥，
        避免探测过程中状态被其他方法修改；RLock 可重入，内部调用
        list_users/set_user_status 不会死锁。
        """
        with self._lock:
            users = self.list_users()
            for user in users:
                # disabled 不可恢复，跳过避免无谓探测
                if user["status"] == "disabled":
                    continue

                user_id = user["user_id"]
                is_valid, reason = validator(user_id)

                if not is_valid and user["status"] == "active":
                    self.set_user_status(user_id, "expired")
                    # _log_event 失败不阻塞状态变更流程（沿用 Task 4 模式）
                    try:
                        self._log_event(user_id, "cookie_expired", {"reason": reason})
                    except Exception:
                        logger.warning(
                            "记录 cookie_expired 事件失败 user_id=%s",
                            user_id, exc_info=True,
                        )
                elif is_valid and user["status"] == "expired":
                    self.set_user_status(user_id, "active")
                    try:
                        self._log_event(user_id, "cookie_recovered", {})
                    except Exception:
                        logger.warning(
                            "记录 cookie_recovered 事件失败 user_id=%s",
                            user_id, exc_info=True,
                        )

    def _log_event(self, user_id: str | None, event_type: str, detail: dict) -> None:
        """记录会话事件日志

        日志失败不应阻塞业务流程（如登录/退出），仅记录 warning。
        """
        with self._engine.connect() as conn:
            conn.execute(sa_text(
                "INSERT INTO user_session_events (user_id, event_type, detail, created_at) "
                "VALUES (:uid, :etype, :detail, :now)"
            ), {
                "uid": user_id,
                "etype": event_type,
                "detail": json.dumps(detail, ensure_ascii=False),
                "now": _utcnow_iso(),
            })
            conn.commit()


# 全局单例
_manager: UserManager | None = None
_manager_lock = threading.Lock()


def get_user_manager() -> UserManager:
    """获取全局 UserManager 单例

    延迟调用 init_db 确保 users 等多用户表存在，
    避免在 startup 的 init_db 之前被早期中间件触发时抛 no such table。
    """
    global _manager
    with _manager_lock:
        if _manager is None:
            from xianyu_hunter.infra.db_models import create_sqlite_engine, init_db
            init_db(_DB_PATH)
            engine = create_sqlite_engine(_DB_PATH)
            _manager = UserManager(engine)
        return _manager


def migrate_to_multi_user(db_path: str = _DB_PATH) -> None:
    """首次升级迁移：单用户 → 多用户（幂等可重复执行）

    init_db 已完成表创建和 tasks.user_id 字段迁移，本函数只负责：
    1. 创建 default 用户记录（识别降级目标）
    2. 迁移旧版 cookies.json → cookies_default.json
    """
    # 局部 import 与 get_user_manager 一致，避免模块加载时触发 db_models 初始化
    from xianyu_hunter.infra.db_models import create_sqlite_engine, init_db

    # 确保 schema 已初始化（幂等），即便 migrate 在 startup 的 init_db 之前被调用也安全
    init_db(db_path)
    engine = create_sqlite_engine(db_path)

    try:
        with engine.connect() as conn:
            # 幂等检查：default 用户已存在则直接返回，重复执行不报错
            count = conn.execute(
                sa_text("SELECT COUNT(*) FROM users WHERE user_id='default'")
            ).fetchone()[0]
            if count > 0:
                logger.info("migrate_to_multi_user: default 用户已存在，跳过迁移")
                return

            # created_at/last_active_at/updated_at 是 NOT NULL 无 server_default，必须显式提供
            now = _utcnow_iso()
            conn.execute(sa_text(
                "INSERT INTO users (user_id, nickname, avatar_url, custom_alias, status, created_at, last_active_at, updated_at) "
                "VALUES ('default', '默认用户', '', '', 'active', :now, :now, :now)"
            ), {"now": now})
            conn.commit()
            logger.info("migrate_to_multi_user: 创建 default 用户")

        # Cookie 文件迁移：src 不存在时静默跳过；目标已存在时不覆盖
        # 走 paths.py 统一入口：避免硬编码 Path("data")
        old_path = get_data_dir() / "cookies.json"
        new_path = get_data_dir() / "cookies_default.json"
        if old_path.exists() and not new_path.exists():
            try:
                old_path.rename(new_path)
                logger.info("migrate_to_multi_user: 迁移 cookies.json → cookies_default.json")
            except OSError:
                # 迁移失败不阻塞启动（与 delete_user 的 IO 错误降级策略一致）
                logger.warning("migrate_to_multi_user: Cookie 文件迁移失败", exc_info=True)
    finally:
        # 函数内创建的 engine 必须显式 dispose，避免连接泄漏
        engine.dispose()
