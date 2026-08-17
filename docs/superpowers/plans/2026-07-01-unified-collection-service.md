# Unified Collection Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a shared item collection service so lightweight refresh, official collection, and batch refresh use one merge and persistence path.

**Architecture:** Add `xianyu_hunter.modules.collection_service` as the business boundary for item collection. API routes translate HTTP concerns into service calls, while `BatchRefreshScheduler` calls the same service directly and keeps its existing progress, pause, stop, and history behavior.

**Tech Stack:** Python 3.11, FastAPI route layer, Playwright-backed `Collector`, SQLAlchemy repository methods, pytest with mocks.

---

## File Structure

- Create `backend/xianyu_hunter/modules/collection_service.py`: collection modes, result/error types, merge helpers, cookie/review helpers, and `ItemCollectionService`.
- Create `tests/test_collection_service.py`: service-level unit tests for old-value protection, official collection persistence, sold handling, and route-compatible result shape.
- Modify `backend/xianyu_hunter/web/routes/api_items.py`: delegate `/api/items/{item_id}/refresh` to the service.
- Modify `backend/xianyu_hunter/web/routes/api_evaluations.py`: keep public route functions but delegate `_collect_official_and_evaluate` to the service and remove duplicated persistence logic after tests pass.
- Modify `backend/xianyu_hunter/modules/batch_refresh_scheduler.py`: delegate `_refresh_one()` to the service and use returned `changed_fields`.
- Modify `tests/test_batch_refresh_scheduler.py`: assert the scheduler invokes the service path and preserves existing counters.
- Modify `tests/test_official_collect_integration.py`: update mocks to target service delegation while keeping old-value protection and `data_source="official"` assertions.

## Task 1: Service Tests And Core Types

**Files:**
- Create: `tests/test_collection_service.py`
- Create: `backend/xianyu_hunter/modules/collection_service.py`

- [ ] **Step 1: Write failing tests for merge and detail-only collection**

Add `tests/test_collection_service.py`:

```python
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from xianyu_hunter.domain.item import ItemDetail
from xianyu_hunter.modules.collection_service import (
    CollectionMode,
    ItemCollectionService,
    merge_item_row,
)


pytestmark = pytest.mark.asyncio


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


async def test_detail_only_collection_preserves_old_title_and_syncs_display() -> None:
    detail = ItemDetail(
        id="i1",
        title="",
        price=99.0,
        seller_id="seller1",
        region="上海",
        want_cnt=0,
        view_cnt=0,
        thumb_url="",
        is_sold=False,
    )
    container = MagicMock()
    container.collector.detail = AsyncMock(return_value=detail)
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_collection_service.py -q`

Expected: fail with `ModuleNotFoundError: No module named 'xianyu_hunter.modules.collection_service'`.

- [ ] **Step 3: Add service skeleton and merge helper**

