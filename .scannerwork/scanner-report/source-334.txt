"""list_links API 端点 sold_filter 参数测试

回归测试：Task 5 为 list_links 端点新增 sold_filter 参数，
通过 JOIN items 表下推 SQL 过滤，支持 all/onsale/sold 三种模式。
seller 类型行不受 sold_filter 影响（task_links.link_key 与 items.id 仅在
link_type='item' 时等价）。
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


_TEST_TOKEN = "test-token-list-links-sold-filter"


@pytest.fixture
def tmp_repo() -> Repository:
    """使用临时数据库"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db_path = str(Path(d) / "test.db")
        repo = Repository(db_path)
        yield repo
        repo.engine.dispose()


@pytest.fixture
def client(tmp_repo: Repository, monkeypatch) -> TestClient:
    """构造 TestClient，注入临时 repository 和测试 token"""
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


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_TEST_TOKEN}"}


def _seed_item(repo: Repository, item_id: str, title: str, *, is_sold: bool = False) -> None:
    """写入 items 表并设置 is_sold 状态

    为什么先 upsert_item 再按需 mark_sold：upsert_item 默认 is_sold=0，
    避免在 upsert 时直接传 is_sold 字段触发 on_conflict 行为差异。
    """
    repo.upsert_item({
        "id": item_id,
        "task_id": "t1",
        "title": title,
        "price": 100.0,
        "is_sold": 0,
    })
    if is_sold:
        repo.mark_sold(item_id)


def _seed_link(repo: Repository, item_id: str, title: str, *, link_type: str = "item") -> None:
    """写入 task_links 表（display 中 is_sold 默认 False，由 enrich 从 items 表覆盖）"""
    repo.upsert_task_link(
        task_id="t1",
        link_type=link_type,
        link_key=item_id,
        display={
            "title": title,
            "price": 100.0,
            "is_sold": False,
        },
        source="auto",
    )


