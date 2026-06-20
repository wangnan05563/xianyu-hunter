"""P1-6 价格行情看板增强 API - 品类级价格统计与横向对比

在 F-12 价格直方图基础上，增加品类维度的深度统计：
- 均价 / 中位数 / 历史最低价 / 价格分位数（P10/P25/P75/P90）
- 多品类横向对比（按任务关键词聚合，支持排序）

端点：
- GET /api/prices/category-stats        单品类或全品类价格统计
- GET /api/prices/category-comparison   多品类横向对比
"""
from __future__ import annotations

import math
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from xianyu_hunter.container import Container
from xianyu_hunter.infra.db_models import ItemRow, TaskRow, _utcnow
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.utils import to_datetime

router = APIRouter(prefix="/api", tags=["price-dashboard"])


def _percentile(sorted_prices: list[float], p: float) -> float:
    """线性插值分位数（与 price_histogram.py 保持一致）"""
    if not sorted_prices:
        return 0.0
    n = len(sorted_prices)
    if n == 1:
        return float(sorted_prices[0])
    rank = p * (n - 1)
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return float(sorted_prices[lo])
    frac = rank - lo
    return sorted_prices[lo] * (1 - frac) + sorted_prices[hi] * frac


def _compute_stats(prices: list[float]) -> dict[str, float]:
    """计算单组价格的完整统计指标

    返回均价/中位数/历史最低价/历史最高价/P10/P25/P75/P90/样本数。
    分位数采用线性插值法，与 price_histogram 保持算法一致。
    """
    if not prices:
        return {
            "count": 0, "min": 0.0, "max": 0.0, "mean": 0.0, "median": 0.0,
            "p10": 0.0, "p25": 0.0, "p75": 0.0, "p90": 0.0,
        }
    sorted_p = sorted(prices)
    n = len(sorted_p)
    return {
        "count": n,
        "min": round(sorted_p[0], 2),
        "max": round(sorted_p[-1], 2),
        "mean": round(sum(prices) / n, 2),
        "median": round(_percentile(sorted_p, 0.5), 2),
        "p10": round(_percentile(sorted_p, 0.10), 2),
        "p25": round(_percentile(sorted_p, 0.25), 2),
        "p75": round(_percentile(sorted_p, 0.75), 2),
        "p90": round(_percentile(sorted_p, 0.90), 2),
    }


def _load_category_prices(
    conn, task_id: str | None = None
) -> dict[str, dict[str, Any]]:
    """加载各品类（任务）的价格样本

    返回 {task_id: {"name": ..., "keyword": ..., "prices": [...]}}。
    task_id=None 时加载全部任务；每个品类的价格样本含 publish_time 用于历史最低价计算。
    """
    # 先取任务元信息
    if task_id:
        task_rows = conn.execute(
            select(TaskRow.id, TaskRow.name, TaskRow.keyword).where(TaskRow.id == task_id)
        ).all()
    else:
        task_rows = conn.execute(
            select(TaskRow.id, TaskRow.name, TaskRow.keyword)
        ).all()

    task_map: dict[str, dict[str, Any]] = {
        r[0]: {"name": r[1] or r[0], "keyword": r[2] or "", "prices": []}
        for r in task_rows
    }

    # 取商品价格
    if task_id:
        item_rows = conn.execute(
            select(ItemRow.task_id, ItemRow.price, ItemRow.publish_time)
            .where(ItemRow.task_id == task_id)
        ).all()
    else:
        item_rows = conn.execute(
            select(ItemRow.task_id, ItemRow.price, ItemRow.publish_time)
        ).all()

    # 归类到对应任务
    orphan_prices: list[float] = []  # task_id 为 NULL 或任务不存在的孤儿商品
    for r in item_rows:
        tid, price, _ = r[0], r[1], r[2]
        if price is None:
            continue
        p = float(price)
        if tid and tid in task_map:
            task_map[tid]["prices"].append(p)
        else:
            orphan_prices.append(p)

    # 把孤儿商品单独归为一类，便于全量统计
    if orphan_prices and not task_id:
        task_map["__orphan__"] = {
            "name": "未分类",
            "keyword": "",
            "prices": orphan_prices,
        }

    return task_map


