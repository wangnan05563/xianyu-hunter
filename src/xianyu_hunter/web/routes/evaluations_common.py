"""评估模块共享常量、DTO 构建器、事件发布、价格策略工具

从 api_evaluations.py 拆分，统一 recompute / batch / official 三条评估路径的公共逻辑：
- 常量：事件类型前缀、标签字面量
- 价格策略缓存闭包（统一 _make_recompute_price_strategy_getter / _make_batch_price_strategy_getter）
- ItemDetail / SellerProfile 构建（统一 _build_*_item_detail / _build_*_seller_profile）
- 评估结果 → 事件日志级别 / 事件 payload / EVAL_PASSED 事件发布
"""
from __future__ import annotations

import json
from typing import Any

from loguru import logger

from xianyu_hunter.container import Container
from xianyu_hunter.domain.evaluation import RiskLevel
from xianyu_hunter.domain.events import Event, EventType
from xianyu_hunter.infra.db_models import _utcnow
from xianyu_hunter.modules.evaluator import PriceRange

# ---- 共享常量 ----
_BROKEN_LABEL = "有故障/维修"
_USED_TRACE_LABEL = "有使用痕迹"
_EVAL_TYPE_PREFIX = "eval."
_EVAL_SCORED_TYPE = "eval.scored"


# ============== 价格策略缓存闭包 ==============
def make_price_strategy_getter(container: Container, log_prefix: str = "eval"):
    """创建任务级 PriceStrategy 缓存查询闭包

    统一 recompute / batch_evaluate 两条路径的价格策略获取逻辑。
    按 task_id 缓存，避免重复构造 PriceStrategy。

    Args:
        container: DI 容器
        log_prefix: 日志前缀（如 "recompute" / "batch_evaluate"），便于区分日志来源
    """
    _price_strategy_cache: dict[str, "PriceStrategy"] = {}
    _skip_price_check_task_ids: set[str] = set()

    def _get_price_strategy(tid: str | None) -> "PriceStrategy | None":
        """按 task_id 获取任务级 PriceStrategy。task_id 为空或任务不存在时返回 None（跳过门禁）"""
        if not tid:
            return None
        if tid in _skip_price_check_task_ids:
            return None
        if tid in _price_strategy_cache:
            return _price_strategy_cache[tid]
        try:
            task_raw = container.repo.get_task(tid)
            if not task_raw:
                _skip_price_check_task_ids.add(tid)
                return None
            ps = container.build_task_price_strategy(task_raw)
            _price_strategy_cache[tid] = ps
            return ps
        except Exception as e:
            logger.warning(f"{log_prefix} 读取任务 {tid} 价格策略失败，跳过门禁: {e}")
            _skip_price_check_task_ids.add(tid)
            return None

    return _get_price_strategy


# ============== 评估级别 / 价格范围评估 ==============
def determine_eval_level(eval_result) -> str:
    """根据评估结果确定事件日志级别

    与 worker.py 保持一致：通过=info，极端风险=err，其他=warn；UNKNOWN 兜底为 warn"""
    if eval_result.is_passed:
        level = "info"
    elif eval_result.risk_level != RiskLevel.EXTREME:
        level = "warn"
    else:
        level = "err"
    if eval_result.risk_level == RiskLevel.UNKNOWN:
        level = "warn"
    return level


def evaluate_with_task_price_range(evaluator, detail, seller, price_strategy):
    """带任务级价格范围的评估

    price_strategy 为 None 时退化为普通评估"""
    price_range = PriceRange.from_price_config(getattr(price_strategy, "config", None))
    if price_range is None:
        return evaluator.evaluate(detail, seller)
    return evaluator.evaluate(detail, seller, price_range=price_range)


