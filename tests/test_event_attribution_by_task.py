"""T02801 回归：后台事件按 task_id 反查归属，不再用「最后活跃用户」近似

背景：T02684 给无 request 上下文的事件写入补了 `_active_user_id_for_background_write()`
（最近活跃的非 default 用户）。单用户部署下正确，但调度器启动时会加载**所有用户**的任务
（web/startup.py 的 `list_tasks()` 不带 user_id），多账号并发时「最后活跃」会把 A 任务
的事件写到 B 名下 —— 甲看不到自己的日志，乙的列表混入他人记录。

本单把取值顺序改为：显式 user_id → tasks.user_id（带缓存）→ 活跃用户 → default。
运行：
    .venv/Scripts/python.exe -m pytest tests/test_event_attribution_by_task.py -o addopts="" -p no:cacheprovider -q
"""
from __future__ import annotations

import pytest

from xianyu_hunter.infra import repo_events


@pytest.fixture
def repo(tmp_path):
    from xianyu_hunter.infra.repository import Repository

    return Repository(db_path=str(tmp_path / "attribution.db"))


def _mk_task(repo, task_id: str, user_id: str) -> None:
    repo.upsert_task({
        "id": task_id, "name": task_id, "keyword": "iphone",
        "mode": "confirm", "cron": "*/5 * * * *", "user_id": user_id,
    })


def _ev(task_id: str | None, message: str, **extra) -> dict:
    row: dict = {
        "type": "task.search_done",
        "task_id": task_id,
        "stage": "search",
        "level": "info",
        "message": message,
        "payload": None,
    }
    row.update(extra)
    return row


def test_background_event_follows_task_owner_not_active_user(repo, monkeypatch) -> None:
    """任务属于 alice、当前活跃是 bob：事件必须落 alice，且读侧各看各的"""
    _mk_task(repo, "t-alice", "alice")
    monkeypatch.setattr(repo_events, "_active_user_id_for_background_write", lambda: "bob")

    eid = repo.save_event(_ev("t-alice", "alice-search"))

    assert repo.get_event(eid)["user_id"] == "alice"
    assert [e["message"] for e in repo.list_events(user_id="alice")] == ["alice-search"]
    assert repo.list_events(user_id="bob") == []


def test_explicit_user_id_still_wins(repo, monkeypatch) -> None:
    _mk_task(repo, "t-alice", "alice")
    monkeypatch.setattr(repo_events, "_active_user_id_for_background_write", lambda: "carol")

    eid = repo.save_event(_ev("t-alice", "explicit", user_id="bob"))

    assert repo.get_event(eid)["user_id"] == "bob"


def test_unknown_task_falls_back_to_active_user(repo, monkeypatch) -> None:
    """任务还没落库 / 已被删除：退回旧口径，事件不能因此丢失"""
    monkeypatch.setattr(repo_events, "_active_user_id_for_background_write", lambda: "bob")

    eid = repo.save_event(_ev("t-missing", "orphan"))

    assert repo.get_event(eid)["user_id"] == "bob"


def test_no_task_id_falls_back_to_active_user(repo, monkeypatch) -> None:
    """审计类事件（task_id=None）没有可反查的任务，保持旧口径"""
    monkeypatch.setattr(repo_events, "_active_user_id_for_background_write", lambda: "bob")

    eid = repo.save_event(_ev(None, "db_admin.delete"))

    assert repo.get_event(eid)["user_id"] == "bob"


def test_task_owner_lookup_is_cached(repo, monkeypatch) -> None:
    """同一任务连写多条日志只查一次 tasks，避免每条事件一次 SELECT"""
    _mk_task(repo, "t-alice", "alice")
    monkeypatch.setattr(repo_events, "_active_user_id_for_background_write", lambda: "bob")
    calls: list[str] = []
    original = repo.get_task

    def _counting_get_task(task_id, user_id=None):
        calls.append(task_id)
        return original(task_id, user_id=user_id)

    monkeypatch.setattr(repo, "get_task", _counting_get_task)

    repo.save_event(_ev("t-alice", "one"))
    repo.save_event(_ev("t-alice", "two"))

    assert calls == ["t-alice"]


def test_owner_cache_is_per_repository(tmp_path, monkeypatch) -> None:
    """缓存不能做成模块级：两个库里的同名任务归属不同，不能互相串味"""
    from xianyu_hunter.infra.repository import Repository

    r1 = Repository(db_path=str(tmp_path / "one.db"))
    r2 = Repository(db_path=str(tmp_path / "two.db"))
    _mk_task(r1, "t-shared", "alice")
    _mk_task(r2, "t-shared", "carol")
    monkeypatch.setattr(repo_events, "_active_user_id_for_background_write", lambda: "bob")

    e1 = r1.save_event(_ev("t-shared", "from-one"))
    e2 = r2.save_event(_ev("t-shared", "from-two"))

    assert r1.get_event(e1)["user_id"] == "alice"
    assert r2.get_event(e2)["user_id"] == "carol"


def test_lookup_failure_does_not_drop_event(repo, monkeypatch) -> None:
    """反查异常时降级到活跃用户：归属可以错，事件不能丢"""
    monkeypatch.setattr(repo_events, "_active_user_id_for_background_write", lambda: "bob")

    def _boom(task_id, user_id=None):
        raise RuntimeError("db busy")

    monkeypatch.setattr(repo, "get_task", _boom)

    eid = repo.save_event(_ev("t-alice", "still-written"))

    assert repo.get_event(eid)["user_id"] == "bob"
