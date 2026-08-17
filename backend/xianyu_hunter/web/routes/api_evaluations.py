"""评估明细 API — 路由聚合入口

本模块仅负责从 8 个职责子模块导入 router 并统一 re-export，
不再包含任何业务逻辑实现。

子模块分工：
- evaluations_list.py         → 评估列表 + 数据丰富 + 过滤 + 成色标签
- evaluations_distribution.py → 分数×价格二维分布 + 阈值建议 + 自动采集统计
- evaluations_seller_trend.py → F-12 卖家历史价格趋势
- evaluations_feedback.py     → P3 评估反馈闭环
- evaluations_recompute.py    → 历史评估重新计算
- evaluations_batch.py        → 批量评估未评估商品
- evaluations_official.py     → 官方页面采集 + 重新评估

共享模块：
- evaluations_common.py       → 常量、DTO 构建器、事件发布、价格策略
- evaluations_data_cleaner.py → seller_nick 脏数据清洗
"""
from __future__ import annotations

from fastapi import APIRouter

from xianyu_hunter.web.routes.evaluations_list import router as list_router
from xianyu_hunter.web.routes.evaluations_distribution import router as dist_router
from xianyu_hunter.web.routes.evaluations_seller_trend import router as trend_router
from xianyu_hunter.web.routes.evaluations_feedback import router as feedback_router
from xianyu_hunter.web.routes.evaluations_recompute import router as recompute_router
from xianyu_hunter.web.routes.evaluations_batch import router as batch_router
from xianyu_hunter.web.routes.evaluations_official import router as official_router

# 向后兼容：外部模块/测试通过 api_evaluations 导入的内部符号
# 重构后这些函数已迁移到子模块，此处仅做 re-export 避免破坏已有导入
from xianyu_hunter.web.routes.evaluations_official import _collect_official_and_evaluate  # noqa: F401
from xianyu_hunter.web.routes.evaluations_official import _ensure_official_collect_cookies  # noqa: F401
from xianyu_hunter.web.routes.evaluations_list import _enrich_eval_with_item  # noqa: F401

# 聚合所有子模块路由。
#
# 子模块的 router 已自带 prefix="/api/evaluations"；
# 这里不能再加 prefix，否则会注册成 /api/evaluations/api/evaluations。
#
# include_router 顺序说明：
# 固定路径路由（如 /distribution、/recompute）在前，
# 动态路径路由（如 /{item_id}/seller-trend）在后，
# 避免动态路径误匹配固定路径。
# 实际上本模块所有动态路径都是两段式（/{item_id}/xxx），
# 与单段固定路径（/distribution）不冲突，但保持安全顺序。
router = APIRouter(tags=["evaluations"])
router.include_router(list_router)
router.include_router(dist_router)
router.include_router(trend_router)
router.include_router(feedback_router)
router.include_router(recompute_router)
router.include_router(batch_router)
router.include_router(official_router)
