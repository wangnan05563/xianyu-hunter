"""P1-6 价格行情看板增强 API - 品类级价格统计与横向对比

在 F-12 价格直方图基础上，增加品类维度的深度统计：
- 均价 / 中位数 / 历史最低价 / 价格分位数（P10/P25/P75/P90）
- 多品类横向对比（按任务关键词聚合，支持排序）
- 同类物品已售价格区间（捡漏价格参考）
- 捡漏价格多维评估（bargain-eval）

端点：
- GET /api/prices/category-stats        单品类或全品类价格统计
- GET /api/prices/category-comparison   多品类横向对比
- GET /api/prices/sold-range            同类物品已售价格区间（捡漏价格参考）
- GET /api/prices/bargain-eval          捡漏价格多维评估
"""
from __future__ import annotations

import math
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func

from xianyu_hunter.container import Container
from xianyu_hunter.infra.db_models import ItemRow, TaskLinkRow, TaskRow, _utcnow
from xianyu_hunter.web.deps import get_container

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


# ============== 品类级价格统计 ==============


def _load_category_prices(
    conn, task_id: str | None = None,
    apply_task_range_filter: bool = True,
) -> dict[str, dict[str, Any]]:
    """加载各品类（任务）的价格样本

    返回 {task_id: {"name": ..., "keyword": ..., "prices": [...], "task_price_range": {...}}}。
    task_id=None 时加载全部任务；每个品类的价格样本含 publish_time 用于历史最低价计算。

    apply_task_range_filter=True 时按每个任务配置的 min_price/max_price 过滤超范围样本，
    剔除 1 元引流/配件/超范围高价，与 sold_range 端点口径一致。
    task_map 中每个品类会携带 task_price_range 字段，供前端展示任务价格区间。
    """
    # 先取任务元信息（含价格区间）
    if task_id:
        task_rows = conn.execute(
            select(TaskRow.id, TaskRow.name, TaskRow.keyword, TaskRow.min_price, TaskRow.max_price)
            .where(TaskRow.id == task_id)
        ).all()
    else:
        task_rows = conn.execute(
            select(TaskRow.id, TaskRow.name, TaskRow.keyword, TaskRow.min_price, TaskRow.max_price)
        ).all()

    task_map: dict[str, dict[str, Any]] = {
        r[0]: {
            "name": r[1] or r[0],
            "keyword": r[2] or "",
            "prices": [],
            "task_price_range": {
                "min_price": float(r[3]) if r[3] is not None else None,
                "max_price": float(r[4]) if r[4] is not None else None,
            },
        }
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
            # 按任务价格区间过滤，剔除 1 元引流/配件/超范围高价
            if apply_task_range_filter:
                tr = task_map[tid]["task_price_range"]
                lo = tr["min_price"]
                hi = tr["max_price"]
                if (lo is not None and p < lo) or (hi is not None and p > hi):
                    continue
            task_map[tid]["prices"].append(p)
        else:
            orphan_prices.append(p)

    # 把孤儿商品单独归为一类，便于全量统计
    if orphan_prices and not task_id:
        task_map["__orphan__"] = {
            "name": "未分类",
            "keyword": "",
            "prices": orphan_prices,
            "task_price_range": {"min_price": None, "max_price": None},
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

    每个品类按各自任务配置的 min_price/max_price 过滤超范围样本，
    最高价/最低价均不会超出任务配置的上限/下限。
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
            "task_price_range": info.get("task_price_range", {"min_price": None, "max_price": None}),
            **stats,
        })

    # 按样本数降序，便于前端优先展示主流品类
    categories.sort(key=lambda c: c["count"], reverse=True)
    return {"categories": categories, "total_count": total}


_ALLOWED_COMPARISON_SORT = {"mean", "median", "min", "max", "p10", "p25", "p75", "p90", "count"}


def _normalize_comparison_params(sort_by: str, order: str) -> tuple[str, str]:
    """白名单校验排序字段和方向，防止 SQL 注入和无效字段

    非法值统一回退到默认值，不抛错让前端能继续展示。
    """
    if sort_by not in _ALLOWED_COMPARISON_SORT:
        sort_by = "mean"
    if order not in ("asc", "desc"):
        order = "asc"
    return sort_by, order


