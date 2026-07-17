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


class _FakeBrowserLock:
    def __init__(self, *, owned_by_current_task: bool = False) -> None:
        self.owned_by_current_task = owned_by_current_task
        self.acquire = AsyncMock()
        self.release = MagicMock()


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


@pytest.mark.asyncio
async def test_official_full_uses_low_priority_browser_lock_when_not_owned() -> None:
    page = MagicMock()
    page.close = AsyncMock()
    detail = ItemDetail(id="i1", title="title", price=99.0, seller_id="seller1")
    seller = SellerProfile(id="seller1", nick="seller", credit_score=700)
    container = MagicMock()
    container.browser_lock = _FakeBrowserLock(owned_by_current_task=False)
    container.browser.new_page = AsyncMock(return_value=page)
    container.collector.detail = AsyncMock(return_value=detail)
    container.collector.seller_profile = AsyncMock(return_value=seller)
    container.collector.seller_profile_fallback = MagicMock(return_value=seller)
    container.repo.get_item.return_value = {"id": "i1"}
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
    service.extract_reviews_from_page = AsyncMock(return_value=[])

    result = await service.collect("i1", task_id="t1", mode=CollectionMode.OFFICIAL_FULL)

    assert result.ok is True
    container.browser_lock.acquire.assert_awaited_once_with(priority="low")
    container.browser_lock.release.assert_called_once()


@pytest.mark.asyncio
async def test_official_full_does_not_reenter_browser_lock_when_already_owned() -> None:
    page = MagicMock()
    page.close = AsyncMock()
    detail = ItemDetail(id="i1", title="title", price=99.0, seller_id="seller1")
    seller = SellerProfile(id="seller1", nick="seller", credit_score=700)
    container = MagicMock()
    container.browser_lock = _FakeBrowserLock(owned_by_current_task=True)
    container.browser.new_page = AsyncMock(return_value=page)
    container.collector.detail = AsyncMock(return_value=detail)
    container.collector.seller_profile = AsyncMock(return_value=seller)
    container.collector.seller_profile_fallback = MagicMock(return_value=seller)
    container.repo.get_item.return_value = {"id": "i1"}
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
    service.extract_reviews_from_page = AsyncMock(return_value=[])

    result = await service.collect("i1", task_id="t1", mode=CollectionMode.OFFICIAL_FULL)

    assert result.ok is True
    container.browser_lock.acquire.assert_not_called()
    container.browser_lock.release.assert_not_called()


# ============== _refresh_token_and_retry_detail 两级自愈测试 ==============
# 背景：last_session_invalid 熔断标志未被重置导致重试被短路（已修复）；
# 增强：_m_h5_tk 刷新后重试仍失败时，从 cookie_store 强制注入完整 cookie 后再重试。


def _make_refresh_container(
    *,
    failure_reason: str = "home_title_redirect",
    session_invalid: bool = True,
    m5tk_refreshed: bool = True,
    first_retry_detail: Any = "__sentinel__",
    second_retry_detail: Any = "__sentinel__",
) -> tuple[MagicMock, ItemCollectionService]:
    """构造测试 _refresh_token_and_retry_detail 的 mock container

    Args:
        failure_reason: collector.last_detail_failure_reason 初始值
        session_invalid: collector.last_session_invalid 初始值
        m5tk_refreshed: _ensure_fresh_m5tk 返回 True(已刷新)/False(跳过)
        first_retry_detail: 第一级重试（_m_h5_tk 刷新后）的 detail 返回值；
                            "__sentinel__" 表示返回 None（失败），None 也表示失败
        second_retry_detail: 第二级重试（cookie 重新注入后）的 detail 返回值
    """
    container = MagicMock()
    container.collector = MagicMock()
    container.collector.last_detail_failure_reason = failure_reason
    container.collector.last_session_invalid = session_invalid
    container.collector._ensure_fresh_m5tk = AsyncMock(return_value=m5tk_refreshed)

    refresh_page = MagicMock()
    refresh_page.close = AsyncMock()
    container.browser.new_page = AsyncMock(return_value=refresh_page)

    detail_call_count = 0

    async def detail_side_effect(item_id: str, page: Any = None) -> Any:
        nonlocal detail_call_count
        detail_call_count += 1
        # 模拟 _detail.py:781-784 的短路逻辑：last_session_invalid=True 时直接返回 None
        if getattr(container.collector, "last_session_invalid", False):
            container.collector.last_detail_failure_reason = "home_title_redirect"
            return None
        # 第 1 次调用 = 第一级重试
        if detail_call_count == 1:
            if first_retry_detail != "__sentinel__":
                return first_retry_detail
            # 失败：再次标记会话失效
            container.collector.last_session_invalid = True
            container.collector.last_detail_failure_reason = "home_title_redirect"
            return None
        # 第 2 次调用 = 第二级重试（cookie 重新注入后）
        if second_retry_detail != "__sentinel__":
            return second_retry_detail
        container.collector.last_session_invalid = True
        container.collector.last_detail_failure_reason = "home_title_redirect"
        return None

    container.collector.detail = AsyncMock(side_effect=detail_side_effect)

    service = ItemCollectionService(container)
    # mock 第二级自愈的依赖方法，避免真实 cookie_store 调用
    service._force_reinject_cookies_from_store = AsyncMock()
    service._log_cookie_diagnostics = AsyncMock()
    return container, service


