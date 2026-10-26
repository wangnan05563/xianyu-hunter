"""T02814 回归：通知去重范围是「同一用户内的同一业务事件」

裁决 A：`notifications` 约束从 UNIQUE(dedup_key) 迁移为 UNIQUE(user_id, dedup_key)。

原缺陷：dedup_key 由业务事件生成（订单号/商品 ID），全局唯一时两个用户触发同一事件，
后写者命中先写者的行——后写者的通知在自己列表里看不到，文案还会覆掉前一个人的，
`reset_read` 也会把前一个人读过的东西重置成未读。

本文件钉四件事：
1. 两个用户同 dedup_key → 两行，各自只看到自己那行；
2. 同一用户重复触发 → 仍是一行，内容被刷新（去重本身没被放松）；
3. `add_notification` 的返回值必须是「调用者自己那行」，不是别人的；
4. `reset_read=False`（刷新正文不重置已读）只改正文、保留 read_at，默认 True 才重置；
5. 旧库（单列 UNIQUE）经 `init_db` 重建后换成联合唯一，且历史行不丢；
6. 重建中断留下的 `notifications_old` 会在下次启动被收尾（复制数据、释放索引名）。
"""
from __future__ import annotations

import sqlite3

from xianyu_hunter.infra.db_models import init_db
from xianyu_hunter.infra.repository import Repository


def _add(repo: Repository, user_id: str, key: str, title: str = "t") -> dict:
    return repo.add_notification(
        level="info",
        category="price",
        title=title,
        message="m",
        link=None,
        dedup_key=key,
        user_id=user_id,
    )


def test_same_dedup_key_two_users_get_separate_rows(tmp_path):
    repo = Repository(db_path=str(tmp_path / "t.db"))

    alice = _add(repo, "alice", "price_drop:item1:10.00", "alice 的降价提醒")
    bob = _add(repo, "bob", "price_drop:item1:10.00", "bob 的降价提醒")

    assert alice["id"] != bob["id"]
    assert alice["user_id"] == "alice"
    assert bob["user_id"] == "bob"
    # 返回值必须是调用者那行，而不是「先写到的那行」
    assert alice["title"] == "alice 的降价提醒"
    assert bob["title"] == "bob 的降价提醒"

    assert [r["title"] for r in repo.list_notifications(user_id="alice")] == ["alice 的降价提醒"]
    assert [r["title"] for r in repo.list_notifications(user_id="bob")] == ["bob 的降价提醒"]
    assert repo.count_notifications(user_id="alice") == 1
    assert repo.count_notifications(user_id="bob") == 1


def test_same_user_same_key_still_dedups(tmp_path):
    repo = Repository(db_path=str(tmp_path / "t.db"))

    first = _add(repo, "alice", "order_timeout:o1:15min", "15 分钟")
    second = _add(repo, "alice", "order_timeout:o1:15min", "15 分钟（刷新）")

    assert first["id"] == second["id"]
    assert repo.count_notifications(user_id="alice") == 1
    assert repo.list_notifications(user_id="alice")[0]["title"] == "15 分钟（刷新）"


def test_reset_read_only_touches_writers_own_row(tmp_path):
    repo = Repository(db_path=str(tmp_path / "t.db"))

    alice = _add(repo, "alice", "auth_down:u1:20261026am")
    assert repo.mark_notification_read(alice["id"], user_id="alice")

    # bob 触发同 dedup_key：alice 的已读状态不能被他重置
    _add(repo, "bob", "auth_down:u1:20261026am")
    assert repo.count_notifications("unread", user_id="alice") == 0
    assert repo.count_notifications("unread", user_id="bob") == 1


def test_reset_read_false_keeps_read_state(tmp_path):
    repo = Repository(db_path=str(tmp_path / "t.db"))

    first = _add(repo, "alice", "task_failed:t1:3x", "3 次失败")
    assert repo.mark_notification_read(first["id"], user_id="alice")

    repo.add_notification(
        level="info", category="task", title="3 次失败（刷新）", message="m",
        link=None, dedup_key="task_failed:t1:3x", reset_read=False, user_id="alice",
    )
    rows = repo.list_notifications(user_id="alice")
    assert len(rows) == 1
    assert rows[0]["title"] == "3 次失败（刷新）"
    assert rows[0]["read_at"] is not None

    _add(repo, "alice", "task_failed:t1:3x", "再来一次")
    assert repo.count_notifications("unread", user_id="alice") == 1


