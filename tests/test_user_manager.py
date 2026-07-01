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
