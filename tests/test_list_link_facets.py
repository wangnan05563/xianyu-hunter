"""GET /api/tasks/{id}/links/facets 测试（T02566 §2.3-3 + T02661 裁决「方案1」）

回归点：商品列表页的地区/品牌下拉原先由前端从「当前页 items」提取，
翻页后选项集还会变；facets 接口把 DISTINCT 放到后端一次取全。

T02661 之后口径改成「候选与列表同源收缩」：关键词 / 销售状态 / 价格区间 / 发布天数
都跟着列表走（选了就有），只有 region/brand 本身留在收缩之外（否则又回到
「选了一个地区后候选只剩该地区」的自锁死）。
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


def test_facets_not_shrunk_by_region_or_brand(client: TestClient, tmp_repo: Repository) -> None:
    """核心修复点（T02566）：选了地区后仍能选到别的地区

    「方案1」收缩的是列表那套条件（关键词/销售状态/价格/发布天数），
    region/brand 本身必须留在收缩之外——否则「先筛武汉再换上海」又得先清空，
    自锁死立刻复现。端点连这两个参数都不收，多传了也只是被忽略。
    """
    _seed_task(tmp_repo)
    _seed(tmp_repo, "i1", region="武汉", brand="金士顿")
    _seed(tmp_repo, "i2", region="上海", brand="三星")

    # 先按 region=武汉 过滤列表（列表只剩 1 行）
    listed = client.get("/api/tasks/t1/links", params={"type": "item", "region": "武汉"},
                        headers=_auth_headers()).json()
    assert {i["link_key"] for i in listed["items"]} == {"i1"}
    # 候选项不受 region/brand 影响：上海依旧可选（旧后端多传的参数会被 FastAPI 忽略）
    facets = client.get("/api/tasks/t1/links/facets",
                        params={"region": "武汉", "brand": "金士顿"},
                        headers=_auth_headers()).json()
    assert "上海" in facets["regions"], facets["regions"]
    assert "三星" in facets["brands"], facets["brands"]


def test_facets_shrink_with_keyword_and_sold_filter(client: TestClient, tmp_repo: Repository) -> None:
    """方案1 的正面断言：候选与列表同源收缩，「选了就有」

    同一批数据：不带筛选时 4 个地区全在；带上 keyword=金士顿 后只剩两行，
    候选就必须只剩那两行的地区——而不是继续列出筛完根本看不到的地区。
    """
    _seed_task(tmp_repo)
    _seed(tmp_repo, "i1", region="武汉", brand="金士顿")
    _seed(tmp_repo, "i2", region="上海", brand="三星")
    _seed(tmp_repo, "i3", region="广州", brand="金士顿")

    full = client.get("/api/tasks/t1/links/facets", headers=_auth_headers()).json()
    assert set(full["regions"]) == {"武汉", "上海", "广州"}, full["regions"]

    shrunk = client.get("/api/tasks/t1/links/facets", params={"keyword": "i3"},
                        headers=_auth_headers()).json()
    assert shrunk["regions"] == ["广州"], shrunk
    assert shrunk["brands"] == ["金士顿"], shrunk

    # 与列表口径逐字对齐：同样的 keyword 过滤下，列表命中的地区集合 == 候选集合
    listed = client.get("/api/tasks/t1/links", params={"type": "item", "keyword": "i3"},
                        headers=_auth_headers()).json()
    assert {i["display"]["region"] for i in listed["items"]} == set(shrunk["regions"]), listed

    # sold=sold 时现场没有已入库的已售行，候选应当为空（空是真的空，不是接口没接上）
    empty = client.get("/api/tasks/t1/links/facets", params={"sold_filter": "sold"},
                       headers=_auth_headers()).json()
    assert empty == {"task_id": "t1", "regions": [], "brands": []}, empty


def test_facets_shrink_with_task_price_and_publish_days(client: TestClient, tmp_repo: Repository) -> None:
    """价格区间与发布天数不是本页筛选，但列表一直在按它们过滤——候选必须跟上

    这正是 T02661 里「29 个候选全是死项」的成因：不跟上的话下拉列出一堆
    点了必空的选项，用户只会以为是数据没有这个地区。
    """
    repo = tmp_repo
    repo.upsert_task({"id": "t1", "name": "测试任务", "keyword": "DDR4",
                      "min_price": 500.0, "max_price": 2000.0})
    # 两行都带 publish_time：不写的话发布天数过滤对 NULL 一律放行（兼容旧数据），
    # 这里要测的正是「条件把行筛掉」而不是「字段缺失」
    repo.upsert_task_link(task_id="t1", link_type="item", link_key="i1",
                          display={"title": "DDR4 内存 i1", "price": 100.0,
                                   "region": "武汉", "brand": "金士顿",
                                   "publish_time": "2020-01-01T00:00:00+00:00"}, source="auto")
    repo.upsert_task_link(task_id="t1", link_type="item", link_key="i2",
                          display={"title": "DDR4 内存 i2", "price": 800.0,
                                   "region": "上海", "brand": "三星",
                                   "publish_time": "2020-01-01T00:00:00+00:00"}, source="auto")

    facets = client.get("/api/tasks/t1/links/facets", headers=_auth_headers()).json()
    assert facets["regions"] == ["上海"], facets
    assert facets["brands"] == ["三星"], facets

    listed = client.get("/api/tasks/t1/links", params={"type": "item"},
                        headers=_auth_headers()).json()
    assert {i["link_key"] for i in listed["items"]} == {"i2"}, listed

    # 再把发布天数收到 0 天：唯一的幸存者也被筛掉，候选与列表同时为空
    # （空候选是方案1 的已知代价，不是 bug——见工单回传里的「重述后果」）
    repo.upsert_task({"id": "t1", "name": "测试任务", "keyword": "DDR4",
                      "min_price": 500.0, "max_price": 2000.0, "max_publish_days": 0})
    shrunk = client.get("/api/tasks/t1/links/facets", headers=_auth_headers()).json()
    assert shrunk == {"task_id": "t1", "regions": [], "brands": []}, shrunk
    listed_after = client.get("/api/tasks/t1/links", params={"type": "item"},
                              headers=_auth_headers()).json()
    assert listed_after["items"] == [], listed_after


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
