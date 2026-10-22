"""抢单记录「演练单」筛选（T02673）

演练模式开启期间 orders 表里 real/dry_run 混排，高频用户无法只看（或避开）
演练记录。type 参数走独立白名单（real|dry_run），不挤占 status——dry_run
不是订单状态，混进 ?status= 会被深链白名单拒绝。

钉住：
1. type=dry_run / real 各自只命中本类型的行，total 与列表同源；
2. 非法 type 422 而非静默降级（与 status/sort_by 同一口径）；
3. status 与 type 可组合；
4. 四张状态卡是全量口径（count_orders_by_status 不受 type 影响）——
   这是文档化语义（卡片提示词 STATS_SCOPE 已说明），有意钉住防漂移。

按前端实际调用的端点打真实 FastAPI 应用，与 test_order_stats_and_notif_batch.py 同口径。
"""
from __future__ import annotations

from datetime import datetime

import pytest


class _ContainerShim:
    def __init__(self, repo):
        self.repo = repo


@pytest.fixture
def api(tmp_path):
    from fastapi.testclient import TestClient

    from xianyu_hunter.config import get_settings
    from xianyu_hunter.infra.repository import Repository
    from xianyu_hunter.web.app import create_app
    from xianyu_hunter.web.deps import get_container

    repo = Repository(db_path=str(tmp_path / "t02673.db"))
    app = create_app()
    app.dependency_overrides[get_container] = lambda: _ContainerShim(repo)

    client = TestClient(app)
    client.cookies.set("xh_token", get_settings().web_token)
    return client, repo


def _mk(repo, oid: str, order_type: str, status: str = "succeeded") -> None:
    repo.upsert_order({
        "id": oid,
        "task_id": "t1",
        "item_id": f"i_{oid}",
        "price": 100.0,
        "status": status,
        "type": order_type,
        "created_at": datetime(2026, 10, 1, 10),
    })


def test_type_filter_splits_dry_run_and_real(api) -> None:
    client, repo = api
    _mk(repo, "r1", "real")
    _mk(repo, "r2", "real")
    _mk(repo, "d1", "dry_run")
    _mk(repo, "d2", "dry_run", status="failed")

    dry = client.get("/api/orders", params={"type": "dry_run"}).json()
    assert sorted(o["id"] for o in dry["items"]) == ["d1", "d2"]
    assert dry["total"] == 2

    real = client.get("/api/orders", params={"type": "real"}).json()
    assert sorted(o["id"] for o in real["items"]) == ["r1", "r2"]
    assert real["total"] == 2

    both = client.get("/api/orders").json()
    assert both["total"] == 4


def test_type_combines_with_status_filter(api) -> None:
    client, repo = api
    _mk(repo, "d1", "dry_run", status="failed")
    _mk(repo, "d2", "dry_run", status="succeeded")
    _mk(repo, "r1", "real", status="failed")

    res = client.get("/api/orders", params={"type": "dry_run", "status": "failed"}).json()
    assert [o["id"] for o in res["items"]] == ["d1"]
    assert res["total"] == 1


def test_type_whitelist_rejects_unknown(api) -> None:
    client, repo = api
    _mk(repo, "r1", "real")
    for bad in ("fake", "REAL", "real; --"):
        res = client.get("/api/orders", params={"type": bad})
        assert res.status_code == 422, bad
    # 非法参数打完，默认查询照常
    assert client.get("/api/orders").json()["total"] == 1


def test_stats_cards_stay_full_scope_under_type_filter(api) -> None:
    """状态卡是全量口径：演练筛选只影响列表与 total，不重算卡片（文档化语义）"""
    client, repo = api
    _mk(repo, "r1", "real")
    _mk(repo, "d1", "dry_run")

    res = client.get("/api/orders", params={"type": "dry_run"}).json()
    assert res["total"] == 1
    assert res["stats"]["total"] == 2
