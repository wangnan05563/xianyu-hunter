"""ItemDedup 单元测试"""
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


@pytest.mark.asyncio
async def test_filter_new_empty_input(dedup: ItemDedup) -> None:
    """空输入返回空"""
    result = dedup.filter_new([])
    assert result == []


@pytest.mark.asyncio
async def test_filter_new_all_new(dedup: ItemDedup) -> None:
    """全部新商品返回全部"""
    items = [make_item("1"), make_item("2"), make_item("3")]
    result = dedup.filter_new(items)
    assert len(result) == 3
    assert {i.id for i in result} == {"1", "2", "3"}


@pytest.mark.asyncio
async def test_filter_new_some_existing(dedup: ItemDedup) -> None:
    """部分已存在，只返回新商品"""
    # 先入库 1 和 2
    dedup.save([make_item("1"), make_item("2")])
    # 查询 1, 2, 3
    items = [make_item("1"), make_item("2"), make_item("3")]
    result = dedup.filter_new(items)
    assert len(result) == 1
    assert result[0].id == "3"


@pytest.mark.asyncio
async def test_filter_new_all_existing(dedup: ItemDedup) -> None:
    """全部已存在返回空"""
    dedup.save([make_item("1"), make_item("2")])
    result = dedup.filter_new([make_item("1"), make_item("2")])
    assert result == []


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


@pytest.mark.asyncio
async def test_save_then_filter(dedup: ItemDedup) -> None:
    """保存后过滤"""
    dedup.save([make_item("1")])
    result = dedup.filter_new([make_item("1"), make_item("2")])
    assert len(result) == 1
    assert result[0].id == "2"