@router.get("/prices/category-stats")
def category_stats(
    task_id: str | None = Query(None, description="任务 ID；不传则返回全部品类"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """单品类或全品类价格统计

    返回每个品类的均价/中位数/历史最低价/历史最高价/价格分位数。
    task_id 为空时返回全部品类的统计字典。
    """
    engine = container.repo.engine
    with engine.connect() as conn:
        task_map = _load_category_prices(conn, task_id)

    if not task_map:
        return {"categories": [], "total_count": 0}

    categories: list[dict[str, Any]] = []
    total = 0
    for tid, info in task_map.items():
        stats = _compute_stats(info["prices"])
        total += stats["count"]
        categories.append({
            "task_id": tid if tid != "__orphan__" else None,
            "name": info["name"],
            "keyword": info["keyword"],
            **stats,
        })

    # 按样本数降序，便于前端优先展示主流品类
    categories.sort(key=lambda c: c["count"], reverse=True)
    return {"categories": categories, "total_count": total}


@router.get("/prices/category-comparison")
def category_comparison(
    sort_by: str = Query("mean", description="排序字段: mean/median/min/p25/p75/count"),
    order: str = Query("asc", description="排序方向: asc/desc"),
    limit: int = Query(20, ge=1, le=100, description="最多返回品类数"),
    range_days: int = Query(0, ge=0, description="仅统计最近 N 天的商品；0=全部"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """多品类横向对比

    按 sort_by 排序后返回前 limit 个品类的价格统计。
    range_days>0 时仅统计最近 N 天的商品，便于观察短期行情变化。
    """
    # 白名单校验排序字段，防止 SQL 注入和无效字段
    allowed_sort = {"mean", "median", "min", "max", "p10", "p25", "p75", "p90", "count"}
    if sort_by not in allowed_sort:
        sort_by = "mean"
    if order not in ("asc", "desc"):
        order = "asc"

    engine = container.repo.engine
    with engine.connect() as conn:
        task_map = _load_category_prices(conn)

        # range_days 过滤：基于 publish_time 筛选
        if range_days > 0:
            cutoff = _utcnow() - timedelta(days=range_days)
            # 重新加载带时间过滤的样本
            item_rows = conn.execute(
                select(ItemRow.task_id, ItemRow.price, ItemRow.publish_time)
                .where(ItemRow.publish_time >= cutoff)
            ).all()
            # 清空原有 prices，重新填充
            for info in task_map.values():
                info["prices"] = []
            orphan_prices: list[float] = []
            for r in item_rows:
                tid, price, _ = r[0], r[1], r[2]
                if price is None:
                    continue
                p = float(price)
                if tid and tid in task_map:
                    task_map[tid]["prices"].append(p)
                else:
                    orphan_prices.append(p)
            if orphan_prices:
                task_map["__orphan__"] = {
                    "name": "未分类",
                    "keyword": "",
                    "prices": orphan_prices,
                }

    # 计算统计并排序
    categories: list[dict[str, Any]] = []
    for tid, info in task_map.items():
        stats = _compute_stats(info["prices"])
        categories.append({
            "task_id": tid if tid != "__orphan__" else None,
            "name": info["name"],
            "keyword": info["keyword"],
            **stats,
        })

    # 空样本的品类排在最后，避免 0 值干扰排序
    categories.sort(
        key=lambda c: c[sort_by] if c["count"] > 0 else (float("inf") if order == "asc" else float("-inf")),
        reverse=(order == "desc"),
    )

    # 截取前 limit 个
    categories = categories[:limit]

    # 计算横向对比指标：每个品类相对全体的偏离度
    all_prices = [p for c in categories for _ in range(min(c["count"], 100)) for p in [c["mean"]]]
    overall_mean = round(sum(all_prices) / len(all_prices), 2) if all_prices else 0.0
    for c in categories:
        if overall_mean > 0 and c["count"] > 0:
            c["deviation_pct"] = round((c["mean"] - overall_mean) / overall_mean * 100, 1)
        else:
            c["deviation_pct"] = 0.0

    return {
        "categories": categories,
        "overall_mean": overall_mean,
        "sort_by": sort_by,
        "order": order,
        "range_days": range_days,
        "total_categories": len(categories),
    }
