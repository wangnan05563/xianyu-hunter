"""PriceStrategy 单元测试"""
from __future__ import annotations

import pytest

from xianyu_hunter.domain.item import ItemDetail
from xianyu_hunter.modules.price_strategy import (
    MarketContext,
    PriceConfig,
    PriceStrategy,
)


def make_item(price: float) -> ItemDetail:
    return ItemDetail(id="i1", title="t", price=price)


# ============== 硬性上限 ==============


def test_max_price_pass() -> None:
    """价格低于上限通过"""
    s = PriceStrategy(PriceConfig(max_price=1000))
    v = s.check(make_item(price=500))
    assert v.pass_ is True


def test_max_price_reject() -> None:
    """价格超过上限拒绝"""
    s = PriceStrategy(PriceConfig(max_price=1000))
    v = s.check(make_item(price=1500))
    assert v.pass_ is False
    assert any("> max" in r for r in v.reasons)


# ============== 硬性下限 ==============


def test_min_price_pass() -> None:
    """价格高于下限通过"""
    s = PriceStrategy(PriceConfig(min_price=10))
    v = s.check(make_item(price=100))
    assert v.pass_ is True


def test_min_price_reject() -> None:
    """价格低于下限拒绝（防 1 元引流）"""
    s = PriceStrategy(PriceConfig(min_price=10))
    v = s.check(make_item(price=1))
    assert v.pass_ is False
    assert any("< min" in r for r in v.reasons)


# ============== 低于市场参考价 ==============


def test_market_ratio_pass() -> None:
    """低于市场参考价通过"""
    s = PriceStrategy(PriceConfig(market_ratio=0.8))
    market = MarketContext(median_price=1000, sample_size=10)
    v = s.check(make_item(price=700), market)  # 700 < 1000*0.8=800
    assert v.pass_ is True


def test_market_ratio_reject() -> None:
    """高于市场参考价拒绝"""
    s = PriceStrategy(PriceConfig(market_ratio=0.8))
    market = MarketContext(median_price=1000, sample_size=10)
    v = s.check(make_item(price=900), market)  # 900 > 1000*0.8=800
    assert v.pass_ is False


def test_market_ratio_skipped_when_small_sample() -> None:
    """样本数 < 3 跳过市场参考价检查"""
    s = PriceStrategy(PriceConfig(market_ratio=0.8))
    market = MarketContext(median_price=1000, sample_size=2)  # < 3
    v = s.check(make_item(price=900), market)
    # 样本不足，应通过
    assert v.pass_ is True


def test_market_ratio_skipped_when_no_median() -> None:
    """无 median 时跳过"""
    s = PriceStrategy(PriceConfig(market_ratio=0.8))
    market = MarketContext(median_price=None, sample_size=10)
    v = s.check(make_item(price=900), market)
    assert v.pass_ is True


# ============== TopN ==============


def test_top_n_pass_when_in_top() -> None:
    """价格在前 N 名内通过"""
    s = PriceStrategy(PriceConfig(top_n=3))
    market = MarketContext(cheaper_seller_count=1, sample_size=10)
    v = s.check(make_item(price=100), market)
    # cheaper_seller_count=1 < top_n=3 → 在前 3 名内
    assert v.pass_ is True


def test_top_n_reject_when_not_in_top() -> None:
    """不在前 N 名拒绝"""
    s = PriceStrategy(PriceConfig(top_n=3))
    market = MarketContext(cheaper_seller_count=5, sample_size=10)
    v = s.check(make_item(price=100), market)
    # 5 个卖家更便宜，说明本商品不在 top 3
    assert v.pass_ is False
    assert any("not_in_top_3" in r for r in v.reasons)


def test_top_n_skipped_when_sample_too_small() -> None:
    """样本数 <= top_n 时跳过"""
    s = PriceStrategy(PriceConfig(top_n=3))
    market = MarketContext(cheaper_seller_count=10, sample_size=3)
    v = s.check(make_item(price=100), market)
    # sample_size == top_n 时跳过
    assert v.pass_ is True


# ============== 组合策略 ==============


def test_combine_max_and_market() -> None:
    """上限 + 市场参考价同时启用"""
    s = PriceStrategy(PriceConfig(max_price=1000, market_ratio=0.8))
    market = MarketContext(median_price=900, sample_size=10)
    # 850 < 1000 OK, 850 < 900*0.8=720 FAIL
    v = s.check(make_item(price=850), market)
    assert v.pass_ is False
    # 应同时报 2 个 reason
    assert len(v.reasons) == 1  # 只有市场参考价未通过（上限通过）


def test_default_config_allows() -> None:
    """默认配置（无规则）全部放行"""
    s = PriceStrategy()  # 全 None
    v = s.check(make_item(price=12345))
    assert v.pass_ is True
    assert v.reasons == []


def test_has_any_rule() -> None:
    """PriceConfig.has_any_rule 判断"""
    assert PriceConfig().has_any_rule() is False
    assert PriceConfig(max_price=100).has_any_rule() is True
    assert PriceConfig(min_price=10).has_any_rule() is True
    assert PriceConfig(market_ratio=0.8).has_any_rule() is True
    assert PriceConfig(top_n=3).has_any_rule() is True
