"""Repository 单元测试"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.infra.repo_links import task_keyword_matches_title


@pytest.fixture
def tmp_repo() -> Repository:
    """使用临时数据库，避免污染真实数据"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db_path = str(Path(d) / "test.db")
        repo = Repository(db_path)
        yield repo
        # 关键：释放 SQLAlchemy 持有的文件句柄（Windows 上必须）
        repo.engine.dispose()


def test_init_db_creates_tables(tmp_repo: Repository) -> None:
    """初始化应创建 6 张表"""
    from sqlalchemy import inspect

    inspector = inspect(tmp_repo.engine)
    tables = set(inspector.get_table_names())
    assert {"tasks", "items", "sellers", "evaluations", "orders", "events"} <= tables


def test_task_crud(tmp_repo: Repository) -> None:
    """任务创建、查询、状态更新"""
    task = {
        "id": "t1",
        "name": "测试任务",
        "keyword": "iphone",
        "max_price": 5000.0,
        "mode": "confirm",
        "cron": "*/5 * * * *",
    }
    tmp_repo.upsert_task(task)

    # 查
    loaded = tmp_repo.get_task("t1")
    assert loaded is not None
    assert loaded["name"] == "测试任务"
    assert loaded["max_price"] == 5000.0

    # 更新状态
    tmp_repo.update_task_status("t1", "paused")
    loaded = tmp_repo.get_task("t1")
    assert loaded["status"] == "paused"

    # 列表
    tasks = tmp_repo.list_tasks(status="paused")
    assert len(tasks) == 1


def test_item_dedup(tmp_repo: Repository) -> None:
    """批量查存在的商品 ID"""
    ids = [f"item_{i}" for i in range(5)]
    for i in ids[:3]:
        tmp_repo.upsert_item({"id": i, "title": f"title_{i}", "price": 100.0})

    existing = tmp_repo.items_exist(ids)
    assert existing == set(ids[:3])


def test_event_save_and_list(tmp_repo: Repository) -> None:
    """事件写入与按级别过滤"""
    for i, lvl in enumerate(["INFO", "WARN", "ERROR", "INFO"]):
        tmp_repo.save_event({
            "task_id": "t1",
            "stage": "search",
            "level": lvl,
            "message": f"event_{i}",
        })

    all_events = tmp_repo.list_events(limit=10)
    assert len(all_events) == 4

    errors = tmp_repo.list_events(level="ERROR", limit=10)
    assert len(errors) == 1
    # 唯一一条 ERROR 的 message 是 event_2
    assert errors[0]["message"] == "event_2"


def test_seller_upsert_and_get(tmp_repo: Repository) -> None:
    """卖家 upsert + get"""
    seller = {
        "id": "u1",
        "nick": "卖家A",
        "credit_score": 700,
        "on_sale_count": 5,
    }
    tmp_repo.upsert_seller(seller)

    loaded = tmp_repo.get_seller("u1")
    assert loaded is not None
    assert loaded["nick"] == "卖家A"
    assert loaded["credit_score"] == 700
    assert loaded["on_sale_count"] == 5

    # 更新
    seller["on_sale_count"] = 50
    seller["nick"] = "卖家A-改名"
    tmp_repo.upsert_seller(seller)
    loaded = tmp_repo.get_seller("u1")
    assert loaded["on_sale_count"] == 50
    assert loaded["nick"] == "卖家A-改名"


def test_evaluation_save_and_get_latest(tmp_repo: Repository) -> None:
    """评估结果保存与查最新

    为什么用显式 created_at 而非默认值：SQLite 默认时间精度为秒级，
    连续 3 次 insert 可能在同秒内完成，导致 order_by(created_at desc)
    排序不唯一，测试结果不稳定。用显式时间确保排序确定性。
    """
    from datetime import datetime, timezone

    for i in range(3):
        tmp_repo.save_evaluation({
            "item_id": "i1",
            "seller_id": "u1",
            "score": 60 + i * 10,
            "risk_level": "low",
            "dimension_scores": "{}",
            "reject_reasons": "[]",
            "created_at": datetime(2026, 1, 1, 0, 0, i, tzinfo=timezone.utc),
        })

    latest = tmp_repo.get_latest_evaluation("i1")
    assert latest is not None
    # 3 次评估中分数最高的是最后一次 80
    assert latest["score"] == 80


def test_order_upsert_and_list(tmp_repo: Repository) -> None:
    """订单 upsert + 列表过滤"""
    for i, status in enumerate(["pending_pay", "pending_pay", "paid"]):
        tmp_repo.upsert_order({
            "id": f"o_{i}",
            "item_id": f"i_{i}",
            "price": 100.0 * (i + 1),
            "status": status,
        })

    pending = tmp_repo.list_orders(status="pending_pay")
    assert len(pending) == 2

    paid = tmp_repo.list_orders(status="paid")
    assert len(paid) == 1
    assert paid[0]["price"] == 300.0


