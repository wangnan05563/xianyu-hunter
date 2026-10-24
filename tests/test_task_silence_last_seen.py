# tests/test_task_silence_last_seen.py
"""GET /api/tasks 的 last_seen_at —— 「沉默」判定的数据契约（T02652）

缺陷来源：任务列表的「沉默」标签按 updated_at 判定，编辑任务也会刷新该列，
于是长期零命中、刚被编辑过的任务显示成「活跃」。前端改为消费
list_tasks_with_last_seen 聚合出的 last_seen_at（max(items.last_seen)）。

这里打真实端点固定三件事：
1) last_seen_at = 该任务所有商品里最近一次命中时间，编辑任务不影响它；
2) 没有商品的未跑任务返回 null（前端才能回落 created_at，而不是判活跃）；
3) 该聚合仍然按 user_id 隔离，不能把他人任务/商品的时间泄漏进来。
"""
from __future__ import annotations

import tempfile
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from xianyu_hunter.config import Settings
from xianyu_hunter.infra.db_models import _utcnow
from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.web.app import app
from xianyu_hunter.web.deps import get_container

_TEST_TOKEN = "test-token-task-silence"


@pytest.fixture
def tmp_repo() -> Repository:
    """临时数据库，避免污染开发库"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        repo = Repository(str(Path(d) / "test.db"))
        yield repo
        repo.engine.dispose()


@pytest.fixture
def client(tmp_repo: Repository, monkeypatch) -> TestClient:
    test_settings = Settings(web_token=_TEST_TOKEN)

    def _fake_settings():
        return test_settings

    monkeypatch.setattr("xianyu_hunter.config.get_settings", _fake_settings)
    monkeypatch.setattr("xianyu_hunter.web.app.get_settings", _fake_settings, raising=False)

    class _FakeContainer:
        def __init__(self, repo):
            self.repo = repo

    fake = _FakeContainer(tmp_repo)
    app.dependency_overrides[get_container] = lambda: fake
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_TEST_TOKEN}"}


def _seed_task(repo: Repository, task_id: str, **overrides) -> None:
    now = _utcnow()
    task = {
        "id": task_id,
        "name": task_id,
        "keyword": f"关键词{task_id}",
        "mode": "confirm",
        "cron": "*/5 * * * *",
        "created_at": now - timedelta(days=400),
        "updated_at": now - timedelta(days=400),
        **overrides,
    }
    repo.upsert_task(task)


def _seed_item(repo: Repository, item_id: str, task_id: str, last_seen, user_id: str = "default") -> None:
    repo.upsert_item({
        "id": item_id,
        "task_id": task_id,
        "title": item_id,
        "price": 100.0,
        "last_seen": last_seen,
        "user_id": user_id,
    })


def _items_by_id(client: TestClient) -> dict[str, dict]:
    body = client.get("/api/tasks?limit=200", headers=_headers()).json()
    return {it["id"]: it for it in body["items"]}


def test_last_seen_at_is_latest_hit_not_edit_time(client, tmp_repo):
    """核心回归：编辑刷新 updated_at，但沉默判定用的 last_seen_at 必须停在旧命中时间"""
    now = _utcnow()
    hit_at = now - timedelta(days=40)
    _seed_task(tmp_repo, "t_silent", updated_at=now)  # 刚被编辑过
    _seed_item(tmp_repo, "i_old", "t_silent", hit_at - timedelta(days=10))
    _seed_item(tmp_repo, "i_latest", "t_silent", hit_at)

    item = _items_by_id(client)["t_silent"]
    # SQLite 读回的是 naive UTC，API 序列化不带时区后缀
    assert item["last_seen_at"] == hit_at.replace(tzinfo=None).isoformat()
    assert item["last_seen_at"] != item["updated_at"]


def test_task_without_items_reports_null(client, tmp_repo):
    """从未命中的任务返回 null，而不是伪造一个「活跃」时间"""
    _seed_task(tmp_repo, "t_never")
    item = _items_by_id(client)["t_never"]
    assert "last_seen_at" in item
    assert item["last_seen_at"] is None


def test_last_seen_aggregation_is_user_scoped(client, tmp_repo):
    """多用户隔离：他人任务的聚合时间不得混入"""
    now = _utcnow()
    _seed_task(tmp_repo, "t_mine")
    _seed_task(tmp_repo, "t_theirs", user_id="u_other")
    _seed_item(tmp_repo, "i_theirs", "t_theirs", now - timedelta(days=1), user_id="u_other")

    items = _items_by_id(client)
    assert set(items) == {"t_mine"}
    assert items["t_mine"]["last_seen_at"] is None
