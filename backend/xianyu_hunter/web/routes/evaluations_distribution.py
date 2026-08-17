"""评估分布统计 API — 分数×价格二维分布 + 阈值建议 + 自动采集统计

从 api_evaluations.py 拆分。
"""
from __future__ import annotations

import json
import math
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from loguru import logger

from xianyu_hunter.container import Container
from xianyu_hunter.infra.db_models import _utcnow
from xianyu_hunter.infra.yaml_config import get_config
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.routes.evaluations_common import (
    _EVAL_SCORED_TYPE,
    _EVAL_TYPE_PREFIX,
)
from xianyu_hunter.web.routes.evaluations_list import _match_task_id_filter, _filter_price_range, _parse_eval_score
from xianyu_hunter.web.utils import to_datetime

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])


# ============== Task 11: 自动官方采集统计 API ==============
# ==== auto_collect_stats 辅助函数 ====
def _aggregate_failed_events(failed_rows) -> tuple[int, "Counter[str]"]:
    """聚合失败事件，返回 (failed_count, error_counter)

    error 字段截断前 100 字符作为 reason 分组，
    便于聚合 Top N（原始 error 含堆栈/参数，不截断会导致分组过于分散）"""
    from collections import Counter
    failed_count = 0
    error_counter: Counter[str] = Counter()
    for row in failed_rows:
        failed_count += 1
        try:
            payload = json.loads(row.payload) if isinstance(row.payload, str) else row.payload
            if not isinstance(payload, dict):
                error_counter["解析失败"] += 1
                continue
            # error 字段可能很长，截断前 100 字符作为 reason 分组
            # 为什么截断：原始 error 含堆栈/参数，截断后便于聚合 Top N
            error = str(payload.get("error", "未知错误"))[:100]
            error_counter[error] += 1
        except (json.JSONDecodeError, TypeError):
            error_counter["解析失败"] += 1
    return failed_count, error_counter


def _check_pause_status(conn, fail_pause_threshold: int) -> bool:
    """判断当前是否处于退避暂停状态

    取最近一条 collect.official.failed 事件的 consecutive_failures 字段，
    若 >= 阈值则视为暂停。为什么用最近一条而非累计：退避语义是"连续失败"，
    最近一条的 consecutive_failures 反映了最新连续失败计数"""
    from sqlalchemy import select
    from xianyu_hunter.infra.db_models import EventRow
    latest_failed_row = conn.execute(
        select(EventRow.payload)
        .where(EventRow.type == "collect.official.failed")
        .order_by(EventRow.created_at.desc())
        .limit(1)
    ).first()
    if not latest_failed_row:
        return False
    try:
        latest_payload = json.loads(latest_failed_row.payload) if isinstance(latest_failed_row.payload, str) else latest_failed_row.payload
        if isinstance(latest_payload, dict):
            latest_consecutive = int(latest_payload.get("consecutive_failures", 0))
            return latest_consecutive >= fail_pause_threshold
    # S5713: json.JSONDecodeError 是 ValueError 的子类，移除冗余子类
    except (TypeError, ValueError):
        pass
    return False


