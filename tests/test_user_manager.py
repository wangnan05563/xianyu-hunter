"""UserManager 与多用户数据表单元测试"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import inspect

from xianyu_hunter.infra.db_models import create_sqlite_engine, init_db, Base


@pytest.fixture
def tmp_db():
    """临时数据库，避免污染真实数据"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db_path = str(Path(d) / "test.db")
        init_db(db_path)
        engine = create_sqlite_engine(db_path)
        yield engine
        engine.dispose()


def test_multi_user_tables_created(tmp_db):
    """初始化后应创建 6 张用户相关表"""
    inspector = inspect(tmp_db)
    tables = set(inspector.get_table_names())
    expected = {
        "users", "user_sessions", "user_cookies",
        "user_menu_configs", "user_preferences", "user_session_events"
    }
    assert expected <= tables, f"缺失表: {expected - tables}"


def test_tasks_table_has_user_id(tmp_db):
    """tasks 表应包含 user_id 列，默认 'default'"""
    from sqlalchemy import inspect, text as sa_text

    inspector = inspect(tmp_db)
    columns = {c["name"]: c for c in inspector.get_columns("tasks")}
    assert "user_id" in columns, "tasks 表缺少 user_id 列"

    # 验证已有数据 user_id 填充 default
    with tmp_db.connect() as conn:
        conn.execute(sa_text(
            "INSERT INTO tasks (id, name, keyword, cron, use_cron, interval_seconds, mode, status, created_at, updated_at) "
            "VALUES ('t1', 'test', 'iphone', '*/5 * * * *', 0, 60.0, 'confirm', 'running', '2026-01-01', '2026-01-01')"
        ))
        conn.commit()

        result = conn.execute(sa_text("SELECT user_id FROM tasks WHERE id='t1'")).fetchone()
        assert result is not None
        # SQLite ALTER TABLE ADD COLUMN DEFAULT 'default' 后，新插入行应自动填充
        assert result[0] == "default"


def test_tasks_user_id_indexes_exist(tmp_db):
    """tasks 表应有 user_id 相关索引"""
    from sqlalchemy import inspect

    inspector = inspect(tmp_db)
    index_names = {idx["name"] for idx in inspector.get_indexes("tasks")}
    assert "idx_tasks_user" in index_names
    assert "idx_tasks_user_created" in index_names
    assert "idx_tasks_user_status" in index_names


from xianyu_hunter.web.services.user_manager import UserManager

@pytest.fixture
def user_mgr(tmp_db):
    """UserManager 实例（使用临时数据库）"""
    mgr = UserManager.__new__(UserManager)
    mgr._engine = tmp_db
    mgr._verify_cache = {}
    mgr._lock = __import__("threading").RLock()
    return mgr


def test_identify_or_create_with_unb(user_mgr):
    """从 Cookie 的 unb 字段识别用户"""
    cookies = [
        {"name": "unb", "value": "220812345678"},
        {"name": "cookie2", "value": "a" * 32},
    ]
    user_id = user_mgr.identify_or_create(cookies)
    assert user_id == "220812345678"

    # 验证用户记录已创建
    user = user_mgr.get_user("220812345678")
    assert user is not None
    assert user["user_id"] == "220812345678"
    assert user["status"] == "active"


def test_identify_or_create_fallback_to_cookie2(user_mgr):
    """unb 缺失时降级为 sha256(cookie2)[:16]"""
    cookies = [
        {"name": "cookie2", "value": "abcdef1234567890abcdef1234567890"},
    ]
    import hashlib
    expected = hashlib.sha256(b"abcdef1234567890abcdef1234567890").hexdigest()[:16]
    user_id = user_mgr.identify_or_create(cookies)
    assert user_id == expected


def test_identify_or_create_fallback_to_default(user_mgr):
    """unb 和 cookie2 都缺失时降级为 default"""
    cookies = [{"name": "other", "value": "xxx"}]
    user_id = user_mgr.identify_or_create(cookies)
    assert user_id == "default"


def test_identify_or_create_idempotent(user_mgr):
    """重复识别同一用户不报错，不创建重复记录"""
    cookies = [{"name": "unb", "value": "220812345678"}]
    user_mgr.identify_or_create(cookies)
    user_mgr.identify_or_create(cookies)  # 第二次不应报错

    from sqlalchemy import text as sa_text
    with user_mgr._engine.connect() as conn:
        count = conn.execute(
            sa_text("SELECT COUNT(*) FROM users WHERE user_id='220812345678'")
        ).fetchone()[0]
        assert count == 1


def test_issue_session_returns_token(user_mgr):
    """签发会话返回 64 字符 token"""
    user_mgr.identify_or_create([{"name": "unb", "value": "220812345678"}])
    token = user_mgr.issue_session("220812345678")
    assert len(token) >= 60  # token_urlsafe(48) 约 64 字符
    assert token != "220812345678"  # 不是 user_id 本身


