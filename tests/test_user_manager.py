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


def test_verify_session_renews_when_expiring_soon(user_mgr):
    """距过期 < 7 天时，verify_session 触发滑动续期"""
    user_mgr.identify_or_create([{"name": "unb", "value": "220812345678"}])
    token = user_mgr.issue_session("220812345678")

    import hashlib
    from sqlalchemy import text as sa_text
    from datetime import datetime, timezone, timedelta

    token_hash = hashlib.sha256(token.encode()).hexdigest()

    # 手动将 expires_at 设为未来 5 天（< 7 天，应触发续期）
    soon = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    with user_mgr._engine.connect() as conn:
        conn.execute(
            sa_text("UPDATE user_sessions SET expires_at=:exp WHERE token_hash=:thash"),
            {"exp": soon, "thash": token_hash}
        )
        conn.commit()

    # 清除缓存，强制下次 verify 查库
    user_mgr._verify_cache.clear()

    # 调用 verify_session，应触发续期
    user_mgr.verify_session(token)

    # 验证 expires_at 已被延长（应 >= 未来 25 天，因为续期到 30 天）
    with user_mgr._engine.connect() as conn:
        row = conn.execute(
            sa_text("SELECT expires_at, last_renewed_at FROM user_sessions WHERE token_hash=:thash"),
            {"thash": token_hash}
        ).fetchone()
        expires_at = datetime.fromisoformat(row[0])
        last_renewed_at = datetime.fromisoformat(row[1])

    now = datetime.now(timezone.utc)
    assert (expires_at - now).days >= 25, f"续期后应至少还有 25 天，实际 {(expires_at - now).days} 天"
    assert (last_renewed_at - now).total_seconds() < 60, "last_renewed_at 应为近期时间"


def test_verify_session_no_renew_when_not_expiring_soon(user_mgr):
    """距过期 >= 7 天时，verify_session 不触发续期"""
    user_mgr.identify_or_create([{"name": "unb", "value": "220812345678"}])
    token = user_mgr.issue_session("220812345678")

    import hashlib
    from sqlalchemy import text as sa_text
    from datetime import datetime, timezone, timedelta

    token_hash = hashlib.sha256(token.encode()).hexdigest()

    # 读取原始 expires_at（issue_session 签发时为 30 天后）
    with user_mgr._engine.connect() as conn:
        orig_row = conn.execute(
            sa_text("SELECT expires_at FROM user_sessions WHERE token_hash=:thash"),
            {"thash": token_hash}
        ).fetchone()
        orig_expires = datetime.fromisoformat(orig_row[0])

    # 清除缓存，强制下次 verify 查库
    user_mgr._verify_cache.clear()

    # 调用 verify_session（距过期 30 天 >= 7 天，不应续期）
    user_mgr.verify_session(token)

    # 验证 expires_at 未被修改
    with user_mgr._engine.connect() as conn:
        row = conn.execute(
            sa_text("SELECT expires_at FROM user_sessions WHERE token_hash=:thash"),
            {"thash": token_hash}
        ).fetchone()
        expires_at = datetime.fromisoformat(row[0])

    assert expires_at == orig_expires, "距过期 >= 7 天时不应触发续期"


def test_delete_user_raises_for_default_user(user_mgr):
    """禁止删除 default 用户"""
    with pytest.raises(ValueError, match="禁止删除 default 用户"):
        user_mgr.delete_user("default")


def test_delete_user_revokes_sessions(user_mgr):
    """delete_user 撤销用户所有会话"""
    user_mgr.identify_or_create([{"name": "unb", "value": "220812345678"}])
    token = user_mgr.issue_session("220812345678")
    assert user_mgr.verify_session(token) == "220812345678"

    user_mgr.delete_user("220812345678")

    # token 应失效
    assert user_mgr.verify_session(token) is None