def test_list_links_sold_filter_all_returns_all_items(client: TestClient, tmp_repo: Repository) -> None:
    """sold_filter=all：返回所有 item 行（在售 + 已售）

    验证默认行为与未传 sold_filter 一致，不引入性能回归。
    """
    tmp_repo.upsert_task({"id": "t1", "name": "测试任务", "keyword": "DDR4"})

    _seed_item(tmp_repo, "item_onsale_1", "DDR4 在售商品 1", is_sold=False)
    _seed_item(tmp_repo, "item_sold_1", "DDR4 已售商品 1", is_sold=True)
    _seed_link(tmp_repo, "item_onsale_1", "DDR4 在售商品 1")
    _seed_link(tmp_repo, "item_sold_1", "DDR4 已售商品 1")

    resp = client.get(
        "/api/tasks/t1/links",
        params={"sold_filter": "all"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    keys = {item["link_key"] for item in data["items"]}
    assert keys == {"item_onsale_1", "item_sold_1"}, \
        f"sold_filter=all 应返回所有 item 行，但得到 {keys}"


def test_list_links_sold_filter_onsale_excludes_sold(client: TestClient, tmp_repo: Repository) -> None:
    """sold_filter=onsale：仅返回 items.is_sold=0 的 item 行

    SQL 下推 JOIN items 表 WHERE is_sold=0，过滤掉已售商品。
    """
    tmp_repo.upsert_task({"id": "t1", "name": "测试任务", "keyword": "DDR4"})

    _seed_item(tmp_repo, "item_onsale_1", "DDR4 在售商品 1", is_sold=False)
    _seed_item(tmp_repo, "item_onsale_2", "DDR4 在售商品 2", is_sold=False)
    _seed_item(tmp_repo, "item_sold_1", "DDR4 已售商品 1", is_sold=True)
    _seed_link(tmp_repo, "item_onsale_1", "DDR4 在售商品 1")
    _seed_link(tmp_repo, "item_onsale_2", "DDR4 在售商品 2")
    _seed_link(tmp_repo, "item_sold_1", "DDR4 已售商品 1")

    resp = client.get(
        "/api/tasks/t1/links",
        params={"sold_filter": "onsale"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    keys = {item["link_key"] for item in data["items"]}
    assert keys == {"item_onsale_1", "item_onsale_2"}, \
        f"sold_filter=onsale 应仅返回在售 item，但得到 {keys}"


def test_list_links_sold_filter_sold_excludes_onsale(client: TestClient, tmp_repo: Repository) -> None:
    """sold_filter=sold：仅返回 items.is_sold=1 的 item 行

    SQL 下推 JOIN items 表 WHERE is_sold=1，过滤掉在售商品。
    """
    tmp_repo.upsert_task({"id": "t1", "name": "测试任务", "keyword": "DDR4"})

    _seed_item(tmp_repo, "item_onsale_1", "DDR4 在售商品 1", is_sold=False)
    _seed_item(tmp_repo, "item_sold_1", "DDR4 已售商品 1", is_sold=True)
    _seed_item(tmp_repo, "item_sold_2", "DDR4 已售商品 2", is_sold=True)
    _seed_link(tmp_repo, "item_onsale_1", "DDR4 在售商品 1")
    _seed_link(tmp_repo, "item_sold_1", "DDR4 已售商品 1")
    _seed_link(tmp_repo, "item_sold_2", "DDR4 已售商品 2")

    resp = client.get(
        "/api/tasks/t1/links",
        params={"sold_filter": "sold"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    keys = {item["link_key"] for item in data["items"]}
    assert keys == {"item_sold_1", "item_sold_2"}, \
        f"sold_filter=sold 应仅返回已售 item，但得到 {keys}"


def test_list_links_sold_filter_preserves_seller_rows(client: TestClient, tmp_repo: Repository) -> None:
    """sold_filter=onsale/sold 时 seller 类型行应保留

    为什么 seller 行必须保留：task_links.link_key 与 items.id 仅在 link_type='item'
    时等价，seller 行的 link_key 是 seller_id，JOIN items 不应排除 seller 行。
    使用 OUTER JOIN + WHERE 限定保证 seller 行在 onsale/sold 过滤下仍能保留。
    """
    tmp_repo.upsert_task({"id": "t1", "name": "测试任务", "keyword": "DDR4"})

    _seed_item(tmp_repo, "item_sold_1", "DDR4 已售商品 1", is_sold=True)
    _seed_link(tmp_repo, "item_sold_1", "DDR4 已售商品 1")
    # seller 行：link_key 是 seller_id，不在 items 表中
    _seed_link(tmp_repo, "seller_001", "DDR4 卖家店铺", link_type="seller")

    # sold_filter=onsale：item_sold_1 应被排除，seller 行应保留
    resp = client.get(
        "/api/tasks/t1/links",
        params={"sold_filter": "onsale"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    by_type = {item["link_key"]: item["link_type"] for item in data["items"]}
    assert "seller_001" in by_type, \
        f"sold_filter=onsale 应保留 seller 行，但得到 {by_type}"
    assert "item_sold_1" not in by_type, \
        f"sold_filter=onsale 应排除已售 item，但得到 {by_type}"

    # sold_filter=sold：item_sold_1 应保留，seller 行也应保留
    resp = client.get(
        "/api/tasks/t1/links",
        params={"sold_filter": "sold"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    by_type = {item["link_key"]: item["link_type"] for item in data["items"]}
    assert "seller_001" in by_type, \
        f"sold_filter=sold 应保留 seller 行，但得到 {by_type}"
    assert "item_sold_1" in by_type, \
        f"sold_filter=sold 应保留已售 item，但得到 {by_type}"


def test_list_links_sold_filter_default_is_all(client: TestClient, tmp_repo: Repository) -> None:
    """不传 sold_filter 时默认 all，行为与之前一致（向后兼容）"""
    tmp_repo.upsert_task({"id": "t1", "name": "测试任务", "keyword": "DDR4"})

    _seed_item(tmp_repo, "item_onsale_1", "DDR4 在售商品 1", is_sold=False)
    _seed_item(tmp_repo, "item_sold_1", "DDR4 已售商品 1", is_sold=True)
    _seed_link(tmp_repo, "item_onsale_1", "DDR4 在售商品 1")
    _seed_link(tmp_repo, "item_sold_1", "DDR4 已售商品 1")

    # 不传 sold_filter
    resp = client.get("/api/tasks/t1/links", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    keys = {item["link_key"] for item in data["items"]}
    assert keys == {"item_onsale_1", "item_sold_1"}, \
        f"默认 sold_filter=all 应返回所有 item，但得到 {keys}"


def test_list_links_sold_filter_invalid_value_rejected(client: TestClient, tmp_repo: Repository) -> None:
    """sold_filter 非法值应被 FastAPI pattern 校验拒绝（422）"""
    tmp_repo.upsert_task({"id": "t1", "name": "测试任务", "keyword": "DDR4"})

    resp = client.get(
        "/api/tasks/t1/links",
        params={"sold_filter": "invalid"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 422, \
        f"sold_filter=invalid 应被 pattern 校验拒绝（422），但得到 {resp.status_code}"
