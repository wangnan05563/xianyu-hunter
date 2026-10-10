# tests/test_task_dry_run_api.py
"""任务级演练开关 API 测试（PRD FR-C3-1，REQ-011）"""
import pytest
from fastapi.testclient import TestClient

from xianyu_hunter.web.app import create_app
from xianyu_hunter.config import get_settings


@pytest.fixture
def client():
    return TestClient(create_app())


def _auth_headers() -> dict:
    """WEB_TOKEN 管理令牌直通（与 test_mu2_integration 同一认证方式）"""
    return {"Authorization": f"Bearer {get_settings().web_token}"}


def _create_task(client, **overrides) -> str:
    body = {
        "keyword": "演练测试",
        "mode": "auto",
        **overrides,
    }
    resp = client.post("/api/tasks", json=body, headers=_auth_headers())
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def test_create_task_dry_run_default_false(client):
    """不传 dry_run 时默认关闭（向后兼容）"""
    task_id = _create_task(client)
    t = client.get(f"/api/tasks/{task_id}", headers=_auth_headers()).json()
    assert bool(t.get("dry_run") in (1, True)) is False


def test_create_task_with_dry_run(client):
    """创建任务携带 dry_run=true 并能读回"""
    task_id = _create_task(client, dry_run=True)
    t = client.get(f"/api/tasks/{task_id}", headers=_auth_headers()).json()
    assert t.get("dry_run") in (1, True)


def test_update_task_dry_run_patch(client):
    """PATCH 三态语义：传 bool 更新演练开关"""
    task_id = _create_task(client)
    resp = client.patch(f"/api/tasks/{task_id}", json={"dry_run": True}, headers=_auth_headers())
    assert resp.status_code == 200
    t = client.get(f"/api/tasks/{task_id}", headers=_auth_headers()).json()
    assert t.get("dry_run") in (1, True)
    # 再关掉
    client.patch(f"/api/tasks/{task_id}", json={"dry_run": False}, headers=_auth_headers())
    t = client.get(f"/api/tasks/{task_id}", headers=_auth_headers()).json()
    assert bool(t.get("dry_run") in (1, True)) is False


def test_task_list_contains_dry_run_field(client):
    """任务列表带出 dry_run 字段（全局「演练中」横幅的数据源）"""
    task_id = _create_task(client, dry_run=True)
    rows = client.get("/api/tasks", headers=_auth_headers()).json()["items"]
    row = next(r for r in rows if r["id"] == task_id)
    assert "dry_run" in row
    assert row["dry_run"] in (1, True)
