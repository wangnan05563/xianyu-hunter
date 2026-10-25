"""T02800 回归：error_logs 补 user_id 后的多用户隔离（读 / 写 / 改 / 链路聚合）

背景：error_logs 原本没有 user_id 列，T02684 只能隔离 events 侧；
/api/error-logs/* 与 /api/logs/request/{id} 的异常分支跨用户可见。
本单补列 + 历史行归 default，读改删清理全部接 reader_user_id 口径。

运行：
    .venv/Scripts/python.exe -m pytest tests/test_error_logs_user_isolation.py -o addopts="" -p no:cacheprovider -q
"""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest


@pytest.fixture
def repo(tmp_path):
    from xianyu_hunter.infra.repository import Repository

    return Repository(db_path=str(tmp_path / "error_logs_iso.db"))


def _mk_log(repo, user_id: str, message: str, *, status: str = "new",
            request_id: str | None = None, timestamp: datetime | None = None) -> int:
    row: dict = {
        "error_type": "ValueError",
        "error_message": message,
        "status": status,
        "user_id": user_id,
    }
    if request_id:
        row["request_id"] = request_id
    if timestamp:
        row["timestamp"] = timestamp
    return repo.save_error_log(row)


def _req(user_id: str | None):
    if user_id is None:
        return SimpleNamespace(state=SimpleNamespace())
    return SimpleNamespace(state=SimpleNamespace(user_id=user_id))


@pytest.fixture
def shim(repo):
    return SimpleNamespace(repo=repo)


R_ID = "req-20260701120000537-a3b2c1"


# ==================== 仓储层 ====================
def test_list_error_logs_is_user_scoped(repo) -> None:
    _mk_log(repo, "alice", "alice-err")
    _mk_log(repo, "bob", "bob-err")

    assert [r["error_message"] for r in repo.list_error_logs(user_id="alice")] == ["alice-err"]
    assert [r["error_message"] for r in repo.list_error_logs(user_id="bob")] == ["bob-err"]
    # None = 管理令牌直通/单用户：不过滤
    assert len(repo.list_error_logs()) == 2


def test_get_update_delete_reject_other_users_row(repo) -> None:
    a = _mk_log(repo, "alice", "a")
    b = _mk_log(repo, "bob", "b")

    assert repo.get_error_log(a, user_id="alice")["error_message"] == "a"
    assert repo.get_error_log(b, user_id="alice") is None
    assert repo.update_error_log_status(b, "resolved", user_id="alice") is False
    assert repo.get_error_log(b)["status"] == "new"
    assert repo.delete_error_log(b, user_id="alice") is False
    assert repo.get_error_log(b) is not None


def test_batch_actions_only_touch_own_rows(repo) -> None:
    a = _mk_log(repo, "alice", "a")
    b = _mk_log(repo, "bob", "b")

    assert repo.batch_update_error_log_status([a, b], "resolved", user_id="alice") == 1
    assert repo.get_error_log(a)["status"] == "resolved"
    assert repo.get_error_log(b)["status"] == "new"

    assert repo.batch_delete_error_logs([a, b], user_id="alice") == 1
    assert repo.get_error_log(a) is None
    assert repo.get_error_log(b) is not None


def test_status_counts_are_user_scoped(repo) -> None:
    _mk_log(repo, "alice", "a1")
    _mk_log(repo, "alice", "a2", status="resolved")
    _mk_log(repo, "bob", "b1", status="resolved")

    assert repo.count_error_logs_by_status(user_id="alice") == {"new": 1, "resolved": 1}
    assert repo.count_error_logs_by_status(user_id="bob") == {"resolved": 1}


def test_cleanup_only_removes_own_old_rows(repo) -> None:
    old = datetime.now() - timedelta(days=90)
    a = _mk_log(repo, "alice", "old-a", status="resolved", timestamp=old)
    b = _mk_log(repo, "bob", "old-b", status="resolved", timestamp=old)

    assert repo.cleanup_old_error_logs(days=30, user_id="alice") == 1
    assert repo.get_error_log(a) is None
    assert repo.get_error_log(b) is not None


def test_save_error_log_attribution(repo, monkeypatch) -> None:
    from xianyu_hunter.infra import repo_events

    monkeypatch.setattr(repo_events, "_active_user_id_for_background_write", lambda: "bob")

    explicit = _mk_log(repo, "alice", "explicit")
    assert repo.get_error_log(explicit)["user_id"] == "alice"

    # 后台/直调没传身份 → 与 events 同源的活跃用户兜底
    fallback = repo.save_error_log({"error_type": "RuntimeError", "error_message": "bg", "status": "new"})
    assert repo.get_error_log(fallback)["user_id"] == "bob"


