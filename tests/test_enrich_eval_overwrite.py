"""_enrich_eval_with_item 字段覆盖策略测试

修复前：eval 事件 payload 中的商品基础信息字段（item_price 等）采用
"仅缺失时填充"策略，导致用户点击标题刷新后，评估明细页仍显示评估时的旧快照。
修复后：items 表和 task_links.display 有最新值时覆盖 payload 旧快照，
无最新值时保留 payload 旧快照。
"""
from __future__ import annotations

from types import SimpleNamespace

from xianyu_hunter.web.routes.api_evaluations import _enrich_eval_with_item


def test_item_price_overwritten_by_items_table_latest_value() -> None:
    """refresh_item 更新 items.price=888 后，评估列表应显示 888 而非旧快照 905"""
    payload = {
        "item_id": "i1",
        "item_price": 905.0,  # 评估时的旧快照
        "score": 75,
    }
    item_map = {"i1": {"price": 888.0}}  # refresh 后 items 表的最新值
    result = _enrich_eval_with_item(payload, item_map)
    assert result["item_price"] == 888.0


def test_item_price_preserved_when_items_table_empty() -> None:
    """items 表无记录时，保留 payload 中的旧快照"""
    payload = {
        "item_id": "i1",
        "item_price": 905.0,
        "score": 75,
    }
    item_map = {}
    result = _enrich_eval_with_item(payload, item_map)
    assert result["item_price"] == 905.0


def test_item_price_not_overwritten_by_zero() -> None:
    """items.price=0 可能是采集失败，不应覆盖有效旧值"""
    payload = {
        "item_id": "i1",
        "item_price": 905.0,
        "score": 75,
    }
    item_map = {"i1": {"price": 0.0}}
    result = _enrich_eval_with_item(payload, item_map)
    assert result["item_price"] == 905.0


def test_item_price_filled_from_link_when_payload_missing() -> None:
    """payload 无 item_price 时，从 task_links.display 填充"""
    payload = {"item_id": "i1", "score": 75}
    link_map = {"i1": {"price": "100.5"}}  # task_links.display 中 price 是字符串
    result = _enrich_eval_with_item(payload, {}, link_map=link_map)
    assert result["item_price"] == 100.5


def test_item_title_overwritten_by_latest() -> None:
    """商品改标题后，评估列表应显示最新标题"""
    payload = {"item_id": "i1", "item_title": "旧标题", "score": 75}
    item_map = {"i1": {"title": "新标题（已降价）"}}
    result = _enrich_eval_with_item(payload, item_map)
    assert result["item_title"] == "新标题（已降价）"


def test_thumb_url_overwritten_by_latest() -> None:
    """商品换图后，评估列表应显示最新缩略图"""
    payload = {"item_id": "i1", "thumb_url": "old.jpg", "score": 75}
    item_map = {"i1": {"thumb_url": "new.jpg"}}
    result = _enrich_eval_with_item(payload, item_map)
    assert result["thumb_url"] == "new.jpg"


def test_is_sold_overwritten_by_items_table() -> None:
    """商品已售后，评估列表应显示最新已售状态（即使评估时是在售）"""
    payload = {"item_id": "i1", "is_sold": False, "score": 75}
    item_map = {"i1": {"is_sold": 1}}  # items 表 is_sold=1（已售）
    result = _enrich_eval_with_item(payload, item_map)
    assert result["is_sold"] is True


def test_is_sold_preserved_when_no_latest_data() -> None:
    """items 表和 task_links 都无 is_sold 时，保留 payload 旧值"""
    payload = {"item_id": "i1", "is_sold": True, "score": 75}
    item_map = {}
    result = _enrich_eval_with_item(payload, item_map)
    assert result["is_sold"] is True


def test_brand_overwritten_by_latest() -> None:
    """品牌推断改进后，评估列表应显示最新品牌"""
    payload = {"item_id": "i1", "brand": "", "score": 75}
    link_map = {"i1": {"brand": "联想"}}
    result = _enrich_eval_with_item(payload, {}, link_map=link_map)
    assert result["brand"] == "联想"


def test_brand_preserved_when_latest_empty() -> None:
    """最新 brand 为空时（未命中别名表），保留 payload 中的旧品牌"""
    payload = {"item_id": "i1", "brand": "联想", "score": 75}
    link_map = {"i1": {"brand": ""}}  # detail.brand="" 未覆盖 task_links.display
    result = _enrich_eval_with_item(payload, {}, link_map=link_map)
    # link.brand="" 是 falsy，brand_candidate 为空，不覆盖
    assert result["brand"] == "联想"


def test_want_cnt_overwritten_by_latest() -> None:
    """想要数会增长，评估列表应显示最新值"""
    payload = {"item_id": "i1", "want_cnt": 5, "score": 75}
    item_map = {"i1": {"want_cnt": 10}}
    result = _enrich_eval_with_item(payload, item_map)
    assert result["want_cnt"] == 10


def test_want_cnt_not_overwritten_by_zero() -> None:
    """want_cnt=0 可能是采集失败，不应覆盖有效旧值"""
    payload = {"item_id": "i1", "want_cnt": 5, "score": 75}
    item_map = {"i1": {"want_cnt": 0}}
    result = _enrich_eval_with_item(payload, item_map)
    assert result["want_cnt"] == 5


def test_view_cnt_overwritten_by_latest() -> None:
    """浏览数会增长，评估列表应显示最新值"""
    payload = {"item_id": "i1", "view_cnt": 100, "score": 75}
    item_map = {"i1": {"view_cnt": 200}}
    result = _enrich_eval_with_item(payload, item_map)
    assert result["view_cnt"] == 200


def test_seller_nick_preserved_when_payload_has_value() -> None:
    """seller_nick 有脏数据清洗特殊逻辑，保持"仅缺失时填充"策略"""
    payload = {"item_id": "i1", "seller_nick": "小明", "score": 75}
    item_map = {"i1": {"seller_nick": "小红"}}
    result = _enrich_eval_with_item(payload, item_map)
    # seller_nick 不被覆盖
    assert result["seller_nick"] == "小明"


def test_seller_id_overwritten_by_latest() -> None:
    """seller_id 有最新值则覆盖"""
    payload = {"item_id": "i1", "seller_id": "old_seller", "score": 75}
    item_map = {"i1": {"seller_id": "new_seller"}}
    result = _enrich_eval_with_item(payload, item_map)
    assert result["seller_id"] == "new_seller"


def test_region_overwritten_by_latest() -> None:
    """地区有最新值则覆盖"""
    payload = {"item_id": "i1", "region": "北京", "score": 75}
    item_map = {"i1": {"region": "上海"}}
    result = _enrich_eval_with_item(payload, item_map)
    assert result["region"] == "上海"
