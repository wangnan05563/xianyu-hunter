"""商品已售状态检测与信息刷新 - Repository 层测试"""
import json
import tempfile

from xianyu_hunter.infra.repository import Repository


def _new_repo() -> Repository:
    """创建临时数据库的 Repository"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    return Repository(db_path=tmp.name)


def test_mark_sold_updates_item():
    repo = _new_repo()
    repo.upsert_item({
        "id": "item_001",
        "task_id": "t1",
        "title": "测试商品",
        "price": 100.0,
    })
    # 初始状态：未售
    assert repo.get_item("item_001").get("is_sold") == 0

    repo.mark_sold("item_001")

    item = repo.get_item("item_001")
    assert item["is_sold"] == 1
    assert item["sold_detected_at"] is not None


def test_mark_sold_syncs_task_link_display():
    repo = _new_repo()
    repo.upsert_item({"id": "item_002", "task_id": "t2", "title": "测试", "price": 50.0})
    # 先建立 task_links.display（含 is_sold=False）
    repo.upsert_task_link("t2", "item", "item_002", display={
        "title": "测试", "price": 50.0, "is_sold": False, "url": "https://example.com"
    })
    repo.mark_sold("item_002")

    links = repo.lookup_task_links("item", "item_002")
    assert links, "task_link 不存在"
    display = links[0].get("display")
    if isinstance(display, str):
        display = json.loads(display)
    assert display.get("is_sold") is True