# ==================== 路由层 ====================
def test_list_route_filters_by_session_user(shim, repo) -> None:
    from xianyu_hunter.web.routes import api_error_logs

    _mk_log(repo, "alice", "alice-err")
    _mk_log(repo, "bob", "bob-err")

    # 直接调用路由函数时 Query 默认值不会由 FastAPI 解析，显式传 None/默认值
    _defaults = dict(status=None, error_type=None, request_path=None, request_id=None,
                     start=None, end=None, limit=50, offset=0)
    res = api_error_logs.list_error_logs(request=_req("alice"), container=shim, **_defaults)

    assert [i["error_message"] for i in res["items"]] == ["alice-err"]
    assert res["status_counts"] == {"new": 1}

    as_default = api_error_logs.list_error_logs(request=_req("default"), container=shim, **_defaults)
    # "default" 是直通身份 → reader_user_id 返回 None，两行都可见
    assert len(as_default["items"]) == 2


def test_detail_and_batch_routes_cannot_reach_other_user(shim, repo) -> None:
    from fastapi import HTTPException
    from xianyu_hunter.web.routes import api_error_logs

    b = _mk_log(repo, "bob", "bob-err")

    with pytest.raises(HTTPException) as exc:
        api_error_logs.get_error_log(request=_req("alice"), error_log_id=b, container=shim)
    assert exc.value.status_code == 404

    payload = api_error_logs.BatchActionRequest(ids=[b], action="delete")
    res = api_error_logs.batch_action(request=_req("alice"), payload=payload, container=shim)
    assert res["affected"] == 0
    assert repo.get_error_log(b) is not None


def test_request_chain_filters_error_logs_and_keeps_flag(shim, repo) -> None:
    from xianyu_hunter.web.routes import api_logs

    repo.save_event({"type": "task.search_done", "stage": "search", "level": "info",
                     "message": "alice-ev", "payload": None, "request_id": R_ID, "user_id": "alice"})
    repo.save_event({"type": "task.search_done", "stage": "search", "level": "info",
                     "message": "bob-ev", "payload": None, "request_id": R_ID, "user_id": "bob"})
    _mk_log(repo, "alice", "alice-err", request_id=R_ID)
    _mk_log(repo, "bob", "bob-err", request_id=R_ID)

    res = api_logs.get_request_chain(request=_req("alice"), request_id=R_ID, limit=100, container=shim)

    # events 用 message，error_logs 用 error_message，统一取展示文本
    msgs = sorted(i.get("message") or i.get("error_message") or "" for i in res["chain"])
    assert msgs == ["alice-err", "alice-ev"]
    assert res["error_logs_total"] == 1
    assert res["error_logs_isolated"] is True

    as_default = api_logs.get_request_chain(request=_req("default"), request_id=R_ID,
                                            limit=100, container=shim)
    assert len(as_default["chain"]) == 4
    assert as_default["error_logs_isolated"] is False


def test_capture_request_error_stamps_request_user(repo, monkeypatch) -> None:
    """写侧：HTTP 请求内异常必须带上请求身份，不能靠「最后活跃用户」猜"""
    from xianyu_hunter.web.middleware import error_capture

    shim = SimpleNamespace(repo=repo)
    monkeypatch.setattr("xianyu_hunter.web.deps.get_container", lambda: shim)

    fake_request = SimpleNamespace(
        method="GET",
        url=SimpleNamespace(path="/api/boom"),
        headers={},
        client=None,
        query_params={},
        state=SimpleNamespace(user_id="alice"),
    )
    eid = error_capture.capture_request_error(fake_request, RuntimeError("boom"))

    assert eid is not None
    assert repo.get_error_log(eid, user_id="alice")["request_path"] == "/api/boom"
    assert repo.get_error_log(eid, user_id="bob") is None


def test_migration_adds_user_id_and_backfills_default(tmp_path) -> None:
    """旧库（无 user_id 列）升级后：列存在、历史行归 default、再次 init 幂等"""
    import sqlite3
    from sqlalchemy import create_engine, text

    from xianyu_hunter.infra.db_models import init_db

    db = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{db.as_posix()}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE error_logs ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME NOT NULL, "
            "error_type VARCHAR NOT NULL, error_message TEXT NOT NULL, status VARCHAR NOT NULL)"
        ))
        conn.execute(text(
            "INSERT INTO error_logs (timestamp, error_type, error_message, status) "
            "VALUES ('2026-01-01 00:00:00', 'ValueError', 'legacy', 'new')"
        ))
    engine.dispose()

    init_db(str(db))
    init_db(str(db))  # 幂等

    with sqlite3.connect(db) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(error_logs)")}
        assert "user_id" in cols
        assert conn.execute("SELECT user_id FROM error_logs").fetchone()[0] == "default"