Create `backend/xianyu_hunter/modules/collection_service.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from xianyu_hunter.domain.evaluation import EvalResult
from xianyu_hunter.domain.item import ItemDetail
from xianyu_hunter.domain.seller import SellerProfile
from xianyu_hunter.infra.item_display_sync import sync_item_display_from_detail
from xianyu_hunter.infra.logger import get_logger

logger = get_logger()


class CollectionMode(str, Enum):
    DETAIL_ONLY = "detail_only"
    OFFICIAL_FULL = "official_full"


@dataclass
class CollectionError(Exception):
    status_code: int
    detail: str
    item_id: str = ""

    def __str__(self) -> str:
        return self.detail


@dataclass
class CollectionResult:
    ok: bool
    item_id: str
    mode: CollectionMode
    detail: ItemDetail | None = None
    seller: SellerProfile | None = None
    reviews: list[str] = field(default_factory=list)
    evaluation: EvalResult | None = None
    changed_fields: list[str] = field(default_factory=list)


_DEFAULT_ALWAYS_OVERWRITE = {
    "task_id",
    "publish_time",
    "view_cnt",
    "want_cnt",
    "region",
    "seller_id",
    "is_sold",
}


def _is_blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and value == "")


def merge_item_row(
    existing: dict[str, Any] | None,
    incoming: dict[str, Any],
    *,
    always_overwrite: set[str] | None = None,
) -> dict[str, Any]:
    existing = existing or {}
    overwrite = always_overwrite or _DEFAULT_ALWAYS_OVERWRITE
    merged: dict[str, Any] = {}
    for key, value in incoming.items():
        if key in overwrite:
            merged[key] = value
        elif _is_blank(value):
            merged[key] = existing.get(key)
        else:
            merged[key] = value
    return merged


class ItemCollectionService:
    def __init__(self, container: Any) -> None:
        self.container = container

    async def collect(
        self,
        item_id: str,
        *,
        task_id: str | None = None,
        mode: CollectionMode = CollectionMode.OFFICIAL_FULL,
        existing_item: dict[str, Any] | None = None,
        source: str = "official",
        reuse_page: Any | None = None,
        evaluate: bool | None = None,
    ) -> CollectionResult:
        if mode == CollectionMode.DETAIL_ONLY:
            return await self._collect_detail_only(
                item_id,
                task_id=task_id,
                existing_item=existing_item,
                source=source,
                reuse_page=reuse_page,
            )
        raise CollectionError(500, f"Unsupported collection mode: {mode}", item_id=item_id)

    async def _collect_detail_only(
        self,
        item_id: str,
        *,
        task_id: str | None,
        existing_item: dict[str, Any] | None,
        source: str,
        reuse_page: Any | None,
    ) -> CollectionResult:
        detail = await self.container.collector.detail(item_id, page=reuse_page)
        if detail is None:
            raise CollectionError(502, "采集商品详情失败：页面不可达或登录已过期", item_id=item_id)

        old_item = existing_item if existing_item is not None else (self.container.repo.get_item(item_id) or {})
        effective_task_id = str(old_item.get("task_id") or task_id or "")
        incoming = self._item_row_from_detail(item_id, detail, effective_task_id)
        is_delisted = detail.is_sold and not detail.title
        changed_fields = self.diff_fields(old_item, incoming)

        if not (is_delisted and old_item):
            self.container.repo.upsert_item(merge_item_row(old_item, incoming))
        if detail.is_sold:
            self.container.repo.mark_sold(item_id)
        if effective_task_id and not is_delisted:
            sync_item_display_from_detail(self.container.repo, effective_task_id, item_id, detail, source="auto")
        self._update_data_source(item_id, source)

        return CollectionResult(
            ok=True,
            item_id=item_id,
            mode=CollectionMode.DETAIL_ONLY,
            detail=detail,
            changed_fields=changed_fields,
        )

    def _item_row_from_detail(self, item_id: str, detail: ItemDetail, task_id: str) -> dict[str, Any]:
        return {
            "id": item_id,
            "task_id": task_id,
            "title": detail.title,
            "price": detail.price,
            "description": detail.description or "",
            "image_urls": json.dumps(detail.image_urls, ensure_ascii=False) if detail.image_urls else None,
            "seller_id": detail.seller_id or "",
            "region": detail.region or "",
            "want_cnt": detail.want_cnt,
            "view_cnt": detail.view_cnt,
            "thumb_url": detail.thumb_url or "",
            "publish_time": detail.publish_time,
            "is_sold": 1 if detail.is_sold else 0,
        }

    def _update_data_source(self, item_id: str, source: str) -> None:
        try:
            self.container.repo.update_data_source(item_id, source)
        except Exception as exc:
            logger.warning("更新 data_source={} 失败 item={}: {}", source, item_id, exc)

    @staticmethod
    def diff_fields(existing: dict[str, Any], incoming: dict[str, Any]) -> list[str]:
        fields = ["title", "price", "seller_id", "region", "want_cnt", "view_cnt", "thumb_url", "is_sold"]
        changed: list[str] = []
        for field_name in fields:
            old = existing.get(field_name)
            new = incoming.get(field_name)
            if field_name == "price":
                try:
                    if float(old or 0) != float(new or 0):
                        changed.append(field_name)
                except (TypeError, ValueError):
                    changed.append(field_name)
            elif field_name in {"want_cnt", "view_cnt", "is_sold"}:
                if int(old or 0) != int(new or 0):
                    changed.append(field_name)
            elif (old or "") != (new or ""):
                changed.append(field_name)
        return changed
```