@pytest.mark.asyncio
async def test_refresh_token_resets_session_invalid_before_retry() -> None:
    """修复验证：刷新 token 前必须重置 last_session_invalid=False

    为什么需要：detail() 入口(_detail.py:781-784)检查 last_session_invalid，
    为 True 时直接短路返回 None。若不重置，刷新 _m_h5_tk 后的重试根本不会
    发起 HTTP 请求，重试形同虚设（用户看到"已强制刷新"日志但仍然失败）。
    """
    expected_detail = ItemDetail(id="i1", title="成功", price=99.0)
    container, service = _make_refresh_container(
        session_invalid=True,
        m5tk_refreshed=True,
        first_retry_detail=expected_detail,
    )

    result = await service._refresh_token_and_retry_detail("i1", reuse_page=MagicMock())

    # 第一级重试成功，不需要走第二级
    assert result is not None, "重试应返回有效 detail，而非被 last_session_invalid 短路"
    assert result.id == "i1"
    assert container.collector.detail.await_count == 1
    service._force_reinject_cookies_from_store.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_token_second_level_heal_succeeds() -> None:
    """两级自愈：_m_h5_tk 刷新后重试失败，cookie 重新注入后重试成功

    场景：身份 cookie 服务端失效，_m_h5_tk 刷新无济于事（第一级失败），
    但从 cookie_store 重新注入完整 cookie 后会话恢复（第二级成功）。
    """
    expected_detail = ItemDetail(id="i1", title="cookie注入后成功", price=99.0)
    container, service = _make_refresh_container(
        session_invalid=True,
        m5tk_refreshed=True,
        first_retry_detail=None,  # 第一级失败
        second_retry_detail=expected_detail,  # 第二级成功
    )

    result = await service._refresh_token_and_retry_detail("i1", reuse_page=MagicMock())

    assert result is not None, "cookie 重新注入后应重试成功"
    assert result.id == "i1"
    # detail 被调用 2 次：第一级 + 第二级
    assert container.collector.detail.await_count == 2
    # cookie 重新注入被调用 1 次
    service._force_reinject_cookies_from_store.assert_awaited_once()
    # 诊断日志不应被调用（因为最终成功了）
    service._log_cookie_diagnostics.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_token_both_levels_fail_logs_diagnostics() -> None:
    """两级自愈均失败时记录诊断日志，便于定位根因

    场景：_m_h5_tk 刷新失败 + cookie 重新注入也失败 → 服务端会话彻底失效，
    需用户重新登录。诊断日志记录身份 cookie 状态，帮助区分"cookie 缺失"
    还是"cookie 完整但服务端拒绝"。
    """
    container, service = _make_refresh_container(
        session_invalid=True,
        m5tk_refreshed=True,
        first_retry_detail=None,   # 第一级失败
        second_retry_detail=None,  # 第二级也失败
    )

    result = await service._refresh_token_and_retry_detail("i1", reuse_page=MagicMock())

    assert result is None, "两级自愈均失败时应返回 None"
    assert container.collector.detail.await_count == 2
    service._force_reinject_cookies_from_store.assert_awaited_once()
    # 诊断日志应被调用，记录 cookie 状态便于排查
    service._log_cookie_diagnostics.assert_awaited_once_with("i1")


@pytest.mark.asyncio
async def test_refresh_token_skips_when_reason_not_home_title_redirect() -> None:
    """非 home_title_redirect 原因直接返回 None，不刷新 token 也不重试

    为什么：page_closed/http_status_error 等原因与 token 无关，刷新 _m_h5_tk 无意义。
    """
    container, service = _make_refresh_container(
        failure_reason="page_closed",
        session_invalid=False,
    )

    result = await service._refresh_token_and_retry_detail("i1", reuse_page=MagicMock())

    assert result is None
    container.collector._ensure_fresh_m5tk.assert_not_awaited()
    container.collector.detail.assert_not_awaited()
    service._force_reinject_cookies_from_store.assert_not_awaited()
