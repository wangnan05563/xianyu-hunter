"""批量评估 API — 批量评估未评估商品

从 api_evaluations.py 拆分。
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from loguru import logger

from xianyu_hunter.container import Container
from xianyu_hunter.infra.db_models import _utcnow
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.routes.evaluations_common import (
    _EVAL_SCORED_TYPE,
    _EVAL_TYPE_PREFIX,
    build_item_detail_from_item_row,
    build_seller_profile,
    determine_eval_level,
    evaluate_with_task_price_range,
    is_price_skipped,
    make_price_strategy_getter,
    persist_eval_event,
    publish_eval_passed_event,
)

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])


def _collect_evaluated_ids(container: Container, user_id: str | None = None) -> set[str]:
    """获取所有已评估的 item_id 集合"""
    eval_events, _ = container.repo.list_events_by_type_prefix(
        type_prefix=_EVAL_TYPE_PREFIX, user_id=user_id,
    )
    evaluated_ids: set[str] = set()
    for e in eval_events:
        payload = e.get("payload") or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except (ValueError, TypeError):
                payload = {}
        iid = str(payload.get("item_id") or e.get("item_id") or "")
        if iid:
            evaluated_ids.add(iid)
    return evaluated_ids


def _load_batch_seller_map(container: Container, to_evaluate: list[dict]) -> dict[str, dict]:
    """预加载 sellers 数据（批量查询避免 N+1）"""
    seller_ids_set: set[str] = set()
    for it in to_evaluate:
        sid = str(it.get("seller_id") or "")
        if sid:
            seller_ids_set.add(sid)
    if not seller_ids_set:
        return {}
    seller_map: dict[str, dict] = {}
    seller_rows = container.repo.list_sellers_by_ids(list(seller_ids_set))
    for s in seller_rows:
        sid = str(s.get("id") or "")
        if sid:
            seller_map[sid] = s
    return seller_map


def _persist_batch_eval_event(
    container: Container, item_id: str, effective_task_id: str,
    detail, eval_result, user_id: str | None,
) -> None:
    """写入 eval 事件，data_source=batch_unevaluated 标记来源便于追踪

    为什么用 upsert：按 task_id+item_id 去重，防止重复评估"""
    score_display = eval_result.score if eval_result.score is not None else "N/A"
    level = determine_eval_level(eval_result)
    container.repo.upsert_eval_event({
        "type": _EVAL_SCORED_TYPE,
        "task_id": effective_task_id,
        "item_id": item_id,
        "stage": "eval",
        "level": level,
        "message": f"商品 {item_id} 批量评估分 {score_display} ({eval_result.risk_level.value}) [数据质量: {eval_result.data_quality}]",
        "payload": json.dumps({
            "task_id": effective_task_id,
            "item_id": item_id,
            "item_title": detail.title,
            "item_price": detail.price,
            "seller_id": detail.seller_id,
            "seller_nick": detail.seller_nick,
            "score": eval_result.score,
            "risk_level": eval_result.risk_level.value,
            "dimension_scores": eval_result.dimension_scores,
            "reject_reasons": eval_result.reject_reasons,
            "is_passed": eval_result.is_passed,
            "data_quality": eval_result.data_quality,
            "data_source": "batch_unevaluated",
        }, ensure_ascii=False, default=str),
    }, user_id=user_id or "default")


def _do_evaluate_single_unevaluated_item(
    it: dict, container: Container, seller_map: dict[str, dict],
    get_price_strategy, evaluator, task_id: str | None,
    notify: bool, user_id: str | None,
) -> str:
    """实际评估逻辑

    拆分自 _evaluate_single_unevaluated_item：把核心逻辑从 try/except 中拆出，
    降低嵌套层级；原函数仅负责异常兜底"""
    item_id = str(it.get("id") or "")
    if not item_id:
        return "noop"
    seller_id = str(it.get("seller_id") or "")
    seller_data = seller_map.get(seller_id, {})
    detail = build_item_detail_from_item_row(it, seller_data)
    seller = build_seller_profile(seller_id, seller_data)

    effective_task_id = str(it.get("task_id") or task_id or "")
    if is_price_skipped(get_price_strategy, effective_task_id, detail, item_id, log_prefix="batch_evaluate"):
        return "skipped"

    price_strategy = get_price_strategy(effective_task_id)
    eval_result = evaluate_with_task_price_range(evaluator, detail, seller, price_strategy)
    _persist_batch_eval_event(container, item_id, effective_task_id, detail, eval_result, user_id)

    # 评估通过 → 触发 EVAL_PASSED 事件，让 NotifierHub 推送钉钉等通知
    # 为什么 notify 默认 True：与 collection_service 官方采集语义一致，
    # 用户主动触发的批量评估，通过的商品值得通知
    # 返回 "notified" 而非 "evaluated"：让调用方统计通知数
    if notify and eval_result.is_passed:
        publish_eval_passed_event(
            container, effective_task_id, item_id, detail, seller, eval_result,
            data_source="batch_unevaluated",
        )
        return "notified"
    return "evaluated"


def _evaluate_single_unevaluated_item(
    it: dict,
    container: Container,
    seller_map: dict[str, dict],
    get_price_strategy,
    evaluator,
    task_id: str | None,
    notify: bool = True,
    user_id: str | None = None,
) -> str:
    """评估单个未评估商品并写入 eval.* 事件

    返回值：evaluated=已评估 / skipped=价格门禁跳过 / error=异常 / noop=item_id 为空

    为什么默认 notify=True：批量评估是用户主动触发的新评估，评估通过应该通知用户
    （与官方采集语义一致）；recompute 是历史回算，默认不通知，由调用方传 False
    """
    try:
        return _do_evaluate_single_unevaluated_item(
            it, container, seller_map, get_price_strategy, evaluator,
            task_id, notify, user_id,
        )
    except Exception as e:
        logger.warning(f"批量评估失败 item_id={it.get('id')}: {e}")
        return "error"


@router.post("/batch-evaluate-unevaluated")
def batch_evaluate_unevaluated(
    request: Request,
    task_id: str | None = Query(None, description="可选：仅评估指定任务的商品"),
    limit: int = Query(200, ge=1, le=1000, description="单次最大评估数量"),
    notify: bool = Query(
        True,
        description="评估通过是否触发钉钉等通知。默认 True：批量评估是用户主动触发的新评估，"
        "通过的商品值得通知；批量评估大量商品时可传 False 关闭避免刷爆群",
    ),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """批量评估 items 表中未被评估的商品

    解决商品采集与评估是独立流程导致的大量商品未被评估的问题。
    查询 items 表中不在 eval.* 事件中的商品，用当前评估规则批量评估。
    """
    evaluator = container.evaluator
    get_price_strategy = make_price_strategy_getter(container, log_prefix="batch_evaluate")

    # 多用户隔离：仅评估当前账号的商品
    user_id = getattr(request.state, "user_id", None)
    # 1. 获取所有已评估的 item_id 集合
    evaluated_ids = _collect_evaluated_ids(container, user_id=user_id)

    # 2. 获取 items 表中所有商品（按 task_id 过滤）
    # items 表量级可控（通常 < 1000），一次查询即可
    all_items = container.repo.list_items(task_id=task_id, limit=5000, offset=0, user_id=user_id)
    unevaluated = [it for it in all_items if str(it.get("id") or "") not in evaluated_ids]

    if not unevaluated:
        return {
            "ok": True,
            "evaluated": 0,
            "skipped": 0,
            "errors": 0,
            "total": 0,
            "message": "所有商品均已评估，无需批量评估",
        }

    # 限制单次评估数量，避免长时间阻塞
    to_evaluate = unevaluated[:limit]
    skipped = len(unevaluated) - len(to_evaluate)

    # 3. 预加载 sellers 数据
    seller_map = _load_batch_seller_map(container, to_evaluate)

    # 4. 遍历评估并写入 eval.* 事件
    evaluated = 0
    errors = 0
    notified = 0
    for it in to_evaluate:
        result = _evaluate_single_unevaluated_item(
            it, container, seller_map, get_price_strategy, evaluator, task_id,
            notify=notify, user_id=user_id,
        )
        if result == "notified":
            notified += 1
            evaluated += 1
        elif result == "evaluated":
            evaluated += 1
        elif result == "skipped":
            skipped += 1
        elif result == "error":
            errors += 1
        # "noop"：item_id 为空，不增加任何计数

    return {
        "ok": True,
        "evaluated": evaluated,
        "notified": notified,
        "skipped": skipped,
        "errors": errors,
        "total": evaluated,
        "message": (
            f"已批量评估 {evaluated} 条未评估商品（跳过 {skipped}，错误 {errors}）"
            + (f"，触发通知 {notified} 条" if notify else "")
        ),
    }
