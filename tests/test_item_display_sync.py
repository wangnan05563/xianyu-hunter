from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from xianyu_hunter.infra.item_display_sync import merge_item_display_from_detail


def test_detail_merge_clears_stale_brand_when_detail_has_no_brand() -> None:
    existing = {
        "title": "#笔记本电脑配件 DDR4-3200-32G笔记本内存#笔记",
        "brand": "联想",
        "seller_credit": "信用极好",
    }
    detail = SimpleNamespace(
        title="#笔记本电脑配件 DDR4-3200-32G笔记本内存#笔记",
        price=650.0,
        seller_id="209478264",
        region="广州",
        thumb_url="//img.alicdn.com/example.jpg",
        want_cnt=4,
        view_cnt=106,
        publish_time=datetime(2026, 6, 27, 12, 4, tzinfo=timezone.utc),
        is_sold=False,
        brand="",
    )

    merged = merge_item_display_from_detail(existing, detail)

    assert merged["brand"] == ""
    assert merged["seller_credit"] == "信用极好"
    assert merged["price"] == 650.0
    assert merged["publish_time"] == "2026-06-27T12:04:00+00:00"
