from __future__ import annotations

from xianyu_hunter.modules.collector_utils import extract_brand, normalize_display_fields


def test_brand_like_seller_nick_region_masked_nick_moves_to_brand() -> None:
    display = {
        "title": "镁光ddr4 32G 3200 笔记本内存条",
        "price": 268.0,
        "seller_nick": "镁光数码",
        "region": "牧***蓉",
        "seller_credit": "",
        "is_sold": False,
    }

    corrected, field_map = normalize_display_fields(display)

    assert corrected["brand"] == "镁光数码"
    assert corrected["seller_nick"] == "牧***蓉"
    assert corrected["region"] == ""
    assert "brand" in field_map
    assert field_map["brand"]["label"] == "品牌"


def test_brand_alias_seller_nick_region_masked_nick_moves_to_brand() -> None:
    display = {
        "title": "SK海力士 DDR4 16G 3200 笔记本内存",
        "price": 139.0,
        "seller_nick": "现代海力士",
        "region": "行***三",
        "seller_credit": "",
        "is_sold": False,
    }

    corrected, _ = normalize_display_fields(display)

    assert corrected["brand"] == "现代海力士"
    assert corrected["seller_nick"] == "行***三"
    assert corrected["region"] == ""


def test_brand_inferred_from_title_without_moving_normal_seller() -> None:
    display = {
        "title": "三星 DDR4 16G 3200 台式机内存",
        "price": 120.0,
        "seller_nick": "小明",
        "region": "天津",
        "seller_credit": "",
        "is_sold": False,
    }

    corrected, _ = normalize_display_fields(display)

    assert corrected["brand"] == "三星"
    assert corrected["seller_nick"] == "小明"
    assert corrected["region"] == "天津"


def test_stale_display_brand_is_cleared_when_title_does_not_match() -> None:
    display = {
        "title": "#笔记本电脑配件 DDR4-3200-32G笔记本内存#笔记",
        "brand": "联想",
        "price": 650.0,
        "seller_nick": "我喜欢工作",
        "region": "广州",
        "seller_credit": "",
        "is_sold": False,
    }

    corrected, field_map = normalize_display_fields(display)

    assert corrected["brand"] == ""
    assert "brand" not in field_map


def test_raw_brand_is_ignored_when_title_does_not_match() -> None:
    brand = extract_brand(
        {"brand": "联想"},
        title="#笔记本电脑配件 DDR4-3200-32G笔记本内存#笔记",
        seller_candidate="我喜欢工作",
    )

    assert brand == ""


def test_raw_brand_is_kept_when_title_alias_matches() -> None:
    brand = extract_brand(
        {"brand": "联想"},
        title="ThinkPad T14 笔记本内存",
        seller_candidate="我喜欢工作",
    )

    assert brand == "联想"