def test_delete_user_clears_user_data(user_mgr):
    """delete_user 清除用户相关数据（cookie/菜单配置/偏好）"""
    from sqlalchemy import text as sa_text

    user_mgr.identify_or_create([{"name": "unb", "value": "220812345678"}])
    user_id = "220812345678"

    # 插入测试数据
    # user_cookies 的 path/expires/is_secure/is_httponly/created_at 均为 NOT NULL 无 server_default，
    # 直接 SQL INSERT 时需显式提供（ORM default 仅 Python 端生效）
    with user_mgr._engine.connect() as conn:
        conn.execute(sa_text(
            "INSERT INTO user_cookies (user_id, host_key, name, value, path, expires, is_secure, is_httponly, created_at, updated_at) "
            "VALUES (:uid, 'taobao.com', 'test', 'val', '/', -1, 1, 1, '2026-01-01', '2026-01-01')"
        ), {"uid": user_id})
        conn.execute(sa_text(
            "INSERT INTO user_menu_configs (user_id, menu_key, visible, sort_order, group_name, custom_label, updated_at) "
            "VALUES (:uid, 'tasks', 1, 10, 'data_view', '', '2026-01-01')"
        ), {"uid": user_id})
        conn.execute(sa_text(
            "INSERT INTO user_preferences (user_id, pref_key, pref_value, updated_at) "
            "VALUES (:uid, 'columns', '{}', '2026-01-01')"
        ), {"uid": user_id})
        conn.commit()

    user_mgr.delete_user(user_id)

    # 验证数据已清除
    with user_mgr._engine.connect() as conn:
        for table in ("user_cookies", "user_menu_configs", "user_preferences"):
            count = conn.execute(
                sa_text(f"SELECT COUNT(*) FROM {table} WHERE user_id=:uid"),
                {"uid": user_id}
            ).fetchone()[0]
            assert count == 0, f"{table} 应被清空"


def test_delete_user_marks_user_disabled(user_mgr):
    """delete_user 将用户标记为 disabled"""
    user_mgr.identify_or_create([{"name": "unb", "value": "220812345678"}])
    user_mgr.delete_user("220812345678")

    user = user_mgr.get_user("220812345678")
    assert user is not None  # 用户记录仍存在
    assert user["status"] == "disabled"


def test_delete_user_with_delete_tasks_removes_tasks(user_mgr):
    """delete_user(delete_tasks=True) 删除用户任务"""
    from sqlalchemy import text as sa_text

    user_mgr.identify_or_create([{"name": "unb", "value": "220812345678"}])
    user_id = "220812345678"

    # 插入测试任务
    with user_mgr._engine.connect() as conn:
        conn.execute(sa_text(
            "INSERT INTO tasks (id, name, keyword, cron, use_cron, interval_seconds, mode, status, created_at, updated_at, user_id) "
            "VALUES ('t1', 'test', 'iphone', '*/5 * * * *', 0, 60.0, 'confirm', 'running', '2026-01-01', '2026-01-01', :uid)"
        ), {"uid": user_id})
        conn.commit()

    user_mgr.delete_user(user_id, delete_tasks=True)

    with user_mgr._engine.connect() as conn:
        count = conn.execute(
            sa_text("SELECT COUNT(*) FROM tasks WHERE user_id=:uid"),
            {"uid": user_id}
        ).fetchone()[0]
        assert count == 0, "任务应被删除"


def test_delete_user_without_delete_tasks_keeps_tasks(user_mgr):
    """delete_user(delete_tasks=False) 保留用户任务"""
    from sqlalchemy import text as sa_text

    user_mgr.identify_or_create([{"name": "unb", "value": "220812345678"}])
    user_id = "220812345678"

    with user_mgr._engine.connect() as conn:
        conn.execute(sa_text(
            "INSERT INTO tasks (id, name, keyword, cron, use_cron, interval_seconds, mode, status, created_at, updated_at, user_id) "
            "VALUES ('t1', 'test', 'iphone', '*/5 * * * *', 0, 60.0, 'confirm', 'running', '2026-01-01', '2026-01-01', :uid)"
        ), {"uid": user_id})
        conn.commit()

    user_mgr.delete_user(user_id, delete_tasks=False)

    with user_mgr._engine.connect() as conn:
        count = conn.execute(
            sa_text("SELECT COUNT(*) FROM tasks WHERE user_id=:uid"),
            {"uid": user_id}
        ).fetchone()[0]
        assert count == 1, "任务应保留"