- [ ] **Step 4: Run tests and verify detail-only tests pass**

Run: `pytest tests/test_collection_service.py -q`

Expected: both tests pass.

## Task 2: Official Full Collection In Service

**Files:**
- Modify: `backend/xianyu_hunter/modules/collection_service.py`
- Modify: `tests/test_collection_service.py`

- [ ] **Step 1: Write failing official-full test**

Append to `tests/test_collection_service.py`:

```python
from xianyu_hunter.domain.evaluation import EvalResult, RiskLevel
from xianyu_hunter.domain.seller import SellerProfile


def _eval_result(score: int = 88) -> EvalResult:
    return EvalResult(
        score=score,
        risk_level=RiskLevel.LOW,
        dimension_scores={"price": 90},
        reject_reasons=[],
        data_quality="full",
    )


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
```

- [ ] **Step 2: Run the failing official-full test**

Run: `pytest tests/test_collection_service.py::test_official_full_writes_seller_and_eval_event -q`

Expected: fail with `CollectionError: Unsupported collection mode`.

- [ ] **Step 3: Implement official-full path**

Update `backend/xianyu_hunter/modules/collection_service.py`:

```python
import asyncio
from datetime import datetime, timezone
```

Add methods inside `ItemCollectionService` and route `OFFICIAL_FULL` to `_collect_official_full`:

