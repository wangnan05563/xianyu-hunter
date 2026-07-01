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