def test_interrupted_rebuild_is_finished_on_next_init(tmp_path):
    """重建中断（新表已建、旧表还没删）时，下次 init_db 必须把数据收尾而不是丢表"""
    db = tmp_path / "crashed.db"
    cols = (
        "id INTEGER NOT NULL, level VARCHAR NOT NULL, category VARCHAR NOT NULL, "
        "title VARCHAR NOT NULL, message TEXT NOT NULL, link VARCHAR, "
        "dedup_key VARCHAR NOT NULL, read_at DATETIME, created_at DATETIME NOT NULL, "
        "user_id VARCHAR DEFAULT 'default' NOT NULL, PRIMARY KEY (id)"
    )
    con = sqlite3.connect(db)
    con.execute(f"CREATE TABLE notifications ({cols}, UNIQUE (user_id, dedup_key))")
    con.execute(f"CREATE TABLE notifications_old ({cols}, UNIQUE (dedup_key))")
    con.execute(
        "INSERT INTO notifications_old (level, category, title, message, dedup_key, created_at, user_id) "
        "VALUES ('info','price','legacy','m','price_drop:item1:10.00','2026-01-01 00:00:00','alice')"
    )
    con.execute("CREATE INDEX ix_notifications_user_read ON notifications_old (user_id, read_at)")
    con.commit()
    con.close()

    init_db(str(db))

    con = sqlite3.connect(db)
    tables = {
        r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    rows = con.execute("SELECT title, user_id FROM notifications").fetchall()
    indexes = {r[1] for r in con.execute("PRAGMA index_list(notifications)").fetchall()}
    con.close()

    assert "notifications_old" not in tables
    assert rows == [("legacy", "alice")]
    assert "ix_notifications_user_read" in indexes

    repo = Repository(db_path=str(db))
    _add(repo, "bob", "price_drop:item1:10.00", "bob")
    assert repo.count_notifications(user_id="bob") == 1
    assert repo.count_notifications(user_id="alice") == 1


def test_old_single_column_unique_is_migrated_by_init_db(tmp_path):
    db = tmp_path / "legacy.db"
    con = sqlite3.connect(db)
    con.execute(
        """
        CREATE TABLE notifications (
            id INTEGER NOT NULL,
            level VARCHAR NOT NULL,
            category VARCHAR NOT NULL,
            title VARCHAR NOT NULL,
            message TEXT NOT NULL,
            link VARCHAR,
            dedup_key VARCHAR NOT NULL,
            read_at DATETIME,
            created_at DATETIME NOT NULL,
            user_id VARCHAR DEFAULT 'default' NOT NULL,
            PRIMARY KEY (id),
            CONSTRAINT uq_notification_dedup UNIQUE (dedup_key)
        )
        """
    )
    con.execute(
        "INSERT INTO notifications (level, category, title, message, dedup_key, created_at, user_id) "
        "VALUES ('info','price','legacy','m','price_drop:item1:10.00','2026-01-01 00:00:00','alice')"
    )
    # 真实的旧库上带着 init_db 早就建好的索引；RENAME 会把索引一起带走，
    # 迁移必须能处理这种索引名冲突（否则全量回归会出现 index already exists）
    con.execute("CREATE INDEX ix_notifications_user_read ON notifications (user_id, read_at)")
    con.commit()
    con.close()

    init_db(str(db))

    con = sqlite3.connect(db)
    ddl = " ".join(con.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='notifications'"
    ).fetchone()[0].split())
    rows = con.execute("SELECT title, user_id FROM notifications").fetchall()
    indexes = {r[1] for r in con.execute("PRAGMA index_list(notifications)").fetchall()}
    con.close()

    assert "UNIQUE (user_id, dedup_key)" in ddl
    assert "UNIQUE (dedup_key)" not in ddl
    assert "ix_notifications_user_read" in indexes
    assert rows == [("legacy", "alice")]

    # 迁移后同一 dedup_key 允许第二个用户各占一行
    repo = Repository(db_path=str(db))
    _add(repo, "bob", "price_drop:item1:10.00", "bob")
    assert repo.count_notifications(user_id="bob") == 1
    assert repo.count_notifications(user_id="alice") == 1