```python
    async def collect(
        self,
        item_id: str,
        *,
        task_id: str | None = None,
        mode: CollectionMode = CollectionMode.OFFICIAL_FULL,
        existing_item: dict[str, Any] | None = None,
        source: str = "official",
        reuse_page: Any | None = None,
        evaluate: bool | None = None,
    ) -> CollectionResult:
        if mode == CollectionMode.DETAIL_ONLY:
            return await self._collect_detail_only(
                item_id,
                task_id=task_id,
                existing_item=existing_item,
                source=source,
                reuse_page=reuse_page,
            )
        if mode == CollectionMode.OFFICIAL_FULL:
            return await self._collect_official_full(
                item_id,
                task_id=task_id,
                existing_item=existing_item,
                source=source,
                reuse_page=reuse_page,
            )
        raise CollectionError(500, f"Unsupported collection mode: {mode}", item_id=item_id)

    async def ensure_official_cookies(self) -> None:
        return None

    async def extract_reviews_from_page(self, page: Any) -> list[str]:
        reviews: list[str] = []
        selectors = [
            "[class*='review'] [class*='item']",
            "[class*='comment'] [class*='item']",
            "[class*='evaluation'] [class*='item']",
            "[class*='message'] [class*='item']",
        ]
        for selector in selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements[:10]:
                    text = (await element.inner_text()).strip()
                    if text and len(text) > 5:
                        reviews.append(text)
                if reviews:
                    break
            except Exception:
                continue
        return reviews

    async def _collect_official_full(
        self,
        item_id: str,
        *,
        task_id: str | None,
        existing_item: dict[str, Any] | None,
        source: str,
        reuse_page: Any | None,
    ) -> CollectionResult:
        await self.ensure_official_cookies()
        own_page = reuse_page is None
        page = reuse_page or await self.container.browser.new_page()
        detail: ItemDetail | None = None
        seller: SellerProfile | None = None
        reviews: list[str] = []
        try:
            detail = await self.container.collector.detail(item_id, page=page)
            if detail is None:
                raise CollectionError(410, f"采集商品 {item_id} 详情失败：页面可能未正常加载或商品已下架", item_id=item_id)

            async def safe_seller_profile() -> SellerProfile | None:
                if not detail or not detail.seller_id:
                    return None
                try:
                    return await self.container.collector.seller_profile(detail.seller_id)
                except Exception as exc:
                    logger.warning("采集卖家主页失败 seller={}: {}", detail.seller_id, exc)
                    return None

            reviews, seller = await asyncio.gather(
                self.extract_reviews_from_page(page),
                safe_seller_profile(),
            )
        finally:
            if own_page:
                await page.close()

        if seller is None:
            seller = await self.container.collector.seller_profile_fallback(None, detail)
        else:
            self._merge_detail_seller_fields(seller, detail)

        old_item = existing_item if existing_item is not None else (self.container.repo.get_item(item_id) or {})
        effective_task_id = self._resolve_task_id(item_id, task_id, old_item)
        incoming = self._item_row_from_detail(item_id, detail, effective_task_id)
        changed_fields = self.diff_fields(old_item, incoming)
        self.container.repo.upsert_item(merge_item_row(old_item, incoming))
        self._update_data_source(item_id, source)
        if detail.is_sold:
            self.container.repo.mark_sold(item_id)
        if effective_task_id:
            sync_item_display_from_detail(self.container.repo, effective_task_id, item_id, detail, source="auto")
        self._save_seller(seller)
        eval_result = self.container.evaluator.evaluate(detail, seller)
        if effective_task_id:
            self._save_eval_event(effective_task_id, item_id, detail, seller, reviews, eval_result)
        return CollectionResult(
            ok=True,
            item_id=item_id,
            mode=CollectionMode.OFFICIAL_FULL,
            detail=detail,
            seller=seller,
            reviews=reviews,
            evaluation=eval_result,
            changed_fields=changed_fields,
        )

    def _resolve_task_id(self, item_id: str, task_id: str | None, old_item: dict[str, Any]) -> str:
        if task_id:
            return task_id
        payload = self.container.repo.get_eval_payload_by_item(item_id)
        if payload:
            return str(payload.get("task_id") or "")
        return str(old_item.get("task_id") or "")

    @staticmethod
    def _merge_detail_seller_fields(seller: SellerProfile, detail: ItemDetail) -> None:
        if not seller.nick and detail.detail_seller_nick:
            seller.nick = detail.detail_seller_nick
        if seller.credit_score is None and detail.detail_credit_score is not None:
            seller.credit_score = detail.detail_credit_score
        if not seller.sold_count and detail.detail_sold_count:
            seller.sold_count = detail.detail_sold_count
        if not seller.register_days and detail.detail_register_days:
            seller.register_days = detail.detail_register_days

    def _save_seller(self, seller: SellerProfile | None) -> None:
        if not seller or not seller.id or seller.id == "unknown":
            return
        self.container.repo.upsert_seller({
            "id": seller.id,
            "nick": seller.nick or "",
            "credit_score": seller.credit_score,
            "register_days": seller.register_days,
            "on_sale_count": seller.on_sale_count,
            "sold_count": seller.sold_count,
            "last_visited": datetime.now(timezone.utc),
        })

    def _save_eval_event(
        self,
        task_id: str,
        item_id: str,
        detail: ItemDetail,
        seller: SellerProfile | None,
        reviews: list[str],
        eval_result: EvalResult,
    ) -> None:
        score_display = eval_result.score if eval_result.score is not None else "N/A"
        level = "info" if eval_result.is_passed else "warn"
        if getattr(eval_result, "risk_level", None) and eval_result.risk_level.value == "EXTREME":
            level = "err"
        if getattr(eval_result, "risk_level", None) and eval_result.risk_level.value == "UNKNOWN":
            level = "warn"
        payload = {
            "task_id": task_id,
            "item_id": item_id,
            "item_title": detail.title,
            "item_price": detail.price,
            "item_description": detail.description or "",
            "seller_id": detail.seller_id or "",
            "seller_nick": seller.nick if seller else "",
            "seller_credit_score": seller.credit_score if seller else None,
            "seller_on_sale_count": seller.on_sale_count if seller else 0,
            "seller_sold_count": seller.sold_count if seller else 0,
            "seller_register_days": seller.register_days if seller else 0,
            "score": eval_result.score,
            "risk_level": eval_result.risk_level.value,
            "dimension_scores": eval_result.dimension_scores,
            "reject_reasons": eval_result.reject_reasons,
            "is_passed": eval_result.is_passed,
            "data_quality": eval_result.data_quality,
            "data_source": "official",
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "reviews": reviews,
            "image_urls": detail.image_urls if detail.image_urls else [],
        }
        self.container.repo.upsert_eval_event({
            "type": "eval.scored",
            "task_id": task_id,
            "item_id": item_id,
            "stage": "eval",
            "level": level,
            "message": f"商品 {item_id} 官方采集评估到 {score_display} ({eval_result.risk_level.value}) [数据质量: {eval_result.data_quality}]",
            "payload": json.dumps(payload, ensure_ascii=False, default=str),
        })
```

