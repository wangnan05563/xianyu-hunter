"""价格策略引擎（设计文档 §3.5 / §6.4）

支持 4 种策略：
1. 硬性价格上限
2. 硬性价格下限（防 1 元引流）
3. 低于市场参考价
4. 同类低价 TopN
"""
from __future__ import annotations

from dataclasses import dataclass

from xianyu_hunter.domain.item import ItemDetail


@dataclass
class PriceConfig:
    min_price: float | None = None        # 下限
    max_price: float | None = None        # 上限
    market_ratio: float | None = None     # 低于市场均价的多少倍（None 表示禁用）
    top_n: int | None = None              # 同类最低前 N 个

    def has_any_rule(self) -> bool:
        return any(
            v is not None for v in (self.min_price, self.max_price, self.market_ratio, self.top_n)
        )


@dataclass
class MarketContext:
    """市场参考上下文（采集器提供）"""
    median_price: float | None = None          # 同关键词中位数
    cheaper_seller_count: int = 0              # 比本商品更便宜的卖家数（逐商品计算）
    sample_size: int = 0                       # 样本数
    # 所有商品价格列表（排序后），供 TopN 策略逐商品计算 cheaper_seller_count
    all_prices: list[float] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.all_prices is None:
            self.all_prices = []

    def cheaper_count_for(self, price: float) -> int:
        """计算比给定价格更便宜的卖家数（用于 TopN 策略逐商品判定）"""
        if not self.all_prices:
            return 0
        return sum(1 for p in self.all_prices if p < price)


@dataclass
class PriceVerdict:
    """价格策略判定结果"""
    pass_: bool                                # 通过（True/False）
    reasons: list[str]


class PriceStrategy:
    """价格策略引擎

    使用：
        strategy = PriceStrategy(PriceConfig(max_price=5000))
        verdict = strategy.check(item, market)
        if not verdict.pass_:
            ...
    """

    def __init__(self, config: PriceConfig | None = None):
        self.config = config or PriceConfig()

    def check(self, item: ItemDetail, market: MarketContext | None = None) -> PriceVerdict:
        reasons: list[str] = []

        # 1. 上限检查
        if self.config.max_price is not None and item.price > self.config.max_price:
            reasons.append(
                f"price {item.price} > max {self.config.max_price}"
            )

        # 2. 下限检查（防 1 元引流）
        if self.config.min_price is not None and item.price < self.config.min_price:
            reasons.append(
                f"price {item.price} < min {self.config.min_price}"
            )

        # 3. 低于市场参考价
        if (
            self.config.market_ratio is not None
            and self.config.market_ratio < 1.0
            and market is not None
            and market.median_price is not None
            and market.sample_size >= 3   # 至少 3 个样本
            and item.price > market.median_price * self.config.market_ratio
        ):
            reasons.append(
                f"price {item.price} > median*ratio {market.median_price * self.config.market_ratio:.0f}"
            )

        # 4. 同类 TopN：只保留最低前 N 个
        if (
            self.config.top_n is not None
            and market is not None
            and market.sample_size > self.config.top_n
        ):
            # 优先从 all_prices 逐商品计算；若未提供则回退到 cheaper_seller_count 字段
            if market.all_prices:
                cheaper = market.cheaper_count_for(item.price)
            else:
                cheaper = market.cheaper_seller_count
            if cheaper >= self.config.top_n:
                reasons.append(
                    f"not_in_top_{self.config.top_n} (cheaper_count={cheaper})"
                )

        return PriceVerdict(
            pass_=len(reasons) == 0,
            reasons=reasons,
        )