# ============== ItemDetail 构建（统一三个 _build_*_item_detail） ==============
def build_item_detail_from_display(item_id: str, display: dict):
    """从 task_links.display 构造 ItemDetail"""
    from xianyu_hunter.domain.item import ItemDetail
    price_val = display.get("price")
    # price 为 None 时用 0.0 兜底，避免 ItemDetail 构造失败
    price_float = float(price_val) if price_val is not None else 0.0
    return ItemDetail(
        id=str(item_id),
        title=str(display.get("title") or ""),
        price=price_float,
        region=str(display.get("region") or ""),
        seller_id=str(display.get("seller_id") or ""),
        seller_nick=str(display.get("seller_nick") or ""),
        thumb_url=str(display.get("thumb_url") or ""),
        is_sold=bool(display.get("is_sold", False)),
        want_cnt=int(display.get("want_cnt") or 0),
        view_cnt=int(display.get("view_cnt") or 0),
        description="",
    )


def build_item_detail_from_item_row(it: dict, seller_data: dict | None = None):
    """从 items 表行构建 ItemDetail（batch / recompute 共用）

    seller_nick 优先从 sellers 表取（ItemRow 无此字段）"""
    from xianyu_hunter.domain.item import ItemDetail
    seller_nick = ""
    if seller_data:
        seller_nick = str(seller_data.get("nick") or "")
    return ItemDetail(
        id=str(it.get("id") or it.get("item_id") or ""),
        title=str(it.get("title") or ""),
        price=float(it.get("price") or 0),
        region=str(it.get("region") or ""),
        seller_id=str(it.get("seller_id") or ""),
        seller_nick=seller_nick,
        thumb_url=str(it.get("thumb_url") or ""),
        want_cnt=int(it.get("want_cnt") or 0),
        view_cnt=int(it.get("view_cnt") or 0),
    )


def build_item_detail_from_payload(item_id: str, item_data: dict, payload: dict, seller_data: dict):
    """从 items 表行 + payload 回退构建 ItemDetail（recompute 路径）

    seller_nick 优先从 sellers 表取（ItemRow 无此字段），回退到 payload"""
    from xianyu_hunter.domain.item import ItemDetail
    seller_id = str(item_data.get("seller_id") or payload.get("seller_id") or "")
    return ItemDetail(
        id=item_id,
        title=str(item_data.get("title") or payload.get("item_title") or ""),
        price=float(item_data.get("price") or 0),
        region=str(item_data.get("region") or ""),
        seller_id=seller_id,
        seller_nick=str(seller_data.get("nick") or payload.get("seller_nick") or ""),
    )


# ============== SellerProfile 构建（统一两个 _build_*_seller_profile） ==============
def build_seller_profile(seller_id: str, seller_data: dict):
    """构建 SellerProfile（recompute / batch 共用）

    recompute 路径需要 top_category / bad_review_count 等完整字段；
    batch 路径不需要但传入无副作用"""
    from xianyu_hunter.domain.seller import SellerProfile
    return SellerProfile(
        id=seller_id or "unknown",
        nick=str(seller_data.get("nick") or ""),
        credit_score=seller_data.get("credit_score"),
        register_days=int(seller_data.get("register_days") or 0),
        on_sale_count=int(seller_data.get("on_sale_count") or 0),
        sold_count=int(seller_data.get("sold_count") or 0),
        top_category=seller_data.get("top_category"),
        top_category_ratio=float(seller_data.get("top_category_ratio") or 0),
        post_count_30d=int(seller_data.get("post_count_30d") or 0),
        bad_review_count=int(seller_data.get("bad_review_count") or 0),
        in_blacklist=bool(seller_data.get("in_blacklist") or False),
    )


# ============== 价格门禁（统一 _is_recompute_price_skipped / _is_batch_price_skipped） ==============
def is_price_skipped(
    get_price_strategy, task_id: str, detail, item_id: str, log_prefix: str = "eval",
) -> bool:
    """价格门禁：与 worker.py 搜索流水线一致，超范围商品不写入 eval.scored 事件

    为什么 skip 而非删除旧事件：recompute 语义是"重算"而非"清理"，
    保留旧事件供 include_out_of_range=True 审计；list_evaluations 的
    价格过滤会默认隐藏这些超范围商品"""
    price_strategy = get_price_strategy(task_id)
    if price_strategy is None:
        return False
    verdict = price_strategy.check(detail, market=None)
    if verdict.pass_:
        return False
    logger.info(
        "{} 跳过超范围商品: item_id={}, price={}, reasons={}",
        log_prefix, item_id, detail.price, verdict.reasons,
    )
    return True