def test_list_users_returns_all_users(user_mgr):
    """list_users 返回所有用户记录"""
    user_mgr.identify_or_create([{"name": "unb", "value": "220812345678"}])
    user_mgr.identify_or_create([{"name": "unb", "value": "220812345679"}])

    users = user_mgr.list_users()
    assert len(users) == 2
    user_ids = {u["user_id"] for u in users}
    assert user_ids == {"220812345678", "220812345679"}


def test_list_users_returns_empty_for_no_users(user_mgr):
    """无用户时 list_users 返回空列表"""
    users = user_mgr.list_users()
    assert users == []


def test_list_users_returns_dict_format(user_mgr):
    """list_users 返回的每条记录是 dict 格式"""
    user_mgr.identify_or_create([{"name": "unb", "value": "220812345678"}])

    users = user_mgr.list_users()
    assert len(users) == 1
    user = users[0]
    assert isinstance(user, dict)
    assert "user_id" in user
    assert "status" in user
    assert "created_at" in user


def test_set_user_status_updates_status(user_mgr):
    """set_user_status 更新用户状态"""
    user_mgr.identify_or_create([{"name": "unb", "value": "220812345678"}])

    user_mgr.set_user_status("220812345678", "expired")

    user = user_mgr.get_user("220812345678")
    assert user["status"] == "expired"


def test_set_user_status_updates_updated_at(user_mgr):
    """set_user_status 更新 updated_at 字段"""
    from sqlalchemy import text as sa_text
    from datetime import datetime, timezone

    user_mgr.identify_or_create([{"name": "unb", "value": "220812345678"}])

    # 读取原始 updated_at
    with user_mgr._engine.connect() as conn:
        orig_row = conn.execute(
            sa_text("SELECT updated_at FROM users WHERE user_id='220812345678'")
        ).fetchone()
        orig_updated = datetime.fromisoformat(orig_row[0])

    # 等待一小段时间确保时间差
    import time
    time.sleep(0.01)

    user_mgr.set_user_status("220812345678", "disabled")

    # 验证 updated_at 已更新
    with user_mgr._engine.connect() as conn:
        row = conn.execute(
            sa_text("SELECT updated_at FROM users WHERE user_id='220812345678'")
        ).fetchone()
        new_updated = datetime.fromisoformat(row[0])

    assert new_updated > orig_updated


def test_probe_all_accounts_marks_expired_for_invalid_cookies(user_mgr):
    """Cookie 失效的 active 账号被标记为 expired"""
    user_mgr.identify_or_create([{"name": "unb", "value": "220812345678"}])

    # validator 返回 (False, "cookie expired")
    def validator(user_id):
        return (False, "cookie expired")

    user_mgr.probe_all_accounts(validator)

    user = user_mgr.get_user("220812345678")
    assert user["status"] == "expired"


def test_probe_all_accounts_marks_active_for_recovered_cookies(user_mgr):
    """Cookie 恢复的 expired 账号被标记为 active"""
    user_mgr.identify_or_create([{"name": "unb", "value": "220812345678"}])
    user_mgr.set_user_status("220812345678", "expired")  # 先设为 expired

    # validator 返回 (True, "")
    def validator(user_id):
        return (True, "")

    user_mgr.probe_all_accounts(validator)

    user = user_mgr.get_user("220812345678")
    assert user["status"] == "active"


def test_probe_all_accounts_skips_disabled_users(user_mgr):
    """disabled 用户被跳过，不调用 validator"""
    user_mgr.identify_or_create([{"name": "unb", "value": "220812345678"}])
    user_mgr.set_user_status("220812345678", "disabled")

    validator_call_count = 0
    def validator(user_id):
        nonlocal validator_call_count
        validator_call_count += 1
        return (False, "should not be called")

    user_mgr.probe_all_accounts(validator)

    assert validator_call_count == 0, "disabled 用户不应调用 validator"


