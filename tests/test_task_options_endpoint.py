# tests/test_task_options_endpoint.py
"""GET /api/tasks/options —— 任务下拉候选端点（T02654）

缺陷来源：任务管理页「闲鱼内容关联」面板的任务下拉直接复用了列表的当页数据。
任务多于 pageSize 时，分页范围外的任务在下拉里根本选不到，其关联也就无从删除
（评审实测：dev 库 34 个任务，夹具任务落在第 2 页时面板搜不到，把它提到第 1 页立刻能删）。

这里打真实端点验证四件事：候选与列表分页解耦、只回轻字段、排除软删除、
仍然按 user_id 隔离（前端不得绕过这个过滤）。
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from xianyu_hunter.config import Settings
from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.web.app import app
from xianyu_hunter.web.deps import get_container

_TEST_TOKEN = "test-token-task-options"


@pytest.fixture
def tmp_repo() -> Repository:
    """临时数据库，避免污染开发库"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        repo = Repository(str(Path(d) / "test.db"))
        yield repo
        # Windows 上必须先释放 sqlite 文件句柄
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


def _seed_task(repo: Repository, idx: int, **overrides) -> str:
    task = {
        "id": f"topt_{idx:03d}",
        "name": f"任务{idx}",
        "keyword": f"关键词{idx}",
        "mode": "confirm",
        "cron": "*/5 * * * *",
        **overrides,
    }
    repo.upsert_task(task)
    return task["id"]


def test_options_returns_only_light_fields(client, tmp_repo):
    """下拉候选只回 id/name/keyword：不带 config 大字段，才敢放宽 limit"""
    _seed_task(tmp_repo, 1)
    body = client.get("/api/tasks/options", headers=_headers()).json()
    assert body["count"] == 1
    item = body["items"][0]
    assert set(item.keys()) == {"id", "name", "keyword"}
    assert item["name"] == "任务1"


def test_options_not_bounded_by_list_pagination(client, tmp_repo):
    """核心回归：列表按 limit 截断，候选必须是全量，否则第 2 页任务选不到"""
    for i in range(25):
        _seed_task(tmp_repo, i)
    listed = client.get("/api/tasks?limit=1&offset=0", headers=_headers()).json()
    assert len(listed["items"]) == 1
    assert listed["total"] == 25

    opts = client.get("/api/tasks/options", headers=_headers()).json()
    assert opts["count"] == 25


def test_options_excludes_soft_deleted(client, tmp_repo):
    """软删除任务不得出现在候选里（与 list_tasks 的默认过滤一致）"""
    kept = _seed_task(tmp_repo, 1)
    removed = _seed_task(tmp_repo, 2, status="deleted")
    ids = {i["id"] for i in client.get("/api/tasks/options", headers=_headers()).json()["items"]}
    assert kept in ids
    assert removed not in ids


def test_options_scoped_to_user(client, tmp_repo):
    """多用户隔离：管理令牌直通 = default 用户，不得看到他人任务"""
    mine = _seed_task(tmp_repo, 1)
    theirs = _seed_task(tmp_repo, 2, user_id="u_other")
    ids = {i["id"] for i in client.get("/api/tasks/options", headers=_headers()).json()["items"]}
    assert ids == {mine}
    assert theirs not in ids


def test_options_route_wins_over_task_id_path():
    """路由顺序守卫：/options 必须声明在 /{task_id} 之前，否则 "options" 被当成任务 id"""
    get_paths = [
        r.path for r in app.routes
        if getattr(r, "path", "").startswith("/api/tasks") and "GET" in getattr(r, "methods", set())
    ]
    assert "/api/tasks/options" in get_paths
    assert get_paths.index("/api/tasks/options") < get_paths.index("/api/tasks/{task_id}")
