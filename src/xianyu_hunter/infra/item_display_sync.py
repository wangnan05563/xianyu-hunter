"""Helpers for keeping task_links.display aligned with freshly collected item details."""
from __future__ import annotations

from datetime import datetime
from typing import Any


def merge_item_display_from_detail(existing_display: dict | None, detail: Any) -> dict[str, Any]:
    """Merge detail fields into an existing task_links.display dict.

    Most fields only overwrite when detail collected a non-empty value. Brand is different:
    an empty detail.brand means the current official/detail page did not support the old
    inferred brand, so it must clear stale display.brand values.
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

    publish_time = getattr(detail, "publish_time", None)
    if isinstance(publish_time, datetime):
        merged["publish_time"] = publish_time.isoformat()
    elif publish_time:
        merged["publish_time"] = str(publish_time)

    is_sold = getattr(detail, "is_sold", None)
    if is_sold is not None:
        merged["is_sold"] = bool(is_sold)

    merged["brand"] = getattr(detail, "brand", "") or ""
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
