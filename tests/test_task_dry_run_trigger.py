# tests/test_task_dry_run_trigger.py
"""演练一次入口与频控测试（PRD FR-C3-5，REQ-015）"""
import pytest
from fastapi.testclient import TestClient

from xianyu_hunter.web.app import create_app
from xianyu_hunter.web.routes import api_tasks as at
from xianyu_hunter.config import get_settings


@pytest.fixture
def client():
    return TestClient(create_app())


def _auth() -> dict:
    return {"Authorization": f"Bearer {get_settings().web_token}"}


def _create_running_task(client) -> str:
    resp = client.post("/api/tasks", json={
        "keyword": "演练入口", "mode": "auto", "status": "running",
    }, headers=_auth())
    assert resp.status_code == 200
    tid = resp.json()["id"]
    client.patch(f"/api/tasks/{tid}", json={"status": "running"}, headers=_auth())
    return tid


def test_dry_run_rate_limit_429(client):
    """同任务 60s 内重复触发 → 429（FR-C3-5 频率限制）"""
    tid = _create_running_task(client)
    # 清空模块级频控状态，保证测试确定性
    at._dry_run_last_triggered.clear()
    at._dry_run_running.clear()

    r1 = client.post(f"/api/tasks/{tid}/dry-run", headers=_auth())
    assert r1.status_code == 200, r1.text
    # 触发成功即记账：60s 内第二次触发被拒
    r2 = client.post(f"/api/tasks/{tid}/dry-run", headers=_auth())
    assert r2.status_code == 429
    assert "60" in r2.json()["detail"]


def test_dry_run_not_running_task_400(client):
    """非 running 任务无法演练（浏览器未就绪）"""
    resp = client.post("/api/tasks", json={
        "keyword": "暂停任务", "mode": "auto",
    }, headers=_auth())
    tid = resp.json()["id"]
    # TaskCreate 无 status 字段（默认 running），显式 PATCH 为 paused
    client.patch(f"/api/tasks/{tid}", json={"status": "paused"}, headers=_auth())
    at._dry_run_last_triggered.clear()
    at._dry_run_running.clear()
    r = client.post(f"/api/tasks/{tid}/dry-run", headers=_auth())
    assert r.status_code == 400
    at._dry_run_last_triggered.clear()


def test_dry_run_unknown_task_404(client):
    at._dry_run_last_triggered.clear()
    r = client.post("/api/tasks/t_nonexistent/dry-run", headers=_auth())
    assert r.status_code == 404