def test_issue_session_stores_hash_not_plaintext(user_mgr):
    """库内存储 sha256 哈希，不是明文 token"""
    import hashlib
    from sqlalchemy import text as sa_text

    user_mgr.identify_or_create([{"name": "unb", "value": "220812345678"}])
    token = user_mgr.issue_session("220812345678")

    expected_hash = hashlib.sha256(token.encode()).hexdigest()
    with user_mgr._engine.connect() as conn:
        row = conn.execute(
            sa_text("SELECT token_hash FROM user_sessions WHERE user_id='220812345678'")
        ).fetchone()
        assert row is not None
        assert row[0] == expected_hash  # 存的是哈希
        assert row[0] != token  # 不是明文


def test_issue_session_invalidates_old_sessions(user_mgr):
    """新签发的 session 使旧 session 失效（会话固定防护）"""
    user_mgr.identify_or_create([{"name": "unb", "value": "220812345678"}])
    token1 = user_mgr.issue_session("220812345678")
    token2 = user_mgr.issue_session("220812345678")

    # token1 应该失效
    assert user_mgr.verify_session(token1) is None
    # token2 应该有效
    assert user_mgr.verify_session(token2) == "220812345678"


def test_verify_session_returns_user_id_for_valid_token(user_mgr):
    """有效 token 校验返回 user_id"""
    user_mgr.identify_or_create([{"name": "unb", "value": "220812345678"}])
    token = user_mgr.issue_session("220812345678")
    assert user_mgr.verify_session(token) == "220812345678"


def test_verify_session_returns_none_for_invalid_token(user_mgr):
    """无效 token 校验返回 None"""
    user_mgr.identify_or_create([{"name": "unb", "value": "220812345678"}])
    assert user_mgr.verify_session("invalid_token_xxx") is None


def test_verify_session_returns_none_for_empty_token(user_mgr):
    """空 token 校验返回 None"""
    assert user_mgr.verify_session("") is None
    assert user_mgr.verify_session(None) is None


def test_verify_session_uses_cache_on_second_call(user_mgr):
    """第二次校验命中缓存（不查库）"""
    user_mgr.identify_or_create([{"name": "unb", "value": "220812345678"}])
    token = user_mgr.issue_session("220812345678")

    # 第一次校验，查库
    assert user_mgr.verify_session(token) == "220812345678"

    # 验证缓存已写入
    import hashlib
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    assert token_hash in user_mgr._verify_cache

    # 第二次校验，应命中缓存（即使数据库被清空也应返回 user_id）
    # 通过删除数据库行模拟缓存命中场景
    from sqlalchemy import text as sa_text
    with user_mgr._engine.connect() as conn:
        conn.execute(sa_text("DELETE FROM user_sessions"))
        conn.commit()

    # 缓存命中，仍返回 user_id
    assert user_mgr.verify_session(token) == "220812345678"


def test_revoke_session_invalidates_all_user_sessions(user_mgr):
    """revoke_session 撤销用户所有活跃 session"""
    user_mgr.identify_or_create([{"name": "unb", "value": "220812345678"}])
    token1 = user_mgr.issue_session("220812345678")
    token2 = user_mgr.issue_session("220812345678")  # 会使 token1 失效

    user_mgr.revoke_session("220812345678")

    # token2 也应失效
    assert user_mgr.verify_session(token2) is None


def test_revoke_session_clears_verify_cache(user_mgr):
    """revoke_session 清除缓存中该用户的条目"""
    user_mgr.identify_or_create([{"name": "unb", "value": "220812345678"}])
    token = user_mgr.issue_session("220812345678")
    user_mgr.verify_session(token)  # 写入缓存

    user_mgr.revoke_session("220812345678")

    # 缓存应被清除
    import hashlib
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    assert token_hash not in user_mgr._verify_cache


def test_verify_session_invalidates_expired_token(user_mgr):
    """过期 token 校验时标记 is_active=0 并返回 None"""
    import hashlib
    from sqlalchemy import text as sa_text
    from datetime import datetime, timezone, timedelta

    user_mgr.identify_or_create([{"name": "unb", "value": "220812345678"}])
    token = user_mgr.issue_session("220812345678")

    # 手动将 expires_at 设为过去时间
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with user_mgr._engine.connect() as conn:
        conn.execute(
            sa_text("UPDATE user_sessions SET expires_at=:exp WHERE token_hash=:thash"),
            {"exp": past, "thash": token_hash}
        )
        conn.commit()

    # 校验应返回 None
    assert user_mgr.verify_session(token) is None

    # 验证 is_active 被标记为 0
    with user_mgr._engine.connect() as conn:
        row = conn.execute(
            sa_text("SELECT is_active FROM user_sessions WHERE token_hash=:thash"),
            {"thash": token_hash}
        ).fetchone()
        assert row[0] == 0
