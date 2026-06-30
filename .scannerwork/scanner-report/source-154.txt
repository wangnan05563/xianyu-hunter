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
from xianyu_hunter.infra.db_models import ItemRow, _utcnow
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


@router.get("/stats/price-trend")
def price_trend(
    task_id: str | None = None,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """O-09-26 价格趋势对比基线

    返回今日均价、7日均价、30日均价及相对涨跌幅。
    数据源：items 表 publish_time 字段（商品发布时间）。
    """
    now = _utcnow()
    yesterday_start = now - timedelta(days=1)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)

    engine = container.repo.engine
    with engine.connect() as conn:
        # 拉取最近 2000 条带时间的价格，覆盖 30 天窗口足够
        # 与 price_histogram._build_compare_means 口径一致，确保数据可比
        if task_id and task_id != "all":
            rows = conn.execute(
                select(ItemRow.price, ItemRow.publish_time)
                .where(ItemRow.task_id == task_id)
                .order_by(ItemRow.publish_time.desc())
                .limit(2000)
            ).all()
        else:
            rows = conn.execute(
                select(ItemRow.price, ItemRow.publish_time)
                .order_by(ItemRow.publish_time.desc())
                .limit(2000)
            ).all()

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
    }
