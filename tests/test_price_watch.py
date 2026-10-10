# tests/test_price_watch.py
"""降价检测与通知引擎测试（PRD FR-F1-3/FR-F1-4，REQ-008/009）"""
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.modules.price_watch import observe_price, observe_prices, get_drop_threshold


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
