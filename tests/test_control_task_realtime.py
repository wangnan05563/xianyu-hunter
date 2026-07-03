"""P0-2 control_task 实时唤醒 Scheduler 测试

回归背景：control_task 端点之前仅改 DB status 字段，需重启 run 进程才生效。
修复后 XH_WITH_SCHEDULER=1 模式下直接调用 scheduler.pause/resume/stop/start
实时操作内存对象，纯 web 模式下仅改 DB（与现有 api_items/api_orders 降级范式一致）。

测试覆盖：
1. 纯 web 模式（collector=None）：仅改 DB，note 不含"调度器"
2. scheduler 模式：调用 scheduler.pause/resume/stop
3. restart 已注册任务：执行 stop+start
4. 未注册任务：不抛异常，note 含"未注册"
5. 任务不存在：返回 404
6. 未知 action：返回 400
"""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from xianyu_hunter.config import Settings
from xianyu_hunter.domain.task import Task
from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.modules.scheduler import TaskScheduler
from xianyu_hunter.web.app import app
from xianyu_hunter.web.deps import get_container


_TEST_TOKEN = "test-token-control-realtime"


@pytest.fixture
def tmp_repo() -> Repository:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db_path = str(Path(d) / "test.db")
        repo = Repository(db_path)
        yield repo
        repo.engine.dispose()


def _make_scheduler_with_task(task_id: str) -> tuple[TaskScheduler, MagicMock, MagicMock, AsyncMock, MagicMock]:
    """构造一个真实 TaskScheduler 并注册一个任务，返回 scheduler + mock 方法

    用 asyncio.run 执行 register 协程，避免在同步 fixture 中依赖 pytest-asyncio
    """
    scheduler = TaskScheduler()

    # 用 MagicMock 构造 worker，避免依赖真实 Collector/Buyer
    worker = MagicMock()
    worker.run_once = AsyncMock(return_value=MagicMock(should_pause=False))

    task = Task(id=task_id, name="test", keyword="kw")
    # register 内部只是 async with lock + 字典赋值，asyncio.run 同步执行即可
    asyncio.run(scheduler.register(task, worker))

    # pause/resume/start 是同步方法用 MagicMock，stop 是 async 用 AsyncMock
    # 之前误用 AsyncMock 导致 api_tasks 同步调用时 assert_awaited 失败
    scheduler.pause = MagicMock()
    scheduler.resume = MagicMock()
    scheduler.stop = AsyncMock()
    scheduler.start = MagicMock()
    scheduler.is_running = MagicMock(return_value=False)
    scheduler.list_tasks = MagicMock(return_value=[task])

    return scheduler, scheduler.pause, scheduler.resume, scheduler.stop, scheduler.start


@pytest.fixture
def client_pure_web(tmp_repo: Repository, monkeypatch) -> TestClient:
    """纯 web 模式：collector=None，scheduler=None"""
    test_settings = Settings(web_token=_TEST_TOKEN)
    monkeypatch.setattr("xianyu_hunter.config.get_settings", lambda: test_settings)
    monkeypatch.setattr("xianyu_hunter.web.app.get_settings", lambda: test_settings, raising=False)

    class _FakeContainer:
        def __init__(self, repo):
            self.repo = repo
            self.collector = None  # 纯 web 模式标志
            self.scheduler = None

    fake = _FakeContainer(tmp_repo)
    app.dependency_overrides[get_container] = lambda: fake
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture
def client_scheduler_mode(tmp_repo: Repository, monkeypatch) -> TestClient:
    """scheduler 模式：collector 非 None，scheduler 是 mock"""
    test_settings = Settings(web_token=_TEST_TOKEN)
    monkeypatch.setattr("xianyu_hunter.config.get_settings", lambda: test_settings)
    monkeypatch.setattr("xianyu_hunter.web.app.get_settings", lambda: test_settings, raising=False)

    scheduler, _, _, _, _ = _make_scheduler_with_task("t1")

    class _FakeContainer:
        def __init__(self, repo):
            self.repo = repo
            self.collector = MagicMock()  # 非 None 表示 scheduler 模式
            self.scheduler = scheduler

    fake = _FakeContainer(tmp_repo)
    app.dependency_overrides[get_container] = lambda: fake
    yield TestClient(app, raise_server_exceptions=False), scheduler
    app.dependency_overrides.clear()


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_TEST_TOKEN}"}


