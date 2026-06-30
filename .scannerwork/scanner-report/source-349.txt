"""官方采集+评估集成测试

回归测试：验证 api_evaluations._collect_official_and_evaluate 的核心行为：
1. _coalesce 旧值保留策略：新值为空时保留旧值（避免半残数据覆盖本地有效数据）
2. _ALWAYS_OVERWRITE 白名单字段强制覆盖（采集时刻+来源信息应优先更新）
3. 采集成功后 events.payload.data_source='official' 标记写入

实现说明：
- _coalesce / _is_blank / _ALWAYS_OVERWRITE 是 _collect_official_and_evaluate
  内的闭包/局部变量，无法直接 import。通过调用 _collect_official_and_evaluate
  并捕获 container.repo.upsert_item 的参数来间接验证合并行为。
- 全部依赖均 mock，不需要真实数据库或浏览器。
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xianyu_hunter.domain.evaluation import EvalResult, RiskLevel
from xianyu_hunter.domain.item import ItemDetail
from xianyu_hunter.domain.seller import SellerProfile
from xianyu_hunter.web.routes.api_evaluations import _collect_official_and_evaluate


def _make_page() -> MagicMock:
    """构造 mock browser page

    为什么用 MagicMock + AsyncMock 混合：page.url 是同步属性，
    page.title() / page.close() 是 async 方法，需分别用不同 mock。
    """
    page = MagicMock()
    page.url = "https://example.com/item/i1"
    page.title = AsyncMock(return_value="商品详情")
    page.close = AsyncMock()
    return page


def _make_seller(seller_id: str = "seller_1") -> SellerProfile:
    """构造有效 SellerProfile，避免触发 seller_profile_fallback 分支"""
    return SellerProfile(
        id=seller_id,
        nick="测试卖家",
        credit_score=700,
        register_days=365,
        on_sale_count=10,
        sold_count=50,
    )


def _make_eval_result(*, is_passed: bool = True, score: int = 80) -> EvalResult:
    """构造评估通过的 EvalResult（risk_level=LOW 保证 is_passed=True）"""
    return EvalResult(
        score=score,
        risk_level=RiskLevel.LOW,
        dimension_scores={"price": 80, "seller": 80},
        reject_reasons=[],
        data_quality="full",
    )


def _make_container(
    *,
    detail: ItemDetail,
    seller: SellerProfile | None = None,
    old_item: dict | None = None,
    eval_result: EvalResult | None = None,
) -> MagicMock:
    """构造 mock container，注入采集/评估/仓储依赖

    Args:
        detail: collector.detail 返回的 ItemDetail
        seller: collector.seller_profile 返回的 SellerProfile；
                None 时默认用 detail.seller_id 构造，避免触发 fallback
        old_item: repo.get_item 返回的旧商品记录（用于 _coalesce 测试）
        eval_result: evaluator.evaluate 返回的评估结果
    """
    container = MagicMock()
    # browser/page
    container.browser.new_page = AsyncMock(return_value=_make_page())
    # collector（async 方法）
    container.collector.detail = AsyncMock(return_value=detail)
    if seller is None:
        seller = _make_seller(detail.seller_id or "seller_1")
    container.collector.seller_profile = AsyncMock(return_value=seller)
    container.collector.seller_profile_fallback = AsyncMock(return_value=seller)
    # repo（同步方法）
    container.repo.get_item.return_value = old_item or {}
    container.repo.get_eval_payload_by_item.return_value = None
    container.repo.upsert_item = MagicMock()
    container.repo.mark_sold = MagicMock()
    container.repo.upsert_seller = MagicMock()
    container.repo.upsert_eval_event = MagicMock()
    # evaluator（同步方法）
    container.evaluator.evaluate.return_value = eval_result or _make_eval_result()
    return container


@pytest.fixture(autouse=True)
def _mock_helpers():
    """patch 模块级辅助函数，避免访问真实 page DOM 和 task_links.display

    _extract_reviews_from_page：在 asyncio.gather 中调用，patch 成 AsyncMock 返回 []
    sync_item_display_from_detail：同步函数，patch 成 MagicMock 避免实际写库
    """
    with patch(
        "xianyu_hunter.web.routes.api_evaluations._extract_reviews_from_page",
        new=AsyncMock(return_value=[]),
    ), patch(
        "xianyu_hunter.web.routes.api_evaluations.sync_item_display_from_detail",
        new=MagicMock(),
    ):
        yield


# ========== SubTask 4.1：_coalesce 新值为空时保留旧值 ==========


async def test_coalesce_preserves_old_when_new_empty() -> None:
    """_coalesce 新值为空时保留旧值

    覆盖 4 个非白名单字段：title / price / description / thumb_url
    - 新值为 "" / None 时，_is_blank 返回 True，_coalesce 返回旧值
    - 设计目的：避免官方采集半残数据覆盖本地搜索已写入的有效数据
    """
    old_item = {
        "id": "i1",
        "task_id": "old_task",
        "title": "旧标题",
        "price": 100.0,
        "description": "旧描述",
        "thumb_url": "http://old.jpg",
        "image_urls": "[]",
    }
    # 构造非白名单字段全空的 ItemDetail
    # price=None 触发 _is_blank(None)=True；其余字段为 "" 触发 _is_blank("")=True
    detail = ItemDetail(
        id="i1",
        title="",            # 空 → 保留旧值
        price=None,          # None → 保留旧值
        description="",      # 空 → 保留旧值（new_item_row 中经 `or ""` 后仍为 ""）
        thumb_url="",        # 空 → 保留旧值
        seller_id="seller_1",  # 非空，避免触发 seller_profile_fallback
        is_sold=False,
    )
    container = _make_container(detail=detail, old_item=old_item)

    await _collect_official_and_evaluate(container, "i1", task_id="t1")

    # 捕获 upsert_item 收到的合并后 item_row
    container.repo.upsert_item.assert_called_once()
    item_row = container.repo.upsert_item.call_args.args[0]

    # 断言非白名单字段保留旧值
    assert item_row["title"] == "旧标题", \
        f"title 新值为空时应保留旧值，但得到 {item_row['title']}"
    assert item_row["price"] == 100.0, \
        f"price 新值为 None 时应保留旧值，但得到 {item_row['price']}"
    assert item_row["description"] == "旧描述", \
        f"description 新值为空时应保留旧值，但得到 {item_row['description']}"
    assert item_row["thumb_url"] == "http://old.jpg", \
        f"thumb_url 新值为空时应保留旧值，但得到 {item_row['thumb_url']}"


# ========== SubTask 4.2：ALWAYS_OVERWRITE 白名单字段强制覆盖 ==========


async def test_coalesce_overwrites_whitelist_fields() -> None:
    """_ALWAYS_OVERWRITE 白名单字段即使旧值非空也强制覆盖

    覆盖全部 7 个白名单字段：
    task_id / publish_time / view_cnt / want_cnt / region / seller_id / is_sold
    - 这些字段代表采集时刻+来源信息，应优先更新
    - 数字 0 是合法值（_is_blank 已修正），view_cnt/want_cnt=0 也会覆盖
    """
    old_item = {
        "id": "i1",
        "task_id": "old_task",
        "publish_time": "旧时间",
        "view_cnt": 10,
        "want_cnt": 5,
        "region": "北京",
        "seller_id": "old_seller",
        "is_sold": 0,
        "title": "旧标题",
        "price": 100.0,
    }
    # 构造白名单字段全为新值的 ItemDetail
    detail = ItemDetail(
        id="i1",
        title="新标题",
        price=200.0,
        publish_time="新时间",
        view_cnt=20,
        want_cnt=8,
        region="上海",
        seller_id="new_seller",
        is_sold=True,
    )
    container = _make_container(detail=detail, old_item=old_item)

    # 传入 task_id="new_task"，应覆盖 old_item["task_id"]="old_task"
    await _collect_official_and_evaluate(container, "i1", task_id="new_task")

    container.repo.upsert_item.assert_called_once()
    item_row = container.repo.upsert_item.call_args.args[0]

    # 断言所有白名单字段用新值（即使旧值非空）
    assert item_row["task_id"] == "new_task", \
        f"task_id 应强制覆盖为新值，但得到 {item_row['task_id']}"
    assert item_row["publish_time"] == "新时间", \
        f"publish_time 应强制覆盖为新值，但得到 {item_row['publish_time']}"
    assert item_row["view_cnt"] == 20, \
        f"view_cnt 应强制覆盖为新值，但得到 {item_row['view_cnt']}"
    assert item_row["want_cnt"] == 8, \
        f"want_cnt 应强制覆盖为新值，但得到 {item_row['want_cnt']}"
    assert item_row["region"] == "上海", \
        f"region 应强制覆盖为新值，但得到 {item_row['region']}"
    assert item_row["seller_id"] == "new_seller", \
        f"seller_id 应强制覆盖为新值，但得到 {item_row['seller_id']}"
    assert item_row["is_sold"] == 1, \
        f"is_sold 应强制覆盖为新值（True→1），但得到 {item_row['is_sold']}"


# ========== SubTask 4.3：data_source='official' 标记写入 ==========


async def test_data_source_official_written_to_events() -> None:
    """采集成功后 events.payload.data_source='official' 标记写入

    验证 L1933-1967 的 eval_payload 写入逻辑：
    - eval_payload["data_source"] = "official"（L1951）
    - 通过 upsert_eval_event 持久化到 events 表（payload 为 JSON 字符串）
    - 返回结果 evaluation.data_source 也应为 'official'
    """
    detail = ItemDetail(
        id="i1",
        title="测试商品",
        price=100.0,
        description="测试描述",
        seller_id="seller_1",
        is_sold=False,
    )
    container = _make_container(
        detail=detail,
        eval_result=_make_eval_result(is_passed=True, score=85),
    )

    result = await _collect_official_and_evaluate(container, "i1", task_id="t1")

    # 捕获 upsert_eval_event 收到的事件
    container.repo.upsert_eval_event.assert_called_once()
    event = container.repo.upsert_eval_event.call_args.args[0]
    assert event["type"] == "eval.scored"
    assert event["task_id"] == "t1"
    assert event["item_id"] == "i1"

    # payload 是 JSON 字符串，解析后断言 data_source
    payload = json.loads(event["payload"])
    assert payload["data_source"] == "official", \
        f"payload.data_source 应为 'official'，但得到 {payload.get('data_source')}"

    # 同时验证返回结果中的 evaluation.data_source
    assert result["evaluation"]["data_source"] == "official", \
        f"result.evaluation.data_source 应为 'official'，但得到 {result['evaluation'].get('data_source')}"