@router.get("/auto-collect-stats")
def auto_collect_stats(
    range_hours: int = 24,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """自动官方采集统计（最近 N 小时）

    聚合两类事件：
    - eval.scored AND payload.data_source='official' → 成功采集
    - collect.official.failed → 失败采集

    Returns:
        {
            "range_hours": 24,
            "total": 10,          # 成功 + 失败
            "success": 7,         # 成功采集数
            "failed": 3,          # 失败采集数
            "success_rate": 0.7,  # 成功率（0-1）
            "is_paused": False,   # 当前是否处于退避暂停状态
            "fail_pause_threshold": 3,  # 退避阈值（来自全局配置）
            "top_failures": [     # 失败原因 Top3
                {"reason": "Cookie 过期", "count": 2},
                {"reason": "超时", "count": 1},
            ],
        }
    """
    # range_hours 限定为 {1, 6, 24, 168} 之一（与 /distribution 风格一致）
    # 为什么不用 Query(le/ge)：枚举白名单更严格，避免任意数值输入
    if range_hours not in (1, 6, 24, 168):
        range_hours = 24
    now = _utcnow()
    cutoff = now - timedelta(hours=range_hours)

    from sqlalchemy import select

    from xianyu_hunter.infra.db_models import EventRow
    from xianyu_hunter.infra.yaml_config import get_config

    # 退避阈值来自全局配置（任务级覆盖无法在全局统计端点感知，用全局值近似）
    fail_pause_threshold = get_config().eval.auto_collect_fail_pause_threshold

    success_count = 0
    failed_count = 0
    is_paused = False

    with container.repo.engine.connect() as conn:
        # 成功事件：eval.scored + payload.data_source='official'
        # 用 json_extract 精确查询 JSON 字段 + SQL COUNT，避免 LIKE 全表扫描和 Python 层解析
        # 为什么用 json_extract：LIKE 无法区分 'official' vs 'official_xxx'，
        # 且 json_extract 在 SQLite 3.38+ 有查询优化；COUNT 不加载 payload 到内存
        from sqlalchemy import func
        success_count = conn.execute(
            select(func.count())
            .select_from(EventRow)
            .where(EventRow.type == _EVAL_SCORED_TYPE)
            .where(EventRow.created_at >= cutoff)
            .where(func.json_extract(EventRow.payload, '$.data_source') == 'official')
        ).scalar() or 0

        # 失败事件：collect.official.failed（需加载 payload 聚合 top_failures）
        failed_rows = conn.execute(
            select(EventRow.payload)
            .where(EventRow.type == "collect.official.failed")
            .where(EventRow.created_at >= cutoff)
        ).all()
        failed_count, error_counter = _aggregate_failed_events(failed_rows)

        # 判断当前是否处于退避暂停状态
        is_paused = _check_pause_status(conn, fail_pause_threshold)

    total = success_count + failed_count
    success_rate = (success_count / total) if total > 0 else 0

    return {
        "range_hours": range_hours,
        "total": total,
        "success": success_count,
        "failed": failed_count,
        "success_rate": round(success_rate, 4),
        "is_paused": is_paused,
        "fail_pause_threshold": fail_pause_threshold,
        "top_failures": [
            {"reason": reason, "count": count}
            for reason, count in error_counter.most_common(3)
        ],
    }


# ==== evaluations_distribution 辅助函数 ====
def _load_dist_item_price_map(container: Container, events: list[dict]) -> dict[str, float]:
    """预加载 items 价格映射，用于热力图统计

    为什么按 item_id 批量查询：之前用 list_items(limit=5000) 全量加载"""
    dist_item_ids: set[str] = set()
    for ev in events:
        ev_payload = ev.get("payload") or {}
        iid = str(ev_payload.get("item_id") or ev.get("item_id") or "")
        if iid:
            dist_item_ids.add(iid)
    items = container.repo.list_items_by_ids(list(dist_item_ids)) if dist_item_ids else []
    item_price_map: dict[str, float] = {}
    for it in items:
        iid = it.get("item_id") or it.get("id")
        price = it.get("price")
        if iid and price is not None:
            try:
                item_price_map[str(iid)] = float(price)
            except (TypeError, ValueError):
                pass
    return item_price_map


def _is_within_eval_cutoff(e: dict, cutoff: Any) -> bool:
    """检查事件是否在统计时间窗口内（有合法时间戳且不早于 cutoff）

    拆分自 _collect_dist_eval_records：将时间戳解析 + cutoff 判断收敛到单一函数，
    降低主循环嵌套层级"""
    ts = e.get("created_at", "")
    if not ts:
        return False
    d = to_datetime(ts)
    return d is not None and d >= cutoff


def _resolve_eval_price_from_payload(
    payload: dict, e: dict, item_price_map: dict[str, float],
) -> float | None:
    """从 item_price_map 或 payload.item_price 解析价格

    优先用 item_price_map（items 表结构化数据），其次 payload 中的 item_price
    （_enrich_eval_with_item 补充的历史快照）。转换失败返回 None"""
    item_id = payload.get("item_id") or e.get("item_id")
    price = item_price_map.get(str(item_id)) if item_id else None
    if price is not None:
        return price
    raw_price = payload.get("item_price")
    if raw_price is None:
        return None
    try:
        return float(raw_price)
    except (TypeError, ValueError):
        return None


def _collect_dist_eval_records(
    events: list[dict],
    cutoff: Any,
    item_price_map: dict[str, float],
    task_id: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    include_out_of_range: bool = False,
) -> tuple[list[tuple[float, float | None]], int]:
    """收集评估记录（score, price_or_None），返回 (records, insufficient_count)

    score 必须有（非 None），price 可选。
    分数分布只依赖 score，热力图依赖 price × score。
    score=None（数据不足）的记录不计入分数分布，但计入 insufficient_count

    为什么只统计 eval.scored 而非所有 eval.*：NotifierHub 推送钉钉时会写入
    type="eval.passed"、payload=None、stage="notify" 的记录（hub.py 第 196-204 行），
    这些通知事件没有 score 字段，若用 startswith("eval.") 过滤会被误算为
    insufficient_count，导致前端误报"有 N 条评估记录因卖家信息缺失仅基于价格评估"
    """
    eval_records: list[tuple[float, float | None]] = []
    insufficient_count = 0  # 数据不足的评估数
    for e in events:
        if str(e.get("type", "")) != _EVAL_SCORED_TYPE:
            continue
        if not _is_within_eval_cutoff(e, cutoff):
            continue
        payload = e.get("payload") or {}
        if _match_task_id_filter(payload, e, task_id):
            continue
        price = _resolve_eval_price_from_payload(payload, e, item_price_map)
        price_payload = {**payload, "item_price": price}
        if _filter_price_range(price_payload, min_price, max_price, include_out_of_range):
            continue
        # score=None（数据不足）计入 insufficient_count，区别于转换失败（跳过）
        raw_score = payload.get("score")
        if raw_score is None:
            insufficient_count += 1
            continue
        score = _parse_eval_score(payload)
        if score is None:
            continue
        eval_records.append((score, price))
    return eval_records, insufficient_count


def _calc_marginal_score_and_result(
    eval_records: list[tuple[float, float | None]],
    score_bin_count: int,
    pass_threshold: float,
    auto_threshold: float,
) -> tuple[list[int], dict[str, int]]:
    """计算分数边际分布 + 结果分类（只依赖 score，不依赖 price）

    阈值从实时配置读取，确保与配置页面一致"""
    marginal_score = [0] * score_bin_count
    result_totals: dict[str, int] = {"pass": 0, "auto": 0, "fail": 0}
    smin, smax = 0.0, 100.0
    for score, _ in eval_records:
        si = int((score - smin) / (smax - smin) * score_bin_count)
        si = max(0, min(score_bin_count - 1, si))
        marginal_score[si] += 1
        if score >= auto_threshold:
            result_totals["auto"] += 1
        elif score >= pass_threshold:
            result_totals["pass"] += 1
        else:
            result_totals["fail"] += 1
    return marginal_score, result_totals


def _compute_log_price_bounds(
    prices: list[float],
) -> tuple[float, float, float, float, list[float]]:
    """计算对数价格桶边界，返回 (pmin, pmax, log_pmin, log_pmax, price_range)

    拆分自 _build_2d_buckets：将边界计算（含 pmin==pmax 和 log_pmax==log_pmin
    两个边界情况处理）收敛到独立函数，降低主函数条件分支数"""
    pmin = max(1.0, min(prices))
    pmax = max(prices)
    if pmin == pmax:
        pmin = max(1.0, pmin * 0.9)
        pmax = pmax * 1.1
    log_pmin = math.log10(pmin)
    log_pmax = math.log10(pmax)
    if log_pmax == log_pmin:
        log_pmax = log_pmin + 0.1
    return pmin, pmax, log_pmin, log_pmax, [round(pmin, 2), round(pmax, 2)]


def _init_2d_buckets(
    score_bin_count: int, price_bin_count: int,
) -> list[list[dict[str, int]]]:
    """初始化二维桶，每个桶包含 count/pass/auto/fail 计数

    拆分自 _build_2d_buckets：将嵌套列表推导提取为独立函数，
    避免嵌套推导增加认知复杂度"""
    return [
        [{"count": 0, "pass": 0, "auto": 0, "fail": 0} for _ in range(price_bin_count)]
        for _ in range(score_bin_count)
    ]


def _compute_price_bin_index(
    price: float, pmin: float, pmax: float,
    log_pmin: float, log_pmax: float, price_bin_count: int,
) -> int:
    """计算价格在对数桶中的索引

    拆分自 _build_2d_buckets：将 if/else 分支 + 对数计算提取为独立函数"""
    if pmin <= price <= pmax:
        log_p = math.log10(price)
        pi = int((log_p - log_pmin) / (log_pmax - log_pmin) * price_bin_count)
        return max(0, min(price_bin_count - 1, pi))
    return price_bin_count - 1


def _classify_score_result(
    score: float, pass_threshold: float, auto_threshold: float,
) -> str:
    """按阈值分类评估结果，返回 "auto"/"pass"/"fail"

    拆分自 _build_2d_buckets：将 if/elif/else 链提取为独立函数"""
    if score >= auto_threshold:
        return "auto"
    if score >= pass_threshold:
        return "pass"
    return "fail"


def _sum_price_marginals(
    buckets: list[list[dict[str, int]]],
    score_bin_count: int, price_bin_count: int,
) -> list[int]:
    """按价格桶汇总所有分数桶的 count

    拆分自 _build_2d_buckets：将嵌套推导（list comp + generator in sum）
    提取为独立函数，避免嵌套推导增加认知复杂度"""
    return [
        sum(buckets[si][pi]["count"] for si in range(score_bin_count))
        for pi in range(price_bin_count)
    ]


def _build_2d_buckets(
    eval_records: list[tuple[float, float | None]],
    score_bin_count: int,
    price_bin_count: int,
    pass_threshold: float,
    auto_threshold: float,
) -> tuple[list[list[dict[str, int]]], list[int], list[float]]:
    """构建二维热力图桶，返回 (buckets, marginal_price, price_range)

    价格范围：对数桶（闲鱼商品价格跨 4 个数量级：1元 ~ 1万元）。
    无价格数据时返回空 buckets 和零值 marginal_price。"""
    pairs_with_price: list[tuple[float, float]] = [
        (p, s) for s, p in eval_records if p is not None
    ]
    if not pairs_with_price:
        # 无价格数据时：热力图为空，但分数分布仍有数据
        return [], [0] * price_bin_count, [0.0, 0.0]

    prices = [p for p, _ in pairs_with_price]
    pmin, pmax, log_pmin, log_pmax, price_range = _compute_log_price_bounds(prices)
    buckets = _init_2d_buckets(score_bin_count, price_bin_count)
    smin, smax = 0.0, 100.0
    for price, score in pairs_with_price:
        pi = _compute_price_bin_index(
            price, pmin, pmax, log_pmin, log_pmax, price_bin_count,
        )
        # 分数桶
        si = int((score - smin) / (smax - smin) * score_bin_count)
        si = max(0, min(score_bin_count - 1, si))
        buckets[si][pi]["count"] += 1
        buckets[si][pi][_classify_score_result(score, pass_threshold, auto_threshold)] += 1

    marginal_price = _sum_price_marginals(buckets, score_bin_count, price_bin_count)
    return buckets, marginal_price, price_range


def _build_distribution_5bin(marginal_score: list[int]) -> list[dict[str, Any]]:
    """F-15：5 档分布（0-20/20-40/40-60/60-80/80-100），便于前端直方图直接消费

    使用边界检查避免 marginal_score 长度不足时越界"""
    def _bin_pair_sum(i: int, j: int) -> int:
        return (marginal_score[i] if len(marginal_score) > i else 0) + \
               (marginal_score[j] if len(marginal_score) > j else 0)
    return [
        {"range": "0-20", "count": _bin_pair_sum(0, 1)},
        {"range": "20-40", "count": _bin_pair_sum(2, 3)},
        {"range": "40-60", "count": _bin_pair_sum(4, 5)},
        {"range": "60-80", "count": _bin_pair_sum(6, 7)},
        {"range": "80-100", "count": _bin_pair_sum(8, 9)},
    ]


def _compute_passing_count(marginal_score: list[int], threshold: float) -> float:
    """计算在指定阈值下的通过数量（桶内线性插值）

    threshold 右侧的分数视为通过；桶内 straddle threshold 时按比例计算。
    拆分自 _calc_suggested_threshold：两个循环（二分搜索 + 最终计算）
    复用同一逻辑，消除重复代码并降低嵌套"""
    passing = 0
    for i in range(len(marginal_score)):
        bin_low = i * 10
        bin_high = (i + 1) * 10
        if threshold <= bin_low:
            # 整个桶都在阈值之上，全部通过
            passing += marginal_score[i] or 0
        elif threshold < bin_high:
            # 桶内线性插值：threshold 右侧部分通过
            passing += (marginal_score[i] or 0) * (bin_high - threshold) / 10
    return passing


def _calc_suggested_threshold(
    marginal_score: list[int], total: int,
) -> tuple[int, float]:
    """F-15：二分查找建议阈值——找到使通过率最接近 75% 的分数

    通过率随阈值单调递减，因此二分查找收敛到目标通过率对应的分数。
    无数据时使用配置的 pass_score，避免硬编码导致与实际配置不一致"""
    target_rate = 0.75
    if total == 0:
        return get_config().eval.pass_score, 0.75

    lo, hi = 0.0, 100.0
    for _ in range(30):
        mid = (lo + hi) / 2
        rate = _compute_passing_count(marginal_score, mid) / total
        if rate > target_rate:
            lo = mid
        else:
            hi = mid
    suggested_score = round((lo + hi) / 2)
    # 计算该阈值下的实际通过率
    actual_passing = _compute_passing_count(marginal_score, suggested_score)
    actual_pass_rate = round(actual_passing / total, 2)
    return suggested_score, actual_pass_rate


# ============== P3-UX-09 评估分分布 API ==============
@router.get("/distribution")
def evaluations_distribution(
    request: Request,
    range_hours: int = 168,
    price_bin_count: int = 10,
    score_bin_count: int = 10,
    task_id: str | None = Query(None, description="任务 ID 模糊匹配；用于与评估列表统计口径一致"),
    min_price: float | None = Query(None, ge=0, description="价格下限（含）。未传但传了 task_id 时自动从任务配置读取"),
    max_price: float | None = Query(None, ge=0, description="价格上限（含）。未传但传了 task_id 时自动从任务配置读取"),
    include_out_of_range: bool = Query(False, description="是否显示超出任务价格范围的历史商品"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """P3-UX-09：评估分 × 价格的二维分布

    Args:
        range_hours: 多久内的评估（默认 7 天 = 168h）
        price_bin_count: 价格桶数（X 轴 10 桶）
        score_bin_count: 分数桶数（Y 轴 10 桶，每桶 10 分）

    Returns:
        {
          "range_hours": 168,
          "price_bin_count": 10,
          "score_bin_count": 10,
          "price_range": [0, 5000],     # 价格区间 [min, max]
          "score_range": [0, 100],      # 分数区间
          "buckets": [                  # 10x10 二维桶
            # 桶 [score_idx][price_idx] = {"count": 5, "pass": 2, "auto": 0, "fail": 3}
            [[...], ...],
          ],
          "marginals": {
            "price": [...],   # 10 个价格桶总数
            "score": [...],   # 10 个分数桶总数
            "result": {"pass": N, "auto": N, "fail": N},
          },
          "total": int,
        }
    """
    if range_hours not in (24, 72, 168, 720):
        range_hours = 168
    price_bin_count = max(4, min(price_bin_count, 20))
    score_bin_count = max(5, min(score_bin_count, 20))
    now = _utcnow()
    cutoff = now - timedelta(hours=range_hours)

    # 从 events 拉 eval.*，并 join items 拿价格（item_id 在 payload.item_id）
    # 修复：之前用 list_events(limit=5000) + list_items(limit=5000) 全量加载，
    # 改为按 type 前缀过滤 events，按涉及 item_id 批量查询 items
    # 多用户隔离：仅统计当前账号的评估事件
    user_id = getattr(request.state, "user_id", None)
    events, _ = container.repo.list_events_by_type_prefix(
        type_prefix=_EVAL_TYPE_PREFIX, user_id=user_id,
    )
    from xianyu_hunter.web.routes.evaluations_list import _apply_task_price_fallback
    min_price, max_price = _apply_task_price_fallback(
        container, task_id, min_price, max_price, include_out_of_range
    )
    item_price_map = _load_dist_item_price_map(container, events)

    eval_records, insufficient_count = _collect_dist_eval_records(
        events,
        cutoff,
        item_price_map,
        task_id=task_id,
        min_price=min_price,
        max_price=max_price,
        include_out_of_range=include_out_of_range,
    )

    # total = 所有有 score 的评估数（不要求有 price）
    total = len(eval_records)

    # 阈值从实时配置读取，确保与配置页面一致
    eval_cfg = get_config().eval
    pass_threshold = eval_cfg.pass_score
    auto_threshold = eval_cfg.auto_buy_score

    marginal_score, result_totals = _calc_marginal_score_and_result(
        eval_records, score_bin_count, pass_threshold, auto_threshold
    )

    buckets, marginal_price, price_range = _build_2d_buckets(
        eval_records, score_bin_count, price_bin_count, pass_threshold, auto_threshold
    )

    distribution_5bin = _build_distribution_5bin(marginal_score)

    suggested_score, actual_pass_rate = _calc_suggested_threshold(marginal_score, total)
    suggested_threshold = {"score": suggested_score, "pass_rate": actual_pass_rate}

    return {
        "range_hours": range_hours,
        "price_bin_count": price_bin_count,
        "score_bin_count": score_bin_count,
        "price_range": price_range,
        "score_range": [0, 100],
        "buckets": buckets,
        "marginals": {
            "price": marginal_price,
            "score": marginal_score,
            "result": result_totals,
        },
        "total": total,
        "insufficient_count": insufficient_count,
        "distribution": distribution_5bin,
        "suggested_threshold": suggested_threshold,
        # 返回当前生效的阈值，前端据此动态显示分类标签
        "thresholds": {"pass_score": pass_threshold, "auto_buy_score": auto_threshold},
    }


# ============== F-15 评估分布 + 阈值建议 ==============
# 注意：固定路径路由必须放在动态路径 /{item_id}/ 之前，否则 FastAPI 会把
# "threshold-suggestion" 当作 item_id 匹配到 /{item_id}/seller-trend
# ==== threshold_suggestion 辅助函数 ====
def _build_5bin_distribution(score_marginals: list[int]) -> dict[str, int]:
    """构建 5 档分数分布（0-20/20-40/40-60/60-80/80-100）

    每个 5 档对应 2 个 10 分 score_marginals 桶"""
    labels = ["0-20", "20-40", "40-60", "60-80", "80-100"]
    distribution: dict[str, int] = {}
    for bin_idx in range(5):
        low = score_marginals[bin_idx * 2] if bin_idx * 2 < len(score_marginals) else 0
        high = score_marginals[bin_idx * 2 + 1] if bin_idx * 2 + 1 < len(score_marginals) else 0
        distribution[labels[bin_idx]] = low + high
    return distribution


def _find_suggested_threshold(score_marginals: list[int], total: int, target_pass_rate: float) -> int:
    """从高分到低分累加，找到达到 target_pass_rate 的分数即为建议阈值

    score_marginals[i] 对应 [i*10, (i+1)*10) 分数段；
    在命中桶内线性插值估算精确阈值"""
    target_count = total * target_pass_rate
    accumulated = 0
    suggested_threshold = 100
    for i in range(len(score_marginals) - 1, -1, -1):
        bin_count = score_marginals[i] if i < len(score_marginals) else 0
        accumulated += bin_count
        if accumulated >= target_count:
            # 在该桶内线性插值估算精确阈值
            bin_low = i * 10
            # 桶内还需要多少条才达到目标
            excess = accumulated - target_count
            if bin_count > 0:
                # 从桶底开始，跳过 excess 条对应的分数
                ratio = excess / bin_count
                suggested_threshold = round(bin_low + ratio * 10)
            else:
                suggested_threshold = bin_low
            break
    return suggested_threshold


def _calc_current_pass_rate(score_marginals: list[int], total: int, current_pass: int) -> float:
    """计算当前配置阈值对应的通过率"""
    pass_bin = current_pass // 10  # score_marginals 索引
    pass_count = sum(score_marginals[i] for i in range(pass_bin, len(score_marginals)) if i < len(score_marginals))
    return round(pass_count / total, 2)


@router.get("/threshold-suggestion")
def threshold_suggestion(
    request: Request,
    target_pass_rate: float = Query(0.7, ge=0.1, le=0.95, description="目标通过率"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """F-15：基于评估分布反推建议阈值

    算法：从高分到低分累加，直到达到 target_pass_rate 对应的分数即为建议阈值。
    复用 distribution API 的 marginals.score 数据，不需要新的数据源。
    """
    # 复用 distribution API 获取分数分布（默认 7 天）
    # 多用户隔离：传递 request 以复用用户过滤逻辑
    # 为什么显式传 None：evaluations_distribution 的 task_id 等参数默认值是 Query(None) 对象
    # （FastAPI 路由专用），直接当函数调用时 Query 对象会原样透传，下游 task_id.lower() 崩溃
    dist_data = evaluations_distribution(
        range_hours=168,
        price_bin_count=10,
        score_bin_count=10,
        task_id=None,
        min_price=None,
        max_price=None,
        include_out_of_range=False,
        request=request,
        container=container,
    )

    total = dist_data.get("total", 0)
    score_marginals = dist_data.get("marginals", {}).get("score", [])

    # 5 档分布（0-20/20-40/40-60/60-80/80-100）
    distribution = _build_5bin_distribution(score_marginals)

    if total == 0:
        return {
            "suggested_threshold": get_config().eval.pass_score,
            "target_pass_rate": target_pass_rate,
            "current_pass_rate": 0.0,
            "distribution": distribution,
            "analysis": "暂无评估数据，使用当前配置阈值",
        }

    suggested_threshold = _find_suggested_threshold(score_marginals, total, target_pass_rate)

    # 当前通过率（使用配置的 pass_score 而非硬编码 60）
    current_pass = get_config().eval.pass_score
    current_pass_rate = _calc_current_pass_rate(score_marginals, total, current_pass)

    # 生成分析文本
    analysis = (
        f"当前阈值 {current_pass} 导致 {round(current_pass_rate * 100)}% 通过率，"
        f"建议调至 {suggested_threshold} 分可达到 {round(target_pass_rate * 100)}% 通过率"
    )

    return {
        "suggested_threshold": suggested_threshold,
        "target_pass_rate": target_pass_rate,
        "current_pass_rate": current_pass_rate,
        "distribution": distribution,
        "analysis": analysis,
    }