- [ ] **Step 4: Run service tests**

Run: `pytest tests/test_collection_service.py -q`

Expected: all tests pass.

## Task 3: Move Cookie Helper Into Service

**Files:**
- Modify: `backend/xianyu_hunter/modules/collection_service.py`
- Modify: `backend/xianyu_hunter/web/routes/api_evaluations.py`

- [ ] **Step 1: Copy official cookie check into service**

Move the body of `_ensure_official_collect_cookies(container)` from `api_evaluations.py` into `ItemCollectionService.ensure_official_cookies()`, replacing `container` with `self.container`.

The method signature remains:

```python
    async def ensure_official_cookies(self) -> None:
        container = self.container
        if not container.browser:
            return
        # existing cookie validation and JSON injection logic from api_evaluations.py
```

- [ ] **Step 2: Keep compatibility wrapper in `api_evaluations.py`**

Replace `_ensure_official_collect_cookies` body with:

```python
async def _ensure_official_collect_cookies(container: Container) -> None:
    from xianyu_hunter.modules.collection_service import ItemCollectionService

    await ItemCollectionService(container).ensure_official_cookies()
```

- [ ] **Step 3: Run cookie-related tests**

Run: `pytest tests/test_official_collect_integration.py tests/test_cookie_layer_sync_fix.py -q`

Expected: pass or only fail where mocks need route-to-service retargeting.

## Task 4: Route Delegation

**Files:**
- Modify: `backend/xianyu_hunter/web/routes/api_items.py`
- Modify: `backend/xianyu_hunter/web/routes/api_evaluations.py`
- Modify: `tests/test_official_collect_integration.py`

- [ ] **Step 1: Update `api_items.refresh_item`**

Replace the direct `collector.detail()` persistence block with service delegation:

```python
from xianyu_hunter.modules.collection_service import (
    CollectionError,
    CollectionMode,
    ItemCollectionService,
)

try:
    result = await asyncio.wait_for(
        ItemCollectionService(container).collect(
            item_id,
            task_id=task_id,
            mode=CollectionMode.DETAIL_ONLY,
            source="live",
        ),
        timeout=60.0,
    )
except asyncio.TimeoutError:
    raise HTTPException(
        status_code=504,
        detail="采集超时：浏览器实例异常或闲鱼反爬拦截，请稍后重试或重启服务",
    )
except CollectionError as e:
    raise HTTPException(status_code=e.status_code, detail=e.detail)

detail = result.detail
assert detail is not None
return {
    "ok": True,
    "item_id": item_id,
    "is_sold": detail.is_sold,
    "title": detail.title,
    "price": detail.price,
    "brand": detail.brand,
    "seller_id": detail.seller_id or "",
    "region": detail.region or "",
    "want_cnt": detail.want_cnt,
    "view_cnt": detail.view_cnt,
    "thumb_url": detail.thumb_url or "",
    "image_urls": detail.image_urls or [],
    "publish_time": detail.publish_time.isoformat() if detail.publish_time else None,
    "seller_nick": detail.detail_seller_nick or "",
    "seller_credit": detail.detail_credit_score,
}
```