def test_probe_all_accounts_logs_cookie_expired_event(user_mgr):
    """Cookie 失效时记录 cookie_expired 事件"""
    from sqlalchemy import text as sa_text

    user_mgr.identify_or_create([{"name": "unb", "value": "220812345678"}])

    def validator(user_id):
        return (False, "cookie expired")

    user_mgr.probe_all_accounts(validator)

    # 验证事件已记录
    with user_mgr._engine.connect() as conn:
        row = conn.execute(
            sa_text("SELECT event_type, detail FROM user_session_events WHERE user_id=:uid AND event_type='cookie_expired'"),
            {"uid": "220812345678"}
        ).fetchone()
        assert row is not None
        assert "cookie expired" in row[1]  # detail 包含 reason


def test_probe_all_accounts_logs_cookie_recovered_event(user_mgr):
    """Cookie 恢复时记录 cookie_recovered 事件"""
    from sqlalchemy import text as sa_text

    user_mgr.identify_or_create([{"name": "unb", "value": "220812345678"}])
    user_mgr.set_user_status("220812345678", "expired")

    def validator(user_id):
        return (True, "")

    user_mgr.probe_all_accounts(validator)

    with user_mgr._engine.connect() as conn:
        row = conn.execute(
            sa_text("SELECT event_type FROM user_session_events WHERE user_id=:uid AND event_type='cookie_recovered'"),
            {"uid": "220812345678"}
        ).fetchone()
        assert row is not None


def test_migrate_to_multi_user_creates_default_user(tmp_db):
    """migrate_to_multi_user 创建 default 用户"""
    from xianyu_hunter.web.services.user_manager import migrate_to_multi_user
    from sqlalchemy import text as sa_text

    # 获取临时数据库路径
    db_path = str(tmp_db.engine.url.database)

    migrate_to_multi_user(db_path)

    # 验证 default 用户已创建
    with tmp_db.connect() as conn:
        row = conn.execute(
            sa_text("SELECT user_id, nickname, status FROM users WHERE user_id='default'")
        ).fetchone()
        assert row is not None
        assert row[0] == "default"
        assert row[1] == "默认用户"
        assert row[2] == "active"


def test_migrate_to_multi_user_idempotent(tmp_db):
    """migrate_to_multi_user 幂等可重复执行"""
    from xianyu_hunter.web.services.user_manager import migrate_to_multi_user
    from sqlalchemy import text as sa_text

    db_path = str(tmp_db.engine.url.database)

    # 第一次执行
    migrate_to_multi_user(db_path)
    # 第二次执行（不应报错）
    migrate_to_multi_user(db_path)

    # 验证只有一个 default 用户
    with tmp_db.connect() as conn:
        count = conn.execute(
            sa_text("SELECT COUNT(*) FROM users WHERE user_id='default'")
        ).fetchone()[0]
        assert count == 1


def test_migrate_to_multi_user_migrates_cookie_file(tmp_db, monkeypatch):
    """migrate_to_multi_user 迁移 cookies.json → cookies_default.json"""
    from xianyu_hunter.web.services.user_manager import migrate_to_multi_user
    from pathlib import Path
    import tempfile

    db_path = str(tmp_db.engine.url.database)

    # ignore_cleanup_errors=True：与 tmp_db fixture 一致，避免 Windows 上
    # cwd 仍在 tmp_dir 时清理失败（monkeypatch 在 with 块清理后才恢复 cwd）
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        # 切换工作目录到临时目录
        monkeypatch.chdir(tmp_dir)

        # 创建 data/ 目录和 cookies.json
        data_dir = Path("data")
        data_dir.mkdir()
        old_cookie = data_dir / "cookies.json"
        old_cookie.write_text('[]', encoding='utf-8')

        migrate_to_multi_user(db_path)

        # 验证 cookies.json 已重命名为 cookies_default.json
        assert not old_cookie.exists()
        new_cookie = data_dir / "cookies_default.json"
        assert new_cookie.exists()
        assert new_cookie.read_text(encoding='utf-8') == '[]'


