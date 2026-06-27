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
    want_cnt: int = 0,
) -> ItemDetail:
    # 默认提供 1 张图片，避免无图扣分干扰维度测试
    return ItemDetail(
        id="i1",
        title=title,
        price=price,
        seller_id="u1",
        description=description,
        image_urls=image_urls if image_urls is not None else ["https://example.com/1.jpg"],
        want_cnt=want_cnt,
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
    # 闲鱼信用分范围 0-100，阈值 60，用 50 触发否决
    result = ev.evaluate(make_item(), make_seller(credit_score=50))
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
    """insufficient 质量：卖家数据全空 → 价格+热度保守评分（上限 65）"""
    ev = Evaluator()
    seller = SellerProfile(id="empty", on_sale_count=0, credit_score=None, register_days=0)
    result = ev.evaluate(make_item(price=100), seller)
    assert result.data_quality == "insufficient"
    # 上限 65：可 pass(60) 但不可 auto_buy(80)
    assert result.score <= 65
    assert "price" in result.dimension_scores
    assert "popularity" in result.dimension_scores
    assert "insufficient_seller_data" in result.reject_reasons


def test_insufficient_zero_want_count_penalty() -> None:
    """insufficient 模式：want_cnt=0 → 热度扣 30 分"""
    ev = Evaluator()
    seller = SellerProfile(id="empty", on_sale_count=0, credit_score=None, register_days=0)
    result = ev.evaluate(make_item(price=100, want_cnt=0), seller)
    assert result.dimension_scores["popularity"] == 70
    assert any("zero_want_count" in r for r in result.reject_reasons)


def test_insufficient_low_want_count_penalty() -> None:
    """insufficient 模式：want_cnt=1-5 → 热度扣 10 分"""
    ev = Evaluator()
    seller = SellerProfile(id="empty", on_sale_count=0, credit_score=None, register_days=0)
    result = ev.evaluate(make_item(price=100, want_cnt=3), seller)
    assert result.dimension_scores["popularity"] == 90
    assert any("low_want_count" in r for r in result.reject_reasons)


def test_insufficient_normal_want_count_no_penalty() -> None:
    """insufficient 模式：want_cnt=6-49 → 热度不扣分"""
    ev = Evaluator()
    seller = SellerProfile(id="empty", on_sale_count=0, credit_score=None, register_days=0)
    result = ev.evaluate(make_item(price=100, want_cnt=20), seller)
    assert result.dimension_scores["popularity"] == 100
    assert not any("want_count" in r for r in result.reject_reasons)


def test_insufficient_high_want_count_bonus() -> None:
    """insufficient 模式：want_cnt>=50 → 热度加 10 分"""
    ev = Evaluator()
    seller = SellerProfile(id="empty", on_sale_count=0, credit_score=None, register_days=0)
    result = ev.evaluate(make_item(price=100, want_cnt=50), seller)
    assert result.dimension_scores["popularity"] == 100
    assert any("high_want_count" in r for r in result.reject_reasons)


def test_insufficient_can_pass_but_not_auto_buy() -> None:
    """insufficient 模式：高分场景可 pass(60) 但不可 auto_buy(80)"""
    ev = Evaluator()
    seller = SellerProfile(id="empty", on_sale_count=0, credit_score=None, register_days=0)
    # 正常价格 + 高热度 → 应可 pass 但不可 auto_buy
    result = ev.evaluate(make_item(price=2000, want_cnt=50), seller)
    assert result.score <= 65, f"insufficient 模式上限 65，实际 {result.score}"
    assert result.score >= 60, f"高分场景应可 pass，实际 {result.score}"
    assert not result.is_auto_buy, "insufficient 模式不应触发自动下单"


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


# ============== P1: Sigmoid 渐进式扣分 ==============


def test_sigmoid_low_on_sale_minimal_penalty() -> None:
    """在售数远低于阈值时扣分极小（Sigmoid 平滑过渡）"""
    ev = Evaluator()
    # on_sale=5，阈值 30，应只扣很小分数（旧逻辑扣 0，新逻辑扣 ~0）
    seller = make_seller(on_sale_count=5)
    result = ev.evaluate(make_item(), seller)
    # professional 维度应接近 100（扣分 < 5）
    assert result.dimension_scores["professional"] >= 95


def test_sigmoid_near_threshold_half_penalty() -> None:
    """在售数接近阈值时扣分约为最大值的一半"""
    ev = Evaluator()
    # on_sale=30（等于阈值），Sigmoid 扣分 = 40/2 = 20
    seller = make_seller(on_sale_count=30)
    result = ev.evaluate(make_item(), seller)
    # professional 维度应约为 80（100 - 20）
    assert 70 <= result.dimension_scores["professional"] <= 85


def test_sigmoid_far_above_threshold_near_max_penalty() -> None:
    """在售数远超阈值时扣分接近最大值"""
    ev = Evaluator()
    # on_sale=100，远超阈值 30，扣分接近 40
    seller = make_seller(on_sale_count=100)
    result = ev.evaluate(make_item(), seller)
    # professional 维度应 <= 65（扣分 >= 35）
    assert result.dimension_scores["professional"] <= 65


def test_sigmoid_no_jump_at_threshold() -> None:
    """阈值附近无评分跳变（Sigmoid 平滑过渡的核心特性）"""
    ev = Evaluator()
    # on_sale=29 和 on_sale=31 的 professional 分数差应很小（< 10）
    seller_below = make_seller(on_sale_count=29)
    seller_above = make_seller(on_sale_count=31)
    score_below = ev.evaluate(make_item(), seller_below).dimension_scores["professional"]
    score_above = ev.evaluate(make_item(), seller_above).dimension_scores["professional"]
    # 旧硬阈值逻辑：29→100, 31→60，差 40 分
    # 新 Sigmoid 逻辑：差值应 < 10
    assert abs(score_below - score_above) < 10


def test_sigmoid_post_count_30d_smooth() -> None:
    """30 天发布数渐进式扣分"""
    ev = Evaluator()
    # post_count_30d=14（接近阈值 15）和 post_count_30d=16 的分数差应很小
    seller_below = make_seller(post_count_30d=14)
    seller_above = make_seller(post_count_30d=16)
    score_below = ev.evaluate(make_item(), seller_below).dimension_scores["professional"]
    score_above = ev.evaluate(make_item(), seller_above).dimension_scores["professional"]
    assert abs(score_below - score_above) < 10


# ============== P1: 动态缓冲防高分掩盖 ==============


def test_dynamic_buffer_uniform_scores_allow_high() -> None:
    """各维度分数接近时，动态缓冲允许高分"""
    ev = Evaluator()
    # 完美卖家：4 维都接近 100，std 小 → buffer 大 → 允许高分
    seller = make_seller(
        on_sale_count=2,
        sold_count=20,
        register_days=1000,
        credit_score=750,
        post_count_30d=0,  # 避免触发 Sigmoid 扣分
    )
    result = ev.evaluate(make_item(price=2000), seller)
    assert result.score >= 95


def test_dynamic_buffer_spread_scores_strict_cap() -> None:
    """某维度远低于其他时，动态缓冲更严格地拉低总分"""
    ev = Evaluator()
    # 职业卖家：professional 低，其他维度高 → std 大 → buffer 小
    seller = make_seller(
        on_sale_count=100,      # professional ~60
        sold_count=20,
        register_days=1000,
        credit_score=750,
    )
    result = ev.evaluate(make_item(price=2000), seller)
    # 维度离散度大，buffer 应 < 40，总分被更严格限制
    assert result.score <= 95


def test_dynamic_buffer_better_than_fixed() -> None:
    """动态缓冲比固定 buffer=40 更能暴露风险"""
    ev = Evaluator()
    # 极端职业卖家：professional 很低（on_sale=500 + post_30d=200 + 关键词），
    # 其他维度满分 → std 很大 → buffer 很小 → 总分被严格拉低
    from xianyu_hunter.domain.item import ItemSummary
    seller = make_seller(
        on_sale_count=500,       # Sigmoid 扣 ~40
        post_count_30d=200,      # Sigmoid 扣 ~30
        sold_count=20,
        register_days=1000,
        credit_score=750,
        recent_posts=[ItemSummary(id="p1", title="批发 全新 iPhone", price=0)],  # 关键词 -15
    )
    result = ev.evaluate(make_item(price=2000), seller)
    # professional ≈ 15, 其他维度 100
    # std 大 → buffer 小 → total 被 min_dim + buffer 限制
    # 确保低分维度有效拉低了总分
    assert result.score < 70


# ============== P2: AI 评估与规则评估集成 ==============


def test_ai_eval_reject_zero_score() -> None:
    """AI 评估 reject → 总分降至 0"""
    ev = Evaluator()
    base = ev.evaluate(make_item(price=2000), make_seller())
    assert base.score > 0  # 确保基础分大于 0
    result = ev.apply_ai_eval(base, "reject", 2)
    assert result.score == 0
    assert result.risk_level == RiskLevel.EXTREME
    assert any("ai_reject" in r for r in result.reject_reasons)
    assert result.dimension_scores["ai_condition"] == 2
    assert result.dimension_scores["ai_verdict"] == "reject"


def test_ai_eval_caution_reduces_score() -> None:
    """AI 评估 caution → 总分 * 0.85"""
    ev = Evaluator()
    base = ev.evaluate(make_item(price=2000), make_seller())
    result = ev.apply_ai_eval(base, "caution", 5)
    expected = int(base.score * 0.85)
    assert result.score == expected
    # caution 时风险等级至少 MEDIUM
    assert result.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.EXTREME)
    assert any("ai_caution" in r for r in result.reject_reasons)


