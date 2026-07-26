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
