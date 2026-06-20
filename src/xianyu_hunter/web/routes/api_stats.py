"""统计 + SSE 事件流 API - 路由注册入口（聚合子模块）

本模块仅负责从 8 个职责子模块导入 router 并统一 re-export，
不再包含任何业务逻辑实现。

子模块分工：
- stats_overview.py    → 总览统计（/stats, /events/recent）
- stats_today.py       → 今日异常雷达（/stats/today）
- timeline.py          → 统一时间线（/timeline）
- sse_stream.py        → SSE 事件流（/events/stream）
- price_histogram.py   → 价格直方图（/prices/histogram）
- trend.py             → 趋势数据（/stats/trend）
- business_kpi.py      → 业务 KPI 看板（/stats/business-kpi）
- seller_trend.py      → 卖家价格趋势（/stats/seller-price-trend）
"""
from __future__ import annotations

from fastapi import APIRouter

from xianyu_hunter.web.routes.stats_overview import router as overview_router
from xianyu_hunter.web.routes.stats_today import router as today_router
from xianyu_hunter.web.routes.timeline import router as timeline_router
from xianyu_hunter.web.routes.sse_stream import router as sse_router
from xianyu_hunter.web.routes.price_histogram import router as price_router
from xianyu_hunter.web.routes.trend import router as trend_router
from xianyu_hunter.web.routes.business_kpi import router as kpi_router
from xianyu_hunter.web.routes.seller_trend import router as seller_router

# 聚合所有子模块路由（保持原有 URL 路径不变）。
#
# 子模块的 router 已经自带 /api 前缀；这里不能再加 prefix="/api"，
# 否则会注册成 /api/api/stats，导致页面顶部状态徽章请求 /api/stats 时 404。
router = APIRouter(tags=["stats"])
router.include_router(overview_router)
router.include_router(today_router)
router.include_router(timeline_router)
router.include_router(sse_router)
router.include_router(price_router)
router.include_router(trend_router)
router.include_router(kpi_router)
router.include_router(seller_router)
