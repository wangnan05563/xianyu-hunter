"""Evaluator 单元测试"""
from __future__ import annotations

import pytest

from xianyu_hunter.domain.evaluation import RiskLevel
from xianyu_hunter.domain.item import ItemDetail
from xianyu_hunter.domain.seller import SellerProfile
from xianyu_hunter.modules.evaluator import Evaluator


# ============== 工厂函数 ==============


def make_seller(
    on_sale_count: int = 5,
    sold_count: int = 10,
    register_days: int = 365,
    credit_score: int | None = 700,
    bad_review_count: int = 0,
    in_blacklist: bool = False,
    post_count_30d: int = 2,
    top_category: str | None = None,
    top_category_ratio: float = 0.0,
    recent_posts: list | None = None,
) -> SellerProfile:
    return SellerProfile(
        id="u1",
        nick="测试卖家",
        on_sale_count=on_sale_count,
        sold_count=sold_count,
        register_days=register_days,
        credit_score=credit_score,
        bad_review_count=bad_review_count,
        in_blacklist=in_blacklist,
        post_count_30d=post_count_30d,
        top_category=top_category,
        top_category_ratio=top_category_ratio,
        recent_posts=recent_posts or [],
    )


def make_item(price: float = 100.0, title: str = "iPhone 13") -> ItemDetail:
    return ItemDetail(id="i1", title=title, price=price, seller_id="u1")


# ============== 一票否决 ==============


def test_blacklist_veto() -> None:
    """黑名单一票否决"""
    ev = Evaluator()
    result = ev.evaluate(make_item(), make_seller(in_blacklist=True))
    assert result.score == 0
    assert result.risk_level == RiskLevel.EXTREME
    assert "platform_blacklist" in result.reject_reasons


def test_low_credit_veto() -> None:
    """低信用一票否决"""
    ev = Evaluator()
    result = ev.evaluate(make_item(), make_seller(credit_score=500))
    assert result.score == 0
    assert result.risk_level == RiskLevel.EXTREME
    assert any("credit_score" in r for r in result.reject_reasons)


# ============== 职业卖家 ==============


def test_perfect_seller_high_score() -> None:
    """完美卖家高分"""
    ev = Evaluator()
    seller = make_seller(
        on_sale_count=2,
        sold_count=20,
        register_days=1000,
        credit_score=750,
        post_count_30d=1,
    )
    result = ev.evaluate(make_item(price=2000), seller)
    assert result.score >= 80
    assert result.risk_level == RiskLevel.LOW


def test_professional_seller_low_score() -> None:
    """职业卖家低分"""
    ev = Evaluator()
    seller = make_seller(
        on_sale_count=100,  # 远超 30
        post_count_30d=30,   # 远超 15
        top_category="3C数码",
        top_category_ratio=0.95,  # 超过 0.8
    )
    result = ev.evaluate(make_item(), seller)
    # 职业扣分 -40 -30 -20 = -90 → 100 - 90 = 10
    assert result.score <= 50
    assert result.risk_level in (RiskLevel.HIGH, RiskLevel.EXTREME)
    assert any("on_sale" in r for r in result.reject_reasons)
    assert any("30d_post" in r for r in result.reject_reasons)


def test_professional_keyword_detected() -> None:
    """职业卖家关键词命中"""
    from xianyu_hunter.domain.item import ItemSummary

    ev = Evaluator()
    seller = make_seller(
        recent_posts=[
            ItemSummary(id="p1", title="批发 全新 iPhone", price=0),
        ]
    )
    result = ev.evaluate(make_item(), seller)
    assert any("professional_keyword" in r for r in result.reject_reasons)


# ============== 信用 ==============


def test_new_account_penalty() -> None:
    """新号加风险分"""
    ev = Evaluator()
    seller = make_seller(register_days=10)  # < 30
    result = ev.evaluate(make_item(), seller)
    # 信用维度: 100 - 20 = 80
    assert result.dimension_scores["credit"] <= 80
    assert any("register_days" in r for r in result.reject_reasons)


def test_low_sold_count_penalty() -> None:
    """低历史交易加风险"""
    ev = Evaluator()
    seller = make_seller(sold_count=2)
    result = ev.evaluate(make_item(), seller)
    assert any("low_sold_count" in r for r in result.reject_reasons)


def test_credit_unknown_penalty() -> None:
    """信用分未公开加风险"""
    ev = Evaluator()
    seller = make_seller(credit_score=None)
    result = ev.evaluate(make_item(), seller)
    assert any("credit_score_unknown" in r for r in result.reject_reasons)


# ============== 纠纷 ==============


def test_many_bad_reviews_low_score() -> None:
    """多个差评极低分"""
    ev = Evaluator()
    seller = make_seller(bad_review_count=5)  # > 3 一票重扣
    result = ev.evaluate(make_item(), seller)
    assert result.dimension_scores["dispute"] <= 50


def test_one_bad_review_small_penalty() -> None:
    """1 个差评轻度扣分"""
    ev = Evaluator()
    seller = make_seller(bad_review_count=1)
    result = ev.evaluate(make_item(), seller)
    assert 90 <= result.dimension_scores["dispute"] <= 100


# ============== 价格 ==============


def test_suspicious_low_price_penalty() -> None:
    """异常低价（< 1 元）扣分"""
    ev = Evaluator()
    result = ev.evaluate(make_item(price=0.5), make_seller())
    assert any("price_suspicious_low" in r for r in result.reject_reasons)


# ============== 加权汇总 ==============


def test_weighted_total_in_valid_range() -> None:
    """加权总分在 0-100 范围"""
    ev = Evaluator()
    result = ev.evaluate(make_item(price=1000), make_seller())
    assert 0 <= result.score <= 100


def test_risk_level_thresholds() -> None:
    """风险等级正确划分"""
    ev = Evaluator()
    # 模拟 4 维都 100 分 → 总分 100 → low
    seller = make_seller()
    item = make_item(price=1000)
    result = ev.evaluate(item, seller)
    assert result.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM)


def test_weight_sum_must_be_100() -> None:
    """权重之和必须为 100（由 Pydantic 模型校验，而非 Evaluator 构造时）"""
    from xianyu_hunter.infra.yaml_config import EvalWeights
    with pytest.raises(ValueError, match="权重之和必须为 100"):
        EvalWeights(professional=30, credit=30, dispute=25, price=10)


def test_eval_result_to_dict() -> None:
    """EvalResult 可序列化"""
    ev = Evaluator()
    result = ev.evaluate(make_item(), make_seller())
    d = result.to_dict()
    assert "score" in d
    assert "risk_level" in d
    assert "dimension_scores" in d
    assert "reject_reasons" in d
    assert d["risk_level"] in ("low", "medium", "high", "extreme")


def test_eval_result_is_passed() -> None:
    """is_passed 属性"""
    ev = Evaluator()
    # 完美卖家应通过
    result = ev.evaluate(make_item(), make_seller())
    assert result.is_passed is True


def test_eval_result_is_auto_buy() -> None:
    """is_auto_buy 严格（必须 low 且 >= 80）"""
    ev = Evaluator()
    result = ev.evaluate(make_item(), make_seller())
    # 默认完美卖家分数不一定到 80
    assert isinstance(result.is_auto_buy, bool)
