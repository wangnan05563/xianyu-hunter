"""评估明细 API"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from xianyu_hunter.container import Container
from xianyu_hunter.infra.db_models import _utcnow, ItemRow
from xianyu_hunter.infra.yaml_config import get_config
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.utils import to_datetime

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])


def _enrich_eval_with_item(payload: dict, item_map: dict[str, dict]) -> dict:
    """用 items 表数据丰富评估记录（补充标题、价格、卖家等缺失字段）

    字段名与前端 EvalItem 接口对齐，同时补充商品列表页展示所需的字段。
    """
    item_id = str(payload.get("item_id") or "")
    item = item_map.get(item_id, {})
    if not item:
        return payload

    # 仅补充 payload 中缺失的字段（不覆盖已有值）
    if not payload.get("item_title") and item.get("title"):
        payload["item_title"] = item["title"]
    if not payload.get("item_price") and item.get("price") is not None:
        try:
            payload["item_price"] = float(item["price"])
        except (TypeError, ValueError):
            pass
    if not payload.get("seller_id") and item.get("seller_id"):
        payload["seller_id"] = str(item["seller_id"])
    if not payload.get("seller_nick") and item.get("seller_nick"):
        payload["seller_nick"] = item["seller_nick"]
    if not payload.get("thumb_url") and item.get("thumb_url"):
        payload["thumb_url"] = item["thumb_url"]
    # 补充商品列表页展示字段
    if not payload.get("region") and item.get("region"):
        payload["region"] = item["region"]
    if not payload.get("want_cnt") and item.get("want_cnt") is not None:
        payload["want_cnt"] = item["want_cnt"]
    if not payload.get("publish_time") and item.get("publish_time"):
        payload["publish_time"] = str(item["publish_time"])
    return payload


@router.get("")
def list_evaluations(
    limit: int = 200,
    offset: int = 0,
    page_num: int = Query(1, ge=1, description="页码（从1开始）"),
    page_size: int = Query(20, ge=1, le=200, description="每页条数"),
    item_id: str | None = Query(None, description="商品 ID 模糊匹配"),
    task_id: str | None = Query(None, description="任务 ID 模糊匹配"),
    min_score: int | None = Query(None, ge=0, le=100, description="最低评分"),
    max_score: int | None = Query(None, ge=0, le=100, description="最高评分"),
    start_time: str | None = Query(None, description="开始时间 (YYYY-MM-DD)"),
    end_time: str | None = Query(None, description="结束时间 (YYYY-MM-DD)"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """从 events 表中读 eval.* 事件（与 list_events 共享存储）

    支持按商品 ID、任务 ID 模糊查询，按评分范围、时间范围过滤。
    支持 page_num/page_size 分页（优先于旧版 limit/offset）。
    自动关联 items 表补充标题、价格、卖家等字段。
    """
    # 预解析时间范围边界（避免在循环内反复解析）
    start_dt = to_datetime(start_time) if start_time else None
    end_dt = to_datetime(end_time) if end_time else None
    # end_time 当天结束（23:59:59），覆盖整天
    if end_dt:
        end_dt = end_dt.replace(hour=23, minute=59, second=59)

    rows = container.repo.list_events(limit=limit * 4) or []

    # 预加载 items 表数据，用于丰富评估记录
    item_rows = container.repo.list_items(limit=5000) or []
    item_map: dict[str, dict] = {}
    for it in item_rows:
        iid = str(it.get("item_id") or it.get("id") or "")
        if iid:
            item_map[iid] = it

    evals = []
    for r in rows:
        if not str(r.get("type", "")).startswith("eval."):
            continue
        payload = r.get("payload") or {}

        # 用 items 表数据丰富 payload（补充标题、价格、卖家等）
        _enrich_eval_with_item(payload, item_map)

        # 确保顶层 item_id 有值（兼容旧事件：EventRow.item_id 列可能为空）
        if not r.get("item_id") and payload.get("item_id"):
            r["item_id"] = str(payload["item_id"])

        # 商品 ID 模糊匹配
        if item_id:
            eid = str(payload.get("item_id") or r.get("item_id") or "")
            if item_id.lower() not in eid.lower():
                continue

        # 任务 ID 模糊匹配
        if task_id:
            tid = str(payload.get("task_id") or r.get("task_id") or "")
            if task_id.lower() not in tid.lower():
                continue

        # 评分范围过滤
        score = payload.get("score")
        if score is not None:
            try:
                score = float(score)
            except (TypeError, ValueError):
                score = None
        if min_score is not None and (score is None or score < min_score):
            continue
        if max_score is not None and (score is None or score > max_score):
            continue

        # 时间范围过滤
        if start_dt or end_dt:
            ts = r.get("created_at", "")
            d = to_datetime(ts) if ts else None
            if d is None:
                continue
            if start_dt and d < start_dt:
                continue
            if end_dt and d > end_dt:
                continue

        evals.append(r)

    total = len(evals)
    # 始终使用 page_num/page_size 分页
    actual_offset = (page_num - 1) * page_size
    paged = evals[actual_offset:actual_offset + page_size]
    return {"items": paged, "count": len(paged), "total": total}


@router.get("/latest/{item_id}")
def latest_for_item(
    item_id: str,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    e = container.repo.get_latest_evaluation(item_id)
    if not e:
        raise HTTPException(status_code=404, detail="无该商品评估记录")
    return e


# ============== P3-UX-09 评估分分布 API ==============
@router.get("/distribution")
def evaluations_distribution(
    range_hours: int = 168,
    price_bin_count: int = 10,
    score_bin_count: int = 10,
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
    events = container.repo.list_events(limit=5000) or []
    items = container.repo.list_items(limit=5000) or []
    item_price_map: dict[str, float] = {}
    for it in items:
        iid = it.get("item_id") or it.get("id")
        price = it.get("price")
        if iid and price is not None:
            try:
                item_price_map[str(iid)] = float(price)
            except (TypeError, ValueError):
                pass

    # 收集所有评估事件：score 必须有（非 None），price 可选
    # 分数分布（marginals.score / distribution_5bin）只依赖 score
    # 热力图（buckets）依赖 price × score，price 缺失时跳过热力图但仍计入分数分布
    # 注意：score=None（数据不足）的记录不计入分数分布，但计入总数统计
    eval_records: list[tuple[float, float | None]] = []  # (score, price_or_None)
    insufficient_count = 0  # 数据不足的评估数
    for e in events:
        if not str(e.get("type", "")).startswith("eval."):
            continue
        ts = e.get("created_at", "")
        if not ts:
            continue
        d = to_datetime(ts)
        if d is None or d < cutoff:
            continue
        payload = e.get("payload") or {}
        score = payload.get("score")
        if score is None:
            insufficient_count += 1
            continue
        try:
            score = float(score)
        except (TypeError, ValueError):
            continue
        item_id = payload.get("item_id") or e.get("item_id")
        price = item_price_map.get(str(item_id)) if item_id else None
        # 如果 payload 中已有价格（从 _enrich_eval_with_item 补充的），优先使用
        # 字段名与 worker.py 写入的 payload 对齐：item_price
        if price is None and payload.get("item_price") is not None:
            try:
                price = float(payload["item_price"])
            except (TypeError, ValueError):
                pass
        eval_records.append((score, price))

    # total = 所有有 score 的评估数（不要求有 price）
    total = len(eval_records)

    # 分数边际分布 + 结果分类（只依赖 score，不依赖 price）
    # 阈值从实时配置读取，确保与配置页面一致
    eval_cfg = get_config().eval
    pass_threshold = eval_cfg.pass_score
    auto_threshold = eval_cfg.auto_buy_score

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

    # 二维热力图桶：只统计有 price 的评估
    pairs_with_price: list[tuple[float, float]] = [
        (p, s) for s, p in eval_records if p is not None
    ]

    if not pairs_with_price:
        # 无价格数据时：热力图为空，但分数分布仍有数据
        buckets: list[list[dict[str, int]]] = []
        marginal_price = [0] * price_bin_count
        price_range = [0.0, 0.0]
    else:
        # 价格范围：对数桶（闲鱼商品价格跨 4 个数量级：1元 ~ 1万元）
        prices = [p for p, _ in pairs_with_price]
        pmin = max(1.0, min(prices))
        pmax = max(prices)
        if pmin == pmax:
            pmin = max(1.0, pmin * 0.9)
            pmax = pmax * 1.1
        log_pmin = math.log10(pmin)
        log_pmax = math.log10(pmax)
        if log_pmax == log_pmin:
            log_pmax = log_pmin + 0.1
        price_range = [round(pmin, 2), round(pmax, 2)]

        # 二维桶 [score_idx][price_idx]
        buckets = [
            [{"count": 0, "pass": 0, "auto": 0, "fail": 0} for _ in range(price_bin_count)]
            for _ in range(score_bin_count)
        ]
        for price, score in pairs_with_price:
            # 价格桶（对数刻度）
            if pmin <= price <= pmax:
                log_p = math.log10(price)
                pi = int((log_p - log_pmin) / (log_pmax - log_pmin) * price_bin_count)
                pi = max(0, min(price_bin_count - 1, pi))
            else:
                pi = price_bin_count - 1
            # 分数桶
            si = int((score - smin) / (smax - smin) * score_bin_count)
            si = max(0, min(score_bin_count - 1, si))
            buckets[si][pi]["count"] += 1
            if score >= auto_threshold:
                buckets[si][pi]["auto"] += 1
            elif score >= pass_threshold:
                buckets[si][pi]["pass"] += 1
            else:
                buckets[si][pi]["fail"] += 1

        marginal_price = [sum(buckets[si][pi]["count"] for si in range(score_bin_count))
                          for pi in range(price_bin_count)]

    # F-15：5 档分布之前的准备工作
    # total 已在前面计算（所有有 score 的评估数，不依赖 price）

    # F-15：5 档分布（0-20/20-40/40-60/60-80/80-100），便于前端直方图直接消费
    distribution_5bin: list[dict[str, Any]] = [
        {"range": "0-20", "count": (marginal_score[0] if len(marginal_score) > 0 else 0)
                              + (marginal_score[1] if len(marginal_score) > 1 else 0)},
        {"range": "20-40", "count": (marginal_score[2] if len(marginal_score) > 2 else 0)
                              + (marginal_score[3] if len(marginal_score) > 3 else 0)},
        {"range": "40-60", "count": (marginal_score[4] if len(marginal_score) > 4 else 0)
                              + (marginal_score[5] if len(marginal_score) > 5 else 0)},
        {"range": "60-80", "count": (marginal_score[6] if len(marginal_score) > 6 else 0)
                              + (marginal_score[7] if len(marginal_score) > 7 else 0)},
        {"range": "80-100", "count": (marginal_score[8] if len(marginal_score) > 8 else 0)
                               + (marginal_score[9] if len(marginal_score) > 9 else 0)},
    ]

    # F-15：二分查找建议阈值——找到使通过率最接近 75% 的分数
    # 通过率随阈值单调递减，因此二分查找收敛到目标通过率对应的分数
    target_rate = 0.75
    if total > 0:
        lo, hi = 0.0, 100.0
        for _ in range(30):
            mid = (lo + hi) / 2
            passing = 0
            for i in range(len(marginal_score)):
                bin_low = i * 10
                bin_high = (i + 1) * 10
                if mid <= bin_low:
                    # 整个桶都在阈值之上，全部通过
                    passing += marginal_score[i] or 0
                elif mid < bin_high:
                    # 桶内线性插值：mid 右侧部分通过
                    passing += (marginal_score[i] or 0) * (bin_high - mid) / 10
            rate = passing / total
            if rate > target_rate:
                lo = mid
            else:
                hi = mid
        suggested_score = round((lo + hi) / 2)
        # 计算该阈值下的实际通过率
        passing = 0
        for i in range(len(marginal_score)):
            bin_low = i * 10
            bin_high = (i + 1) * 10
            if suggested_score <= bin_low:
                passing += marginal_score[i] or 0
            elif suggested_score < bin_high:
                passing += (marginal_score[i] or 0) * (bin_high - suggested_score) / 10
        actual_pass_rate = round(passing / total, 2)
    else:
        suggested_score = 60
        actual_pass_rate = 0.75

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


# ============== F-12 卖家历史价格趋势 ==============
@router.get("/seller-price-trend")
def seller_price_trend(
    seller_id: str = Query(..., description="卖家 ID"),
    range_days: int = Query(30, ge=7, le=90, description="统计天数"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """F-12：卖家历史价格趋势

    聚合该卖家所有在售商品的价格分布，按发布日期分组返回价格变化趋势。
    算法：
    1. 从 items 表查询 seller_id 匹配的商品
    2. 按 publish_time（或 first_seen）日期分组
    3. 每组计算 avg/min/max/count
    4. 比较首尾均价判断趋势方向
    """
    now = _utcnow()
    cutoff = now - timedelta(days=range_days)

    # 查询该卖家的所有商品
    all_items = container.repo.list_items(limit=5000) or []
    seller_items = [it for it in all_items if it.get("seller_id") == seller_id]

    if not seller_items:
        # 无数据时返回空结构，前端显示"暂无数据"
        return {
            "seller_id": seller_id,
            "items_count": 0,
            "price_points": [],
            "current_avg": 0,
            "trend": "stable",
        }

    # 按日期分组：优先用 publish_time，缺失时用 first_seen
    daily: dict[str, list[float]] = {}
    for it in seller_items:
        ts = it.get("publish_time") or it.get("first_seen")
        if not ts:
            continue
        d = to_datetime(ts)
        if d is None or d < cutoff:
            continue
        price = it.get("price")
        if price is None:
            continue
        try:
            p = float(price)
        except (TypeError, ValueError):
            continue
        date_key = d.strftime("%Y-%m-%d")
        daily.setdefault(date_key, []).append(p)

    # 按日期排序并计算统计值
    price_points: list[dict[str, Any]] = []
    for date_key in sorted(daily.keys()):
        prices = daily[date_key]
        price_points.append({
            "date": date_key,
            "avg_price": round(sum(prices) / len(prices)),
            "min_price": round(min(prices)),
            "max_price": round(max(prices)),
            "count": len(prices),
        })

    # 当前均价（最近一天或所有商品）
    current_prices = [float(it["price"]) for it in seller_items if it.get("price") is not None]
    current_avg = round(sum(current_prices) / len(current_prices)) if current_prices else 0

    # 趋势判断：比较前 1/3 和后 1/3 的均价
    trend = "stable"
    if len(price_points) >= 3:
        n = len(price_points)
        first_third = price_points[: max(1, n // 3)]
        last_third = price_points[-max(1, n // 3):]
        first_avg = sum(p["avg_price"] for p in first_third) / len(first_third)
        last_avg = sum(p["avg_price"] for p in last_third) / len(last_third)
        # 变化超过 5% 才判定为趋势，避免微小波动误判
        if first_avg > 0 and (last_avg - first_avg) / first_avg > 0.05:
            trend = "up"
        elif first_avg > 0 and (first_avg - last_avg) / first_avg > 0.05:
            trend = "down"

    return {
        "seller_id": seller_id,
        "items_count": len(seller_items),
        "price_points": price_points,
        "current_avg": current_avg,
        "trend": trend,
    }


# ============== F-15 评估分布 + 阈值建议 ==============
# 注意：固定路径路由必须放在动态路径 /{item_id}/ 之前，否则 FastAPI 会把
# "threshold-suggestion" 当作 item_id 匹配到 /{item_id}/seller-trend
@router.get("/threshold-suggestion")
def threshold_suggestion(
    target_pass_rate: float = Query(0.7, ge=0.1, le=0.95, description="目标通过率"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """F-15：基于评估分布反推建议阈值

    算法：从高分到低分累加，直到达到 target_pass_rate 对应的分数即为建议阈值。
    复用 distribution API 的 marginals.score 数据，不需要新的数据源。
    """
    # 复用 distribution API 获取分数分布（默认 7 天）
    dist_data = evaluations_distribution(
        range_hours=168,
        price_bin_count=10,
        score_bin_count=10,
        container=container,
    )

    total = dist_data.get("total", 0)
    score_marginals = dist_data.get("marginals", {}).get("score", [])

    # 5 档分布（0-20/20-40/40-60/60-80/80-100）
    distribution: dict[str, int] = {
        "0-20": (score_marginals[0] if len(score_marginals) > 0 else 0)
                + (score_marginals[1] if len(score_marginals) > 1 else 0),
        "20-40": (score_marginals[2] if len(score_marginals) > 2 else 0)
                 + (score_marginals[3] if len(score_marginals) > 3 else 0),
        "40-60": (score_marginals[4] if len(score_marginals) > 4 else 0)
                 + (score_marginals[5] if len(score_marginals) > 5 else 0),
        "60-80": (score_marginals[6] if len(score_marginals) > 6 else 0)
                 + (score_marginals[7] if len(score_marginals) > 7 else 0),
        "80-100": (score_marginals[8] if len(score_marginals) > 8 else 0)
                  + (score_marginals[9] if len(score_marginals) > 9 else 0),
    }

    if total == 0:
        return {
            "suggested_threshold": get_config().eval.pass_score,
            "target_pass_rate": target_pass_rate,
            "current_pass_rate": 0.0,
            "distribution": distribution,
            "analysis": "暂无评估数据，使用当前配置阈值",
        }

    # 从高分到低分累加，找到达到 target_pass_rate 的分数
    # score_marginals[i] 对应 [i*10, (i+1)*10) 分数段
    target_count = total * target_pass_rate
    accumulated = 0
    suggested_threshold = 100

    for i in range(len(score_marginals) - 1, -1, -1):
        bin_count = score_marginals[i] if i < len(score_marginals) else 0
        accumulated += bin_count
        if accumulated >= target_count:
            # 在该桶内线性插值估算精确阈值
            bin_low = i * 10
            bin_high = (i + 1) * 10
            # 桶内还需要多少条才达到目标
            excess = accumulated - target_count
            if bin_count > 0:
                # 从桶底开始，跳过 excess 条对应的分数
                ratio = excess / bin_count
                suggested_threshold = round(bin_low + ratio * 10)
            else:
                suggested_threshold = bin_low
            break

    # 当前通过率（使用配置的 pass_score 而非硬编码 60）
    current_pass = get_config().eval.pass_score
    pass_bin = current_pass // 10  # score_marginals 索引
    pass_count = sum(score_marginals[i] for i in range(pass_bin, len(score_marginals)) if i < len(score_marginals))
    current_pass_rate = round(pass_count / total, 2)

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


# ============== F-12 评估明细 → 卖家价格趋势 ==============
@router.get("/{item_id}/seller-trend")
def seller_trend_for_item(
    item_id: str,
    range_days: int = Query(30, ge=7, le=90, description="统计天数"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """F-12：通过 item_id 查询卖家价格趋势

    前端在评估明细页点击"卖家价格趋势"时调用，无需用户手动输入 seller_id。
    先通过 item_id 查出 seller_id，再复用本模块的 seller_price_trend。
    """
    engine = container.repo.engine
    with engine.connect() as conn:
        row = conn.execute(
            select(ItemRow.seller_id)
            .where(ItemRow.id == item_id)
            .limit(1)
        ).first()

    if not row or not row.seller_id:
        raise HTTPException(status_code=404, detail="未找到该商品或卖家信息")

    seller_id = row.seller_id

    # 复用本模块的 seller_price_trend（同返回格式，避免跨路由耦合）
    return seller_price_trend(
        seller_id=seller_id,
        range_days=range_days,
        container=container,
    )


# ============== 历史评估重新计算 ==============
@router.post("/recompute")
def recompute_evaluations(
    task_id: str | None = Query(None, description="可选：仅重新计算指定任务的评估"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """用当前配置的评估规则重新计算历史评估数据

    读取 events 表中所有 eval.scored 事件，从 items + sellers 表重建
    ItemDetail 和 SellerProfile，用当前配置的 Evaluator 重新评分，
    更新 events 表的 payload。
    """
    import json as _json
    from xianyu_hunter.domain.item import ItemDetail
    from xianyu_hunter.domain.seller import SellerProfile

    evaluator = container.evaluator

    # 拉取所有评估事件
    events = container.repo.list_events(limit=10000) or []
    eval_events = [e for e in events if str(e.get("type", "")).startswith("eval.")]

    # 按需过滤任务
    if task_id:
        eval_events = [e for e in eval_events if e.get("task_id") == task_id]

    if not eval_events:
        return {"ok": True, "recomputed": 0, "message": "无评估记录需要重新计算"}

    # 预加载 items 和 sellers 数据
    item_rows = container.repo.list_items(limit=10000) or []
    item_map: dict[str, dict] = {}
    for it in item_rows:
        iid = str(it.get("item_id") or it.get("id") or "")
        if iid:
            item_map[iid] = it

    # 预加载 sellers
    seller_map: dict[str, dict] = {}
    for it in item_rows:
        sid = str(it.get("seller_id") or "")
        if sid and sid not in seller_map:
            s = container.repo.get_seller(sid)
            if s:
                seller_map[sid] = s

    recomputed = 0
    skipped = 0
    errors = 0

    for e in eval_events:
        try:
            payload = e.get("payload") or {}
            if isinstance(payload, str):
                payload = _json.loads(payload)

            item_id = str(payload.get("item_id") or e.get("item_id") or "")
            if not item_id:
                skipped += 1
                continue

            item_data = item_map.get(item_id)
            if not item_data:
                skipped += 1
                continue

            seller_id = str(item_data.get("seller_id") or payload.get("seller_id") or "")
            seller_data = seller_map.get(seller_id, {})

            # 重建 ItemDetail（仅包含评估所需字段）
            detail = ItemDetail(
                id=item_id,
                title=str(item_data.get("title") or payload.get("item_title") or ""),
                price=float(item_data.get("price") or 0),
                region=str(item_data.get("region") or ""),
                seller_id=seller_id,
                seller_nick=str(item_data.get("seller_nick") or ""),
            )

            # 重建 SellerProfile
            seller = SellerProfile(
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

            # 用当前配置重新评估
            eval_result = evaluator.evaluate(detail, seller)

            # 更新 payload（保留原始字段，仅更新评分相关字段）
            payload["score"] = eval_result.score
            payload["risk_level"] = eval_result.risk_level.value
            payload["dimension_scores"] = eval_result.dimension_scores
            payload["reject_reasons"] = eval_result.reject_reasons
            payload["is_passed"] = eval_result.is_passed
            payload["data_quality"] = eval_result.data_quality
            payload["recomputed_at"] = _utcnow().isoformat()

            # 更新 events 表
            event_id = e.get("id")
            if event_id:
                container.repo.update_event_payload(event_id, _json.dumps(payload, ensure_ascii=False, default=str))
                recomputed += 1

        except Exception:
            errors += 1
            continue

    return {
        "ok": True,
        "recomputed": recomputed,
        "skipped": skipped,
        "errors": errors,
        "total": len(eval_events),
        "message": f"已重新计算 {recomputed} 条评估记录（跳过 {skipped}，错误 {errors}）",
    }