def test_list_orders_by_item_ids_failed_filter(tmp_repo: Repository) -> None:
    """list_orders_by_item_ids 的 include_failed 参数控制 failed 订单可见性

    回归测试：修复「评估明细看不到失败订单导致用户误以为没下过单」问题。
    - include_failed=False（默认）：跳过 failed，符合「是否允许重新抢单」语义
    - include_failed=True：保留 failed，符合「评估明细展示完整订单历史」语义
    """
    # 同一 item 先失败后成功，再加一个纯失败的 item
    tmp_repo.upsert_order({
        "id": "o_failed_first", "item_id": "i_mixed",
        "price": 100.0, "status": "failed", "task_id": "t1",
    })
    tmp_repo.upsert_order({
        "id": "o_success_later", "item_id": "i_mixed",
        "price": 200.0, "status": "succeeded", "task_id": "t1",
    })
    tmp_repo.upsert_order({
        "id": "o_only_fail", "item_id": "i_only_fail",
        "price": 50.0, "status": "failed", "task_id": "t1",
    })

    # 默认：跳过 failed，i_mixed 应取 succeeded（最新非 failed），
    # i_only_fail 因只有 failed 记录应不在结果中
    default_map = tmp_repo.list_orders_by_item_ids(
        ["i_mixed", "i_only_fail", "i_not_exist"]
    )
    assert "i_mixed" in default_map
    assert default_map["i_mixed"]["status"] == "succeeded"
    assert default_map["i_mixed"]["id"] == "o_success_later"
    assert "i_only_fail" not in default_map
    assert "i_not_exist" not in default_map

    # include_failed=True：i_only_fail 也应返回最新 failed 订单
    include_map = tmp_repo.list_orders_by_item_ids(
        ["i_mixed", "i_only_fail"], include_failed=True
    )
    # i_mixed 最新一条是 succeeded，应保留 succeeded（按 created_at desc 取首条）
    assert include_map["i_mixed"]["status"] == "succeeded"
    assert include_map["i_only_fail"]["status"] == "failed"
    assert include_map["i_only_fail"]["id"] == "o_only_fail"


def test_json_field_parsing(tmp_repo: Repository) -> None:
    """JSON 字段自动解析"""
    tmp_repo.upsert_task({
        "id": "t1",
        "name": "n",
        "keyword": "k",
        "exclude_words": '["iphone", "pro"]',
        "notifier_channels": '["serverchan", "pushplus"]',
    })
    loaded = tmp_repo.get_task("t1")
    assert loaded["exclude_words"] == ["iphone", "pro"]
    assert loaded["notifier_channels"] == ["serverchan", "pushplus"]


def test_task_keyword_matches_chinese_compound_terms() -> None:
    assert task_keyword_matches_title("笔记本内存", "联想笔记本 DDR4 内存条 16G")
    assert not task_keyword_matches_title("笔记本内存", "全新小熊毛巾礼盒")


def test_auto_task_links_are_filtered_by_task_keyword(tmp_repo: Repository) -> None:
    tmp_repo.upsert_task({
        "id": "t1",
        "name": "内存任务",
        "keyword": "笔记本内存",
    })
    tmp_repo.upsert_task_link(
        "t1",
        "item",
        "good",
        display={"title": "联想笔记本内存 16G DDR4"},
        source="auto",
    )
    tmp_repo.upsert_task_link(
        "t1",
        "item",
        "noise",
        display={"title": "全新礼品袋毛巾套装"},
        source="auto",
    )

    rows = tmp_repo.list_task_links("t1", link_type="item")
    assert [r["link_key"] for r in rows] == ["good"]

    counts = tmp_repo.count_task_links("t1")
    assert counts["item"] == 1
    assert counts["total"] == 1


def test_auto_migrate_task_links_creates_item_url_and_seller(tmp_repo: Repository) -> None:
    tmp_repo.upsert_task({"id": "t1", "name": "phone", "keyword": "iPhone 13"})
    tmp_repo.upsert_item({
        "id": "i1",
        "task_id": "t1",
        "title": "iPhone 13 128G",
        "price": 1999.0,
        "seller_id": "s1",
        "thumb_url": "https://img.test/i1.jpg",
    })
    tmp_repo.upsert_item({
        "id": "noise",
        "task_id": "t1",
        "title": "gift towel set",
        "price": 20.0,
        "seller_id": "s2",
    })

    inserted = tmp_repo.auto_migrate_task_links()

    # URL 类型已移除：每个商品生成 item 行，有 seller_id 的额外生成 seller 行
    # auto_migrate 不按关键词过滤，i1 和 noise 都会生成行
    # i1: item + seller = 2 行；noise: item + seller = 2 行
    assert inserted == 4
    # count_task_links 有关键词过滤：noise 标题不匹配 "iPhone 13"，被过滤
    # 只有 i1 的 item 和 seller 行通过过滤
    counts = tmp_repo.count_task_links("t1")
    assert counts["item"] == 1
    assert counts["seller"] == 1
    assert counts["total"] == 2
    assert [r["link_key"] for r in tmp_repo.list_task_links("t1", link_type="seller")] == ["s1"]


def test_auto_migrate_backfills_derived_links_from_existing_item_links(tmp_repo: Repository) -> None:
    tmp_repo.upsert_task({"id": "t1", "name": "phone", "keyword": "iPhone 13"})
    tmp_repo.upsert_task_link(
        "t1",
        "item",
        "i1",
        display={"title": "iPhone 13 128G", "seller_id": "s1"},
        source="auto",
    )

    inserted = tmp_repo.auto_migrate_task_links()

    # URL 类型已移除：已有 item 行不重复插入，仅补全 seller 行
    assert inserted == 1
    counts = tmp_repo.count_task_links("t1")
    assert counts["item"] == 1
    assert counts["seller"] == 1
