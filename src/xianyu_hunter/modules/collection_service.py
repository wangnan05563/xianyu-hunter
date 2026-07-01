"""Shared item collection service.

This module centralizes the merge and persistence rules used by manual refresh,
official collection, and scheduled batch refresh.
"""
from __future__ import annotations

import json
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from xianyu_hunter.domain.evaluation import EvalResult, RiskLevel
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

_OFFICIAL_COLLECT_IDENTITY_COOKIES = ("cookie2", "sgcookie", "unb")


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
        del evaluate
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
        container = self.container
        if not getattr(container, "browser", None):
            return

        async def get_cookies() -> list[dict]:
            try:
                return await container.browser.get_cookies()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to read browser cookies: {}", exc)
                return []

        def cookie_by_name(cookies: list[dict]) -> dict[str, dict]:
            return {
                str(cookie.get("name") or ""): cookie
                for cookie in cookies
                if str(cookie.get("name") or "")
            }

        def expired_identity_cookies(cookies_by_name: dict[str, dict]) -> list[str]:
            now = datetime.now(timezone.utc).timestamp()
            expired: list[str] = []
            for name in _OFFICIAL_COLLECT_IDENTITY_COOKIES:
                cookie = cookies_by_name.get(name)
                if not cookie:
                    continue
                expires = cookie.get("expires", -1)
                if expires > 0 and expires < now:
                    expired.append(name)
            return expired

        from xianyu_hunter.web.services.cookie_store import get_cookie_store, is_test_cookie

        def cookies_from_json() -> tuple[list[dict], dict[str, str]]:
            store = get_cookie_store()
            store.invalidate_cache()
            json_data = store._read_json()
            if not json_data or not json_data.get("cookies"):
                return [], {}

            pw_cookies: list[dict] = []
            identity_values: dict[str, str] = {}
            for cookie in json_data["cookies"]:
                name = str(cookie.get("name") or "")
                value = str(cookie.get("value") or "")
                if not name or not value:
                    continue
                if is_test_cookie(name, value):
                    logger.warning("Official collection skipped test cookie {}={}", name, value)
                    continue

                item = {
                    "name": name,
                    "value": value,
                    "domain": cookie.get("domain") or ".goofish.com",
                    "path": cookie.get("path") or "/",
                }
                expires = cookie.get("expires", -1)
                if expires and expires > 0:
                    item["expires"] = expires
                pw_cookies.append(item)
                if name in _OFFICIAL_COLLECT_IDENTITY_COOKIES:
                    identity_values[name] = value
            return pw_cookies, identity_values

        async def cookie_issues(json_identity_values: dict[str, str]) -> tuple[list[str], list[str], list[str]]:
            cookies_by_name = cookie_by_name(await get_cookies())
            missing = [name for name in _OFFICIAL_COLLECT_IDENTITY_COOKIES if name not in cookies_by_name]
            expired = expired_identity_cookies(cookies_by_name)
            stale = [
                name for name, value in json_identity_values.items()
                if name in cookies_by_name and cookies_by_name[name].get("value") != value
            ]
            return missing, expired, stale

        pw_cookies, json_identity_values = cookies_from_json()
        missing, expired, stale = await cookie_issues(json_identity_values)
        if not missing and not expired and not stale:
            return

        if pw_cookies:
            logger.info(
                "Official collection injecting CookieStore cookies: missing={}, expired={}, stale={}",
                missing,
                expired,
                stale,
            )
            try:
                success = await container.browser.add_cookies(pw_cookies)
                if success:
                    try:
                        from xianyu_hunter.modules.login_orchestrator import sync_cookie_layers_from_json

                        sync_cookie_layers_from_json()
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("Failed to sync cookie layer state after injection: {}", exc)
                else:
                    logger.warning("CookieStore injection did not pass key cookie verification")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to inject CookieStore cookies: {}", exc)

        missing, expired, stale = await cookie_issues(json_identity_values)
        if expired:
            raise CollectionError(
                440,
                f"Xianyu login cookies expired ({', '.join(expired)}), please login again",
            )
        if stale:
            raise CollectionError(
                440,
                f"Xianyu login cookies are stale in worker browser ({', '.join(stale)}), please login again",
            )
        if missing:
            raise CollectionError(
                403,
                f"Xianyu login cookies are incomplete (missing {', '.join(missing)}), please login again",
            )

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

    async def _collect_detail_only(
        self,
        item_id: str,
        *,
        task_id: str | None,
        existing_item: dict[str, Any] | None,
        source: str,
        reuse_page: Any | None,
    ) -> CollectionResult:
        await self._sync_detail_cookies()
        detail = await self.container.collector.detail(item_id, page=reuse_page)
        if detail is None:
            raise CollectionError(
                502,
                "Failed to collect item detail: page unavailable or login expired",
                item_id=item_id,
            )

        old_item = existing_item if existing_item is not None else (self.container.repo.get_item(item_id) or {})
        effective_task_id = str(old_item.get("task_id") or task_id or "")
        incoming = self._item_row_from_detail(item_id, detail, effective_task_id)
        is_delisted = bool(detail.is_sold and not detail.title)
        changed_fields = self.diff_fields(old_item, incoming)

        if not (is_delisted and old_item):
            self.container.repo.upsert_item(merge_item_row(old_item, incoming))
        if detail.is_sold:
            self.container.repo.mark_sold(item_id)
        if effective_task_id and not is_delisted:
            sync_item_display_from_detail(
                self.container.repo,
                effective_task_id,
                item_id,
                detail,
                source="auto",
            )
        self._update_data_source(item_id, source)

        return CollectionResult(
            ok=True,
            item_id=item_id,
            mode=CollectionMode.DETAIL_ONLY,
            detail=detail,
            changed_fields=changed_fields,
        )

    async def _sync_detail_cookies(self) -> None:
        try:
            from xianyu_hunter.web.services.cookie_runtime_sync import (
                inject_cookie_store_to_worker_browser,
            )

            await inject_cookie_store_to_worker_browser(
                "item detail refresh cookie sync",
                force_refresh_m5tk=False,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Detail collection cookie sync failed: {}", exc)

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
                raise CollectionError(
                    410,
                    f"Failed to collect item {item_id}: detail page unavailable or item removed",
                    item_id=item_id,
                )

            async def safe_seller_profile() -> SellerProfile | None:
                if not detail or not detail.seller_id:
                    return None
                try:
                    return await self.container.collector.seller_profile(detail.seller_id)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to collect seller profile seller={}: {}", detail.seller_id, exc)
                    return None

            reviews, seller = await asyncio.gather(
                self.extract_reviews_from_page(page),
                safe_seller_profile(),
            )
        finally:
            if own_page:
                await page.close()

        if detail is None:
            raise CollectionError(410, f"Failed to collect item {item_id}: no detail returned", item_id=item_id)
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
            sync_item_display_from_detail(
                self.container.repo,
                effective_task_id,
                item_id,
                detail,
                source="auto",
            )

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
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to update data_source={} item={}: {}", source, item_id, exc)

    def _resolve_task_id(self, item_id: str, task_id: str | None, old_item: dict[str, Any]) -> str:
        if task_id:
            return task_id
        try:
            payload = self.container.repo.get_eval_payload_by_item(item_id)
        except Exception:  # noqa: BLE001
            payload = None
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
        try:
            self.container.repo.upsert_seller({
                "id": seller.id,
                "nick": seller.nick or "",
                "credit_score": seller.credit_score,
                "register_days": seller.register_days,
                "on_sale_count": seller.on_sale_count,
                "sold_count": seller.sold_count,
                "last_visited": datetime.now(timezone.utc),
            })
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to upsert seller seller={}: {}", seller.id, exc)

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
        if eval_result.is_passed:
            level = "info"
        elif eval_result.risk_level != RiskLevel.EXTREME:
            level = "warn"
        else:
            level = "err"
        if eval_result.risk_level == RiskLevel.UNKNOWN:
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
        try:
            self.container.repo.upsert_eval_event({
                "type": "eval.scored",
                "task_id": task_id,
                "item_id": item_id,
                "stage": "eval",
                "level": level,
                "message": (
                    f"Item {item_id} official collection score {score_display} "
                    f"({eval_result.risk_level.value}) [data_quality: {eval_result.data_quality}]"
                ),
                "payload": json.dumps(payload, ensure_ascii=False, default=str),
            })
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to upsert evaluation event item={}: {}", item_id, exc)

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
