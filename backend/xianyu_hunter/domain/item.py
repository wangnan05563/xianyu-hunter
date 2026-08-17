"""领域模型：商品"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ItemSummary:
    """搜索结果列表中的商品摘要"""
    id: str
    title: str
    price: float
    region: str = ""
    brand: str = ""  # 商品品牌（从搜索 API 或标题兜底推断）
    seller_id: str = ""
    seller_nick: str = ""  # 卖家昵称（从搜索结果提取）
    want_cnt: int = 0
    view_cnt: int = 0
    publish_time: datetime | None = None
    thumb_url: str = ""
    is_sold: bool = False  # 是否已售出（用于前端过滤）
    # 从搜索API提取的卖家基本信息（用于降级评估）
    seller_credit_score: int | None = None  # 芝麻信用分
    seller_on_sale_count: int = 0  # 在售商品数
    seller_sold_count: int = 0  # 已售商品数
    seller_credit: str = ""  # 卖家信用度描述（如"极好/良好/优秀"，从搜索卡片提取）


@dataclass
class ItemDetail(ItemSummary):
    """商品详情"""
    description: str = ""
    image_urls: list[str] = field(default_factory=list)
    raw_json: dict = field(default_factory=dict)
    # 从详情页DOM提取的额外卖家信息（用于降级评估）
    detail_seller_nick: str = ""       # 详情页中的卖家昵称
    detail_credit_score: int | None = None  # 详情页中的信用分
    detail_on_sale_count: int = 0      # 在售数（从详情页）
    detail_sold_count: int = 0         # 已售数（从详情页）
    detail_register_days: int = 0      # 注册天数（从详情页"来闲鱼X天"）
