"""items 表 data_source 列迁移与更新测试

覆盖：
- 列存在性 / 默认值
- update_data_source 的合法/非法/不存在场景
- 迁移幂等性（模拟老数据库缺列后重新迁移）
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import inspect, text as sa_text

from xianyu_hunter.infra.repository import Repository


@pytest.fixture
def tmp_repo() -> Repository:
    """使用临时数据库，避免污染真实数据"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db_path = str(Path(d) / "test.db")
        repo = Repository(db_path)
        yield repo
        # 关键：释放 SQLAlchemy 持有的文件句柄（Windows 上必须）
        repo.engine.dispose()


def _get_item_columns(repo: Repository) -> set[str]:
    """获取 items 表的所有列名"""
    inspector = inspect(repo.engine)
    return {col["name"] for col in inspector.get_columns("items")}


def test_data_source_column_exists(tmp_repo: Repository) -> None:
    """新建 Repository，items 表应包含 data_source 列"""
    assert "data_source" in _get_item_columns(tmp_repo)


def test_default_value_is_search(tmp_repo: Repository) -> None:
    """upsert_item 后，data_source 应默认为 'search'"""
    tmp_repo.upsert_item({
        "id": "item_1",
        "title": "测试商品",
        "price": 100.0,
    })
    item = tmp_repo.get_item("item_1")
    assert item is not None
    assert item["data_source"] == "search"


def test_update_data_source_to_official(tmp_repo: Repository) -> None:
    """update_data_source 应成功更新为 'official'"""
    tmp_repo.upsert_item({
        "id": "item_1",
        "title": "测试商品",
        "price": 100.0,
    })
    ok = tmp_repo.update_data_source("item_1", "official")
    assert ok is True
    item = tmp_repo.get_item("item_1")
    assert item["data_source"] == "official"


def test_update_data_source_to_live(tmp_repo: Repository) -> None:
    """update_data_source 应支持 'live' 取值"""
    tmp_repo.upsert_item({
        "id": "item_live",
        "title": "直播商品",
        "price": 200.0,
    })
    ok = tmp_repo.update_data_source("item_live", "live")
    assert ok is True
    item = tmp_repo.get_item("item_live")
    assert item["data_source"] == "live"


def test_update_data_source_invalid_value_raises(tmp_repo: Repository) -> None:
    """非法 source 取值应抛 ValueError"""
    tmp_repo.upsert_item({
        "id": "item_1",
        "title": "测试商品",
        "price": 100.0,
    })
    with pytest.raises(ValueError):
        tmp_repo.update_data_source("item_1", "invalid")


def test_update_data_source_nonexistent_item_returns_false(tmp_repo: Repository) -> None:
    """更新不存在的商品应返回 False"""
    ok = tmp_repo.update_data_source("nonexistent", "official")
    assert ok is False


def test_migration_idempotent(tmp_repo: Repository) -> None:
    """迁移幂等性：模拟老数据库（删除列后再 init），验证迁移可重复执行"""
    from xianyu_hunter.infra.db_models import init_db

    # 先确认列已存在
    assert "data_source" in _get_item_columns(tmp_repo)

    # 插入一条老数据，验证迁移后数据不丢失
    tmp_repo.upsert_item({
        "id": "item_legacy",
        "title": "老数据",
        "price": 50.0,
    })

    # 模拟老数据库：用裸连接删除 data_source 列
    # SQLite 3.35.0+ 支持 ALTER TABLE DROP COLUMN
    with tmp_repo.engine.begin() as conn:
        conn.execute(sa_text("ALTER TABLE items DROP COLUMN data_source"))

    # 确认列已被删除
    assert "data_source" not in _get_item_columns(tmp_repo)

    # 重新调用 init_db 触发迁移（幂等：列不存在则添加）
    init_db(tmp_repo.db_path)

    # 验证迁移后列已恢复
    assert "data_source" in _get_item_columns(tmp_repo)

    # 验证老数据已被回填为默认值 'search'
    item = tmp_repo.get_item("item_legacy")
    assert item is not None
    assert item["data_source"] == "search"

    # 再次调用 init_db 验证幂等（列已存在时不报错）
    init_db(tmp_repo.db_path)
    assert "data_source" in _get_item_columns(tmp_repo)
