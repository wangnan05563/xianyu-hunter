"""evaluations list API 端点 sold_filter 参数测试

回归测试：Task 6 为 evaluations list 端点新增 sold_filter 参数，
评估事件本身不存 is_sold，需从 items 表批量查询后 Python 端过滤。
覆盖 all/onsale/sold 三种模式。
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from xianyu_hunter.config import Settings
from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.web.app import app
from xianyu_hunter.web.deps import get_container


_TEST_TOKEN = "test-token-evaluations-sold-filter"


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
    """写入 items 表并设置 is_sold 状态"""
    repo.upsert_item({
        "id": item_id,
        "task_id": "t1",
        "title": title,
        "price": 100.0,
        "is_sold": 0,
    })
    if is_sold:
        repo.mark_sold(item_id)


def _seed_eval_event(repo: Repository, item_id: str, title: str, *, score: int = 80) -> None:
    """写入 eval.scored 事件

    为什么用 upsert_eval_event：评估事件按 (task_id, item_id, type) 去重，
    与生产环境写入路径一致。
    """
    repo.upsert_eval_event({
        "type": "eval.scored",
        "task_id": "t1",
        "item_id": item_id,
        "stage": "eval",
        "level": "info",
        "message": f"商品 {item_id} 评估分 {score}",
        "payload": json.dumps({
            "task_id": "t1",
            "item_id": item_id,
            "item_title": title,
            "item_price": 100.0,
            "score": score,
            "is_passed": True,
        }, ensure_ascii=False),
    })


def test_evaluations_sold_filter_all_returns_all(client: TestClient, tmp_repo: Repository) -> None:
    """sold_filter=all：返回所有评估记录（在售 + 已售商品的评估）"""
    tmp_repo.upsert_task({"id": "t1", "name": "测试任务", "keyword": "DDR4"})

    _seed_item(tmp_repo, "item_onsale_1", "DDR4 在售商品 1", is_sold=False)
    _seed_item(tmp_repo, "item_sold_1", "DDR4 已售商品 1", is_sold=True)
    _seed_eval_event(tmp_repo, "item_onsale_1", "DDR4 在售商品 1")
    _seed_eval_event(tmp_repo, "item_sold_1", "DDR4 已售商品 1")

    resp = client.get(
        "/api/evaluations",
        params={"sold_filter": "all"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    item_ids = {item["item_id"] for item in data["items"]}
    assert item_ids == {"item_onsale_1", "item_sold_1"}, \
        f"sold_filter=all 应返回所有评估记录，但得到 {item_ids}"


def test_evaluations_sold_filter_onsale_excludes_sold(client: TestClient, tmp_repo: Repository) -> None:
    """sold_filter=onsale：仅保留 items.is_sold=0 的评估记录

    Python 端过滤：从 item_map 构建 is_sold 映射后过滤。
    """
    tmp_repo.upsert_task({"id": "t1", "name": "测试任务", "keyword": "DDR4"})

    _seed_item(tmp_repo, "item_onsale_1", "DDR4 在售商品 1", is_sold=False)
    _seed_item(tmp_repo, "item_onsale_2", "DDR4 在售商品 2", is_sold=False)
    _seed_item(tmp_repo, "item_sold_1", "DDR4 已售商品 1", is_sold=True)
    _seed_eval_event(tmp_repo, "item_onsale_1", "DDR4 在售商品 1")
    _seed_eval_event(tmp_repo, "item_onsale_2", "DDR4 在售商品 2")
    _seed_eval_event(tmp_repo, "item_sold_1", "DDR4 已售商品 1")

    resp = client.get(
        "/api/evaluations",
        params={"sold_filter": "onsale"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    item_ids = {item["item_id"] for item in data["items"]}
    assert item_ids == {"item_onsale_1", "item_onsale_2"}, \
        f"sold_filter=onsale 应仅返回在售商品的评估，但得到 {item_ids}"
    # total 字段也应反映过滤后的数量
    assert data["total"] == 2, \
        f"total 应为 2（过滤后），但得到 {data['total']}"


def test_evaluations_sold_filter_sold_excludes_onsale(client: TestClient, tmp_repo: Repository) -> None:
    """sold_filter=sold：仅保留 items.is_sold=1 的评估记录"""
    tmp_repo.upsert_task({"id": "t1", "name": "测试任务", "keyword": "DDR4"})

    _seed_item(tmp_repo, "item_onsale_1", "DDR4 在售商品 1", is_sold=False)
    _seed_item(tmp_repo, "item_sold_1", "DDR4 已售商品 1", is_sold=True)
    _seed_item(tmp_repo, "item_sold_2", "DDR4 已售商品 2", is_sold=True)
    _seed_eval_event(tmp_repo, "item_onsale_1", "DDR4 在售商品 1")
    _seed_eval_event(tmp_repo, "item_sold_1", "DDR4 已售商品 1")
    _seed_eval_event(tmp_repo, "item_sold_2", "DDR4 已售商品 2")

    resp = client.get(
        "/api/evaluations",
        params={"sold_filter": "sold"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    item_ids = {item["item_id"] for item in data["items"]}
    assert item_ids == {"item_sold_1", "item_sold_2"}, \
        f"sold_filter=sold 应仅返回已售商品的评估，但得到 {item_ids}"
    assert data["total"] == 2, \
        f"total 应为 2（过滤后），但得到 {data['total']}"


def test_evaluations_sold_filter_default_is_all(client: TestClient, tmp_repo: Repository) -> None:
    """不传 sold_filter 时默认 all，行为与之前一致（向后兼容）"""
    tmp_repo.upsert_task({"id": "t1", "name": "测试任务", "keyword": "DDR4"})

    _seed_item(tmp_repo, "item_onsale_1", "DDR4 在售商品 1", is_sold=False)
    _seed_item(tmp_repo, "item_sold_1", "DDR4 已售商品 1", is_sold=True)
    _seed_eval_event(tmp_repo, "item_onsale_1", "DDR4 在售商品 1")
    _seed_eval_event(tmp_repo, "item_sold_1", "DDR4 已售商品 1")

    # 不传 sold_filter
    resp = client.get("/api/evaluations", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    item_ids = {item["item_id"] for item in data["items"]}
    assert item_ids == {"item_onsale_1", "item_sold_1"}, \
        f"默认 sold_filter=all 应返回所有评估，但得到 {item_ids}"


def test_evaluations_sold_filter_onsale_preserves_items_without_item_record(
    client: TestClient, tmp_repo: Repository
) -> None:
    """sold_filter=onsale 时，items 表无记录的评估应按"在售"保留

    为什么按"在售"处理：评估事件可能引用了未入库的商品（如 live_search 写入 task_links
    但未触发 items 表写入），这种情况按"在售"保留，避免 onsale 过滤时误删有效评估。
    """
    tmp_repo.upsert_task({"id": "t1", "name": "测试任务", "keyword": "DDR4"})

    # item_in_db：在 items 表中，is_sold=0
    _seed_item(tmp_repo, "item_in_db", "DDR4 在售商品", is_sold=False)
    # item_not_in_db：不在 items 表中（评估事件引用了未入库商品）
    _seed_eval_event(tmp_repo, "item_in_db", "DDR4 在售商品")
    _seed_eval_event(tmp_repo, "item_not_in_db", "DDR4 未入库商品")

    resp = client.get(
        "/api/evaluations",
        params={"sold_filter": "onsale"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    item_ids = {item["item_id"] for item in data["items"]}
    # 未入库商品按"在售"保留
    assert item_ids == {"item_in_db", "item_not_in_db"}, \
        f"未入库商品应按在售保留，但得到 {item_ids}"


def test_evaluations_sold_filter_invalid_value_rejected(client: TestClient, tmp_repo: Repository) -> None:
    """sold_filter 非法值应被 FastAPI pattern 校验拒绝（422）"""
    tmp_repo.upsert_task({"id": "t1", "name": "测试任务", "keyword": "DDR4"})

    resp = client.get(
        "/api/evaluations",
        params={"sold_filter": "invalid"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 422, \
        f"sold_filter=invalid 应被 pattern 校验拒绝（422），但得到 {resp.status_code}"
