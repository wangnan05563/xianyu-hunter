"""ItemDedup 单元测试

验证按 task_id 隔离去重策略：
- filter_new 查 task_links 表（非 items 表）
- 不同任务可独立发现同一商品
- 同一任务不重复处理已关联的商品
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from xianyu_hunter.domain.item import ItemSummary
from xianyu_hunter.modules.dedup import ItemDedup


@pytest.fixture
def tmp_repo():
    from xianyu_hunter.infra.repository import Repository

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        repo = Repository(str(Path(d) / "test.db"))
        yield repo
        repo.engine.dispose()


@pytest.fixture
def dedup(tmp_repo) -> ItemDedup:
    return ItemDedup(tmp_repo)


def make_item(item_id: str, price: float = 100.0) -> ItemSummary:
    return ItemSummary(id=item_id, title=f"item-{item_id}", price=price)


def _link_item(repo, task_id: str, item_id: str) -> None:
    """模拟 worker._save_task_links 写入 task_links 关联"""
    repo.upsert_item_task_links(
        task_id=task_id,
        item_id=item_id,
        title=f"item-{item_id}",
    )


@pytest.mark.asyncio
async def test_filter_new_empty_input(dedup: ItemDedup) -> None:
    """空输入返回空"""
    result = dedup.filter_new([], task_id="t1")
    assert result == []


@pytest.mark.asyncio
async def test_filter_new_all_new(dedup: ItemDedup) -> None:
    """task_links 为空时全部视为新商品"""
    items = [make_item("1"), make_item("2"), make_item("3")]
    result = dedup.filter_new(items, task_id="t1")
    assert len(result) == 3
    assert {i.id for i in result} == {"1", "2", "3"}


@pytest.mark.asyncio
async def test_filter_new_some_existing(dedup: ItemDedup, tmp_repo) -> None:
    """部分已关联到当前任务，只返回未关联的商品"""
    _link_item(tmp_repo, "t1", "1")
    _link_item(tmp_repo, "t1", "2")
    items = [make_item("1"), make_item("2"), make_item("3")]
    result = dedup.filter_new(items, task_id="t1")
    assert len(result) == 1
    assert result[0].id == "3"


@pytest.mark.asyncio
async def test_filter_new_all_existing(dedup: ItemDedup, tmp_repo) -> None:
    """全部已关联到当前任务，返回空"""
    _link_item(tmp_repo, "t1", "1")
    _link_item(tmp_repo, "t1", "2")
    result = dedup.filter_new([make_item("1"), make_item("2")], task_id="t1")
    assert result == []


@pytest.mark.asyncio
async def test_filter_new_task_isolation(dedup: ItemDedup, tmp_repo) -> None:
    """不同任务独立去重：任务 t1 已关联商品 1，任务 t2 仍可发现商品 1"""
    _link_item(tmp_repo, "t1", "1")
    # 任务 t1 视角：商品 1 已存在
    result_t1 = dedup.filter_new([make_item("1"), make_item("2")], task_id="t1")
    assert len(result_t1) == 1
    assert result_t1[0].id == "2"
    # 任务 t2 视角：商品 1 未关联，仍视为新商品
    result_t2 = dedup.filter_new([make_item("1"), make_item("2")], task_id="t2")
    assert len(result_t2) == 2
    assert {i.id for i in result_t2} == {"1", "2"}


@pytest.mark.asyncio
async def test_save_returns_count(dedup: ItemDedup) -> None:
    """save 返回写入条数"""
    items = [make_item("1"), make_item("2")]
    n = dedup.save(items)
    assert n == 2


@pytest.mark.asyncio
async def test_save_empty(dedup: ItemDedup) -> None:
    """空 save 返回 0"""
    n = dedup.save([])
    assert n == 0


# ============== T02968 裁决 B：items 写侧归属（首采者持有） ==============


def test_save_attributes_new_items_to_user(dedup, tmp_repo) -> None:
    dedup.save([make_item("own-1")], task_id="t1", user_id="alice")
    assert tmp_repo.get_item("own-1", user_id="alice") is not None
    assert tmp_repo.get_item("own-1", user_id="default") is None


def test_save_without_user_leaves_key_absent(dedup, monkeypatch) -> None:
    """无归属时不写 user_id 键：显式 None 会撞 NOT NULL，交给列默认值落 default"""
    captured: dict[str, list[dict]] = {}

    def fake_batch(items: list[dict]) -> int:
        captured["items"] = items
        return len(items)

    monkeypatch.setattr(dedup.repo, "batch_upsert_items", fake_batch)
    dedup.save([make_item("own-2")], task_id="t1")
    assert "user_id" not in captured["items"][0]


def test_first_collector_keeps_ownership(dedup, tmp_repo) -> None:
    """B：后采者能看到商品内容，但不能把归属改到自己名下"""
    dedup.save([make_item("own-3")], task_id="t1", user_id="alice")
    dedup.save([make_item("own-3", price=88.0)], task_id="t2", user_id="bob")
    alice_row = tmp_repo.get_item("own-3", user_id="alice")
    assert alice_row is not None and alice_row["price"] == 88.0
    assert tmp_repo.get_item("own-3", user_id="bob") is None


def test_upsert_item_does_not_steal_ownership(tmp_repo) -> None:
    """手工/详情采集走 upsert_item，同样不能让 user_id 进 ON CONFLICT 更新集"""
    tmp_repo.upsert_item({"id": "own-4", "title": "t", "price": 10.0, "user_id": "alice"})
    tmp_repo.upsert_item({"id": "own-4", "title": "t2", "price": 9.0, "user_id": "bob"})
    row = tmp_repo.get_item("own-4")
    assert row is not None and row["user_id"] == "alice" and row["price"] == 9.0


def test_collection_row_carries_user_id_only_when_known() -> None:
    from xianyu_hunter.domain.item import ItemDetail
    from xianyu_hunter.modules.collection_service import ItemCollectionService

    svc = ItemCollectionService(object())
    detail = ItemDetail(id="own-5", title="t", price=1.0)
    assert svc._item_row_from_detail("own-5", detail, "t1", user_id="alice")["user_id"] == "alice"
    assert "user_id" not in svc._item_row_from_detail("own-5", detail, "t1")
