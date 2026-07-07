"""卖家价格趋势 API — F-12 卖家历史价格趋势

从 api_evaluations.py 拆分。
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from xianyu_hunter.container import Container
from xianyu_hunter.infra.db_models import _utcnow
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.utils import to_datetime

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])


# ============== F-12 卖家历史价格趋势 ==============
# ==== seller_price_trend 辅助函数 ====
def _group_prices_by_date(seller_items: list[dict], cutoff) -> dict[str, list[float]]:
    """按发布日期分组商品价格

    优先用 publish_time，缺失时用 first_seen；
    过滤掉无时间/无价格/转换失败/早于 cutoff 的商品"""
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
    return daily


def _calc_price_points(daily: dict[str, list[float]]) -> list[dict[str, Any]]:
    """按日期排序并计算每日价格统计值（avg/min/max/count）"""
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
    return price_points


def _calc_current_avg(seller_items: list[dict]) -> int:
    """计算当前均价（所有有效价格商品的均价，无价格时返回 0）"""
    current_prices = [float(it["price"]) for it in seller_items if it.get("price") is not None]
    return round(sum(current_prices) / len(current_prices)) if current_prices else 0


def _determine_trend(price_points: list[dict[str, Any]]) -> str:
    """比较首尾 1/3 均价判断趋势方向

    变化超过 5% 才判定为趋势，避免微小波动误判"""
    if len(price_points) < 3:
        return "stable"
    n = len(price_points)
    first_third = price_points[: max(1, n // 3)]
    last_third = price_points[-max(1, n // 3):]
    first_avg = sum(p["avg_price"] for p in first_third) / len(first_third)
    last_avg = sum(p["avg_price"] for p in last_third) / len(last_third)
    if first_avg > 0 and (last_avg - first_avg) / first_avg > 0.05:
        return "up"
    if first_avg > 0 and (first_avg - last_avg) / first_avg > 0.05:
        return "down"
    return "stable"


@router.get("/seller-price-trend")
def seller_price_trend(
    seller_id: str = Query(..., description="卖家 ID"),
    range_days: int = Query(30, ge=7, le=90, description="统计天数"),
    request: Request = None,  # noqa: B008  # 兼容 seller_trend_for_item 内部调用（FastAPI 路由会注入非 None 值）
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

    # 多用户隔离：仅查询当前账号的商品
    user_id = getattr(request.state, "user_id", None) if request is not None else None
    # 查询该卖家的所有商品（SQL 端按 seller_id 过滤，不加载全量 items 再 Python 过滤）
    seller_items = container.repo.list_items_by_seller(
        seller_id, limit=5000, user_id=user_id,
    ) or []

    if not seller_items:
        # 无数据时返回空结构，前端显示"暂无数据"
        return {
            "seller_id": seller_id,
            "items_count": 0,
            "price_points": [],
            "current_avg": 0,
            "trend": "stable",
        }

    daily = _group_prices_by_date(seller_items, cutoff)
    price_points = _calc_price_points(daily)
    current_avg = _calc_current_avg(seller_items)
    trend = _determine_trend(price_points)

    return {
        "seller_id": seller_id,
        "items_count": len(seller_items),
        "price_points": price_points,
        "current_avg": current_avg,
        "trend": trend,
    }


# ============== F-12 评估明细 → 卖家价格趋势 ==============
@router.get("/{item_id}/seller-trend")
def seller_trend_for_item(
    item_id: str,
    request: Request,
    range_days: int = Query(30, ge=7, le=90, description="统计天数"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """F-12：通过 item_id 查询卖家价格趋势

    前端在评估明细页点击"卖家价格趋势"时调用，无需用户手动输入 seller_id。
    先通过 item_id 查出 seller_id，再复用本模块的 seller_price_trend。
    优先从 items 表查询，若商品未入库则回退到事件 payload 中提取 seller_id。
    """
    seller_id: str | None = None

    # 多用户隔离：仅查询当前账号的商品和评估事件
    user_id = getattr(request.state, "user_id", None)
    # 策略1：优先从 items 表查询（数据更完整）
    # 修复：之前直接访问 engine，改为调用 Repository 方法
    item = container.repo.get_item(item_id, user_id=user_id)
    if item and item.get("seller_id"):
        seller_id = str(item["seller_id"])

    # 策略2：items 表无记录时，从事件 payload 回退（评估事件中包含 seller_id）
    if not seller_id:
        payload = container.repo.get_eval_payload_by_item(item_id, user_id=user_id)
        if payload:
            seller_id = payload.get("seller_id")

    if not seller_id:
        raise HTTPException(status_code=404, detail="未找到该商品的卖家信息（商品未入库且无评估事件）")

    # 复用本模块的 seller_price_trend（同返回格式，避免跨路由耦合）
    # 传递 request 以复用用户过滤逻辑
    return seller_price_trend(
        seller_id=seller_id,
        range_days=range_days,
        request=request,
        container=container,
    )
