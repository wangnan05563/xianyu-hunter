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
from typing import Any, Callable

from xianyu_hunter.domain.evaluation import EvalResult, RiskLevel
from xianyu_hunter.domain.events import Event, EventType
from xianyu_hunter.domain.item import ItemDetail
from xianyu_hunter.domain.seller import SellerProfile
from xianyu_hunter.infra.item_display_sync import sync_item_display_from_detail
from xianyu_hunter.infra.logger import get_logger
from xianyu_hunter.modules.evaluator import PriceRange

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

# 详情页 SPA 渲染必需的非身份 cookie（基于完整 22 个 cookie 集推断）
# 为什么这些 cookie 必需：闲鱼详情页 SPA 依赖 cna/tracknick/_tb_token_/t 等
# 追踪/会话 cookie 进行风控、CSRF 校验和卖家信息渲染，仅身份 cookie 不足以维持详情页会话
_DETAIL_SESSION_COOKIES = {"cna", "tracknick", "_tb_token_", "t", "tfstk"}
# Cookie 完整性判断的最低总数阈值（22 个完整集 vs 4 个不完整集，阈值 10 居中）
_DETAIL_COOKIE_MIN_COUNT = 10
# 详情页必需 cookie 的最低命中数量（5 个中至少命中 3 个才算完整）
_DETAIL_SESSION_MIN_HITS = 3


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

    async def _get_browser_cookies(self) -> list[dict]:
        """读取浏览器当前 cookie，失败时降级为空列表避免阻塞后续校验"""
        try:
            return await self.container.browser.get_cookies()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to read browser cookies: {}", exc)
            return []

    @staticmethod
    def _cookies_indexed_by_name(cookies: list[dict]) -> dict[str, dict]:
        """以 name 为键构建索引，便于 O(1) 查找指定 cookie"""
        return {
            str(cookie.get("name") or ""): cookie
            for cookie in cookies
            if str(cookie.get("name") or "")
        }

    @staticmethod
    def _expired_identity_cookies(cookies_by_name: dict[str, dict]) -> list[str]:
        """筛查身份 cookie 中已过期项；expires<=0 视为会话级 cookie 不参与判断"""
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

    @staticmethod
    def _is_valid_cookie(name: str, value: str, is_test_fn) -> bool:
        """校验 cookie 是否有效（非空且非测试 cookie）

        拆分自 _read_cookies_from_store：将 name/value 判空 + 测试 cookie 校验
        收敛到单一函数，降低主循环的认知复杂度（S3776）。"""
        if not name or not value:
            return False
        if is_test_fn(name, value):
            logger.warning("Official collection skipped test cookie {}={}", name, value)
            return False
        return True

    @staticmethod
    def _build_pw_cookie(name: str, value: str, cookie: dict) -> dict:
        """构建 Playwright 格式的 cookie 对象

        拆分自 _read_cookies_from_store：将字段组装 + expires 条件判断
        收敛到单一函数，降低主循环的嵌套层级（S3776）。"""
        item = {
            "name": name,
            "value": value,
            "domain": cookie.get("domain") or ".goofish.com",
            "path": cookie.get("path") or "/",
        }
        expires = cookie.get("expires", -1)
        if expires and expires > 0:
            item["expires"] = expires
        return item

    def _read_cookies_from_store(self) -> tuple[list[dict], dict[str, str]]:
        """从 CookieStore 读取 cookie，转换为 Playwright 格式

        返回 (pw_cookies, identity_values)：
        - pw_cookies 用于注入浏览器
        - identity_values 仅包含身份 cookie 的值，用于后续 staleness 校验
        延迟导入避免 web.services 模块在采集路径上提前加载

        重构说明：将 cookie 校验和格式构建下沉到独立静态方法（S3776），
        主循环只做迭代与分发，降低嵌套层级与认知负担。
        """
        from xianyu_hunter.web.services.cookie_store import get_cookie_store, is_test_cookie

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
            if not self._is_valid_cookie(name, value, is_test_cookie):
                continue

            pw_cookies.append(self._build_pw_cookie(name, value, cookie))
            if name in _OFFICIAL_COLLECT_IDENTITY_COOKIES:
                identity_values[name] = value
        return pw_cookies, identity_values

    async def _check_cookie_issues(
        self, json_identity_values: dict[str, str]
    ) -> tuple[list[str], list[str], list[str]]:
        """汇总身份 cookie 的三类问题：缺失/过期/浏览器侧值与 store 不一致"""
        cookies_by_name = self._cookies_indexed_by_name(await self._get_browser_cookies())
        missing = [name for name in _OFFICIAL_COLLECT_IDENTITY_COOKIES if name not in cookies_by_name]
        expired = self._expired_identity_cookies(cookies_by_name)
        stale = [
            name for name, value in json_identity_values.items()
            if name in cookies_by_name and cookies_by_name[name].get("value") != value
        ]
        return missing, expired, stale

    async def _check_detail_cookie_completeness(self) -> str | None:
        """检查浏览器 cookie 完整性，返回错误信息或 None

        为什么需要预检：collector.detail() 返回 None 时，上游无法区分是 cookie 失效
        还是页面不可用。预检 cookie 完整性可以在 detail() 调用前识别 cookie 问题，
        给出明确的 401 错误，而非含糊的 502（v4.5 错误语义准确性规则）。

        判断依据（任一命中即视为不完整）：
        1. cookie 总数 < 10：22 个完整集 vs 4 个不完整集，阈值 10 居中
        2. 详情页必需 cookie（cna/tracknick/_tb_token_/t/tfstk）命中数 < 3：
           仅身份 cookie 不足以维持详情页 SPA 会话

        Returns:
            None 表示 cookie 完整；str 表示错误信息（含具体缺失情况，便于用户排查）
        """
        cookies = await self._get_browser_cookies()
        cookie_names = {c.get("name", "") for c in cookies}
        identity_found = set(_OFFICIAL_COLLECT_IDENTITY_COOKIES) & cookie_names
        session_found = _DETAIL_SESSION_COOKIES & cookie_names

        if len(cookies) >= _DETAIL_COOKIE_MIN_COUNT and len(session_found) >= _DETAIL_SESSION_MIN_HITS:
            return None

        return (
            f"闲鱼登录 Cookie 不完整（共 {len(cookies)} 个，"
            f"身份 Cookie {sorted(identity_found)} 存在，"
            f"会话 Cookie {sorted(session_found)} 不足），"
            f"请重新登录或从浏览器导出完整 Cookie 导入"
        )

    async def ensure_official_cookies(self) -> None:
        """确保浏览器有最新的官方采集 cookie

        重构说明：cookie 注入和错误映射下沉到独立私有方法（S3776）。
        """
        container = self.container
        if not getattr(container, "browser", None):
            return

        pw_cookies, json_identity_values = self._read_cookies_from_store()
        missing, expired, stale = await self._check_cookie_issues(json_identity_values)
        if not missing and not expired and not stale:
            return

        if pw_cookies:
            await self._inject_cookies_from_store(
                container, pw_cookies, missing, expired, stale
            )

        # 注入后重新检查，仍存在问题则抛错
        missing, expired, stale = await self._check_cookie_issues(json_identity_values)
        self._raise_cookie_errors(missing, expired, stale)

    async def _inject_cookies_from_store(
        self,
        container: Any,
        pw_cookies: list[dict],
        missing: list[str],
        expired: list[str],
        stale: list[str],
    ) -> None:
        """注入 CookieStore cookie 到浏览器，失败仅记日志不抛异常

        为什么失败不抛：注入失败后由后续 _raise_cookie_errors 根据 cookie 实际状态
        决定是否抛 440/403，避免注入层与校验层重复决策。
        """
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

    @staticmethod
    def _raise_cookie_errors(
        missing: list[str], expired: list[str], stale: list[str]
    ) -> None:
        """根据 cookie 问题类型抛对应 CollectionError

        优先级：expired > stale > missing，先抛最严重的（需重新登录）。
        """
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
        """detail-only 模式采集

        重构说明：token 重试、错误映射、持久化下沉到独立私有方法（S3776）。
        """
        await self._sync_detail_cookies()
        # cookie 完整性预检：detail() 返回 None 时上游无法区分原因，
        # 预检可在调用前识别 cookie 不完整问题，给出 401 而非含糊的 502
        cookie_issue = await self._check_detail_cookie_completeness()
        if cookie_issue:
            raise CollectionError(401, cookie_issue, item_id=item_id)

        detail = await self.container.collector.detail(item_id, page=reuse_page)

        # token 失效自动重试：home_title_redirect 通常是 _m_h5_tk 过期被重定向到首页
        # 强制刷新 token 后重试一次，避免用户因偶发 token 过期看到 502
        if detail is None:
            detail = await self._refresh_token_and_retry_detail(item_id, reuse_page)

        if detail is None:
            # _raise_detail_failure_error 总是抛异常，不会返回
            await self._raise_detail_failure_error(item_id)

        return self._persist_detail_collection(
            item_id, detail, task_id=task_id, existing_item=existing_item, source=source
        )

    async def _refresh_token_and_retry_detail(
        self, item_id: str, reuse_page: Any
    ) -> ItemDetail | None:
        """token 失效时强制刷新 _m_h5_tk 后重试 detail

        仅在 last_detail_failure_reason == home_title_redirect 时尝试，
        其他失败原因直接返回 None 由调用方走错误映射。
        """
        reason = getattr(self.container.collector, "last_detail_failure_reason", "") or ""
        if reason != "home_title_redirect" or self.container.collector is None:
            return None
        try:
            refresh_page = await self.container.browser.new_page()
            try:
                await self.container.collector._ensure_fresh_m5tk(refresh_page, force=True)
            finally:
                try:
                    await refresh_page.close()
                except Exception:
                    pass
            logger.info("token 失效，已强制刷新 _m_h5_tk 后重试 item={}", item_id)
            return await self.container.collector.detail(item_id, page=reuse_page)
        except Exception as exc:  # noqa: BLE001
            logger.warning("token 刷新重试失败 item={}: {}", item_id, exc)
            return None

    async def _raise_detail_failure_error(self, item_id: str) -> None:
        """detail 失败后根据 reason 映射到对应 status_code 并抛 CollectionError

        为什么这么做：所有失败都抛 502 会让用户无法判断是该重登录、该等待还是该手动验证。
        总是抛异常，不会正常返回。
        """
        # detail 失败后再次检查 cookie 完整性：cookie 不完整时给 401 而非 502
        cookie_issue = await self._check_detail_cookie_completeness()
        if cookie_issue:
            raise CollectionError(401, cookie_issue, item_id=item_id)

        reason = getattr(self.container.collector, "last_detail_failure_reason", "") or "unknown"
        if reason in ("home_title_redirect", "login_redirect"):
            # cookie 失效或 _m_h5_tk token 过期，需用户重新登录
            raise CollectionError(
                401,
                "采集失败：登录态失效或 _m_h5_tk token 过期，请重新登录或导入完整 Cookie",
                item_id=item_id,
            )
        if reason == "verify_redirect":
            # 反爬验证码拦截，需用户手动完成验证
            raise CollectionError(
                429,
                "采集失败：触发闲鱼反爬验证码，请手动完成验证后重试",
                item_id=item_id,
            )
        if reason in ("page_closed", "target_closed_exception"):
            # 页面被并发清理关闭，临时性故障，用户可重试
            raise CollectionError(
                503,
                "采集失败：浏览器页面被并发清理关闭，请稍后重试",
                item_id=item_id,
            )
        # 其他原因（http_status_error / title_extraction_failed /
        # price_extraction_failed / redirected_away_from_item / unknown）
        raise CollectionError(
            502,
            f"采集失败：详情页不可用或网络异常（reason={reason}），请稍后重试",
            item_id=item_id,
        )

    def _persist_detail_collection(
        self,
        item_id: str,
        detail: ItemDetail,
        *,
        task_id: str | None,
        existing_item: dict[str, Any] | None,
        source: str,
    ) -> CollectionResult:
        """持久化 detail 采集结果：upsert item、标记售出、同步 display"""
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
        """official-full 模式采集

        重构说明：detail+seller 采集、持久化、价格门禁、评估通知下沉到独立私有方法（S3776）。
        """
        await self.ensure_official_cookies()
        own_page = reuse_page is None
        page = reuse_page or await self.container.browser.new_page()
        # own_page 时注册为外部 page，防止与 TaskScheduler.run_once 的 close_all_pages 并发时被误关
        # 为什么需要在此处 register：detail(item_id, page=page) 走 own_page=False 分支，
        # 不会自动 register；不注册会导致 close_all_pages 把此 page 当残留页面关闭，
        # 在 detail 内 await 期间触发 TargetClosedError（_detail.py:766 已降级为 WARNING）
        if own_page:
            self.container.browser.register_external_page(page)
        try:
            detail, seller, reviews = await self._collect_detail_and_seller(item_id, page)
        finally:
            if own_page:
                # 先 unregister 再 close：close 后 page 引用仍留在 _external_pages 会泄漏
                self.container.browser.unregister_external_page(page)
                await page.close()

        if seller is None:
            seller = self.container.collector.seller_profile_fallback(None, detail)
        else:
            self._merge_detail_seller_fields(seller, detail)

        _, effective_task_id, changed_fields = self._persist_official_collection(
            item_id, detail, seller, task_id=task_id, existing_item=existing_item, source=source
        )

        eval_result = self._evaluate_and_notify(
            item_id, detail, seller, reviews, effective_task_id
        )

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

    async def _collect_detail_and_seller(
        self, item_id: str, page: Any
    ) -> tuple[ItemDetail, SellerProfile | None, list[str]]:
        """采集 detail + seller + reviews，detail 不可用时抛 CollectionError(410)"""
        detail = await self.container.collector.detail(item_id, page=page)
        if detail is None:
            raise CollectionError(
                410,
                f"Failed to collect item {item_id}: detail page unavailable or item removed",
                item_id=item_id,
            )
        reviews, seller = await asyncio.gather(
            self.extract_reviews_from_page(page),
            self._safe_seller_profile(detail),
        )
        return detail, seller, reviews

    async def _safe_seller_profile(self, detail: ItemDetail) -> SellerProfile | None:
        """采集 seller profile，失败时返回 None 不阻塞主流程"""
        if not detail or not detail.seller_id:
            return None
        try:
            return await self.container.collector.seller_profile(detail.seller_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to collect seller profile seller={}: {}", detail.seller_id, exc)
            return None

    def _persist_official_collection(
        self,
        item_id: str,
        detail: ItemDetail,
        seller: SellerProfile | None,
        *,
        task_id: str | None,
        existing_item: dict[str, Any] | None,
        source: str,
    ) -> tuple[dict[str, Any], str, list[str]]:
        """持久化 official 采集结果：upsert item、seller、display sync

        返回 (old_item, effective_task_id, changed_fields) 供调用方构建 CollectionResult。
        """
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
        return old_item, effective_task_id, changed_fields

    def _evaluate_and_notify(
        self,
        item_id: str,
        detail: ItemDetail,
        seller: SellerProfile | None,
        reviews: list[str],
        effective_task_id: str,
    ) -> EvalResult:
        """评估 + 通知：价格门禁通过时写入 eval 事件并发布 EVAL_PASSED

        价格门禁：与 worker.py 搜索流水线一致，超范围商品不写入 eval.scored 事件。
        为什么仍调用 evaluator.evaluate：官方采集弹窗需展示评估分给用户，
        但超范围商品不应进入评估明细菜单（list_evaluations 的价格过滤会二次兜底）。
        """
        price_range = self._price_range_for_task(item_id, effective_task_id)
        if price_range is None:
            eval_result = self.container.evaluator.evaluate(detail, seller)
        else:
            eval_result = self.container.evaluator.evaluate(
                detail, seller, price_range=price_range
            )
        price_filtered = self._check_price_filter(item_id, detail, effective_task_id)
        if not effective_task_id or price_filtered:
            return eval_result
        self._save_eval_event(effective_task_id, item_id, detail, seller, reviews, eval_result)
        # 评估通过才发 EVAL_PASSED，与 worker.py 第 320 行 should_pass 判定语义一致
        # 为什么放在 _save_eval_event 之后：事件落库用于时间线/审计，通知是独立通道，
        # 二者解耦避免通知失败阻塞事件写入；通知失败仅 warning 不影响主流程
        if eval_result.is_passed:
            self._publish_eval_passed_event(
                effective_task_id, item_id, detail, seller, eval_result
            )
        return eval_result

    def _price_range_for_task(self, item_id: str, effective_task_id: str) -> PriceRange | None:
        if not effective_task_id:
            return None
        try:
            task_raw = self.container.repo.get_task(effective_task_id)
            if not task_raw:
                return None
            price_strategy = self.container.build_task_price_strategy(task_raw)
            return PriceRange.from_price_config(getattr(price_strategy, "config", None))
        except Exception as e:
            logger.warning("官方采集评分价格区间读取失败 item_id={}: {}", item_id, e)
            return None

    def _check_price_filter(
        self, item_id: str, detail: ItemDetail, effective_task_id: str
    ) -> bool:
        """价格门禁检查：超范围商品返回 True（过滤 eval 事件写入）"""
        if not effective_task_id:
            return False
        try:
            task_raw = self.container.repo.get_task(effective_task_id)
            if not task_raw:
                return False
            ps = self.container.build_task_price_strategy(task_raw)
            verdict = ps.check(detail, market=None)
            if not verdict.pass_:
                logger.info(
                    "官方采集跳过 eval 事件写入: item_id={}, price={}, reasons={}",
                    item_id, detail.price, verdict.reasons,
                )
                return True
            return False
        except Exception as e:
            logger.warning("官方采集价格门禁检查失败 item_id={}: {}", item_id, e)
            return False

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

    def _publish_eval_passed_event(
        self,
        task_id: str,
        item_id: str,
        detail: ItemDetail,
        seller: SellerProfile | None,
        eval_result: EvalResult,
    ) -> None:
        """官方采集评估通过 → 触发 EVAL_PASSED 事件，让 NotifierHub 等订阅者推送通知

        为什么独立方法而非复用 worker._publish_eval_passed_event：
        - worker 方法绑定 self.task / self.event_bus，无法跨模块复用
        - 官方采集路径走 container.event_bus，与 worker 的 bus 实例一致（同一 DI 容器）
        - payload 字段与 worker._publish_eval_passed_event 完全对齐，保证模板渲染一致

        为什么用 publish_nowait 而非 await publish：
        - 调用方 _collect_official_and_evaluate 虽是 async，但通知是 fire-and-forget
        - 同步入队避免阻塞评估主流程，事件由 EventBus.run_forever 异步消费
        """
        bus = getattr(self.container, "event_bus", None)
        if bus is None:
            return
        try:
            bus.publish_nowait(
                Event(
                    type=EventType.EVAL_PASSED,
                    task_id=task_id,
                    item_id=item_id,
                    payload={
                        "item_id": item_id,
                        "item_title": detail.title,
                        "item_price": detail.price,
                        "thumb_url": getattr(detail, "thumb_url", ""),
                        "region": getattr(detail, "region", ""),
                        "seller_id": detail.seller_id or "",
                        "seller_nick": seller.nick if seller else "",
                        "score": eval_result.score,
                        "risk_level": eval_result.risk_level.value,
                        "data_quality": eval_result.data_quality,
                        "reject_reasons": eval_result.reject_reasons or [],
                        "data_source": "official",
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to publish EVAL_PASSED item={}: {}", item_id, exc)

    @staticmethod
    def _diff_field_price(old: Any, new: Any) -> bool:
        """价格字段比较：浮点比较，解析失败视为变化

        提取为独立比较函数：消除 diff_fields 中 if-elif 多分支，
        降低认知复杂度（S3776）。
        """
        try:
            return float(old or 0) != float(new or 0)
        except (TypeError, ValueError):
            return True

    @staticmethod
    def _diff_field_int(old: Any, new: Any) -> bool:
        """整数字段比较（want_cnt/view_cnt/is_sold）

        提取为独立比较函数：消除 diff_fields 中 if-elif 多分支，
        降低认知复杂度（S3776）。
        """
        return int(old or 0) != int(new or 0)

    @staticmethod
    def _diff_field_str(old: Any, new: Any) -> bool:
        """字符串字段比较（title/seller_id/region/thumb_url 等）

        提取为独立比较函数：消除 diff_fields 中 if-elif 多分支，
        降低认知复杂度（S3776）。
        """
        return (old or "") != (new or "")

    @staticmethod
    def _get_field_comparer(field_name: str) -> Callable[[Any, Any], bool]:
        """根据字段名返回对应的比较函数（查表法）

        用字典映射替代 if-elif-else 多分支，将字段类型判断
        从循环体中分离，降低 diff_fields 的认知复杂度（S3776）。
        """
        int_fields = {"want_cnt", "view_cnt", "is_sold"}
        if field_name == "price":
            return ItemCollectionService._diff_field_price
        if field_name in int_fields:
            return ItemCollectionService._diff_field_int
        return ItemCollectionService._diff_field_str

    @staticmethod
    def diff_fields(existing: dict[str, Any], incoming: dict[str, Any]) -> list[str]:
        """对比两个商品字典，返回发生变化的字段名列表

        重构说明：原函数 CC=20，循环内 if-elif-else 四级分支。
        通过 _get_field_comparer 查表法替代多分支，
        主循环简化为"取比较器→比较→记录"三步线性逻辑，
        显著降低认知复杂度。
        """
        fields = [
            "title", "price", "seller_id", "region",
            "want_cnt", "view_cnt", "thumb_url", "is_sold",
        ]
        changed: list[str] = []
        for field_name in fields:
            old = existing.get(field_name)
            new = incoming.get(field_name)
            comparer = ItemCollectionService._get_field_comparer(field_name)
            if comparer(old, new):
                changed.append(field_name)
        return changed
