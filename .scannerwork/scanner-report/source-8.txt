"""领域模型：卖家"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # 仅类型检查时导入，运行时避免循环依赖
    from xianyu_hunter.domain.item import ItemSummary


@dataclass
class SellerProfile:
    """卖家画像"""
    id: str
    nick: str = ""
    credit_score: int | None = None       # 芝麻信用
    register_days: int = 0
    on_sale_count: int = 0
    sold_count: int = 0
    top_category: str | None = None
    top_category_ratio: float = 0.0
    post_count_30d: int = 0
    bad_review_count: int = 0
    in_blacklist: bool = False
    recent_posts: list["ItemSummary"] = field(default_factory=list)  # M-07 修复：补全类型参数
    last_visited: datetime | None = None
    # 与 SellerRow 对齐：最后一次评估时间，用于评估结果展示
    last_eval: datetime | None = None