- [ ] **Step 2: Update `_collect_official_and_evaluate`**

Replace the function body with:

```python
async def _collect_official_and_evaluate(
    container: Container,
    item_id: str,
    task_id: str | None = None,
) -> dict[str, Any]:
    from xianyu_hunter.modules.collection_service import (
        CollectionError,
        CollectionMode,
        ItemCollectionService,
    )

    try:
        result = await ItemCollectionService(container).collect(
            item_id,
            task_id=task_id,
            mode=CollectionMode.OFFICIAL_FULL,
            source="official",
        )
    except CollectionError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

    detail = result.detail
    seller = result.seller
    eval_result = result.evaluation
    if detail is None or eval_result is None:
        raise HTTPException(status_code=502, detail=f"官方采集 {item_id} 未返回完整结果")

    return {
        "ok": True,
        "item_id": item_id,
        "collected": True,
        "item": {
            "title": detail.title,
            "price": detail.price,
            "description": detail.description or "",
            "image_urls": detail.image_urls or [],
            "thumb_url": detail.thumb_url or "",
            "region": detail.region or "",
            "seller_id": detail.seller_id or "",
            "want_cnt": detail.want_cnt,
            "view_cnt": detail.view_cnt,
        },
        "seller": {
            "id": seller.id if seller else "",
            "nick": seller.nick if seller else "",
            "credit_score": seller.credit_score if seller else None,
            "register_days": seller.register_days if seller else 0,
            "on_sale_count": seller.on_sale_count if seller else 0,
            "sold_count": seller.sold_count if seller else 0,
        },
        "reviews": result.reviews,
        "evaluation": {
            "score": eval_result.score,
            "risk_level": eval_result.risk_level.value,
            "dimension_scores": eval_result.dimension_scores,
            "reject_reasons": eval_result.reject_reasons,
            "is_passed": eval_result.is_passed,
            "data_quality": eval_result.data_quality,
            "data_source": "official",
        },
    }
```

- [ ] **Step 3: Retarget official integration test mocks if needed**

Patch `tests/test_official_collect_integration.py` fixture to mock service review extraction instead of route extraction:

```python
with patch(
    "xianyu_hunter.modules.collection_service.ItemCollectionService.extract_reviews_from_page",
    new=AsyncMock(return_value=[]),
), patch(
    "xianyu_hunter.modules.collection_service.sync_item_display_from_detail",
    new=MagicMock(),
):
    yield
```

- [ ] **Step 4: Run route tests**

Run: `pytest tests/test_official_collect_integration.py tests/test_web_route_registration.py -q`

Expected: pass.

## Task 5: Batch Refresh Delegation

**Files:**
- Modify: `backend/xianyu_hunter/modules/batch_refresh_scheduler.py`
- Modify: `tests/test_batch_refresh_scheduler.py`

- [ ] **Step 1: Write failing scheduler delegation test**

Add to `tests/test_batch_refresh_scheduler.py`:

