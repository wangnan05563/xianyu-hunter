# tests/test_price_history.py
"""价格快照表与落库逻辑测试（PRD FR-F1-1，REQ-006）

覆盖：
- record_price_snapshots：首写/同值去重/降价写入
- record_price_snapshot：单条去重
- list_price_history 排序与天数过滤；get_min_price
- dedup.save 集成（source=collect 快照同步落库）
- 走势 API 端点冒烟
"""
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.modules.dedup import ItemDedup
from xianyu_hunter.domain.item import ItemSummary


@pytest.fixture
def repo():
    """隔离实例：临时目录 SQLite（隔离测试纪律：不触碰生产 data 目录）"""
    tmp = tempfile.mkdtemp()
    return Repository(db_path=str(Path(tmp) / "test.db"))


def test_record_snapshots_first_write(repo):
    """首写：全部商品落快照"""
    n = repo.record_price_snapshots(
        [{"id": "i1", "price": 100.0}, {"id": "i2", "price": 50.0}], source="collect")
    assert n == 2


def test_record_snapshots_dedup_same_price(repo):
    """同值去重：与最新快照同价不重复写（FR-F1-1 去重契约）"""
    repo.record_price_snapshots([{"id": "i1", "price": 100.0}], source="collect")
    n = repo.record_price_snapshots([{"id": "i1", "price": 100.0}], source="collect")
    assert n == 0
    # 降价 → 写入
    n = repo.record_price_snapshots([{"id": "i1", "price": 80.0}], source="detail")
    assert n == 1
    assert repo.get_min_price("i1") == 80.0


def test_record_snapshot_single(repo):
    assert repo.record_price_snapshot("i1", 99.0, "live_search") is True
    # 同值去重
    assert repo.record_price_snapshot("i1", 99.0, "live_search") is False
    # 非法价格拒写
    assert repo.record_price_snapshot("i1", None, "live_search") is False


def test_list_price_history_order_and_days(repo):
    repo.record_price_snapshot("i1", 100.0, "collect")
    repo.record_price_snapshot("i1", 90.0, "detail")
    rows = repo.list_price_history("i1", days=30)
    assert len(rows) == 2
    # 时间升序：第一条是最早快照
    assert rows[0]["price"] == 100.0
    assert rows[1]["price"] == 90.0


def test_dedup_save_writes_collect_snapshots(repo, monkeypatch):
    """采集链路集成：dedup.save 同步写 source=collect 快照"""
    dedup = ItemDedup(repo)
    items = [
        ItemSummary(id="i1", title="商品A", price=100.0),
        ItemSummary(id="i2", title="商品B", price=55.5),
    ]
    dedup.save(items, task_id="t1")
    # items 落库 + 快照同步
    assert repo.list_price_history("i1")[-1]["source"] == "collect"
    assert repo.list_price_history("i2")[-1]["price"] == 55.5
    # 再次保存同价 → 快照去重，不新增
    before = len(repo.list_price_history("i1"))
    dedup.save(items, task_id="t1")
    assert len(repo.list_price_history("i1")) == before


def test_price_history_api_endpoint():
    """走势 API 冒烟：空历史返回空 points + min_price null"""
    from xianyu_hunter.web.app import create_app
    from xianyu_hunter.config import get_settings

    client = TestClient(create_app())
    resp = client.get("/api/items/i_nonexistent/price-history",
                      headers={"Authorization": f"Bearer {get_settings().web_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["points"] == []
    assert data["min_price"] is None