def _filter_category_prices_by_range(conn, task_map: dict, range_days: int) -> None:
    """range_days>0 时基于 publish_time 重新筛选样本，原地修改 task_map

    原始 task_map 由 _load_category_prices 全量加载，这里清空 prices 后
    按时间窗重新填充，保证统计口径与时间过滤一致。
    同时应用任务价格区间过滤（与 _load_category_prices 的过滤逻辑一致），
    避免时间窗筛选后引入超范围样本。
    """
    if range_days <= 0:
        return
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
            # 按任务价格区间过滤，与 _load_category_prices 保持一致
            tr = task_map[tid].get("task_price_range", {})
            lo = tr.get("min_price")
            hi = tr.get("max_price")
            if (lo is not None and p < lo) or (hi is not None and p > hi):
                continue
            task_map[tid]["prices"].append(p)
        else:
            orphan_prices.append(p)
    if orphan_prices:
        task_map["__orphan__"] = {
            "name": "未分类",
            "keyword": "",
            "prices": orphan_prices,
            "task_price_range": {"min_price": None, "max_price": None},
        }


def _make_comparison_sort_key(sort_by: str, order: str):
    """闭包工厂：捕获 sort_by 和 order 返回排序键函数，避免嵌套三元

    空样本根据排序方向推到队尾，避免 0 值干扰排序。
    """
    def _sort_key(c: dict[str, Any]) -> float:
        if c["count"] > 0:
            return c[sort_by]
        # 空样本根据排序方向推到队尾
        if order == "asc":
            return float("inf")
        return float("-inf")
    return _sort_key


