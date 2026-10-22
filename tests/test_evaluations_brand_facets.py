"""评估品牌候选接口（T02662）

评估明细页的品牌下拉原先从「当前页 items」提取：翻页候选变，选中一个品牌后
候选集合收缩到只剩该品牌，换品牌必须先清空（与商品页 T02566 同族自锁）。

本测试钉住新端点 `/api/evaluations/brands` 的三条口径：
1. 全量 DISTINCT，不受分页与品牌过滤影响；
2. 品牌补全顺序与列表 enrich 一致：task_links.display 优先，其次事件 payload；
3. 按账号隔离（与列表同一 user_id 作用域）。

跑法：.venv/Scripts/python.exe -m pytest tests/test_evaluations_brand_facets.py -o addopts="" -q
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from xianyu_hunter.config import Settings
from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.web.app import app
from xianyu_hunter.web.deps import get_container

_TOKEN = "test-token-eval-brand-facets"


@pytest.fixture
def repo():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        repository = Repository(str(Path(d) / "brand_facets.db"))
        yield repository
        repository.engine.dispose()


@pytest.fixture
def client(repo, monkeypatch):
    settings = Settings(web_token=_TOKEN)

    def _fake_settings():
        return settings

    monkeypatch.setattr("xianyu_hunter.config.get_settings", _fake_settings)
    monkeypatch.setattr("xianyu_hunter.web.app.get_settings", _fake_settings, raising=False)

    class _FakeContainer:
        def __init__(self, repository):
            self.repo = repository

    fake = _FakeContainer(repo)
    app.dependency_overrides[get_container] = lambda: fake
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_TOKEN}"}


def _seed_eval(
    repo: Repository,
    *,
    task_id: str,
    item_id: str,
    link_brand: str | None = None,
    payload_brand: str | None = None,
    user_id: str = "default",
) -> None:
    payload = {
        "task_id": task_id,
        "item_id": item_id,
        # 品牌归一化要求标题能解释 display 品牌，这里让标题包含品牌，贴近真实数据
        "item_title": f"{link_brand or payload_brand or item_id} 商品",
        "item_price": 100.0,
        "score": 80,
        "is_passed": True,
    }
    if payload_brand:
        payload["brand"] = payload_brand
    repo.upsert_eval_event({
        "type": "eval.scored",
        "task_id": task_id,
        "item_id": item_id,
        "stage": "eval",
        "level": "info",
        "message": f"商品 {item_id} 评估分 80",
        "payload": json.dumps(payload, ensure_ascii=False),
    }, user_id=user_id)
    if link_brand:
        repo.upsert_task_link(
            task_id, "item", item_id,
            {"brand": link_brand, "title": payload["item_title"]},
            user_id=user_id,
        )


def test_brand_facets_cover_all_pages_and_ignore_brand_filter(client, repo) -> None:
    """候选来自全量评估记录：翻页、选中品牌后都不收缩"""
    repo.upsert_task({"id": "t1", "name": "任务一", "keyword": "DDR4"})
    repo.upsert_task({"id": "t2", "name": "任务二", "keyword": "DDR5"})
    _seed_eval(repo, task_id="t1", item_id="a1", link_brand="罗技")
    _seed_eval(repo, task_id="t1", item_id="a2", link_brand="雷蛇")
    _seed_eval(repo, task_id="t1", item_id="a3", payload_brand="达尔优")
    _seed_eval(repo, task_id="t2", item_id="b1", link_brand="双飞燕")

    resp = client.get(
        "/api/evaluations/brands", params={"task_id": "t1"}, headers=_auth_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["brands"] == sorted(["罗技", "雷蛇", "达尔优"])

    # 列表本身是分页的：一页只有 1 条，但候选仍是 3 个
    page = client.get(
        "/api/evaluations",
        params={"task_id": "t1", "page_size": 1, "include_out_of_range": True},
        headers=_auth_headers(),
    ).json()
    assert len(page["items"]) == 1 and page["total"] == 3

    # 选中品牌后列表收缩到 1 条，候选不跟着收缩（否则换品牌必须先清空）
    filtered = client.get(
        "/api/evaluations",
        params={"task_id": "t1", "brand": "罗技", "include_out_of_range": True},
        headers=_auth_headers(),
    ).json()
    assert filtered["total"] == 1
    again = client.get(
        "/api/evaluations/brands", params={"task_id": "t1"}, headers=_auth_headers(),
    ).json()["brands"]
    assert again == sorted(["罗技", "雷蛇", "达尔优"])


def test_brand_facets_prefers_link_display_over_payload(client, repo) -> None:
    """品牌补全与列表 enrich 同序：task_links.display 有值时覆盖 payload"""
    _seed_eval(
        repo, task_id="t1", item_id="a1",
        link_brand="新品牌", payload_brand="旧品牌",
    )
    brands = client.get("/api/evaluations/brands", headers=_auth_headers()).json()["brands"]
    assert brands == ["新品牌"]


def test_brand_facets_are_scoped_by_user(repo) -> None:
    """按账号隔离：另一个账号的品牌不出现在候选里

    身份由鉴权中间件写进 request.state.user_id，走 HTTP 需要签真实 session token；
    这里直接调用路由函数，只锁「路由有没有把身份透传到仓储」。
    """
    from xianyu_hunter.web.routes.evaluations_list import list_evaluation_brands

    class _ContainerShim:
        def __init__(self, repository):
            self.repo = repository

    _seed_eval(repo, task_id="t1", item_id="a1", link_brand="ALICE", user_id="alice")
    _seed_eval(repo, task_id="t1", item_id="b1", link_brand="BOB", user_id="bob")

    def _brands(user_id: str) -> list[str]:
        return list_evaluation_brands(
            request=SimpleNamespace(state=SimpleNamespace(user_id=user_id)),
            task_id=None,
            container=_ContainerShim(repo),
        )["brands"]

    assert _brands("alice") == ["ALICE"]
    assert _brands("bob") == ["BOB"]
