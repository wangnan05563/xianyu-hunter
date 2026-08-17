"""Chrome Cookies 表 SQLite 操作封装

将分散在 cookie_inject / browser_import / cookie_store 中的
Chrome Cookies 表建表与 upsert 操作收敛到统一入口。

原因：Chromium Cookies 表结构变更时需要同步修改多处，
集中管理避免遗漏。函数接受任意具有 execute/commit 方法的连接对象
（sqlite3.Connection 或 SQLAlchemy Connection 均可）。
"""
from __future__ import annotations

from typing import Any, Protocol


class _ConnectionLike(Protocol):
    """兼容 sqlite3.Connection 与 SQLAlchemy Connection 的最小接口"""
    def execute(self, sql: str, parameters: Any = ...) -> Any: ...
    def commit(self) -> None: ...


# Chrome Cookies 表结构（与 Chromium Network/Cookies 保持一致）
# 三个调用点（cookie_inject/browser_import/cookie_store）原各自维护一份
# 完全相同的 DDL，收敛至此避免表结构变更时漏改
_CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS cookies (
        host_key TEXT NOT NULL,
        name TEXT NOT NULL,
        value TEXT NOT NULL,
        encrypted_value BLOB DEFAULT '',
        path TEXT NOT NULL,
        expires_utc INTEGER DEFAULT 0,
        is_secure INTEGER DEFAULT 0,
        is_httponly INTEGER DEFAULT 0,
        creation_utc INTEGER DEFAULT 0,
        last_access_utc INTEGER DEFAULT 0,
        has_expires INTEGER DEFAULT 1,
        is_persistent INTEGER DEFAULT 0,
        priority INTEGER DEFAULT 1,
        samesite INTEGER DEFAULT -1,
        source_scheme INTEGER DEFAULT 0,
        source_port INTEGER DEFAULT -1,
        top_frame_site_key TEXT DEFAULT '',
        PRIMARY KEY (host_key, name)
    )
"""

# INSERT OR REPLACE 固定尾部 6 个字段：
# has_expires=1, is_persistent=1, priority=1, samesite=-1, source_scheme=2, source_port=0
# 这是闲鱼 Cookie 注入场景的统一默认值（HTTPS + 持久化 + 跨站点宽松策略），
# 三个调用点原硬编码完全一致，收敛后仍保持不变
_UPSERT_SQL = """
    INSERT OR REPLACE INTO cookies (
        host_key, name, value, path, expires_utc,
        is_secure, is_httponly, creation_utc, last_access_utc,
        has_expires, is_persistent, priority, samesite,
        source_scheme, source_port
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 1, -1, 2, 0)
"""


def init_cookie_table(conn: _ConnectionLike) -> None:
    """建表（如果不存在）"""
    conn.execute(_CREATE_TABLE_SQL)


def upsert_cookie(conn: _ConnectionLike, cookie_data: dict) -> None:
    """插入/更新单条 cookie（不捕获异常，由调用方决定错误处理策略）

    cookie_data 必须包含以下字段：
    host_key, name, value, path, expires_utc,
    is_secure, is_httponly, creation_utc, last_access_utc
    """
    conn.execute(_UPSERT_SQL, (
        cookie_data["host_key"],
        cookie_data["name"],
        cookie_data["value"],
        cookie_data["path"],
        cookie_data["expires_utc"],
        cookie_data["is_secure"],
        cookie_data["is_httponly"],
        cookie_data["creation_utc"],
        cookie_data["last_access_utc"],
    ))


def batch_upsert_cookies(conn: _ConnectionLike, cookies: list[dict]) -> int:
    """批量插入/更新 cookie

    单条失败不影响其他 cookie（与 cookie_store._sync_to_sqlite 原逻辑一致），
    需要收集错误信息的场景请直接调用 upsert_cookie 并自行 try/except。

    Returns:
        成功插入的 cookie 数量
    """
    count = 0
    for cookie_data in cookies:
        try:
            upsert_cookie(conn, cookie_data)
            count += 1
        except Exception:
            # 静默跳过单条失败，保持与原 _sync_to_sqlite 行为一致
            pass
    return count


def get_cookies_by_domain(conn: _ConnectionLike, domain: str) -> list[dict]:
    """按域名模糊查询 cookie（host_key LIKE %domain%）"""
    rows = conn.execute(
        "SELECT host_key, name, value, path, expires_utc, is_secure, is_httponly "
        "FROM cookies WHERE host_key LIKE ?",
        (f"%{domain}%",),
    ).fetchall()
    return [
        {
            "host_key": row[0],
            "name": row[1],
            "value": row[2],
            "path": row[3],
            "expires_utc": row[4],
            "is_secure": row[5],
            "is_httponly": row[6],
        }
        for row in rows
    ]


def delete_cookies_by_domain(conn: _ConnectionLike, domain: str) -> int:
    """按域名模糊删除 cookie（host_key LIKE %domain%）

    Returns:
        删除的 cookie 数量
    """
    cursor = conn.execute(
        "DELETE FROM cookies WHERE host_key LIKE ?",
        (f"%{domain}%",),
    )
    return cursor.rowcount
