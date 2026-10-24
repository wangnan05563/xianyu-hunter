# tests/test_price_watch.py
"""降价检测与通知引擎测试（PRD FR-F1-3/FR-F1-4，REQ-008/009）"""
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.modules.price_watch import observe_price, observe_prices, get_drop_threshold
from xianyu_hunter.domain.item import ItemSummary


@pytest.fixture
def repo():
    tmp = tempfile.mkdtemp()
    return Repository(db_path=str(Path(tmp) / "test.db"))


@pytest.fixture
def bus():
    b = MagicMock()
    b.publish_nowait = MagicMock()
    return b


def test_first_price_no_drop(repo, bus):
    """首次落价无历史基线 → 不触发降价"""
    info = observe_price(repo, bus, "i1", 100.0, "collect")
    assert info is None
    assert bus.publish_nowait.called is False


def test_price_drop_triggers_three_notifications(repo, bus):
    """降价触发三路通知：事件时间线 + 站内通知 + 渠道推送"""
    observe_price(repo, bus, "i1", 100.0, "collect")
    info = observe_price(repo, bus, "i1", 80.0, "detail")
    assert info is not None
    assert info["new_price"] == 80.0
    assert info["prev_min_price"] == 100.0
    assert info["drop_pct"] == pytest.approx(0.2)
    # 1. 事件时间线
    events = [e for e in repo.list_events(limit=50) if e.get("stage") == "price_drop"]
    assert events, "降价事件未写入时间线"
    # 2. 渠道推送
    assert bus.publish_nowait.called
    evt = bus.publish_nowait.call_args[0][0]
    assert evt.type.value == "price.dropped"
    assert evt.payload["new_price"] == 80.0
    # 3. 站内通知（list_notifications 属 NotificationsMixin）
    notes = repo.list_notifications(limit=50)
    assert any("降价" in (n.get("title") or "") for n in notes)


def test_price_rise_no_trigger(repo, bus):
    """涨价不触发降价提醒"""
    observe_price(repo, bus, "i1", 100.0, "collect")
    assert observe_price(repo, bus, "i1", 120.0, "detail") is None
    assert bus.publish_nowait.called is False


def _mk_task(repo, tid: str, price_config: dict | None = None) -> None:
    repo.upsert_task({"id": tid, "name": tid, "keyword": "k", "mode": "auto",
                      "price_config": json.dumps(price_config) if price_config else None})


def test_task_threshold_filters_small_drop(repo, bus):
    """任务级阈值：threshold=0.1 时 5% 降幅不触发"""
    _mk_task(repo, "t1", {"price_drop_threshold": 0.1})
    observe_price(repo, bus, "i1", 100.0, "collect", task_id="t1")
    assert observe_price(repo, bus, "i1", 95.0, "detail", task_id="t1") is None
    # 15% 降幅触发
    assert observe_price(repo, bus, "i1", 85.0, "detail", task_id="t1") is not None


def test_get_drop_threshold(repo):
    assert get_drop_threshold(repo, None) == 0.0
    _mk_task(repo, "t2", {"price_drop_threshold": 0.05})
    assert get_drop_threshold(repo, "t2") == pytest.approx(0.05)
    # 非法配置回退默认
    _mk_task(repo, "t3", {"price_drop_threshold": 5})
    assert get_drop_threshold(repo, "t3") == 0.0


def test_batch_observe_prices(repo, bus):
    """批量观察：同批多个商品各自检测，互不污染基线"""
    drops = observe_prices(
        repo, bus,
        [{"id": "i1", "price": 100.0}, {"id": "i2", "price": 60.0}],
        "collect",
    )
    assert drops == []  # 首写无基线
    # 同批内 i1 降到 50：基于批前基线 100 检测
    drops = observe_prices(
        repo, bus,
        [{"id": "i1", "price": 50.0}, {"id": "i2", "price": 60.0}],
        "collect",
    )
    assert len(drops) == 1
    assert drops[0]["item_id"] == "i1"


def test_price_dropped_template_render():
    """FR-F1-4 推送文案：含现价/历史最低/降幅/商品详情链接"""
    from xianyu_hunter.domain.events import Event, EventType
    from xianyu_hunter.modules.notifier.templates import render

    title, body = render(Event(
        type=EventType.PRICE_DROPPED,
        item_id="i1",
        payload={
            "item_id": "i1", "item_title": "佳能相机",
            "new_price": 80.0, "prev_min_price": 100.0,
            "drop_pct": 0.2, "source": "detail",
        },
    ))
    assert "降价" in title
    for token in ("¥80.00", "¥100.00", "20.0%", "goofish.com/item?id=i1", "m/items"):
        assert token in body, f"文案缺少 {token}"


