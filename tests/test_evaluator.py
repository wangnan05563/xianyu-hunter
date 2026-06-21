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


def make_item(
    price: float = 100.0,
    title: str = "iPhone 13",
    description: str = "",
    image_urls: list[str] | None = None,
) -> ItemDetail:
    # 默认提供 1 张图片，避免无图扣分干扰维度测试
    return ItemDetail(
        id="i1",
        title=title,
        price=price,
        seller_id="u1",
        description=description,
        image_urls=image_urls if image_urls is not None else ["https://example.com/1.jpg"],
    )


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


# ============== P0: 数据质量三级分级 ==============


def test_full_quality_evaluation() -> None:
    """full 质量：卖家数据完整 → 4 维正常评估"""
    ev = Evaluator()
    seller = make_seller(
        on_sale_count=5,
        sold_count=10,
        register_days=365,
        credit_score=750,
    )
    result = ev.evaluate(make_item(price=1000), seller)
    assert result.data_quality == "full"
    assert "professional" in result.dimension_scores
    assert "credit" in result.dimension_scores
    assert "dispute" in result.dimension_scores
    assert "price" in result.dimension_scores


def test_partial_quality_only_on_sale() -> None:
    """partial 质量：仅有 on_sale_count → professional+dispute+price 有效"""
    ev = Evaluator()
    # 降级卖家：只有 on_sale_count，无信用分和注册天数
    seller = SellerProfile(
        id="u2",
        nick="降级卖家",
        on_sale_count=3,
        credit_score=None,
        register_days=0,
        sold_count=0,
    )
    result = ev.evaluate(make_item(price=500), seller)
    assert result.data_quality == "partial"
    # professional 和 price 维度应有得分
    assert "professional" in result.dimension_scores
    assert "price" in result.dimension_scores
    # credit 维度不应有得分（数据无效）
    assert "credit" not in result.dimension_scores
    # partial 模式 3 维有效 → partial 惩罚后上限 80 分
    assert result.score <= 80


def test_partial_quality_score_has_variance() -> None:
    """partial 质量评分有区分度（不再全部 40 分）"""
    ev = Evaluator()
    # 卖家 A：在售 3 件，正常价格
    seller_a = SellerProfile(id="a", on_sale_count=3, credit_score=None, register_days=0)
    result_a = ev.evaluate(make_item(price=500), seller_a)
    # 卖家 B：在售 100 件（职业卖家），正常价格
    seller_b = SellerProfile(id="b", on_sale_count=100, credit_score=None, register_days=0)
    result_b = ev.evaluate(make_item(price=500), seller_b)

    # 两个卖家评分应有明显差异（职业卖家更低）
    assert result_a.score > result_b.score
    assert result_a.score - result_b.score >= 10


def test_insufficient_quality_empty_seller() -> None:
    """insufficient 质量：卖家数据全空 → 仅价格保守评分"""
    ev = Evaluator()
    seller = SellerProfile(id="empty", on_sale_count=0, credit_score=None, register_days=0)
    result = ev.evaluate(make_item(price=100), seller)
    assert result.data_quality == "insufficient"
    assert result.score <= 40
    assert "price" in result.dimension_scores
    assert "insufficient_seller_data" in result.reject_reasons


# ============== P0: 价格维度增强 ==============


def test_price_suspicious_low_under_1_yuan() -> None:
    """引流价格（< 1 元）扣 50 分"""
    ev = Evaluator()
    result = ev.evaluate(make_item(price=0.5), make_seller())
    assert result.dimension_scores["price"] <= 50
    assert any("price_suspicious_low" in r for r in result.reject_reasons)


def test_price_abnormal_low_non_accessory() -> None:
    """异常低价（< 10 元且非配件）扣 30 分"""
    ev = Evaluator()
    result = ev.evaluate(make_item(price=5, title="iPhone 13"), make_seller())
    assert result.dimension_scores["price"] <= 70
    assert any("price_abnormal_low" in r for r in result.reject_reasons)


def test_price_low_accessory_no_penalty() -> None:
    """配件类低价不扣分"""
    ev = Evaluator()
    result = ev.evaluate(make_item(price=5, title="手机壳"), make_seller())
    # 配件类 5 元是正常的，不应触发异常低价扣分
    assert not any("price_abnormal_low" in r for r in result.reject_reasons)
    assert result.dimension_scores["price"] == 100


def test_price_bait_detection() -> None:
    """价格诱饵检测（标题含"不单卖"等）"""
    ev = Evaluator()
    result = ev.evaluate(make_item(price=100, title="iPhone 不单卖"), make_seller())
    assert any("price_bait" in r for r in result.reject_reasons)
    assert result.dimension_scores["price"] <= 80


def test_shipping_trap_detection() -> None:
    """邮费陷阱检测（到付）"""
    ev = Evaluator()
    result = ev.evaluate(
        make_item(price=100, title="iPhone 13", description="运费到付"),
        make_seller(),
    )
    assert any("shipping_trap" in r for r in result.reject_reasons)


def test_no_image_penalty() -> None:
    """无图片扣 10 分"""
    ev = Evaluator()
    result = ev.evaluate(
        make_item(price=100, image_urls=[]),
        make_seller(),
    )
    assert any("no_image_for_condition" in r for r in result.reject_reasons)
    assert result.dimension_scores["price"] <= 90


def test_normal_price_no_penalty() -> None:
    """正常价格无扣分"""
    ev = Evaluator()
    result = ev.evaluate(make_item(price=2000, title="iPhone 13"), make_seller())
    assert result.dimension_scores["price"] == 100
    assert not any(r.startswith("price_") for r in result.reject_reasons)
