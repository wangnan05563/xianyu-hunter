"""Helpers for keeping task_links.display aligned with freshly collected item details."""
from __future__ import annotations

from datetime import datetime
from typing import Any


def merge_item_display_from_detail(existing_display: dict | None, detail: Any) -> dict[str, Any]:
    """Merge detail fields into an existing task_links.display dict.

    所有字段统一采用 set_if_present 策略：仅当 detail 采集到非空值时才覆盖。
    brand 字段不再强制清空——detail 流程的 extract_brand(raw=None, ...) 仅做标题推断，
    空返回不代表"权威判定无品牌"，只是"标题未命中有限别名表"。
    若旧 brand 确实是搜索 API 污染，评估列表读取时的 normalize_display_brand 会兜底校验。
    """
    merged: dict[str, Any] = dict(existing_display or {})

    def set_if_present(key: str, value: Any) -> None:
        if value is not None and value != "":
            merged[key] = value

    set_if_present("title", getattr(detail, "title", None))
    set_if_present("price", getattr(detail, "price", None))
    set_if_present("seller_id", getattr(detail, "seller_id", None))
    set_if_present("region", getattr(detail, "region", None))
    set_if_present("thumb_url", getattr(detail, "thumb_url", None))
    set_if_present("want_cnt", getattr(detail, "want_cnt", None))
    set_if_present("view_cnt", getattr(detail, "view_cnt", None))

    # 详情页图片列表：前端商品详情和评估页可用此列表展示多图
    image_urls = getattr(detail, "image_urls", None)
    if image_urls:
        merged["image_urls"] = image_urls

    publish_time = getattr(detail, "publish_time", None)
    if isinstance(publish_time, datetime):
        merged["publish_time"] = publish_time.isoformat()
    elif publish_time:
        merged["publish_time"] = str(publish_time)

    is_sold = getattr(detail, "is_sold", None)
    if is_sold is not None:
        merged["is_sold"] = bool(is_sold)

    set_if_present("brand", getattr(detail, "brand", ""))
    return merged


def sync_item_display_from_detail(
    repo: Any,
    task_id: str,
    item_id: str,
    detail: Any,
    source: str = "auto",
) -> dict[str, Any]:
    """Persist detail fields to task_links.display and return the merged display."""
    existing_map = repo.list_link_displays_by_keys([item_id], link_type="item")
    existing_display = existing_map.get(item_id, {})
    merged_display = merge_item_display_from_detail(existing_display, detail)
    repo.upsert_task_link(
        task_id=task_id,
        link_type="item",
        link_key=item_id,
        display=merged_display,
        source=source,
    )
    return merged_display
