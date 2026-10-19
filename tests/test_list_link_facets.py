"""GET /api/tasks/{id}/links/facets 测试（T02566 §2.3-3）

回归点：商品列表页的地区/品牌下拉原先由前端从「当前页 items」提取，
选中一个地区后选项集只剩该地区（换地区必须先清空，自锁死），翻页后选项集还会变。
facets 接口返回该任务 item 行的全量 DISTINCT，不受分页与当前筛选影响。
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


_TEST_TOKEN = "test-token-list-link-facets"


@pytest.fixture
def tmp_repo() -> Repository:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        repo = Repository(str(Path(d) / "test.db"))
        yield repo
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

    app.dependency_overrides[get_container] = lambda: _FakeContainer(tmp_repo)
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_TEST_TOKEN}"}


def _seed(repo: Repository, key: str, *, region: str | None, brand: str | None,
          link_type: str = "item") -> None:
    display: dict = {"title": f"DDR4 内存 {key}", "price": 100.0}
    if region:
        display["region"] = region
    if brand:
        display["brand"] = brand
    repo.upsert_task_link(task_id="t1", link_type=link_type, link_key=key,
                          display=display, source="auto")


def _seed_task(repo: Repository) -> None:
    repo.upsert_task({"id": "t1", "name": "测试任务", "keyword": "DDR4"})


def test_facets_returns_full_distinct_across_pages(client: TestClient, tmp_repo: Repository) -> None:
    """跨页数据一次返回：3 个地区 / 2 个品牌的 DISTINCT 全集，与 limit 无关"""
    _seed_task(tmp_repo)
    _seed(tmp_repo, "i1", region="武汉", brand="金士顿")
    _seed(tmp_repo, "i2", region="上海", brand="三星")
    _seed(tmp_repo, "i3", region="武汉", brand="金士顿")
    _seed(tmp_repo, "i4", region="广州", brand=None)

    resp = client.get("/api/tasks/t1/links/facets", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    # 去重：武汉出现两次只算一个；None/缺失不进选项（按 sorted 稳定输出，不断言中文具体序）
    assert set(data["regions"]) == {"上海", "武汉", "广州"}, data["regions"]
    assert data["regions"] == sorted(data["regions"]), data["regions"]
    assert set(data["brands"]) == {"三星", "金士顿"}, data["brands"]


def test_facets_not_shrunk_by_current_filter(client: TestClient, tmp_repo: Repository) -> None:
    """核心修复点：选了地区后仍能选到别的地区（旧实现在前端只剩当前筛选项）

    facets 只按 task 全量取 DISTINCT，不接当前 keyword/region/brand，
    因此「先筛武汉再换上海」不需要先清空。
    """
    _seed_task(tmp_repo)
    _seed(tmp_repo, "i1", region="武汉", brand="金士顿")
    _seed(tmp_repo, "i2", region="上海", brand="三星")

    # 先按 region=武汉 过滤列表（列表只剩 1 行）
    listed = client.get("/api/tasks/t1/links", params={"type": "item", "region": "武汉"},
                        headers=_auth_headers()).json()
    assert {i["link_key"] for i in listed["items"]} == {"i1"}
    # 但候选项仍是全量：上海依旧可选
    facets = client.get("/api/tasks/t1/links/facets", headers=_auth_headers()).json()
    assert "上海" in facets["regions"], facets["regions"]


def test_facets_ignores_seller_rows(client: TestClient, tmp_repo: Repository) -> None:
    """seller 行不参与地区/品牌维度（其 display 无 region/brand 语义）"""
    _seed_task(tmp_repo)
    _seed(tmp_repo, "i1", region="武汉", brand="金士顿")
    _seed(tmp_repo, "seller_001", region=None, brand=None, link_type="seller")

    data = client.get("/api/tasks/t1/links/facets", headers=_auth_headers()).json()
    assert data["regions"] == ["武汉"], data
    assert data["brands"] == ["金士顿"], data


def test_facets_seller_type_returns_empty(client: TestClient, tmp_repo: Repository) -> None:
    """显式 type=seller 时返回空维度（不是 404，前端可安全调用）"""
    _seed_task(tmp_repo)
    _seed(tmp_repo, "seller_001", region=None, brand=None, link_type="seller")

    data = client.get("/api/tasks/t1/links/facets", params={"type": "seller"},
                      headers=_auth_headers()).json()
    assert data == {"task_id": "t1", "regions": [], "brands": []}


def test_facets_unknown_task_404(client: TestClient, tmp_repo: Repository) -> None:
    resp = client.get("/api/tasks/t9999/links/facets", headers=_auth_headers())
    assert resp.status_code == 404


def test_facets_invalid_type_400(client: TestClient, tmp_repo: Repository) -> None:
    _seed_task(tmp_repo)
    resp = client.get("/api/tasks/t1/links/facets", params={"type": "bogus"},
                      headers=_auth_headers())
    assert resp.status_code == 400, resp.status_code
