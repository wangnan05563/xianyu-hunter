"""用户身份与多账号会话管理。

设计：
- 单例模式（get_user_manager），全局唯一实例；
- 用户身份来源：闲鱼 Cookie 的 unb 字段，缺失降级 sha256(cookie2)[:16]；
- session_token 仅存于 cookie，库内只存 sha256 哈希；
- 会话校验结果缓存 5 分钟，避免每次请求查库。
"""
from __future__ import annotations

import hashlib
import logging
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text as sa_text

logger = logging.getLogger(__name__)


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
        cols = row._mapping.keys()
        return dict(row._mapping)

    def update_last_active(self, user_id: str) -> None:
        """更新最近活跃时间"""
        with self._engine.connect() as conn:
            conn.execute(
                sa_text("UPDATE users SET last_active_at=:now WHERE user_id=:uid"),
                {"now": _utcnow_iso(), "uid": user_id},
            )
            conn.commit()

    def issue_session(self, user_id: str) -> str:
        """为用户签发新的 session_token。

        1. secrets.token_urlsafe(48) 生成 64 字符随机串
        2. sha256(token) 存入 user_sessions 表
        3. 同用户旧 session 标记 is_active=0（会话固定防护）
        4. 返回原始 token（仅此一次明文）
        """
        import secrets

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

        self._log_event(user_id, "login", {})
        return token

    def _log_event(self, user_id: str | None, event_type: str, detail: dict) -> None:
        """记录会话事件日志"""
        import json
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
            init_db("data/xianyu.db")
            engine = create_sqlite_engine("data/xianyu.db")
            _manager = UserManager(engine)
        return _manager