```python
async def test_batch_refresh_uses_collection_service(monkeypatch) -> None:
    items = [{"id": "i1", "task_id": "t1", "title": "old", "price": 50, "is_sold": 0}]
    container = _make_container(items=items, detail_map={})
    scheduler = BatchRefreshScheduler(container, _make_config())
    calls = []

    class FakeService:
        def __init__(self, received_container):
            assert received_container is container

        async def collect(self, item_id, **kwargs):
            calls.append((item_id, kwargs))
            return MagicMock(ok=True, changed_fields=["title"])

    monkeypatch.setattr(
        "xianyu_hunter.modules.batch_refresh_scheduler.ItemCollectionService",
        FakeService,
    )

    await scheduler._run_batch_async(task_id=1)

    assert calls[0][0] == "i1"
    assert calls[0][1]["mode"].value == "official_full"
    assert scheduler._change_log[0]["changed_fields"] == ["title"]
```

- [ ] **Step 2: Run failing scheduler test**

Run: `pytest tests/test_batch_refresh_scheduler.py::test_batch_refresh_uses_collection_service -q`

Expected: fail because `ItemCollectionService` is not imported in `batch_refresh_scheduler.py`.

- [ ] **Step 3: Update scheduler imports and `_refresh_one()`**

At top of `batch_refresh_scheduler.py`, add:

```python
from xianyu_hunter.modules.collection_service import (
    CollectionMode,
    ItemCollectionService,
)
```

Replace `_refresh_one()` body with:

```python
    async def _refresh_one(
        self, item_id: str, existing_item: dict
    ) -> list[str] | None:
        result = await asyncio.wait_for(
            ItemCollectionService(self._container).collect(
                item_id,
                task_id=str(existing_item.get("task_id") or ""),
                mode=CollectionMode.OFFICIAL_FULL,
                existing_item=existing_item,
                source="official",
            ),
            timeout=_DETAIL_TIMEOUT,
        )
        if not result.ok:
            return None
        return result.changed_fields
```

- [ ] **Step 4: Run batch refresh tests**

Run: `pytest tests/test_batch_refresh_scheduler.py -q`

Expected: pass after adjusting mocks that previously asserted direct `repo.upsert_item` calls.

## Task 6: Regression And Cleanup

**Files:**
- Modify only files touched in earlier tasks.

- [ ] **Step 1: Run targeted backend regression**

Run:

```powershell
pytest tests/test_collection_service.py tests/test_official_collect_integration.py tests/test_batch_refresh_scheduler.py tests/test_detail_extract_failure.py tests/test_web_route_registration.py -q
```

Expected: pass.

- [ ] **Step 2: Run import smoke test**

Run:

```powershell
python -m compileall backend/xianyu_hunter/modules/collection_service.py backend/xianyu_hunter/web/routes/api_items.py backend/xianyu_hunter/web/routes/api_evaluations.py backend/xianyu_hunter/modules/batch_refresh_scheduler.py
```

Expected: all files compile without syntax errors.

- [ ] **Step 3: Inspect diff for unrelated changes**

Run: `git diff --stat`

Expected: changed files are limited to the new service, service tests, route delegation, scheduler delegation, and necessary test updates. Existing unrelated dirty files remain untouched unless they are directly required by this implementation.

- [ ] **Step 4: Commit implementation**

Run:

```powershell
git add backend/xianyu_hunter/modules/collection_service.py backend/xianyu_hunter/web/routes/api_items.py backend/xianyu_hunter/web/routes/api_evaluations.py backend/xianyu_hunter/modules/batch_refresh_scheduler.py tests/test_collection_service.py tests/test_batch_refresh_scheduler.py tests/test_official_collect_integration.py
git commit -m "feat: unify item collection service"
```

Expected: commit succeeds with only implementation files staged.

## Self-Review

- Spec coverage: tasks cover service creation, old-value protection, official collection, route compatibility, batch refresh migration, and regression tests.
- Placeholder scan: no task leaves behavior undefined; implementation snippets name exact functions, paths, and commands.
- Type consistency: `CollectionMode`, `CollectionError`, `CollectionResult`, `ItemCollectionService.collect()`, and `merge_item_row()` are introduced before later tasks use them.