def test_migrate_to_multi_user_no_cookie_file(tmp_db, monkeypatch):
    """migrate_to_multi_user 无 cookies.json 时静默跳过"""
    from xianyu_hunter.web.services.user_manager import migrate_to_multi_user
    from pathlib import Path
    import tempfile

    db_path = str(tmp_db.engine.url.database)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        monkeypatch.chdir(tmp_dir)
        # 不创建 data/ 目录和 cookies.json

        migrate_to_multi_user(db_path)

        # 应静默跳过，不报错
        # default 用户仍应创建
        from sqlalchemy import text as sa_text
        with tmp_db.connect() as conn:
            count = conn.execute(
                sa_text("SELECT COUNT(*) FROM users WHERE user_id='default'")
            ).fetchone()[0]
            assert count == 1


# ============ 重复账号自动合并（防复发） ============

def _insert_user_with_nick(user_mgr, user_id: str, nick: str, status: str = "active") -> None:
    """辅助：直接插入带昵称的用户记录（users 表 NOT NULL 列需显式提供）"""
    from sqlalchemy import text as sa_text
    now = "2026-01-01T00:00:00+00:00"
    with user_mgr._engine.connect() as conn:
        conn.execute(sa_text(
            "INSERT INTO users (user_id, nickname, avatar_url, custom_alias, status, "
            "created_at, last_active_at, updated_at) "
            "VALUES (:uid, :nick, '', '', :st, :now, :now, :now)"
        ), {"uid": user_id, "nick": nick, "st": status, "now": now})
        conn.commit()


def test_pick_merge_direction_hash_to_unb():
    """合并方向固定：cookie2 哈希 → unb"""
    from xianyu_hunter.web.services.user_manager import UserManager
    unb = "220812345678"
    hash_id = "abcdef0123456789"
    assert UserManager._pick_merge_direction(unb, hash_id) == (hash_id, unb)
    assert UserManager._pick_merge_direction(hash_id, unb) == (hash_id, unb)


def test_pick_merge_direction_same_type_none():
    """同类型账号（两个 unb / 两个哈希）不合并，避免不同用户同昵称被误合并"""
    from xianyu_hunter.web.services.user_manager import UserManager
    assert UserManager._pick_merge_direction("220812345678", "220812345679") is None
    assert UserManager._pick_merge_direction("abc11111111111", "abc22222222222") is None


def test_merge_duplicate_accounts_hash_to_unb(user_mgr):
    """同昵称的 cookie2 哈希账号数据自动归并到 unb 账号，源账号标记 disabled"""
    import hashlib
    from sqlalchemy import text as sa_text

    unb_id = "220812345678"
    hash_id = hashlib.sha256(b"c" * 32).hexdigest()[:16]
    _insert_user_with_nick(user_mgr, unb_id, "南屿轻舟")
    _insert_user_with_nick(user_mgr, hash_id, "南屿轻舟")

    # 给哈希账号插入任务和偏好数据
    with user_mgr._engine.connect() as conn:
        conn.execute(sa_text(
            "INSERT INTO tasks (id, name, keyword, cron, use_cron, interval_seconds, mode, status, created_at, updated_at, user_id) "
            "VALUES ('t1', 'test', 'iphone', '*/5 * * * *', 0, 60.0, 'confirm', 'running', '2026-01-01', '2026-01-01', :uid)"
        ), {"uid": hash_id})
        conn.execute(sa_text(
            "INSERT INTO user_preferences (user_id, pref_key, pref_value, updated_at) "
            "VALUES (:uid, 'columns', '{}', '2026-01-01')"
        ), {"uid": hash_id})
        conn.commit()

    merged = user_mgr.merge_duplicate_accounts(hash_id)

    assert len(merged) == 1
    assert merged[0]["from"] == hash_id
    assert merged[0]["to"] == unb_id

    with user_mgr._engine.connect() as conn:
        # 任务已归 unb
        row = conn.execute(sa_text("SELECT user_id FROM tasks WHERE id='t1'")).fetchone()
        assert row[0] == unb_id
        # 偏好已归 unb
        row = conn.execute(
            sa_text("SELECT user_id FROM user_preferences WHERE pref_key='columns'")
        ).fetchone()
        assert row[0] == unb_id
        # 源账号标记 disabled
        status = conn.execute(
            sa_text("SELECT status FROM users WHERE user_id=:uid"), {"uid": hash_id}
        ).fetchone()[0]
        assert status == "disabled"


