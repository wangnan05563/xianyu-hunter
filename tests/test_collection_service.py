from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from xianyu_hunter.domain.evaluation import EvalResult, RiskLevel
from xianyu_hunter.domain.item import ItemDetail
from xianyu_hunter.domain.seller import SellerProfile
from xianyu_hunter.modules.collection_service import (
    CollectionMode,
    ItemCollectionService,
    merge_item_row,
)


def test_merge_item_row_preserves_existing_when_incoming_blank() -> None:
    existing = {
        "id": "i1",
        "title": "old title",
        "price": 123.0,
        "description": "old description",
        "image_urls": "[\"old.jpg\"]",
        "thumb_url": "old-thumb.jpg",
        "view_cnt": 7,
    }
    incoming = {
        "id": "i1",
        "title": "",
        "price": None,
        "description": "",
        "image_urls": None,
        "thumb_url": "",
        "view_cnt": 0,
    }

    merged = merge_item_row(existing, incoming, always_overwrite={"view_cnt"})

    assert merged["title"] == "old title"
    assert merged["price"] == 123.0
    assert merged["description"] == "old description"
    assert merged["image_urls"] == "[\"old.jpg\"]"
    assert merged["thumb_url"] == "old-thumb.jpg"
    assert merged["view_cnt"] == 0


@pytest.mark.asyncio
async def test_detail_only_collection_preserves_old_title_and_syncs_display() -> None:
    detail = ItemDetail(
        id="i1",
        title="",
        price=99.0,
        seller_id="seller1",
        region="Shanghai",
        want_cnt=0,
        view_cnt=0,
        thumb_url="",
        is_sold=False,
    )
    container = MagicMock()
    container.collector.detail = AsyncMock(return_value=detail)
    # 模拟完整 cookie 集（身份 + 会话），让 _check_detail_cookie_completeness 预检通过
    container.browser.get_cookies = AsyncMock(return_value=[
        {"name": n, "value": "v"} for n in [
            "cookie2", "sgcookie", "unb", "_m_h5_tk",
            "cna", "tracknick", "_tb_token_", "t", "tfstk",
            "xlly_s", "_samesite_flag_", "KLNotice",
        ]
    ])
    container.repo.get_item.return_value = {"id": "i1", "task_id": "t1", "title": "old title"}
    container.repo.upsert_item = MagicMock()
    container.repo.mark_sold = MagicMock()
    container.repo.update_data_source = MagicMock()
    container.repo.list_link_displays_by_keys.return_value = {"i1": {"title": "old title"}}
    container.repo.upsert_task_link = MagicMock()

    service = ItemCollectionService(container)
    result = await service.collect("i1", task_id="t1", mode=CollectionMode.DETAIL_ONLY, source="live")

    assert result.ok is True
    assert result.mode == CollectionMode.DETAIL_ONLY
    container.repo.upsert_item.assert_called_once()
    saved = container.repo.upsert_item.call_args.args[0]
    assert saved["title"] == "old title"
    assert saved["price"] == 99.0
    container.repo.upsert_task_link.assert_called_once()
    container.repo.update_data_source.assert_called_once_with("i1", "live")


def _eval_result(score: int = 88) -> EvalResult:
    return EvalResult(
        score=score,
        risk_level=RiskLevel.LOW,
        dimension_scores={"price": 90},
        reject_reasons=[],
        data_quality="full",
    )


@pytest.mark.asyncio
async def test_official_full_writes_seller_and_eval_event() -> None:
    page = MagicMock()
    page.close = AsyncMock()
    detail = ItemDetail(
        id="i1",
        title="new title",
        price=199.0,
        description="desc",
        seller_id="seller1",
        detail_seller_nick="nick from detail",
        detail_sold_count=12,
        image_urls=["img.jpg"],
    )
    seller = SellerProfile(
        id="seller1",
        nick="seller nick",
        credit_score=701,
        register_days=365,
        on_sale_count=3,
        sold_count=12,
    )
    container = MagicMock()
    container.browser.new_page = AsyncMock(return_value=page)
    container.collector.detail = AsyncMock(return_value=detail)
    container.collector.seller_profile = AsyncMock(return_value=seller)
    container.collector.seller_profile_fallback = AsyncMock(return_value=seller)
    container.repo.get_item.return_value = {"id": "i1", "task_id": "t1", "title": "old title"}
    container.repo.get_eval_payload_by_item.return_value = None
    container.repo.upsert_item = MagicMock()
    container.repo.mark_sold = MagicMock()
    container.repo.update_data_source = MagicMock()
    container.repo.upsert_seller = MagicMock()
    container.repo.upsert_eval_event = MagicMock()
    container.repo.list_link_displays_by_keys.return_value = {}
    container.repo.upsert_task_link = MagicMock()
    container.evaluator.evaluate.return_value = _eval_result()

    service = ItemCollectionService(container)
    service.ensure_official_cookies = AsyncMock()
    service.extract_reviews_from_page = AsyncMock(return_value=["review text"])

    result = await service.collect("i1", task_id="t1", mode=CollectionMode.OFFICIAL_FULL)

    assert result.ok is True
    assert result.seller == seller
    assert result.reviews == ["review text"]
    container.repo.upsert_seller.assert_called_once()
    container.repo.upsert_eval_event.assert_called_once()
    event = container.repo.upsert_eval_event.call_args.args[0]
    payload = json.loads(event["payload"])
    assert payload["data_source"] == "official"
    assert payload["reviews"] == ["review text"]
    page.close.assert_awaited_once()
