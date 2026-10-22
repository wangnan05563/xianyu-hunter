"""T02642 订单写操作后统计缓存主动失效

覆盖：
1. 缓存工具按前缀失效，且不误伤无关缓存
2. 订单状态变更 / 删除后，/api/stats、/api/stats/today、/api/stats/trend 立即反映新数据
3. takeover / confirm / cancel 写路径均触发失效
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from xianyu_hunter.config import Settings
from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.web import cache
from xianyu_hunter.web.app import app
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.routes import api_orders

_TOKEN = "test-token-order-cache-t02642"


@pytest.fixture
def tmp_repo() -> Repository:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        repo = Repository(str(Path(d) / "test.db"))
        yield repo
        repo.engine.dispose()


@pytest.fixture
def client(tmp_repo: Repository, monkeypatch) -> TestClient:
    test_settings = Settings(web_token=_TOKEN)

    def _fake_settings():
        return test_settings

    monkeypatch.setattr("xianyu_hunter.config.get_settings", _fake_settings)
    monkeypatch.setattr("xianyu_hunter.web.app.get_settings", _fake_settings, raising=False)

    class _FakeContainer:
        def __init__(self, repo):
            self.repo = repo

            class _EmptyNotifierHub:
                notifiers = []

            self.notifier_hub = _EmptyNotifierHub()

            class _EmptyCollector:
                browser = None

            self.collector = _EmptyCollector()

    fake = _FakeContainer(tmp_repo)
    app.dependency_overrides[get_container] = lambda: fake
    cache.invalidate_stats_cache()
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()
    cache.invalidate_stats_cache()


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {_TOKEN}"}


def _seed_order(repo: Repository, order_id: str, status: str) -> None:
    repo.upsert_order({
        "id": order_id,
        "task_id": "t1",
        "item_id": f"item_{order_id}",
        "price": 100.0,
        "status": status,
    })


def test_invalidate_order_stats_cache_only_touches_order_family() -> None:
    with cache._cache_lock:
        cache._cache_store.clear()
        cache._cache_store[("f", "trend:orders:24:all")] = (0.0, {})
        cache._cache_store[("f", "trend:events:24:all")] = (0.0, {})
        cache._cache_store[("g", "stats_today")] = (0.0, {})
        cache._cache_store[("g", "stats_overview")] = (0.0, {})
        cache._cache_store[("h", "kpi:7")] = (0.0, {})
        cache._cache_store[("i", "eval_funnel:7")] = (0.0, {})
        cache._cache_store[("j", "hist:20:all")] = (0.0, {})
        cache._cache_store[("k", ("args",), ())] = (0.0, {})

    removed = cache.invalidate_order_stats_cache()

    assert removed == 5
    assert set(cache._cache_store) == {
        ("i", "eval_funnel:7"),
        ("j", "hist:20:all"),
        ("k", ("args",), ()),
    }


def test_status_write_refreshes_overview_and_today(client: TestClient, tmp_repo: Repository) -> None:
    _seed_order(tmp_repo, "o1", "pending_pay")

    first = client.get("/api/stats", headers=_auth()).json()
    assert first["orders"] == {"total": 1, "succeeded": 0, "failed": 0, "pending": 1}
    today = client.get("/api/stats/today", headers=_auth()).json()
    assert today["today"]["orders"] == 1 and today["today"]["succeeded"] == 0

    resp = client.patch("/api/orders/o1/status", json={"status": "succeeded"}, headers=_auth())
    assert resp.status_code == 200 and resp.json()["changed"] is True

    # 修复前这两个响应会命中 300s 缓存，仍是写前的 0 succeeded
    assert client.get("/api/stats", headers=_auth()).json()["orders"] == {
        "total": 1, "succeeded": 1, "failed": 0, "pending": 0,
    }
    assert client.get("/api/stats/today", headers=_auth()).json()["today"]["succeeded"] == 1


def test_delete_refreshes_overview_and_trend(client: TestClient, tmp_repo: Repository) -> None:
    _seed_order(tmp_repo, "o1", "succeeded")
    params = {"metric": "orders", "range_hours": 24}

    assert client.get("/api/stats/trend", params=params, headers=_auth()).json()["summary"]["current"] == 1
    assert client.get("/api/stats", headers=_auth()).json()["orders"]["total"] == 1

    resp = client.delete("/api/orders/o1", headers=_auth())
    assert resp.status_code == 200 and resp.json()["deleted"] == 1

    assert client.get("/api/stats", headers=_auth()).json()["orders"]["total"] == 0
    assert client.get("/api/stats/trend", params=params, headers=_auth()).json()["summary"]["current"] == 0


def test_takeover_write_paths_invalidate_cache(client: TestClient, tmp_repo: Repository, monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        "xianyu_hunter.web.routes.api_orders.invalidate_order_stats_cache",
        lambda: calls.append("x"),
    )

    _seed_order(tmp_repo, "o1", "pending_pay")
    assert client.post("/api/orders/o1/takeover", headers=_auth()).status_code == 200
    assert len(calls) == 1

    assert client.post("/api/orders/o1/takeover/confirm", headers=_auth()).status_code == 200
    assert len(calls) == 2

    _seed_order(tmp_repo, "o2", "takeover_pending")
    assert client.post("/api/orders/o2/takeover/cancel", headers=_auth()).status_code == 200
    assert len(calls) == 3

    _seed_order(tmp_repo, "o3", "pending_pay")
    assert client.patch("/api/orders/o3/status", json={"status": "cancelled"}, headers=_auth()).status_code == 200
    assert len(calls) == 4

    assert client.delete("/api/orders/o3", headers=_auth()).status_code == 200
    assert len(calls) == 5


@pytest.mark.asyncio
async def test_manual_takeover_invalidates_cache(monkeypatch) -> None:
    """手动抢单会写订单（成功单或失败单），同样需要失效统计缓存"""
    calls: list[str] = []

    class _Outcome:
        value = "success"

    class _Order:
        order_no = "n1"
        price = 100.0
        status = SimpleNamespace(value="pending_pay")

    class _Result:
        outcome = _Outcome()
        error = None
        order = _Order()

    fake = SimpleNamespace(
        repo=MagicMock(),
        buyer=SimpleNamespace(buy=AsyncMock(return_value=_Result())),
        browser_lock=SimpleNamespace(acquire=AsyncMock(return_value=True), release=MagicMock()),
    )

    monkeypatch.setattr(api_orders, "_ensure_takeover_prerequisites", AsyncMock())
    monkeypatch.setattr(api_orders, "_resolve_takeover_item", lambda *a, **k: (100.0, "t1"))
    monkeypatch.setattr(api_orders, "_check_existing_takeover_order", lambda *a, **k: None)
    monkeypatch.setattr(api_orders, "invalidate_order_stats_cache", lambda: calls.append("x"))
    monkeypatch.setattr(
        "xianyu_hunter.web.services.cookie_runtime_sync.inject_cookie_store_to_worker_browser",
        AsyncMock(),
    )

    request = SimpleNamespace(state=SimpleNamespace(user_id="default"))
    resp = await api_orders.manual_takeover(
        {"item_id": "i1", "task_id": "t1"}, request, fake,
    )

    assert resp["ok"] is True
    assert calls == ["x"]
