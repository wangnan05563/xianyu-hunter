"""评估重算 API — 历史评估重新计算

从 api_evaluations.py 拆分，包含：
- recompute_evaluations 路由及其所有辅助函数
- 从 task_links 生成评估的回退逻辑
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
    build_item_detail_from_display,
    build_item_detail_from_payload,
    build_seller_profile,
    determine_eval_level,
    evaluate_with_task_price_range,
    is_price_skipped,
    make_price_strategy_getter,
    persist_eval_event,
    publish_eval_passed_event,
)

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])


# ==== recompute_evaluations 辅助函数 ====
def _upsert_item_from_link_display(
    container: Container,
    item_id: str,
    link: dict,
    display: dict,
    price_float: float,
    task_id: str | None,
    user_id: str | None = None,
) -> bool:
    """补写 items 表：recompute 从 task_links 生成评估时同步写入 items 表

    避免 eval.* 事件引用的 item_id 在 items 表中不存在（孤儿数据）。
    返回 True 表示写入成功，False 表示失败（已记录日志）。"""
    try:
        container.repo.upsert_item({
            "id": str(item_id),
            "task_id": link.get("task_id") or task_id or "",
            "title": str(display.get("title") or ""),
            "price": price_float,
            "region": str(display.get("region") or ""),
            "seller_id": str(display.get("seller_id") or ""),
            "want_cnt": int(display.get("want_cnt") or 0),
            "view_cnt": int(display.get("view_cnt") or 0),
            "thumb_url": str(display.get("thumb_url") or ""),
            "image_urls": "[]",
            "description": "",
            "first_seen": _utcnow(),
            "last_seen": _utcnow(),
        }, user_id=user_id or "default")
        return True
    except Exception as e:
        logger.warning(f"补写 items 表失败 item_id={item_id}: {e}")
        return False


def _persist_eval_from_link(
    container: Container, link: dict, display: dict,
    detail, eval_result, task_id: str | None, user_id: str | None,
    item_id: str, existing_item_ids: set[str],
) -> None:
    """写入 eval 事件，并按需补写 items 表

    为什么补写 items：recompute 从 task_links 生成评估时同步写入 items 表，
    避免 eval.* 事件引用的 item_id 在 items 表中不存在（孤儿数据）。
    拆分自 _recompute_from_task_links：把持久化逻辑抽离，主循环只编排"""
    score_display = eval_result.score if eval_result.score is not None else "N/A"
    level = determine_eval_level(eval_result)
    # S1066：合并嵌套 if，两个条件短路求值语义等价
    if item_id not in existing_item_ids and _upsert_item_from_link_display(
        container, item_id, link, display, detail.price, task_id, user_id=user_id,
    ):
        existing_item_ids.add(item_id)
    # 使用 upsert 按 task_id+item_id 去重，防止重复评估
    container.repo.upsert_eval_event({
        "type": _EVAL_SCORED_TYPE,
        "task_id": link.get("task_id") or task_id or "",
        "item_id": detail.id,
        "stage": "eval",
        "level": level,
        "message": f"商品 {detail.id} 评估分 {score_display} ({eval_result.risk_level.value}) [数据质量: {eval_result.data_quality}]",
        "payload": json.dumps({
            "task_id": link.get("task_id") or task_id or "",  # 写入 payload 供官方采集回查
            "item_id": detail.id,
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
        }, ensure_ascii=False, default=str),
    }, user_id=user_id or "default")


def _process_recompute_link(
    link: dict, container: Container, get_price_strategy, evaluator,
    task_id: str | None, user_id: str | None, existing_item_ids: set[str],
) -> str:
    """处理单条 task_link：构建评估对象 + 价格门禁 + 评估 + 持久化

    返回 generated/error/skip。
    拆分自 _recompute_from_task_links：把 for 循环体提取为独立函数，
    降低 try/except + 嵌套 if 的认知复杂度"""
    from xianyu_hunter.domain.seller import SellerProfile

    display = link.get("display") or {}
    item_id = link.get("link_key") or ""
    if not item_id:
        return "skip"
    try:
        detail = build_item_detail_from_display(item_id, display)
        seller = SellerProfile(
            id=detail.seller_id or "unknown",
            nick=detail.seller_nick or "",
            credit_score=None,
            register_days=0,
            on_sale_count=0,
            sold_count=0,
        )
        effective_task_id = link.get("task_id") or task_id or ""
        # 复用 is_price_skipped：日志前缀一致（都是 "recompute 跳过超范围商品"）
        # 为什么传 market_ctx=None：recompute 无现成市场数据，仅走 min/max 硬性规则
        if is_price_skipped(get_price_strategy, effective_task_id, detail, item_id, log_prefix="recompute"):
            return "skip"
        price_strategy = get_price_strategy(effective_task_id)
        eval_result = evaluate_with_task_price_range(evaluator, detail, seller, price_strategy)
        _persist_eval_from_link(
            container, link, display, detail, eval_result,
            task_id, user_id, item_id, existing_item_ids,
        )
        return "generated"
    except Exception:
        return "error"


def _recompute_from_task_links(
    container: Container,
    task_id: str | None,
    get_price_strategy,
    user_id: str | None = None,
) -> dict[str, Any]:
    """无 eval.* 事件时，从 task_links 生成评估

    覆盖场景：live_search 写入了 task_links 但未触发评估（旧版本）"""
    link_rows = []
    if task_id:
        link_rows = container.repo.list_task_links(
            task_id=task_id, link_type="item", limit=500, user_id=user_id,
        )
    if not link_rows:
        return {"ok": True, "recomputed": 0, "message": "无评估记录需要重新计算，且无 task_links 可生成评估"}

    evaluator = container.evaluator
    generated = 0
    errors = 0
    # 批量检查哪些 item_id 还不在 items 表，避免逐条查询
    # recompute 从 task_links 生成评估时，需同步补写 items 表，防止孤儿数据
    all_link_item_ids = [link.get("link_key") for link in link_rows if link.get("link_key")]
    existing_item_ids = container.repo.items_exist(all_link_item_ids) if all_link_item_ids else set()

    for link in link_rows:
        result = _process_recompute_link(
            link, container, get_price_strategy, evaluator,
            task_id, user_id, existing_item_ids,
        )
        if result == "generated":
            generated += 1
        elif result == "error":
            errors += 1
        # "skip"：item_id 为空或价格门禁跳过，不计数

    return {
        "ok": True,
        "recomputed": generated,
        "skipped": 0,
        "errors": errors,
        "total": generated,
        "message": f"从 task_links 生成 {generated} 条评估记录（错误 {errors}）",
    }


def _load_recompute_item_map(
    container: Container, eval_events: list[dict],
) -> tuple[dict[str, dict], list[dict]]:
    """预加载 items 数据

    修复：之前用 list_items(limit=10000) 全量加载，改为按评估事件涉及的 item_id 批量查询"""
    recompute_item_ids = set()
    for e in eval_events:
        payload = e.get("payload") or {}
        iid = str(payload.get("item_id") or e.get("item_id") or "")
        if iid:
            recompute_item_ids.add(iid)
    item_rows = container.repo.list_items_by_ids(list(recompute_item_ids)) if recompute_item_ids else []
    item_map: dict[str, dict] = {}
    for it in item_rows:
        iid = str(it.get("item_id") or it.get("id") or "")
        if iid:
            item_map[iid] = it
    return item_map, item_rows


def _load_recompute_seller_map(
    container: Container, item_rows: list[dict],
) -> dict[str, dict]:
    """预加载 sellers

    修复：之前对每个 item 的 seller_id 单独调用 get_seller（N+1 查询），
    改为收集所有 seller_id 后批量查询"""
    seller_ids_set: set[str] = set()
    for it in item_rows:
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


def _resolve_recompute_item_data(item_id: str, item_map: dict[str, dict], payload: dict) -> dict:
    """获取商品数据，items 表无记录时回退到 payload

    修复：之前直接 skip，导致 live 搜索写入 task_links 但未入 items 表的商品无法重算评估。
    回退字段由 _enrich_eval_with_item 从 task_links.display 补充"""
    item_data = item_map.get(item_id)
    if item_data:
        return item_data
    return {
        "title": payload.get("item_title") or "",
        "price": payload.get("item_price") or 0,
        "region": payload.get("region") or "",
        "seller_id": payload.get("seller_id") or "",
        "seller_nick": payload.get("seller_nick") or "",
    }


def _update_recompute_payload(payload: dict, eval_result) -> None:
    """更新 payload（保留原始字段，仅更新评分相关字段）"""
    payload["score"] = eval_result.score
    payload["risk_level"] = eval_result.risk_level.value
    payload["dimension_scores"] = eval_result.dimension_scores
    payload["reject_reasons"] = eval_result.reject_reasons
    payload["is_passed"] = eval_result.is_passed
    payload["data_quality"] = eval_result.data_quality
    payload["recomputed_at"] = _utcnow().isoformat()


def _persist_recomputed_eval(
    e: dict, container: Container, payload: dict, eval_result,
    detail, seller, effective_task_id: str, item_id: str, notify: bool,
) -> str:
    """更新 events 表，按需触发 EVAL_PASSED 事件

    返回 recomputed/notified/noop。
    为什么 notify 默认 False：recompute 是历史回算，可能批量重算大量历史数据，
    默认关闭避免刷爆群；用户主动回算想验证通知链路时由调用方传 True"""
    event_id = e.get("id")
    if not event_id:
        return "noop"
    container.repo.update_event_payload(event_id, json.dumps(payload, ensure_ascii=False, default=str))
    if notify and eval_result.is_passed:
        publish_eval_passed_event(
            container, effective_task_id, item_id, detail, seller, eval_result,
            data_source="recompute",
        )
        return "notified"
    return "recomputed"


def _do_recompute_single_eval(
    e: dict,
    container: Container,
    item_map: dict[str, dict],
    seller_map: dict[str, dict],
    get_price_strategy,
    evaluator,
    task_id: str | None,
    notify: bool,
) -> str:
    """实际重算逻辑

    拆分自 _recompute_single_eval：把核心逻辑从 try/except 中拆出，
    降低嵌套层级；原函数仅负责异常兜底"""
    payload = e.get("payload") or {}
    if isinstance(payload, str):
        payload = json.loads(payload)

    item_id = str(payload.get("item_id") or e.get("item_id") or "")
    if not item_id:
        return "skipped"

    item_data = _resolve_recompute_item_data(item_id, item_map, payload)
    seller_id = str(item_data.get("seller_id") or payload.get("seller_id") or "")
    seller_data = seller_map.get(seller_id, {})

    detail = build_item_detail_from_payload(item_id, item_data, payload, seller_data)
    seller = build_seller_profile(seller_id, seller_data)

    effective_task_id = str(payload.get("task_id") or e.get("task_id") or task_id or "")
    if is_price_skipped(get_price_strategy, effective_task_id, detail, item_id, log_prefix="recompute"):
        return "skipped"

    price_strategy = get_price_strategy(effective_task_id)
    eval_result = evaluate_with_task_price_range(evaluator, detail, seller, price_strategy)
    _update_recompute_payload(payload, eval_result)

    return _persist_recomputed_eval(
        e, container, payload, eval_result, detail, seller,
        effective_task_id, item_id, notify,
    )


def _recompute_single_eval(
    e: dict,
    container: Container,
    item_map: dict[str, dict],
    seller_map: dict[str, dict],
    get_price_strategy,
    evaluator,
    task_id: str | None,
    notify: bool = False,
) -> str:
    """重新计算单条评估事件

    返回值：recomputed=已重算 / skipped=跳过 / error=异常 / noop=无 event_id 不计数"""
    try:
        return _do_recompute_single_eval(
            e, container, item_map, seller_map,
            get_price_strategy, evaluator, task_id, notify,
        )
    except Exception:
        return "error"


# ============== 历史评估重新计算 ==============
@router.post("/recompute")
def recompute_evaluations(
    request: Request,
    task_id: str | None = Query(None, description="可选：仅重新计算指定任务的评估"),
    notify: bool = Query(
        False,
        description="评估通过是否触发钉钉等通知。默认 False：recompute 是历史回算，"
        "避免批量重算刷爆通知群；用户主动回算想验证通知链路时传 True",
    ),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """用当前配置的评估规则重新计算历史评估数据

    读取 events 表中所有 eval.scored 事件，从 items + sellers 表重建
    ItemDetail 和 SellerProfile，用当前配置的 Evaluator 重新评分，
    更新 events 表的 payload。
    """
    evaluator = container.evaluator
    get_price_strategy = make_price_strategy_getter(container, log_prefix="recompute")

    # 多用户隔离：仅重新计算当前账号的评估事件
    user_id = getattr(request.state, "user_id", None)
    # 拉取所有评估事件
    # 修复：之前用 list_events(limit=10000) 在 Python 端过滤，改为 SQL 端按 type 前缀过滤
    all_eval_events, _ = container.repo.list_events_by_type_prefix(
        type_prefix=_EVAL_TYPE_PREFIX, task_id=task_id, user_id=user_id,
    )
    eval_events = all_eval_events

    if not eval_events:
        # 没有 eval.* 事件时，从 task_links 生成评估
        # 覆盖场景：live_search 写入了 task_links 但未触发评估（旧版本）
        return _recompute_from_task_links(container, task_id, get_price_strategy, user_id=user_id)

    item_map, item_rows = _load_recompute_item_map(container, eval_events)
    seller_map = _load_recompute_seller_map(container, item_rows)

    recomputed = 0
    skipped = 0
    errors = 0
    notified = 0

    for e in eval_events:
        result = _recompute_single_eval(
            e, container, item_map, seller_map,
            get_price_strategy, evaluator, task_id,
            notify=notify,
        )
        if result == "recomputed":
            recomputed += 1
        elif result == "notified":
            notified += 1
            recomputed += 1
        elif result == "skipped":
            skipped += 1
        elif result == "error":
            errors += 1
        # "noop"：无 event_id，不增加任何计数

    return {
        "ok": True,
        "recomputed": recomputed,
        "notified": notified,
        "skipped": skipped,
        "errors": errors,
        "total": len(eval_events),
        "message": (
            f"已重新计算 {recomputed} 条评估记录（跳过 {skipped}，错误 {errors}）"
            + (f"，触发通知 {notified} 条" if notify else "")
        ),
    }