def test_batch_merge_summary_notification(repo, bus):
    """FR-F1-5 合并推送：单轮多条降价合并为一条汇总通知与一次渠道推送"""
    observe_prices(repo, bus, [
        {"id": "i1", "price": 100.0}, {"id": "i2", "price": 200.0}, {"id": "i3", "price": 50.0},
    ], "collect")
    bus.publish_nowait.reset_mock()
    # 单轮 3 个商品降价
    drops = observe_prices(repo, bus, [
        {"id": "i1", "price": 80.0}, {"id": "i2", "price": 150.0}, {"id": "i3", "price": 40.0},
    ], "collect")
    assert len(drops) == 3
    # 渠道推送只发 1 条汇总事件（payload.summary=True）
    assert bus.publish_nowait.call_count == 1
    evt = bus.publish_nowait.call_args[0][0]
    assert evt.payload.get("summary") is True
    assert evt.payload.get("count") == 3
    # 站内通知为 1 条汇总（非 3 条逐条）
    notes = [n for n in repo.list_notifications(limit=50) if "降价汇总" in (n.get("title") or "")]
    assert len(notes) == 1


def test_first_round_suppress_notify(repo, bus):
    """FR-F1-5 首轮跳过：suppress_notify=True 只建快照不推送"""
    observe_prices(repo, bus, [
        {"id": "i1", "price": 100.0}, {"id": "i2", "price": 80.0},
    ], "collect", suppress_notify=True)
    # 快照已建
    assert repo.list_price_history("i1")
    # 无任何降价通知（即使模拟价格下跌场景也不推送）
    drops = observe_prices(repo, bus, [{"id": "i1", "price": 50.0}], "collect", suppress_notify=True)
    assert drops  # 检测结果仍返回
    assert bus.publish_nowait.called is False
    notes = [n for n in repo.list_notifications(limit=50) if "降价" in (n.get("title") or "")]
    assert notes == []


def test_dedup_cold_start_auto_suppresses(repo, bus):
    """FR-F1-5 冷启动抑制：全批商品均无快照历史时自动不推送（dedup 链路）"""
    from xianyu_hunter.modules.dedup import ItemDedup

    dedup = ItemDedup(repo=repo, bus=bus)
    # 首轮全量建快照：即使「价格低」也不应有任何通知
    dedup.save([
        ItemSummary(id="i7", title="新商品A", price=100.0),
        ItemSummary(id="i8", title="新商品B", price=30.0),
    ], task_id="t7")
    assert bus.publish_nowait.called is False
    notes = [n for n in repo.list_notifications(limit=50) if "降价" in (n.get("title") or "")]
    assert notes == []
    # 第二轮（已有基线）跌价 → 正常触发
    dedup.save([ItemSummary(id="i7", title="新商品A", price=60.0)], task_id="t7")
    assert bus.publish_nowait.called is True


def test_dedup_first_round_suppresses(repo, bus):
    """dedup.save 首轮（任务无 item 关联）自动抑制降价通知"""
    from xianyu_hunter.modules.dedup import ItemDedup

    dedup = ItemDedup(repo=repo, bus=bus)
    # 预置旧快照模拟「重新采集」场景：价格 100
    repo.record_price_snapshot("i9", 100.0, "collect")
    repo.upsert_item({"id": "i9", "title": "旧商品", "price": 100.0})
    dedup.save([ItemSummary(id="i9", title="旧商品", price=100.0)], task_id="t9")
    # 任务 t9 首轮建立 item 关联后再跌价 → 因首轮刚建立 suppress，本轮不推
    bus.publish_nowait.reset_mock()
    dedup.save([ItemSummary(id="i9", title="旧商品", price=50.0)], task_id="t9")
    # 第二轮已非首轮（关联已存在），跌价触发通知
    assert bus.publish_nowait.called is True


def test_dedup_save_threads_user_id_to_drop_notification(repo, bus):
    """T02815：采集链路 dedup.save 透传 user_id → 降价通知归属发起用户，而非 default"""
    from xianyu_hunter.modules.dedup import ItemDedup

    dedup = ItemDedup(repo=repo, bus=bus)
    dedup.save([ItemSummary(id="iu1", title="商品U", price=100.0)], task_id="tu1", user_id="alice")
    bus.publish_nowait.reset_mock()
    dedup.save([ItemSummary(id="iu1", title="商品U", price=60.0)], task_id="tu1", user_id="alice")

    mine = repo.list_notifications(user_id="alice")
    assert [r["dedup_key"] for r in mine] == ["price_drop:iu1:60.00"]
    assert repo.list_notifications(user_id="default") == []
    # 事件时间线同样按 alice 归属
    assert repo.list_events(limit=10, user_id="alice")