# ============== EVAL_PASSED 事件发布 ==============

def should_skip_notify_by_bargain(
    container: Container, task_id: str, item_price: float | None,
) -> bool:
    """notify_bargain_only 开关过滤：返回 True 表示应跳过通知

    与 worker._publish_eval_passed_event 的过滤逻辑对齐，确保所有 EVAL_PASSED
    发布点统一遵守价格过滤。解决元规范 #43（事件多发布点字段对齐）违规：
    之前只有 worker 路径过滤，官方采集/批量评估/重算等旁路绕过过滤，
    导致启用 notify_bargain_only 后高价商品仍触发钉钉通知。

    适用场景：非 worker 路径的 EVAL_PASSED 发布（官方采集/批量评估/重算/补发）
    不适用场景：worker 路径（已有实例级 P10 缓存，复用 _get_task_bargain_price 更高效）

    降级策略：开关关闭 / P10 查询失败 / 无足够已售数据 → 返回 False（不过滤），
    与 worker 的降级行为一致，避免阻断通知链。
    """
    if item_price is None:
        return False
    try:
        task_row = container.repo.get_task(task_id)
        if not task_row:
            return False
        # DB 中 notify_bargain_only 是 INTEGER(0/1)，bool() 转换
        if not bool(task_row.get("notify_bargain_only")):
            return False
    except Exception as exc:  # noqa: BLE001
        logger.warning("notify_bargain_only 开关读取失败 task={}: {}", task_id, exc)
        return False
    # 查任务级 P10 捡漏价，与 worker._get_task_bargain_price 口径一致
    # 为什么 range_days=30：与 worker 保持一致，捡漏参考取近 30 天已售数据
    try:
        from xianyu_hunter.web.routes.price_dashboard import _compute_sold_range
        with container.repo.engine.connect() as conn:
            stats = _compute_sold_range(conn, task_id, range_days=30)
        bargain_price = stats.get("bargain_price")
    except Exception as exc:  # noqa: BLE001
        logger.warning("捡漏价格查询失败，过滤降级为未启用 task={}: {}", task_id, exc)
        return False
    if bargain_price is None:
        return False
    if item_price > bargain_price:
        logger.info(
            "[Task {}] 价格 {} > 捡漏价 {}，notify_bargain_only 过滤跳过通知",
            task_id, item_price, bargain_price,
        )
        return True
    return False


def _load_task_mode(container: Container, task_id: str) -> str:
    """读取 task_mode（SEMI_AUTO 模式下模板渲染"确认抢单"链接）

    为什么独立函数：补发场景没有 task 对象上下文，需查 DB；
    查询失败时返回空字符串，模板层视为非 SEMI_AUTO 模式（保守降级）。
    """
    if not task_id:
        return ""
    try:
        task_row = container.repo.get_task(task_id)
        if task_row:
            return str(task_row.get("mode") or "")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load task mode for EVAL_PASSED task={}: {}", task_id, exc)
    return ""


def _resolve_risk_level_value(eval_result: Any) -> str:
    """统一 risk_level 序列化：兼容 enum 与裸字符串两种类型

    为什么需要兼容：eval_result 可能来自不同 evaluator 实现，
    有的返回 RiskLevel 枚举（有 .value），有的直接传字符串。
    """
    risk_level = getattr(eval_result, "risk_level", None)
    if hasattr(risk_level, "value"):
        return risk_level.value
    # 属性缺失时回退 "medium"；裸字符串/None 时转字符串（与原内联三元一致）
    return str(getattr(eval_result, "risk_level", "medium"))


