"""抢单记录列表服务端排序（T02677）

原先 list_orders 固定 created_at desc，前端时间列没有排序入口：
接管场景下「找最新的待接管单」只能翻页人肉找。

钉住：
1. sort_by/sort_dir 白名单（created_at|confirmed_at|price × asc|desc），
   非法值 422 而非静默降级——与 status 筛选同一口径；
2. 白名单真正落在 SQL 列对象上（列名不拼接用户输入）；
3. 默认行为不变：不带参数 = created_at desc；
4. confirmed_at 含 NULL（未确认的行）时 asc 把 NULL 排最前（SQLite 语义），
   前端「找最早确认的单」不会被 NULL 行淹没。

按前端实际调用的端点打真实 FastAPI 应用，只把数据库换成临时 SQLite，
与 tests/test_order_stats_and_notif_batch.py 同一口径。
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

    repo = Repository(db_path=str(tmp_path / "t02677.db"))
    app = create_app()
    app.dependency_overrides[get_container] = lambda: _ContainerShim(repo)

    client = TestClient(app)
    client.cookies.set("xh_token", get_settings().web_token)
    return client, repo


def _mk(repo, oid: str, *, created_at: datetime, confirmed_at: datetime | None = None,
        price: float = 100.0) -> None:
    repo.upsert_order({
        "id": oid,
        "task_id": "t1",
        "item_id": f"i_{oid}",
        "price": price,
        "status": "succeeded" if confirmed_at else "pending_pay",
        "created_at": created_at,
        "confirmed_at": confirmed_at,
    })


def test_default_is_created_at_desc(api) -> None:
    client, repo = api
    _mk(repo, "o1", created_at=datetime(2026, 10, 1, 10))
    _mk(repo, "o2", created_at=datetime(2026, 10, 3, 10))
    _mk(repo, "o3", created_at=datetime(2026, 10, 2, 10))

    res = client.get("/api/orders").json()
    assert [o["id"] for o in res["items"]] == ["o2", "o3", "o1"]


def test_created_at_asc(api) -> None:
    client, repo = api
    _mk(repo, "o1", created_at=datetime(2026, 10, 1, 10))
    _mk(repo, "o2", created_at=datetime(2026, 10, 3, 10))
    _mk(repo, "o3", created_at=datetime(2026, 10, 2, 10))

    res = client.get("/api/orders", params={"sort_by": "created_at", "sort_dir": "asc"}).json()
    assert [o["id"] for o in res["items"]] == ["o1", "o3", "o2"]


def test_confirmed_at_sorts_and_nulls_lead_asc(api) -> None:
    client, repo = api
    _mk(repo, "o1", created_at=datetime(2026, 10, 1, 10), confirmed_at=datetime(2026, 10, 2, 9))
    _mk(repo, "o2", created_at=datetime(2026, 10, 1, 11))  # 未确认：NULL
    _mk(repo, "o3", created_at=datetime(2026, 10, 1, 12), confirmed_at=datetime(2026, 10, 2, 8))

    asc = client.get("/api/orders", params={"sort_by": "confirmed_at", "sort_dir": "asc"}).json()
    assert [o["id"] for o in asc["items"]] == ["o2", "o3", "o1"]
    desc = client.get("/api/orders", params={"sort_by": "confirmed_at", "sort_dir": "desc"}).json()
    assert [o["id"] for o in desc["items"]] == ["o1", "o3", "o2"]


def test_price_sort(api) -> None:
    client, repo = api
    _mk(repo, "o1", created_at=datetime(2026, 10, 1, 10), price=50.0)
    _mk(repo, "o2", created_at=datetime(2026, 10, 1, 11), price=200.0)
    _mk(repo, "o3", created_at=datetime(2026, 10, 1, 12), price=99.0)

    res = client.get("/api/orders", params={"sort_by": "price", "sort_dir": "asc"}).json()
    assert [o["id"] for o in res["items"]] == ["o1", "o3", "o2"]


def test_sort_whitelist_rejects_unknown_column_and_dir(api) -> None:
    client, repo = api
    _mk(repo, "o1", created_at=datetime(2026, 10, 1, 10))
    # 非法列名 422：白名单防注入的口径与 status 一致，不静默降级
    assert client.get("/api/orders", params={"sort_by": "user_id; DROP TABLE"}).status_code == 422
    assert client.get("/api/orders", params={"sort_by": "password_hash"}).status_code == 422
    assert client.get("/api/orders", params={"sort_dir": "ASC; --"}).status_code == 422
    assert client.get("/api/orders", params={"sort_dir": "descending"}).status_code == 422
    # 回归保护：非法参数打完，表还在、默认查询照常
    assert client.get("/api/orders").json()["total"] == 1