def test_merge_duplicate_accounts_target_preferred_on_conflict(user_mgr):
    """目标 unb 已有同键数据时保留目标值（目标优先）"""
    import hashlib
    from sqlalchemy import text as sa_text

    unb_id = "220812345678"
    hash_id = hashlib.sha256(b"e" * 32).hexdigest()[:16]
    _insert_user_with_nick(user_mgr, unb_id, "南屿轻舟")
    _insert_user_with_nick(user_mgr, hash_id, "南屿轻舟")

    # 双方都有同名偏好键，值不同
    for uid, val in ((unb_id, "target"), (hash_id, "source")):
        with user_mgr._engine.connect() as conn:
            conn.execute(sa_text(
                "INSERT INTO user_preferences (user_id, pref_key, pref_value, updated_at) "
                "VALUES (:uid, 'columns', :val, '2026-01-01')"
            ), {"uid": uid, "val": val})
            conn.commit()

    user_mgr.merge_duplicate_accounts(hash_id)

    with user_mgr._engine.connect() as conn:
        row = conn.execute(
            sa_text("SELECT user_id, pref_value FROM user_preferences WHERE pref_key='columns'")
        ).fetchone()
        # 冲突键保留目标账号的值
        assert row[0] == unb_id
        assert row[1] == "target"


def test_merge_duplicate_accounts_no_merge_same_type(user_mgr):
    """两个同昵称 unb 账号不合并（可能是不同用户），返回空列表"""
    _insert_user_with_nick(user_mgr, "220812345678", "测试")
    _insert_user_with_nick(user_mgr, "220812345679", "测试")

    assert user_mgr.merge_duplicate_accounts("220812345678") == []


def test_merge_duplicate_accounts_skips_disabled(user_mgr):
    """disabled 账号不参与合并（终止态）"""
    import hashlib
    from sqlalchemy import text as sa_text

    unb_id = "220812345678"
    hash_id = hashlib.sha256(b"f" * 32).hexdigest()[:16]
    _insert_user_with_nick(user_mgr, unb_id, "南屿轻舟")
    # 哈希账号已是 disabled → 不应被再次合并
    _insert_user_with_nick(user_mgr, hash_id, "南屿轻舟", status="disabled")

    assert user_mgr.merge_duplicate_accounts(unb_id) == []

    # 两个账号状态不变
    with user_mgr._engine.connect() as conn:
        statuses = {
            row[0]: row[1]
            for row in conn.execute(sa_text("SELECT user_id, status FROM users")).fetchall()
        }
    assert statuses[unb_id] == "active"
    assert statuses[hash_id] == "disabled"


def test_merge_duplicate_accounts_moves_active_session(user_mgr):
    """合并后源账号的活跃 session 归属主账号，旧 token 无感切到主账号身份"""
    import hashlib
    from sqlalchemy import text as sa_text

    unb_id = "220812345678"
    hash_id = hashlib.sha256(b"a" * 32).hexdigest()[:16]
    _insert_user_with_nick(user_mgr, unb_id, "南屿轻舟")
    _insert_user_with_nick(user_mgr, hash_id, "南屿轻舟")

    # 以哈希账号身份签发会话并写入缓存
    token = user_mgr.issue_session(hash_id)
    assert user_mgr.verify_session(token) == hash_id

    user_mgr.merge_duplicate_accounts(hash_id)

    # 同一 token 校验返回 unb 账号（session 已归属主账号，无需重新登录）
    assert user_mgr.verify_session(token) == unb_id


def test_merge_duplicate_accounts_no_duplicate_returns_empty(user_mgr):
    """无重复账号时返回空列表"""
    import hashlib

    unb_id = "220812345678"
    _insert_user_with_nick(user_mgr, unb_id, "南屿轻舟")
    hash_id = hashlib.sha256(b"b" * 32).hexdigest()[:16]
    _insert_user_with_nick(user_mgr, hash_id, "另一个昵称")

    assert user_mgr.merge_duplicate_accounts(unb_id) == []
