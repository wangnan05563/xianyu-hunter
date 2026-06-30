from __future__ import annotations

from xianyu_hunter.modules.collector._search import _extract_api_item_fields


def test_extract_api_item_fields_from_nested_result_list_item() -> None:
    raw = {
        "data": {
            "item": {
                "main": {
                    "itemId": "1050000000000",
                    "title": "联想 DDR4 3200 32G 笔记本内存",
                    "promoPrice": "680.00",
                    "picUrl": "//img.example.com/a.jpg",
                    "wantCnt": "12",
                },
                "sellerInfo": {
                    "sellerId": "seller-1",
                    "sellerNick": "牧***蓉",
                },
                "location": "天津",
            },
            "template": {},
            "templateSingle": {},
        },
        "style": {},
        "type": "item",
    }

    fields = _extract_api_item_fields(raw)

    assert fields["item_id"] == "1050000000000"
    assert fields["title"] == "联想 DDR4 3200 32G 笔记本内存"
    assert fields["price"] == 680.0
    assert fields["thumb_url"] == "https://img.example.com/a.jpg"
    assert fields["seller_id"] == "seller-1"
    assert fields["want_cnt"] == 12
    assert fields["semantic_raw"]["userNick"] == "牧***蓉"
    assert fields["semantic_raw"]["region"] == "天津"


def test_extract_api_item_fields_skips_non_item_shell() -> None:
    raw = {
        "data": {
            "template": {"moduleName": "banner"},
            "trackParams": {"spm": "abc"},
        },
        "type": "banner",
    }

    fields = _extract_api_item_fields(raw)

    assert fields["item_id"] == ""
    assert fields["title"] == ""
