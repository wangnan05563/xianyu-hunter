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
from xianyu_hunter.web.utils import load_task_price_range, to_datetime

router = APIRouter(prefix="/api", tags=["price-trend"])


def _safe_mean(prices: list[float]) -> float:
    """安全计算均值，空列表返回 0.0"""
    return round(sum(prices) / len(prices), 2) if prices else 0.0


def _safe_diff(current: float, baseline: float) -> float:
    """计算相对基线的涨跌幅（百分比），规避 division by zero"""
    if baseline <= 0 or current <= 0:
        return 0.0
    return round((current - baseline) / baseline * 100, 1)


def _build_price_query(task_id: str | None, t_min: float | None, t_max: float | None):
    """构建价格趋势查询语句

    拆分自 price_trend：将 task_id 分支 + 价格区间过滤收敛到单一函数，
    降低主函数的分支嵌套与认知复杂度（S3776）。"""
    base = select(ItemRow.price, ItemRow.publish_time)
    if task_id and task_id != "all":
        base = base.where(ItemRow.task_id == task_id)
    base = base.order_by(ItemRow.publish_time.desc()).limit(2000)

    if t_min is not None:
        base = base.where(ItemRow.price >= t_min)
    if t_max is not None:
        base = base.where(ItemRow.price <= t_max)
    return base


def _classify_prices_by_time(
    rows, yesterday_start, week_start, month_start
) -> tuple[list[float], list[float], list[float]]:
    """按时间窗口将价格数据分类到今日/7日/30日三个桶

    拆分自 price_trend：将行数据校验 + 时间解析 + 窗口判断收敛到单一函数，
    降低主循环的嵌套层级与认知复杂度（S3776）。

    Returns:
        (today_prices, week_prices, month_prices)
    """
    today: list[float] = []
    week: list[float] = []
    month: list[float] = []
    for r in rows:
        if not r or r[0] is None or not r[1]:
            continue
        price = float(r[0])
        d = to_datetime(r[1])
        if d is None:
            continue
        if d >= month_start:
            month.append(price)
        if d >= week_start:
            week.append(price)
        if d >= yesterday_start:
            today.append(price)
    return today, week, month


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

    重构说明：SQL 构建和时间窗口分类下沉到独立函数（S3776），
    主函数只做流程编排，降低分支嵌套与认知负担。
    """
    now = _utcnow()
    yesterday_start = now - timedelta(days=1)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)

    engine = container.repo.engine
    with engine.connect() as conn:
        task_price_range = load_task_price_range(conn, task_id)
        t_min = task_price_range["min_price"]
        t_max = task_price_range["max_price"]

        stmt = _build_price_query(task_id, t_min, t_max)
        rows = conn.execute(stmt).all()

    today_prices, week_prices, month_prices = _classify_prices_by_time(
        rows, yesterday_start, week_start, month_start
    )

    today_avg = _safe_mean(today_prices)
    d7_avg = _safe_mean(week_prices)
    d30_avg = _safe_mean(month_prices)

    return {
        "task_id": task_id,
        "generated_at": now.isoformat(timespec="seconds"),
        "today_avg": today_avg,
        "d7_avg": d7_avg,
        "d30_avg": d30_avg,
        "delta_pct_7d": _safe_diff(today_avg, d7_avg),
        "delta_pct_30d": _safe_diff(today_avg, d30_avg),
        "sample_size": {
            "today": len(today_prices),
            "d7": len(week_prices),
            "d30": len(month_prices),
        },
        "task_price_range": task_price_range,
    }
