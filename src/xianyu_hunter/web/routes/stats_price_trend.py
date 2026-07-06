"""价格趋势对比基线 API - O-09-26

端点：
- GET /api/stats/price-trend   今日/7日/30日均价 + 涨跌幅

独立于 /api/prices/histogram，仅返回基线对比数据，
供未来独立趋势图组件或第三方集成使用。
PriceHistogramCard 继续复用 histogram 的 compare 字段，避免重复查询。
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select

from xianyu_hunter.container import Container
from xianyu_hunter.infra.db_models import ItemRow, TaskRow, _utcnow
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.utils import to_datetime

router = APIRouter(prefix="/api", tags=["price-trend"])


def _safe_mean(prices: list[float]) -> float:
    """安全计算均值，空列表返回 0.0"""
    return round(sum(prices) / len(prices), 2) if prices else 0.0


def _safe_diff(current: float, baseline: float) -> float:
    """计算相对基线的涨跌幅（百分比），规避 division by zero"""
    if baseline <= 0 or current <= 0:
        return 0.0
    return round((current - baseline) / baseline * 100, 1)


def _load_task_price_range(conn, task_id: str | None) -> dict[str, float | None]:
    """读取任务配置的价格区间（min_price/max_price）

    用于过滤超出任务监控范围的异常价格（1 元引流/配件/超范围高价），
    与 price_dashboard.py / price_histogram.py 保持口径一致。

    task_id 为空、"all" 或任务不存在时返回 {min: None, max: None}，
    调用方据此跳过过滤。
    """
    if not task_id or task_id == "all":
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


@router.get("/stats/price-trend")
def price_trend(
    task_id: str | None = None,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """O-09-26 价格趋势对比基线

    返回今日均价、7日均价、30日均价及相对涨跌幅。
    数据源：items 表 publish_time 字段（商品发布时间）。

    应用任务价格区间过滤，剔除超出 min_price/max_price 的异常样本，
    与 price_dashboard.py / price_histogram.py 保持口径一致，
    避免异常价格污染今日/7日/30日均价基线。
    """
    now = _utcnow()
    yesterday_start = now - timedelta(days=1)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)

    engine = container.repo.engine
    with engine.connect() as conn:
        # 读取任务价格区间，task_id 为空或 "all" 时跳过过滤
        task_price_range = _load_task_price_range(conn, task_id)
        t_min = task_price_range["min_price"]
        t_max = task_price_range["max_price"]

        # 拉取最近 2000 条带时间的价格，覆盖 30 天窗口足够
        # 与 price_histogram._build_compare_means 口径一致，确保数据可比
        if task_id and task_id != "all":
            stmt = (
                select(ItemRow.price, ItemRow.publish_time)
                .where(ItemRow.task_id == task_id)
                .order_by(ItemRow.publish_time.desc())
                .limit(2000)
            )
        else:
            stmt = (
                select(ItemRow.price, ItemRow.publish_time)
                .order_by(ItemRow.publish_time.desc())
                .limit(2000)
            )

        # 应用任务价格区间过滤，剔除超出范围的异常样本
        if t_min is not None:
            stmt = stmt.where(ItemRow.price >= t_min)
        if t_max is not None:
            stmt = stmt.where(ItemRow.price <= t_max)

        rows = conn.execute(stmt).all()

    today_prices: list[float] = []
    week_prices: list[float] = []
    month_prices: list[float] = []
    for r in rows:
        if not r or r[0] is None or not r[1]:
            continue
        price = float(r[0])
        d = to_datetime(r[1])
        if d is None:
            continue
        if d >= yesterday_start:
            today_prices.append(price)
        if d >= week_start:
            week_prices.append(price)
        if d >= month_start:
            month_prices.append(price)

    today_avg = _safe_mean(today_prices)
    d7_avg = _safe_mean(week_prices)
    d30_avg = _safe_mean(month_prices)

    return {
        "task_id": task_id,
        "generated_at": now.isoformat(timespec="seconds"),
        "today_avg": today_avg,
        "d7_avg": d7_avg,
        "d30_avg": d30_avg,
        # 今日相对 7 日均价的涨跌幅（短期趋势）
        "delta_pct_7d": _safe_diff(today_avg, d7_avg),
        # 今日相对 30 日均价的涨跌幅（中长期趋势）
        "delta_pct_30d": _safe_diff(today_avg, d30_avg),
        # 样本数（透明展示数据可信度）
        "sample_size": {
            "today": len(today_prices),
            "d7": len(week_prices),
            "d30": len(month_prices),
        },
        # 任务价格区间（让前端能展示过滤范围说明）
        "task_price_range": task_price_range,
    }
