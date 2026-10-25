"""T02981 回归：审计型事件（db_admin / maintenance）按请求用户归属

背景：T02801 让带 `task_id` 的事件按 `tasks.user_id` 归属，但审计事件没有任务可反查，
仍走 `_active_user_id_for_background_write()`（最后活跃用户）。多账号并发下，
甲的数据库改动/清理会记到乙名下 —— 甲看不到自己的操作，乙的列表混入他人记录。

修法：两处都在 HTTP 请求内，身份现成，调用点一律传 `owner_user_id(request)`。
本文件用真实 Repository 验证「两人各写各的，`list_events(user_id=…)` 只看得到自己的」，
并把活跃用户伪造成第三人 —— 一旦归属退回活跃用户兜底，断言立刻红。

运行：
    .venv/Scripts/python.exe -m pytest tests/test_audit_events_user_isolation.py -o addopts="" -p no:cacheprovider -q
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from xianyu_hunter.infra import repo_events
from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.web.routes import api_db_admin as admin
from xianyu_hunter.web.routes import api_maintenance
from xianyu_hunter.web.routes.api_db_admin import BatchDeleteBody, ImportBody, WriteRowBody
from xianyu_hunter.web.routes.api_maintenance import CleanupRequest


@pytest.fixture
def repo(tmp_path):
    return Repository(db_path=str(tmp_path / "audit.db"))


@pytest.fixture
def container(repo):
    class _StubContainer:
        def __init__(self, real_repo):
            self.repo = real_repo

    return _StubContainer(repo)


@pytest.fixture(autouse=True)
def active_user_is_someone_else(monkeypatch):
    """把「最后活跃用户」伪造成第三人：归属若退回兜底，事件会落到 mallory 名下"""
    monkeypatch.setattr(repo_events, "_active_user_id_for_background_write", lambda: "mallory")


def _request(user_id: str):
    return SimpleNamespace(state=SimpleNamespace(user_id=user_id))


def _types(repo, user_id: str | None) -> list[str]:
    return [e["type"] for e in repo.list_events(user_id=user_id, limit=1000)]


def test_db_admin_audit_follows_request_user_not_active_user(repo, container):
    """甲写库 → 审计落甲；活跃用户 mallory 一条都不该拿到"""
    admin.create_row(
        "task_deps", WriteRowBody(values={"task_id": "t1", "depends_on": "t2", "created_at": "2026-01-01T00:00:00"}),
        _request("alice"), container=container,
    )

    events = repo.list_events(user_id="alice", limit=1000)
    assert [e["type"] for e in events] == ["db_admin.create"]
    assert events[0]["user_id"] == "alice"
    assert _types(repo, "mallory") == []


def test_two_users_see_only_their_own_audit_events(repo, container):
    """alice 建行、bob 改行：各自列表只含自己的操作，互不串账"""
    admin.create_row(
        "task_deps", WriteRowBody(values={"task_id": "t1", "depends_on": "t2", "created_at": "2026-01-01T00:00:00"}),
        _request("alice"), container=container,
    )
    with repo.engine.connect() as conn:
        dep_id = conn.execute(text("SELECT MAX(id) FROM task_deps")).scalar()
    admin.update_row(
        "task_deps", str(dep_id), WriteRowBody(values={"depends_on": "t3"}),
        _request("bob"), container=container,
    )

    alice_types = _types(repo, "alice")
    bob_types = _types(repo, "bob")
    assert alice_types == ["db_admin.create"]
    assert bob_types == ["db_admin.update"]
    # 不过滤时两条都在（list_events 默认按时间倒序，只比集合）
    assert sorted(_types(repo, None)) == ["db_admin.create", "db_admin.update"]


def test_delete_batch_delete_and_import_also_follow_request_user(repo, container):
    """其余三类写库动作（单删/批删/导入）同样按请求用户归属"""
    admin.create_row(
        "task_deps",
        WriteRowBody(values={"task_id": "t1", "depends_on": "t2", "created_at": "2026-01-01T00:00:00"}),
        _request("alice"), container=container,
    )
    admin.delete_row(
        "task_deps", "1", _request("alice"), confirm_token=admin.CONFIRM_TOKEN, container=container,
    )
    admin.create_row(
        "task_deps",
        WriteRowBody(values={"task_id": "t1", "depends_on": "t3", "created_at": "2026-01-01T00:00:00"}),
        _request("bob"), container=container,
    )
    with repo.engine.connect() as conn:
        second_id = conn.execute(text("SELECT MAX(id) FROM task_deps")).scalar()
    admin.batch_delete_rows(
        "task_deps",
        BatchDeleteBody(ids=[second_id], confirm_token=admin.CONFIRM_TOKEN),
        _request("bob"), container=container,
    )
    admin.import_rows(
        "task_deps",
        ImportBody(
            rows=[["t7", "t8", "2026-01-01T00:00:00"]],
            headers=["task_id", "depends_on", "created_at"],
            confirm_token=admin.CONFIRM_TOKEN,
        ),
        _request("carol"), container=container,
    )

    assert sorted(_types(repo, "alice")) == ["db_admin.create", "db_admin.delete"]
    assert sorted(_types(repo, "bob")) == ["db_admin.batch_delete", "db_admin.create"]
    assert _types(repo, "carol") == ["db_admin.import"]


def test_passthrough_token_stays_in_default_namespace(repo, container):
    """WEB_TOKEN 直通（user_id=='default'）与通知域同口径：落 default，不借用会话用户"""
    admin.create_row(
        "task_deps", WriteRowBody(values={"task_id": "t1", "depends_on": "t2", "created_at": "2026-01-01T00:00:00"}),
        _request("default"), container=container,
    )

    assert _types(repo, "default") == ["db_admin.create"]
    assert _types(repo, "alice") == []


def test_maintenance_cleanup_audit_follows_request_user(repo, container, monkeypatch, tmp_path: Path):
    """清理审计同样按请求用户归属（预览态就写审计，不必真删文件）"""
    profile = tmp_path / "browser-data"
    profile.mkdir()
    (profile / "Cookies").write_bytes(b"x" * 2048)
    monkeypatch.setattr(api_maintenance, "_browser_data_dir", lambda: profile)

    api_maintenance.cleanup_cache(
        CleanupRequest(target="browser_data", dry_run=True), _request("alice"), container=container,
    )
    api_maintenance.cleanup_cache(
        CleanupRequest(target="browser_data", dry_run=True), _request("bob"), container=container,
    )

    assert _types(repo, "alice") == ["maintenance.cache"]
    assert _types(repo, "bob") == ["maintenance.cache"]
    assert _types(repo, "mallory") == []
