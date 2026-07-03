"""卖家价格趋势 API - F-12 卖家历史价格分析

端点：
- GET /api/stats/seller-price-trend     卖家历史价格趋势（识别涨价模式）
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from xianyu_hunter.container import Container
from xianyu_hunter.infra.db_models import ItemRow, _utcnow
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.utils import to_datetime

router = APIRouter(prefix="/api", tags=["seller-trend"])


@router.get("/stats/seller-price-trend")
def seller_price_trend(
    seller_id: str = Query(..., description="卖家 ID"),
    range_days: int = Query(30, ge=7, le=90, description="统计天数"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """F-12：卖家历史价格趋势

    帮助识别"突然涨价 = 急出/钓鱼"模式
    """
    now = _utcnow()
    cutoff = now - timedelta(days=range_days)
    seven_days_ago = now - timedelta(days=7)

    engine = container.repo.engine
    with engine.connect() as conn:
        # 加 LIMIT 防止贩子类卖家商品数过多撑爆内存（ix_items_seller 索引覆盖 seller_id 过滤）
        rows = conn.execute(
            select(ItemRow.id, ItemRow.title, ItemRow.price, ItemRow.publish_time)
            .where(ItemRow.seller_id == seller_id)
            .order_by(ItemRow.publish_time.asc())
            .limit(500)
        ).all()

    if not rows:
        return {
            "seller_id": seller_id,
            "items": [],
            "price_stats": {"min": 0, "max": 0, "avg": 0, "count": 0, "trend_direction": "stable"},
        }

    items: list[dict[str, Any]] = []
    all_prices: list[float] = []
    recent_prices: list[float] = []
    earlier_prices: list[float] = []

    for row in rows:
        price = float(row.price) if row.price is not None else 0.0
        publish_time = row.publish_time
        pt_dt = to_datetime(publish_time)
        pt_str = pt_dt.isoformat(timespec="seconds") if pt_dt else ""

        items.append({"item_id": row.id, "title": row.title or "", "price": price, "publish_time": pt_str})
        all_prices.append(price)

        # S1066: 合并外层两个 if（pt_dt is not None 与 pt_dt >= cutoff）避免嵌套
        if pt_dt is not None and pt_dt >= cutoff:
            if pt_dt >= seven_days_ago:
                recent_prices.append(price)
            else:
                earlier_prices.append(price)

    price_stats: dict[str, Any] = {
        "min": round(min(all_prices), 2),
        "max": round(max(all_prices), 2),
        "avg": round(sum(all_prices) / len(all_prices), 2),
        "count": len(all_prices),
        "trend_direction": "stable",
    }

    if recent_prices and earlier_prices:
        recent_avg = sum(recent_prices) / len(recent_prices)
        earlier_avg = sum(earlier_prices) / len(earlier_prices)
        if earlier_avg > 0:
            diff_pct = (recent_avg - earlier_avg) / earlier_avg
            if diff_pct > 0.05:
                price_stats["trend_direction"] = "up"
            elif diff_pct < -0.05:
                price_stats["trend_direction"] = "down"
    elif recent_prices and not earlier_prices:
        price_stats["trend_direction"] = "unknown"

    return {
        "seller_id": seller_id,
        "items": items,
        "price_stats": price_stats,
    }