# ============== 纯 web 模式测试 ==============


class TestPureWebMode:
    """collector=None 时仅改 DB，不调用 scheduler"""

    def test_pause_pure_web(self, client_pure_web: TestClient, tmp_repo: Repository):
        tmp_repo.upsert_task({"id": "t1", "name": "test", "keyword": "kw", "status": "running"})

        resp = client_pure_web.post(
            "/api/tasks/t1/control",
            params={"action": "pause"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "paused"
        # 纯 web 模式 note 不含"调度器"
        assert "调度器" not in data["note"]

        # 验证 DB 已更新
        loaded = tmp_repo.get_task("t1")
        assert loaded["status"] == "paused"

    def test_restart_pure_web(self, client_pure_web: TestClient, tmp_repo: Repository):
        tmp_repo.upsert_task({"id": "t1", "name": "test", "keyword": "kw", "status": "stopped"})

        resp = client_pure_web.post(
            "/api/tasks/t1/control",
            params={"action": "restart"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

        loaded = tmp_repo.get_task("t1")
        assert loaded["status"] == "running"


# ============== scheduler 模式测试 ==============


class TestSchedulerModeRealtime:
    """collector 非 None 时实时调用 scheduler 方法"""

    def test_pause_calls_scheduler(self, client_scheduler_mode, tmp_repo: Repository):
        client, scheduler = client_scheduler_mode
        tmp_repo.upsert_task({"id": "t1", "name": "test", "keyword": "kw", "status": "running"})

        resp = client.post(
            "/api/tasks/t1/control",
            params={"action": "pause"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        scheduler.pause.assert_called_once_with("t1")
        assert "已暂停" in resp.json()["note"]

    def test_resume_calls_scheduler(self, client_scheduler_mode, tmp_repo: Repository):
        client, scheduler = client_scheduler_mode
        tmp_repo.upsert_task({"id": "t1", "name": "test", "keyword": "kw", "status": "paused"})

        resp = client.post(
            "/api/tasks/t1/control",
            params={"action": "resume"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        scheduler.resume.assert_called_once_with("t1")
        assert "已恢复" in resp.json()["note"]

    def test_stop_calls_scheduler(self, client_scheduler_mode, tmp_repo: Repository):
        client, scheduler = client_scheduler_mode
        tmp_repo.upsert_task({"id": "t1", "name": "test", "keyword": "kw", "status": "running"})

        resp = client.post(
            "/api/tasks/t1/control",
            params={"action": "stop"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        scheduler.stop.assert_awaited_once_with("t1")
        assert "已停止" in resp.json()["note"]

    def test_restart_registered_task_calls_stop_and_start(
        self, client_scheduler_mode, tmp_repo: Repository
    ):
        """restart 已注册任务：先 stop 再 start"""
        client, scheduler = client_scheduler_mode
        tmp_repo.upsert_task({"id": "t1", "name": "test", "keyword": "kw", "status": "stopped"})

        # is_running 返回 False，跳过 stop 直接 start
        scheduler.is_running = MagicMock(return_value=False)

        resp = client.post(
            "/api/tasks/t1/control",
            params={"action": "restart"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        # is_running=False 时不调用 stop
        scheduler.stop.assert_not_awaited()
        scheduler.start.assert_called_once_with("t1")
        assert "已重启" in resp.json()["note"]

    def test_restart_running_task_calls_stop_then_start(
        self, client_scheduler_mode, tmp_repo: Repository
    ):
        """restart 正在运行的任务：先 stop 再 start"""
        client, scheduler = client_scheduler_mode
        tmp_repo.upsert_task({"id": "t1", "name": "test", "keyword": "kw", "status": "running"})

        # is_running 返回 True，应先 stop 再 start
        scheduler.is_running = MagicMock(return_value=True)

        resp = client.post(
            "/api/tasks/t1/control",
            params={"action": "restart"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        scheduler.stop.assert_awaited_once_with("t1")
        scheduler.start.assert_called_once_with("t1")


# ============== 边界场景测试 ==============


class TestEdgeCases:
    """边界场景：未注册任务、任务不存在、未知 action"""

    def test_restart_unregistered_task_no_crash(
        self, client_scheduler_mode, tmp_repo: Repository
    ):
        """restart 未注册任务：返回 note 但不抛异常"""
        client, scheduler = client_scheduler_mode
        tmp_repo.upsert_task({"id": "t_unregistered", "name": "test", "keyword": "kw"})

        # list_tasks 返回空列表，模拟任务未注册
        scheduler.list_tasks = MagicMock(return_value=[])

        resp = client.post(
            "/api/tasks/t_unregistered/control",
            params={"action": "restart"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        assert "未注册" in resp.json()["note"] or "重启服务" in resp.json()["note"]

    def test_pause_unregistered_task_via_keyerror(
        self, client_scheduler_mode, tmp_repo: Repository
    ):
        """pause 未注册任务：scheduler.pause 抛 KeyError，捕获后 note 含提示"""
        client, scheduler = client_scheduler_mode
        tmp_repo.upsert_task({"id": "t_orphan", "name": "test", "keyword": "kw"})

        # scheduler.pause 抛 KeyError 模拟未注册
        # 用 MagicMock 而非 AsyncMock：api_tasks.py 同步调用 pause（无 await），
        # AsyncMock 的 side_effect 仅在 await 时触发，同步调用只返回 coroutine 不抛错
        scheduler.pause = MagicMock(side_effect=KeyError("任务 t_orphan 未注册"))

        resp = client.post(
            "/api/tasks/t_orphan/control",
            params={"action": "pause"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        # DB 状态已更新，但 note 提示调度器未注册
        assert "未注册" in resp.json()["note"] or "DB" in resp.json()["note"]

    def test_scheduler_runtime_exception_does_not_return_500(
        self, client_scheduler_mode, tmp_repo: Repository
    ):
        """scheduler 抛非 KeyError 异常时不返回 500，DB 状态仍生效

        兜底场景：scheduler.start 内部 asyncio.create_task 在 loop 关闭时抛 RuntimeError，
        control_task 必须 catch Exception 兜底，避免 500 阻断 DB 状态更新。
        """
        client, scheduler = client_scheduler_mode
        tmp_repo.upsert_task({"id": "t1", "name": "test", "keyword": "kw", "status": "running"})

        # scheduler.pause 抛 RuntimeError 模拟内部异常
        # 同理用 MagicMock：同步调用需立即抛错，AsyncMock 的 side_effect 不会触发
        scheduler.pause = MagicMock(side_effect=RuntimeError("loop closed"))

        resp = client.post(
            "/api/tasks/t1/control",
            params={"action": "pause"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()
        # DB 状态已更新
        assert data["status"] == "paused"
        # note 提示异常但不阻断
        assert "异常" in data["note"] or "DB" in data["note"]
        # 验证 DB 已更新
        loaded = tmp_repo.get_task("t1")
        assert loaded["status"] == "paused"

    def test_task_not_found_returns_404(self, client_pure_web: TestClient):
        """任务不存在返回 404"""
        resp = client_pure_web.post(
            "/api/tasks/t_nonexistent/control",
            params={"action": "pause"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 404

    def test_invalid_action_returns_400(self, client_pure_web: TestClient, tmp_repo: Repository):
        """未知 action 返回 400"""
        tmp_repo.upsert_task({"id": "t1", "name": "test", "keyword": "kw"})

        resp = client_pure_web.post(
            "/api/tasks/t1/control",
            params={"action": "invalid"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 400