def publish_eval_passed_event(
    container: Container,
    task_id: str,
    item_id: str,
    detail: Any,
    seller: Any,
    eval_result: Any,
    data_source: str = "",
) -> None:
    """评估通过 → 触发 EVAL_PASSED 事件，让 NotifierHub 推送钉钉等通知

    为什么独立工具函数而非复用 collection_service._publish_eval_passed_event：
    - 该函数被 batch_evaluate / recompute 两条路径共用，避免 payload 构造重复
    - 字段与 worker._publish_eval_passed_event 对齐，保证模板渲染一致
    - 用 getattr 安全访问 detail/seller 字段，兼容 ItemDetail 与 ItemRow 两种类型

    为什么用 publish_nowait：调用方在同步函数中，EventBus.run_forever 异步消费

    notify_bargain_only 过滤：与 worker 路径对齐，价格 > P10 时跳过通知发布。
    之前此函数缺失过滤，导致批量评估/重算路径绕过开关，高价商品仍触发钉钉通知。
    """
    bus = getattr(container, "event_bus", None)
    if bus is None:
        return
    # notify_bargain_only 价格过滤：与 worker._publish_eval_passed_event 对齐
    item_price = getattr(detail, "price", None)
    if should_skip_notify_by_bargain(container, task_id, item_price):
        return
    # task_mode 与 worker 对齐：SEMI_AUTO 模式下模板渲染"确认抢单"链接
    task_mode = _load_task_mode(container, task_id)
    payload: dict[str, Any] = {
        "item_id": item_id,
        "item_title": getattr(detail, "title", "") or "",
        "item_price": getattr(detail, "price", 0) or 0,
        "thumb_url": getattr(detail, "thumb_url", "") or "",
        "region": getattr(detail, "region", "") or "",
        "seller_id": getattr(detail, "seller_id", "") or "",
        "seller_nick": getattr(seller, "nick", "") or "",
        "score": getattr(eval_result, "score", 0),
        "risk_level": _resolve_risk_level_value(eval_result),
        "data_quality": getattr(eval_result, "data_quality", ""),
        "reject_reasons": getattr(eval_result, "reject_reasons", []) or [],
        "task_mode": task_mode,
    }
    if data_source:
        payload["data_source"] = data_source
    try:
        bus.publish_nowait(
            Event(
                type=EventType.EVAL_PASSED,
                task_id=task_id,
                item_id=item_id,
                payload=payload,
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to publish EVAL_PASSED item={}: {}", item_id, exc)


# ============== 评估事件 payload 构建 + 持久化 ==============
def build_eval_event_payload(
    task_id: str, item_id: str, detail, eval_result, data_source: str = "",
) -> dict[str, Any]:
    """构建 eval.scored 事件 payload（recompute / batch / official 共用）"""
    payload: dict[str, Any] = {
        "task_id": task_id,
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
    }
    if data_source:
        payload["data_source"] = data_source
    return payload


def persist_eval_event(
    container: Container,
    item_id: str,
    task_id: str,
    detail,
    eval_result,
    user_id: str | None,
    data_source: str = "",
    message_prefix: str = "商品",
) -> None:
    """写入 eval.scored 事件（upsert 按 task_id+item_id 去重）

    Args:
        message_prefix: 消息前缀（如 "商品" / "商品 {id} 批量评估"），便于区分来源"""
    score_display = eval_result.score if eval_result.score is not None else "N/A"
    level = determine_eval_level(eval_result)
    payload = build_eval_event_payload(task_id, item_id, detail, eval_result, data_source)
    container.repo.upsert_eval_event({
        "type": _EVAL_SCORED_TYPE,
        "task_id": task_id,
        "item_id": item_id,
        "stage": "eval",
        "level": level,
        "message": f"{message_prefix} {item_id} 评估分 {score_display} ({eval_result.risk_level.value}) [数据质量: {eval_result.data_quality}]",
        "payload": json.dumps(payload, ensure_ascii=False, default=str),
    }, user_id=user_id or "default")