def _compute_deviation_pct(c: dict[str, Any], overall_mean: float) -> float:
    """计算单个品类相对全体均价的偏离度百分比"""
    if overall_mean > 0 and c["count"] > 0:
        return round((c["mean"] - overall_mean) / overall_mean * 100, 1)
    return 0.0


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

    每个品类按各自任务配置的 min_price/max_price 过滤超范围样本。
    """
    sort_by, order = _normalize_comparison_params(sort_by, order)

    engine = container.repo.engine
    with engine.connect() as conn:
        task_map = _load_category_prices(conn)
        _filter_category_prices_by_range(conn, task_map, range_days)

    # 计算统计并排序
    categories: list[dict[str, Any]] = []
    for tid, info in task_map.items():
        stats = _compute_stats(info["prices"])
        categories.append({
            "task_id": tid if tid != "__orphan__" else None,
            "name": info["name"],
            "keyword": info["keyword"],
            "task_price_range": info.get("task_price_range", {"min_price": None, "max_price": None}),
            **stats,
        })

    categories.sort(
        key=_make_comparison_sort_key(sort_by, order),
        reverse=(order == "desc"),
    )

    # 截取前 limit 个
    categories = categories[:limit]

    # 计算横向对比指标：每个品类相对全体的偏离度
    all_prices = [p for c in categories for _ in range(min(c["count"], 100)) for p in [c["mean"]]]
    overall_mean = round(sum(all_prices) / len(all_prices), 2) if all_prices else 0.0
    for c in categories:
        c["deviation_pct"] = _compute_deviation_pct(c, overall_mean)

    return {
        "categories": categories,
        "overall_mean": overall_mean,
        "sort_by": sort_by,
        "order": order,
        "range_days": range_days,
        "total_categories": len(categories),
    }


# ============== 同类物品已售价格区间（捡漏价格参考）=============

# 已售样本不足时的回退阈值：低于此值时回退到全部商品价格
_MIN_SOLD_SAMPLES = 3


def _load_task_price_range(conn, task_id: str | None) -> dict[str, float | None]:
    """读取任务配置的价格区间（min_price/max_price）

    用于过滤超出任务监控范围的异常价格（如 1 元引流、配件、超范围商品），
    与 price_histogram.py 的 _resolve_histogram_scope 和 api_evaluations.py
    的 _apply_task_price_fallback 保持口径一致。

    task_id 为空或任务未配置价格区间时返回 {min: None, max: None}，
    调用方据此跳过过滤，保留原有行为。
    """
    if not task_id:
        return {"min_price": None, "max_price": None}
    row = conn.execute(
        select(TaskRow.min_price, TaskRow.max_price)
        .where(TaskRow.id == task_id)
        .limit(1)
    ).first()
    if not row:
        return {"min_price": None, "max_price": None}
    return {
        "min_price": float(row[0]) if row[0] is not None else None,
        "max_price": float(row[1]) if row[1] is not None else None,
    }


def _filter_by_task_range(
    prices: list[float], task_range: dict[str, float | None]
) -> list[float]:
    """按任务价格区间过滤价格样本

    仅当对应边界存在时才过滤，避免 NULL 边界误删有效样本。
    1 元引流、配件、超范围高价商品会被剔除，让捡漏参考贴近任务实际监控目标。
    """
    lo = task_range.get("min_price")
    hi = task_range.get("max_price")
    if lo is None and hi is None:
        return prices
    return [
        p for p in prices
        if (lo is None or p >= lo) and (hi is None or p <= hi)
    ]


def _load_sold_prices_from_links(
    conn, task_id: str | None, range_days: int,
    task_range: dict[str, float | None] | None = None,
) -> tuple[list[float], int]:
    """从 task_links 表加载已售商品价格

    闲鱼搜索 API 返回 is_sold 字段标识商品是否已售，该字段冗余存储在
    task_links.display JSON 中。已售商品的 price 可近似视为"成交价"。

    注意：闲鱼不公开实际成交价，此处的 price 是商品标价，is_sold=true
    表示商品已被买家拍下，标价即近似成交价。

    task_range 非空时按任务价格区间过滤，剔除 1 元引流/配件等异常样本。
    返回 (过滤后价格列表, 过滤前原始样本数)，调用方据此计算 filtered_count。
    """
    # json_extract 提取 display 中的 is_sold 和 price 字段
    sold_flag = func.json_extract(TaskLinkRow.display, '$.is_sold')
    price_expr = func.json_extract(TaskLinkRow.display, '$.price')

    stmt = (
        select(price_expr)
        .where(TaskLinkRow.link_type == "item")
        .where(sold_flag == 1)  # SQLite json_extract 返回 1/0
    )
    if task_id:
        stmt = stmt.where(TaskLinkRow.task_id == task_id)
    if range_days > 0:
        cutoff = _utcnow() - timedelta(days=range_days)
        stmt = stmt.where(TaskLinkRow.updated_at >= cutoff)
    # 加 LIMIT 防止 task_links 量大时全表扫描 + JSON 解析撑爆内存
    stmt = stmt.limit(5000)

    rows = conn.execute(stmt).all()
    prices: list[float] = []
    for r in rows:
        if r[0] is None:
            continue
        try:
            p = float(r[0])
            if p > 0:
                prices.append(p)
        except (TypeError, ValueError):
            continue
    raw_count = len(prices)
    if task_range:
        prices = _filter_by_task_range(prices, task_range)
    return prices, raw_count


def _load_all_prices_from_items(
    conn, task_id: str | None, range_days: int,
    task_range: dict[str, float | None] | None = None,
) -> tuple[list[float], int]:
    """从 items 表加载全部商品价格（已售样本不足时的回退数据源）

    items 表不区分已售/在售，包含所有采集到的商品。作为已售数据的回退，
    提供更充分的市场价格参考样本。

    task_range 非空时按任务价格区间过滤，剔除 1 元引流/配件等异常样本，
    避免回退数据源被异常低价污染。
    返回 (过滤后价格列表, 过滤前原始样本数)，调用方据此计算 filtered_count。
    """
    stmt = select(ItemRow.price)
    if task_id:
        stmt = stmt.where(ItemRow.task_id == task_id)
    if range_days > 0:
        cutoff = _utcnow() - timedelta(days=range_days)
        stmt = stmt.where(ItemRow.publish_time >= cutoff)

    rows = conn.execute(stmt).all()
    prices = [float(r[0]) for r in rows if r and r[0] is not None and float(r[0]) > 0]
    raw_count = len(prices)
    if task_range:
        prices = _filter_by_task_range(prices, task_range)
    return prices, raw_count


def _compute_sold_range(
    conn, task_id: str | None, range_days: int,
) -> dict[str, Any]:
    """sold_range 与 bargain_eval 共享的核心计算

    返回包含完整统计字段的 dict（含 source/样本数/分位数/task_price_range/filtered_count）。
    两个端点的差异仅在响应外壳（bargain_eval 额外计算 score/level/suggestion），
    内层统计逻辑完全一致，避免重复实现导致口径漂移。

    filtered_count 字段记录被任务价格区间过滤掉的样本数，让前端能展示
    "已过滤 N 个超范围样本"的提示，用户可直观确认过滤是否生效。
    """
    task_range = _load_task_price_range(conn, task_id)

    sold_prices, sold_raw = _load_sold_prices_from_links(conn, task_id, range_days, task_range)
    source = "sold"
    prices = sold_prices
    raw_total = sold_raw
    # 已售样本不足时回退到全部商品价格
    if len(sold_prices) < _MIN_SOLD_SAMPLES:
        all_prices, all_raw = _load_all_prices_from_items(conn, task_id, range_days, task_range)
        raw_total += all_raw
        if len(all_prices) >= _MIN_SOLD_SAMPLES:
            prices = all_prices
            source = "all_fallback"
        elif all_prices:
            # 全部商品样本也不足，但仍返回（有总比无好）
            prices = all_prices
            source = "all_fallback_insufficient"

    # 被任务价格区间过滤掉的样本数 = 原始样本数 - 保留样本数
    filtered_count = max(0, raw_total - len(prices))

    base: dict[str, Any] = {
        "task_price_range": task_range,
        "task_id": task_id,
        "range_days": range_days,
        "filtered_count": filtered_count,
    }

    if not prices:
        base.update({
            "min_price": None,
            "max_price": None,
            "median_price": None,
            "bargain_price": None,
            "p10": None, "p25": None, "p75": None, "p90": None,
            "sample_size": 0,
            "source": "empty",
            "message": "暂无同类物品的已售价格数据，建议先执行实时搜索采集更多商品",
        })
        return base

    sorted_p = sorted(prices)
    n = len(sorted_p)
    min_p = round(sorted_p[0], 2)
    max_p = round(sorted_p[-1], 2)
    median_p = round(_percentile(sorted_p, 0.5), 2)
    p10 = round(_percentile(sorted_p, 0.10), 2)
    p25 = round(_percentile(sorted_p, 0.25), 2)
    p75 = round(_percentile(sorted_p, 0.75), 2)
    p90 = round(_percentile(sorted_p, 0.90), 2)

    # 捡漏价格用 P10 分位数替代历史最低价
    # 旧逻辑 bargain_price=min_p 单个异常低价（如 1 元引流漏网）就会让指标失真；
    # P10 已排除低端 10% 噪声，更贴近真实捡漏机会，同时保留 min_price 字段供参考。
    bargain_p = p10

    source_label = {
        "sold": "已售商品成交价",
        "all_fallback": "全部商品参考价（已售样本不足）",
        "all_fallback_insufficient": "全部商品参考价（样本较少）",
    }.get(source, source)

    base.update({
        "min_price": min_p,
        "max_price": max_p,
        "median_price": median_p,
        "bargain_price": bargain_p,
        "p10": p10, "p25": p25, "p75": p75, "p90": p90,
        "sample_size": n,
        "source": source,
        "source_label": source_label,
    })
    return base


@router.get("/prices/sold-range")
def sold_range(
    task_id: str | None = Query(None, description="任务 ID；不传则统计全部任务"),
    range_days: int = Query(30, ge=0, description="仅统计最近 N 天；0=全部，默认 30 天"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """同类物品已售价格区间（捡漏价格参考）

    返回指定品类下近期已售商品的最低价/最高价/中位数/分位数/样本数。
    P10 分位数作为"捡漏价格"参考指标，用于判断当前商品价格是否低于市场成交价。

    数据来源策略（反映近期市场实际交易情况）：
    1. 优先使用 task_links 中 is_sold=true 的商品价格（近似成交价）
    2. 已售样本不足（<3）时回退到 items 表全部商品价格（市场参考价）
    3. 两者均无数据时返回空结果与友好提示

    任务价格区间过滤：若任务配置了 min_price/max_price，会剔除超出区间的异常样本
    （1 元引流、配件、超范围高价），让捡漏参考贴近任务实际监控目标。
    与 price_histogram.py / api_evaluations.py 的实现保持口径一致。

    注意：闲鱼不公开实际成交价，is_sold=true 的商品标价近似为成交价。
    """
    engine = container.repo.engine
    with engine.connect() as conn:
        return _compute_sold_range(conn, task_id, range_days)


# ============== 捡漏价格多维评估 ==============


def _compute_bargain_level(
    current_price: float, p10: float, p25: float, median: float,
) -> tuple[str, int]:
    """根据当前价格相对分位数的位置评定捡漏等级与得分

    返回 (level, score)。score 用于前端排序/可视化，level 用于文案展示。
    等级阈值基于 P10/P25/median 三档划分：
    - 低于 P10 = excellent（极好的捡漏机会）
    - P10~P25 = good（价格划算）
    - P25~median = fair（价格适中）
    - 高于 median = poor（价格偏高）
    """
    if current_price < p10:
        return "excellent", 95
    if current_price < p25:
        return "good", 80
    if current_price <= median:
        return "fair", 60
    return "poor", 30


def _build_bargain_suggestion(
    level: str, current_price: float,
    p10: float, p25: float, median: float,
    task_range: dict[str, float | None],
) -> str:
    """生成捡漏建议文案

    综合分位数等级与任务价格区间两个维度：
    - 任务区间合理性校验优先（低于 task_min 提示假货风险，高于 task_max 提示超范围）
    - 等级给出基础建议（捡漏/观望/避开）
    """
    t_min = task_range.get("min_price")
    t_max = task_range.get("max_price")

    # 任务区间合理性校验优先于分位数等级
    if t_min is not None and current_price < t_min:
        return f"当前价格 ¥{current_price:.2f} 低于任务配置下限 ¥{t_min:.2f}，可能为异常低价（假货/骗子风险），请谨慎核实。"
    if t_max is not None and current_price > t_max:
        return f"当前价格 ¥{current_price:.2f} 高于任务配置上限 ¥{t_max:.2f}，超出监控目标范围，不建议入手。"

    if level == "excellent":
        return f"当前价格 ¥{current_price:.2f} 低于已售 P10（¥{p10:.2f}），属于极好的捡漏机会，建议尽快入手。"
    if level == "good":
        return f"当前价格 ¥{current_price:.2f} 处于已售 P10~P25 区间（¥{p10:.2f}~¥{p25:.2f}），价格较为划算，可考虑入手。"
    if level == "fair":
        return f"当前价格 ¥{current_price:.2f} 处于已售 P25~中位数区间（¥{p25:.2f}~¥{median:.2f}），价格适中，可观望。"
    return f"当前价格 ¥{current_price:.2f} 高于已售中位数（¥{median:.2f}），价格偏高，不建议捡漏。"


@router.get("/prices/bargain-eval")
def bargain_eval(
    task_id: str = Query(..., description="任务 ID（必填，用于读取任务价格区间与已售样本）"),
    current_price: float = Query(..., gt=0, description="待评估的商品当前价格"),
    range_days: int = Query(30, ge=0, description="仅统计最近 N 天；0=全部，默认 30 天"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """捡漏价格多维评估

    基于任务价格区间 + 近期已售商品分位数分布，对待评估价格给出综合评估：
    - bargain_score：0-100 数值得分（越高越值得捡漏）
    - bargain_level：excellent/good/fair/poor 四档等级
    - suggestion：中文建议文案（含任务区间合理性校验）
    - sold_price_stats：完整的已售价格分位数统计（P10/P25/median/P75/P90/min/max/count）
    - task_price_range：任务配置的价格区间

    评估逻辑：
    1. 读取任务 min_price/max_price，过滤超出区间的异常样本
    2. 加载近期已售商品价格，计算分位数
    3. 根据 current_price 相对 P10/P25/median 的位置评定等级
    4. 任务区间校验优先：低于 task_min 提示假货风险，高于 task_max 提示超范围
    """
    engine = container.repo.engine
    with engine.connect() as conn:
        stats = _compute_sold_range(conn, task_id, range_days)

    # 已售样本为空时直接返回，前端展示空态
    if stats.get("source") == "empty" or stats.get("sample_size", 0) == 0:
        return {
            "task_id": task_id,
            "current_price": current_price,
            "range_days": range_days,
            "bargain_score": 0,
            "bargain_level": "unknown",
            "suggestion": stats.get("message") or "暂无已售价格数据，无法评估",
            "sold_price_stats": None,
            "task_price_range": stats.get("task_price_range", {"min_price": None, "max_price": None}),
        }

    p10 = float(stats["p10"])
    p25 = float(stats["p25"])
    median = float(stats["median_price"])
    task_range = stats.get("task_price_range", {"min_price": None, "max_price": None})

    level, score = _compute_bargain_level(current_price, p10, p25, median)
    suggestion = _build_bargain_suggestion(level, current_price, p10, p25, median, task_range)

    return {
        "task_id": task_id,
        "current_price": current_price,
        "range_days": range_days,
        "bargain_score": score,
        "bargain_level": level,
        "suggestion": suggestion,
        "sold_price_stats": {
            "min": stats["min_price"],
            "max": stats["max_price"],
            "median": stats["median_price"],
            "p10": stats["p10"],
            "p25": stats["p25"],
            "p75": stats["p75"],
            "p90": stats["p90"],
            "count": stats["sample_size"],
            "source": stats["source"],
            "source_label": stats.get("source_label"),
        },
        "task_price_range": task_range,
    }
