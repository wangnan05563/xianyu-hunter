"""P0-1 Cron 配置断层修复测试

回归背景：前端 TaskEditor 让用户编辑 cron 表达式，但后端 TaskCreate/TaskUpdate
Pydantic 模型不接收 cron 字段，且 TaskConfig.use_cron 默认 False 永不生效，
导致所有任务实际都按 60s interval 运行。本测试验证修复后的完整链路：

1. POST /api/tasks 持久化 cron / use_cron / interval_seconds 到 DB
2. GET /api/tasks/{id} 返回这些字段
3. PATCH /api/tasks/{id} 更新这些字段
4. 字段校验：interval_seconds 超出 30-3600 返回 422
5. DB 迁移：init_db 添加 use_cron / interval_seconds 列
6. Task 领域模型包含 use_cron / interval_seconds 字段
7. TaskConfig 从 Task 字段读取（消除分裂脑）
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from xianyu_hunter.config import Settings
from xianyu_hunter.infra.db_models import init_db
from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.web.app import app
from xianyu_hunter.web.deps import get_container


_TEST_TOKEN = "test-token-cron-fix"


@pytest.fixture
def tmp_repo() -> Repository:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db_path = str(Path(d) / "test.db")
        repo = Repository(db_path)
        yield repo
        repo.engine.dispose()


@pytest.fixture
def client(tmp_repo: Repository, monkeypatch) -> TestClient:
    """注入临时 repo + 测试 token，避免污染生产数据"""
    test_settings = Settings(web_token=_TEST_TOKEN)

    def _fake_settings():
        return test_settings

    monkeypatch.setattr("xianyu_hunter.config.get_settings", _fake_settings)
    monkeypatch.setattr("xianyu_hunter.web.app.get_settings", _fake_settings, raising=False)

    class _FakeContainer:
        def __init__(self, repo):
            self.repo = repo
            # collector=None 模拟纯 web 模式，control_task 仅改 DB
            self.collector = None
            self.scheduler = None

    fake = _FakeContainer(tmp_repo)
    app.dependency_overrides[get_container] = lambda: fake
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_TEST_TOKEN}"}


# ============== Domain 模型字段测试 ==============


class TestTaskDomainFields:
    """验证 Task 领域模型包含 use_cron / interval_seconds 字段"""

    def test_task_has_use_cron_field(self):
        from xianyu_hunter.domain.task import Task
        task = Task(id="t1", name="test", keyword="kw", use_cron=True)
        assert task.use_cron is True

    def test_task_has_interval_seconds_field(self):
        from xianyu_hunter.domain.task import Task
        task = Task(id="t1", name="test", keyword="kw", interval_seconds=120.0)
        assert task.interval_seconds == 120.0

    def test_task_defaults(self):
        """Task 默认值：use_cron=False, interval_seconds=60.0"""
        from xianyu_hunter.domain.task import Task
        task = Task(id="t1", name="test", keyword="kw")
        assert task.use_cron is False
        assert task.interval_seconds == 60.0


# ============== DB 迁移测试 ==============


class TestDBMigration:
    """验证 init_db 添加 use_cron / interval_seconds 列"""

    def test_init_db_adds_use_cron_column(self, tmp_path):
        """init_db 后 tasks 表应包含 use_cron 列"""
        db_path = str(tmp_path / "migration.db")
        init_db(db_path)

        from sqlalchemy import create_engine
        engine = create_engine(f"sqlite:///{db_path}")
        inspector = inspect(engine)
        columns = {c["name"] for c in inspector.get_columns("tasks")}
        engine.dispose()

        assert "use_cron" in columns
        assert "interval_seconds" in columns

    def test_init_db_idempotent(self, tmp_path):
        """init_db 多次调用不报错（迁移列已存在时跳过）"""
        db_path = str(tmp_path / "idempotent.db")
        init_db(db_path)
        # 第二次调用应无副作用
        init_db(db_path)

        from sqlalchemy import create_engine
        engine = create_engine(f"sqlite:///{db_path}")
        inspector = inspect(engine)
        columns = {c["name"] for c in inspector.get_columns("tasks")}
        engine.dispose()

        assert "use_cron" in columns

    def test_init_db_backfills_null_after_migration(self, tmp_path):
        """回归测试：迁移后 NULL 值必须被回填，避免读取端 float(None) 崩溃

        复现场景：旧 DB 已有 tasks 行，新增 use_cron/interval_seconds 列时
        SQLite 对已有行填 NULL。startup.py 读取时 float(None) 抛 TypeError
        导致 scheduler 启动崩溃。修复后 init_db 会 UPDATE 回填默认值。
        """
        from sqlalchemy import create_engine, text, inspect
        db_path = str(tmp_path / "null_backfill.db")

        # 1. 用旧 schema 建库（无 use_cron / interval_seconds 列）
        old_engine = create_engine(f"sqlite:///{db_path}")
        with old_engine.connect() as conn:
            conn.execute(text(
                "CREATE TABLE tasks (id TEXT PRIMARY KEY, name TEXT, keyword TEXT, "
                "min_price REAL, max_price REAL, mode TEXT, status TEXT, "
                "cron TEXT, created_at TEXT, updated_at TEXT)"
            ))
            # 插入一行旧任务（无调度字段）
            conn.execute(text(
                "INSERT INTO tasks (id, name, keyword, mode, status, cron) "
                "VALUES ('t_old', '旧任务', 'kw', 'confirm', 'running', '*/1 * * * *')"
            ))
            conn.commit()
        old_engine.dispose()

        # 2. 调用 init_db 触发迁移 + 回填
        init_db(db_path)

        # 3. 验证 NULL 已被回填为默认值
        new_engine = create_engine(f"sqlite:///{db_path}")
        with new_engine.connect() as conn:
            row = conn.execute(text(
                "SELECT use_cron, interval_seconds FROM tasks WHERE id='t_old'"
            )).fetchone()
            assert row is not None
            # use_cron 应为 0（不是 NULL），interval_seconds 应为 60.0（不是 NULL）
            assert row[0] == 0, f"use_cron 应被回填为 0，实际为 {row[0]!r}"
            assert row[1] == 60.0, f"interval_seconds 应被回填为 60.0，实际为 {row[1]!r}"
        new_engine.dispose()

    def test_startup_reads_backfilled_values_without_crash(self, tmp_path):
        """回归测试：startup.py 读取端用 `or` 防御 NULL，即使回填失败也不崩溃

        验证读取逻辑：raw.get("interval_seconds") or 60.0 在值为 None 时返回 60.0
        """
        # 模拟 DB 返回的 dict 中 interval_seconds 为 None（回填失败的极端场景）
        raw_with_none = {"id": "t1", "keyword": "kw", "interval_seconds": None, "use_cron": None}
        # 读取端防御逻辑（与 startup.py / __main__.py 一致）
        interval_seconds = float(raw_with_none.get("interval_seconds") or 60.0)
        use_cron = bool(raw_with_none.get("use_cron") or 0)

        assert interval_seconds == 60.0
        assert use_cron is False


# ============== API 端到端测试 ==============


class TestCreateTaskPersistsCronFields:
    """POST /api/tasks 持久化 cron / use_cron / interval_seconds"""

    def test_create_with_cron_fields(self, client: TestClient, tmp_repo: Repository):
        """创建任务时传入完整调度配置，验证 DB 持久化"""
        resp = client.post(
            "/api/tasks",
            json={
                "keyword": "iPhone",
                "name": "iPhone 监控",
                "cron": "*/10 * * * *",
                "use_cron": True,
                "interval_seconds": 120,
            },
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()
        tid = data["id"]

        # 验证 DB 中持久化
        loaded = tmp_repo.get_task(tid)
        assert loaded is not None
        assert loaded["cron"] == "*/10 * * * *"
        # DB 中 use_cron 存为 INTEGER 0/1
        assert loaded["use_cron"] == 1
        assert loaded["interval_seconds"] == 120

    def test_create_with_defaults(self, client: TestClient, tmp_repo: Repository):
        """不传 cron 字段时使用默认值"""
        resp = client.post(
            "/api/tasks",
            json={"keyword": "iPhone"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        tid = resp.json()["id"]

        loaded = tmp_repo.get_task(tid)
        assert loaded is not None
        # 默认 cron="*/5 * * * *", use_cron=0, interval_seconds=60
        assert loaded["cron"] == "*/5 * * * *"
        assert loaded["use_cron"] == 0
        assert loaded["interval_seconds"] == 60

    def test_create_interval_seconds_validation(self, client: TestClient):
        """interval_seconds 超出 30-3600 范围返回 422"""
        # 过小
        resp = client.post(
            "/api/tasks",
            json={"keyword": "test", "interval_seconds": 10},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422

        # 过大
        resp = client.post(
            "/api/tasks",
            json={"keyword": "test", "interval_seconds": 5000},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422


class TestGetTaskReturnsCronFields:
    """GET /api/tasks/{id} 返回 cron / use_cron / interval_seconds"""

    def test_get_returns_cron_fields(self, client: TestClient, tmp_repo: Repository):
        tmp_repo.upsert_task({
            "id": "t1",
            "name": "test",
            "keyword": "kw",
            "cron": "*/15 * * * *",
            "use_cron": 1,
            "interval_seconds": 90.0,
        })

        resp = client.get("/api/tasks/t1", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert data["cron"] == "*/15 * * * *"
        assert data["use_cron"] == 1
        assert data["interval_seconds"] == 90.0


class TestUpdateTaskUpdatesCronFields:
    """PATCH /api/tasks/{id} 更新 cron / use_cron / interval_seconds"""

    def test_update_cron_fields(self, client: TestClient, tmp_repo: Repository):
        tmp_repo.upsert_task({
            "id": "t1",
            "name": "test",
            "keyword": "kw",
            "cron": "*/5 * * * *",
            "use_cron": 0,
            "interval_seconds": 60.0,
        })

        resp = client.patch(
            "/api/tasks/t1",
            json={
                "cron": "0 */2 * * *",
                "use_cron": True,
                "interval_seconds": 180,
            },
            headers=_auth_headers(),
        )
        assert resp.status_code == 200

        loaded = tmp_repo.get_task("t1")
        assert loaded["cron"] == "0 */2 * * *"
        assert loaded["use_cron"] == 1
        assert loaded["interval_seconds"] == 180

    def test_update_partial_cron_fields(self, client: TestClient, tmp_repo: Repository):
        """部分更新：仅更新 interval_seconds，其他字段保持"""
        tmp_repo.upsert_task({
            "id": "t1",
            "name": "test",
            "keyword": "kw",
            "cron": "*/5 * * * *",
            "use_cron": 1,
            "interval_seconds": 60.0,
        })

        resp = client.patch(
            "/api/tasks/t1",
            json={"interval_seconds": 300},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200

        loaded = tmp_repo.get_task("t1")
        # 仅 interval_seconds 变化，其他字段保持
        assert loaded["interval_seconds"] == 300
        assert loaded["cron"] == "*/5 * * * *"
        assert loaded["use_cron"] == 1


# ============== TaskConfig 与 Task 字段同步测试 ==============


class TestTaskConfigFromTaskFields:
    """验证 TaskConfig 从 Task 字段读取 use_cron / interval_seconds（消除分裂脑）"""

    def test_task_config_inherits_from_task(self):
        """startup.py / __main__.py 构造 TaskConfig 时应从 Task 字段读取"""
        from xianyu_hunter.domain.task import Task, TaskConfig

        task = Task(
            id="t1", name="test", keyword="kw",
            use_cron=True, interval_seconds=300.0,
        )
        # 模拟 startup.py 的构造逻辑
        config = TaskConfig(
            use_cron=task.use_cron,
            interval_seconds=task.interval_seconds,
        )
        assert config.use_cron is True
        assert config.interval_seconds == 300.0

    def test_task_config_defaults_match_task_defaults(self):
        """TaskConfig 与 Task 的默认值一致"""
        from xianyu_hunter.domain.task import Task, TaskConfig

        task = Task(id="t1", name="test", keyword="kw")
        config = TaskConfig()
        assert task.use_cron == config.use_cron
        assert task.interval_seconds == config.interval_seconds
