"""P1-5 数据导出 API 单元测试"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from xianyu_hunter.config import get_settings
from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.web.app import app
from xianyu_hunter.web.deps import get_container


_TEST_TOKEN = "test-token-for-export-api"


@pytest.fixture
def tmp_repo() -> Repository:
    """使用临时数据库"""
    import tempfile
    from pathlib import Path
    # 清除 get_settings 缓存，设置测试 token
    get_settings.cache_clear()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db_path = str(Path(d) / "test.db")
        repo = Repository(db_path)
        yield repo
        repo.engine.dispose()
        get_settings.cache_clear()


@pytest.fixture
def client(tmp_repo: Repository, monkeypatch) -> TestClient:
    """构造 TestClient，注入临时 repository 和测试 token"""
    # 直接 patch get_settings 返回带测试 token 的实例，
    # 避免认证中间件读取真实 .env 中的 token
    from xianyu_hunter.config import Settings
    test_settings = Settings(web_token=_TEST_TOKEN)
    monkeypatch.setattr(
        "xianyu_hunter.config.get_settings",
        lambda: test_settings,
    )
    # app.py dispatch 内部 from xianyu_hunter.config import get_settings
    # 所以也要 patch app 模块内的引用（虽然 dispatch 内部是局部导入，但保险起见）
    monkeypatch.setattr(
        "xianyu_hunter.web.app.get_settings",
        lambda: test_settings,
        raising=False,
    )

    class _FakeContainer:
        def __init__(self, repo):
            self.repo = repo
    fake = _FakeContainer(tmp_repo)
    app.dependency_overrides[get_container] = lambda: fake
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _auth_headers() -> dict[str, str]:
    """返回带 Bearer token 的请求头"""
    return {"Authorization": f"Bearer {_TEST_TOKEN}"}


def _seed_data(repo: Repository) -> None:
    """填充测试数据：1 个任务 + 2 个商品 + 1 个评估 + 1 个订单 + 2 个事件"""
    now = datetime.now(timezone.utc)
    repo.upsert_task({
        "id": "t1", "name": "测试任务", "keyword": "iphone",
        "mode": "confirm", "cron": "*/5 * * * *",
    })
    repo.batch_upsert_items([
        {
            "id": "i1", "task_id": "t1", "title": "iPhone 13",
            "price": 3999.0, "seller_id": "s1", "first_seen": now,
        },
        {
            "id": "i2", "task_id": "t1", "title": "iPhone 14",
            "price": 4999.0, "seller_id": "s2", "first_seen": now - timedelta(days=1),
        },
    ])
    repo.save_evaluation({
        "item_id": "i1", "seller_id": "s1", "score": 80,
        "risk_level": "low", "created_at": now,
    })
    repo.upsert_order({
        "id": "o1", "task_id": "t1", "item_id": "i1", "seller_id": "s1",
        "price": 3999.0, "status": "paid", "created_at": now,
    })
    # 插入事件
    from xianyu_hunter.infra.db_models import EventRow
    with repo.engine.begin() as conn:
        conn.execute(EventRow.__table__.insert().values(
            type="order", task_id="t1", item_id="i1", stage="buy",
            level="info", message="订单已支付", created_at=now,
        ))
        conn.execute(EventRow.__table__.insert().values(
            type="system", task_id=None, item_id=None, stage="startup",
            level="info", message="服务启动", created_at=now,
        ))


def test_export_datasets_list(client: TestClient) -> None:
    """列出可导出数据集"""
    resp = client.get("/api/export", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    keys = {d["key"] for d in data["datasets"]}
    assert keys == {"items", "evaluations", "orders", "events"}


def test_export_items_csv(client: TestClient, tmp_repo: Repository) -> None:
    """导出商品 CSV"""
    _seed_data(tmp_repo)
    resp = client.get("/api/export/items", headers=_auth_headers())
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    # 含 BOM 头
    content = resp.content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    # 表头 + 2 条数据
    assert len(rows) == 3
    assert "id" in rows[0]
    assert "title" in rows[0]
    titles = {r[rows[0].index("title")] for r in rows[1:]}
    assert "iPhone 13" in titles


def test_export_items_filter_by_task(client: TestClient, tmp_repo: Repository) -> None:
    """按 task_id 过滤商品"""
    _seed_data(tmp_repo)
    # 再插一个不属 t1 的商品
    now = datetime.now(timezone.utc)
    tmp_repo.batch_upsert_items([{
        "id": "i3", "task_id": "t2", "title": "Other",
        "price": 100.0, "first_seen": now,
    }])
    resp = client.get("/api/export/items", params={"task_id": "t1"}, headers=_auth_headers())
    assert resp.status_code == 200
    content = resp.content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    # 表头 + 2 条数据（i1, i2）
    assert len(rows) == 3


def test_export_orders_csv(client: TestClient, tmp_repo: Repository) -> None:
    """导出订单 CSV"""
    _seed_data(tmp_repo)
    resp = client.get("/api/export/orders", headers=_auth_headers())
    assert resp.status_code == 200
    content = resp.content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    assert len(rows) == 2  # 表头 + 1 条


def test_export_events_csv(client: TestClient, tmp_repo: Repository) -> None:
    """导出事件 CSV"""
    _seed_data(tmp_repo)
    resp = client.get("/api/export/events", headers=_auth_headers())
    assert resp.status_code == 200
    content = resp.content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    # 表头 + 2 条事件
    assert len(rows) == 3


def test_export_evaluations_csv(client: TestClient, tmp_repo: Repository) -> None:
    """导出评估 CSV"""
    _seed_data(tmp_repo)
    resp = client.get("/api/export/evaluations", headers=_auth_headers())
    assert resp.status_code == 200
    content = resp.content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    # 表头 + 1 条评估
    assert len(rows) == 2


def test_export_invalid_dataset_returns_400(client: TestClient) -> None:
    """未知数据集返回 400"""
    resp = client.get("/api/export/unknown", headers=_auth_headers())
    assert resp.status_code == 400


def test_export_items_time_filter(client: TestClient, tmp_repo: Repository) -> None:
    """时间范围过滤"""
    _seed_data(tmp_repo)
    # 只查最近 1 小时
    start = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    resp = client.get("/api/export/items", params={"start": start}, headers=_auth_headers())
    assert resp.status_code == 200
    content = resp.content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    # i1 是 now，i2 是 1 天前，应只返回 i1
    assert len(rows) == 2  # 表头 + i1