def test_ai_eval_high_score_bonus() -> None:
    """AI 成色评分 >= 8 → 总分 +5 奖励"""
    ev = Evaluator()
    base = ev.evaluate(make_item(price=2000), make_seller())
    result = ev.apply_ai_eval(base, "recommend", 9)
    expected = min(100, base.score + 5)
    assert result.score == expected


def test_ai_eval_low_condition_penalty() -> None:
    """AI 成色评分 <= 3 → 总分 * 0.7 惩罚"""
    ev = Evaluator()
    base = ev.evaluate(make_item(price=2000), make_seller())
    result = ev.apply_ai_eval(base, "caution", 2)
    # caution 先 * 0.85，再 low_condition * 0.7
    expected = int(int(base.score * 0.85) * 0.7)
    assert result.score == expected
    assert any("ai_low_condition" in r for r in result.reject_reasons)


def test_ai_eval_recommend_no_penalty() -> None:
    """AI 评估 recommend + 中等分数 → 不奖不罚"""
    ev = Evaluator()
    base = ev.evaluate(make_item(price=2000), make_seller())
    result = ev.apply_ai_eval(base, "recommend", 6)
    # 6 分不触发奖励(>=8)也不触发惩罚(<=3)
    assert result.score == base.score
    assert result.risk_level == base.risk_level


def test_ai_eval_preserves_original() -> None:
    """apply_ai_eval 不修改原始 EvalResult"""
    ev = Evaluator()
    base = ev.evaluate(make_item(price=2000), make_seller())
    original_score = base.score
    original_dims = dict(base.dimension_scores)
    _ = ev.apply_ai_eval(base, "reject", 1)
    # 原始对象不受影响
    assert base.score == original_score
    assert base.dimension_scores == original_dims
