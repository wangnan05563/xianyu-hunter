"""卖家评估器（设计文档 §3.5 / §4.4）

4 维评分模型：
1. 职业卖家识别（权重 30）
2. 信用与资质（权重 30）
3. 历史纠纷与黑名单（权重 25）
4. 价格与竞价异常（权重 15）

输出 EvalResult，含一票否决逻辑。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from xianyu_hunter.domain.evaluation import EvalResult, RiskLevel
from xianyu_hunter.domain.item import ItemDetail
from xianyu_hunter.domain.seller import SellerProfile
from xianyu_hunter.infra.yaml_config import EvalConfig, get_config

logger = logging.getLogger(__name__)


@dataclass
class EvaluationThresholds:
    """运行时阈值（可覆盖 config 默认值）"""
    on_sale_count: int = 30
    post_count_30d: int = 15
    top_category_ratio: float = 0.8
    credit_score_min: int = 600
    bad_review_max: int = 3
    register_days_min: int = 30
    pass_score: int = 60
    auto_buy_score: int = 80

    # 数据质量判定阈值（用于降级策略）
    # 当卖家数据低于这些标准时，评估器会标记为"数据不足"
    min_credit_score_for_valid: int = 400    # 有效信用分最低值（<此值视为无效）
    min_on_sale_for_valid: int = 1           # 有效在售数最低值
    min_sold_for_valid: int = 0             # 有效已售数最低值（可为0）
    min_register_days_for_valid: int = 1     # 有效注册天数最低值

    @classmethod
    def from_config(cls, config: EvalConfig) -> "EvaluationThresholds":
        return cls(
            on_sale_count=config.thresholds.on_sale_count,
            post_count_30d=config.thresholds.post_count_30d,
            top_category_ratio=config.thresholds.top_category_ratio,
            credit_score_min=config.thresholds.credit_score_min,
            bad_review_max=config.thresholds.bad_review_max,
            register_days_min=config.thresholds.register_days_min,
            pass_score=config.pass_score,
            auto_buy_score=config.auto_buy_score,
        )


class Evaluator:
    """4 维卖家评估器

    权重和阈值在每次 evaluate() 调用时从实时配置读取，
    确保配置页面保存后立即生效，无需重启服务。

    使用：
        evaluator = Evaluator()
        result = evaluator.evaluate(item, seller)
        if result.is_passed:
            ...
    """

    def __init__(
        self,
        thresholds: EvaluationThresholds | None = None,
        weights: dict[str, int] | None = None,
        professional_keywords: list[str] | None = None,
    ):
        # 仅作为可选覆盖参数保留（测试用），生产环境不传参，每次 evaluate 从 get_config() 实时读取
        self._override_thresholds = thresholds
        self._override_weights = weights
        self._override_keywords = professional_keywords

    def _get_thresholds(self) -> EvaluationThresholds:
        """每次调用时从实时配置获取阈值（保证配置页面保存后立即生效）"""
        if self._override_thresholds:
            return self._override_thresholds
        return EvaluationThresholds.from_config(get_config().eval)

    def _get_weights(self) -> dict[str, int]:
        if self._override_weights:
            return self._override_weights
        cfg = get_config().eval
        return {
            "professional": cfg.weights.professional,
            "credit": cfg.weights.credit,
            "dispute": cfg.weights.dispute,
            "price": cfg.weights.price,
        }

    def _get_keywords(self) -> list[str]:
        if self._override_keywords is not None:
            return self._override_keywords
        return get_config().eval.professional_keywords

    def evaluate(self, item: ItemDetail, seller: SellerProfile) -> EvalResult:
        """评估卖家 + 价格"""
        # 每次评估时实时获取配置，确保配置变更后立即生效
        self.thresholds = self._get_thresholds()
        self.weights = self._get_weights()
        self.professional_keywords = self._get_keywords()

        # 校验权重和（配置页面可能保存了非法值）
        weight_sum = sum(self.weights.values())
        if weight_sum != 100:
            logger.warning(
                "评估权重之和为 %d（非 100），将按比例归一化计算: %s",
                weight_sum, self.weights,
            )
        # 0. 检测数据质量：如果卖家数据是默认值（采集失败），标记为"数据不足"
        if self._is_default_seller(seller):
            return EvalResult(
                score=None,
                risk_level=RiskLevel.UNKNOWN,
                reject_reasons=["insufficient_seller_data"],
                data_quality="insufficient",
            )

        # 1. 一票否决
        veto_reasons = self._veto(seller)
        if veto_reasons:
            return EvalResult(
                score=0,
                risk_level=RiskLevel.EXTREME,
                reject_reasons=veto_reasons,
                data_quality="partial",
            )

        # 2. 4 维评分
        scores: dict[str, int] = {}
        reasons: list[str] = []

        professional_score, professional_reasons = self._eval_professional(seller)
        scores["professional"] = professional_score
        reasons.extend(professional_reasons)

        credit_score, credit_reasons = self._eval_credit(seller)
        scores["credit"] = credit_score
        reasons.extend(credit_reasons)

        dispute_score, dispute_reasons = self._eval_dispute(seller)
        scores["dispute"] = dispute_score
        reasons.extend(dispute_reasons)

        # 价格维度需要 ItemDetail
        price_score, price_reasons = self._eval_price(item)
        scores["price"] = price_score
        reasons.extend(price_reasons)

        # 3. 加权汇总 + 任意一维过低时拉低总分（防"高分掩盖职业卖家"作弊）
        # 权重和可能非 100（配置页面未归一化），按实际比例计算
        weight_sum = sum(self.weights.values())
        if weight_sum == 0:
            # 全部权重为 0 时退化为等权
            weighted_total = sum(scores.values()) // len(scores) if scores else 0
        else:
            weighted_total = sum(
                scores[k] * self.weights[k] for k in scores
            ) // weight_sum
        # 任一维度极差时不让总分高过"最差维度 + 缓冲"，确保职业/信用/纠纷风险真实暴露
        min_dim = min(scores.values()) if scores else 100
        total = min(weighted_total, min_dim + 40)

        # 4. 风险等级（阈值从实时配置读取，不再硬编码）
        if total >= self.thresholds.auto_buy_score:
            risk = RiskLevel.LOW
        elif total >= self.thresholds.pass_score:
            risk = RiskLevel.MEDIUM
        elif total >= 40:
            risk = RiskLevel.HIGH
        else:
            risk = RiskLevel.EXTREME

        # 始终返回全部 reject_reasons（供下游 buyer/UI 决策），不做风险等级过滤
        return EvalResult(
            score=total,
            risk_level=risk,
            dimension_scores=scores,
            reject_reasons=reasons,
            data_quality="full",
        )

    def _is_default_seller(self, seller: SellerProfile) -> bool:
        """检测卖家数据是否为默认值（采集失败时的空对象）

        使用配置化的数据质量阈值判断（而非硬编码）：
        - 信用分 < min_credit_score_for_valid 视为无效
        - 注册天数 < min_register_days_for_valid 视为无效
        - 在售数 < min_on_sale_for_valid 视为无效

        要求至少 2/3 个关键字段有效才认为是可用数据：
        - seller_profile_fallback() 返回的数据 register_days 恒为 0，
          若 credit_score 也为 None 则仅有 on_sale_count 可能有效（1/3），
          此时信用维度会因缺失数据被恒定扣分（-10-20-10=-40），
          导致所有降级卖家的评分趋同（88分），无区分度。
        """
        thresholds = self.thresholds

        # 检查关键字段是否达到有效标准
        has_valid_credit = (
            seller.credit_score is not None
            and seller.credit_score >= thresholds.min_credit_score_for_valid
        )
        has_valid_register = seller.register_days >= thresholds.min_register_days_for_valid
        has_valid_on_sale = seller.on_sale_count >= thresholds.min_on_sale_for_valid

        # 至少 2/3 个字段有效才认为是可用数据（避免仅 on_sale_count 有效时误判）
        valid_count = sum([has_valid_credit, has_valid_register, has_valid_on_sale])
        if valid_count >= 2:
            return False

        # 有效字段不足 2 个 → 判定为数据不足
        logger.debug(
            "[数据质量] 卖家 %s 数据不足: credit=%s(需>=%d) register=%dd(需>=%dd) on_sale=%d(需>=%d)",
            seller.id,
            seller.credit_score, thresholds.min_credit_score_for_valid,
            seller.register_days, thresholds.min_register_days_for_valid,
            seller.on_sale_count, thresholds.min_on_sale_for_valid,
        )
        return True

    # ============== 一票否决 ==============

    def _veto(self, seller: SellerProfile) -> list[str]:
        """一票否决项（命中即 0 分）"""
        reasons: list[str] = []
        if seller.in_blacklist:
            reasons.append("platform_blacklist")
        if seller.credit_score is not None and seller.credit_score < self.thresholds.credit_score_min:
            reasons.append(f"credit_score {seller.credit_score} < min {self.thresholds.credit_score_min}")
        return reasons

    # ============== 1. 职业卖家识别 ==============

    def _eval_professional(self, seller: SellerProfile) -> tuple[int, list[str]]:
        score = 100
        reasons: list[str] = []

        if seller.on_sale_count > self.thresholds.on_sale_count:
            score -= 40
            reasons.append(
                f"on_sale {seller.on_sale_count} > {self.thresholds.on_sale_count}"
            )

        if seller.post_count_30d > self.thresholds.post_count_30d:
            score -= 30
            reasons.append(
                f"30d_post {seller.post_count_30d} > {self.thresholds.post_count_30d}"
            )

        if (
            seller.top_category_ratio > 0
            and seller.top_category_ratio > self.thresholds.top_category_ratio
        ):
            score -= 20
            reasons.append(
                f"top_category_ratio {seller.top_category_ratio:.0%} > {self.thresholds.top_category_ratio:.0%}"
            )

        # 描述关键词
        for post in seller.recent_posts:
            for kw in self.professional_keywords:
                if post.title and kw in post.title:
                    score -= 15
                    reasons.append(f"professional_keyword:{kw}")
                    return max(score, 0), reasons

        return max(score, 0), reasons

    # ============== 2. 信用与资质 ==============

    def _eval_credit(self, seller: SellerProfile) -> tuple[int, list[str]]:
        score = 100
        reasons: list[str] = []

        if seller.credit_score is None:
            # 未公开信用分
            score -= 10
            reasons.append("credit_score_unknown")
        elif seller.credit_score < 700:
            # 信用 600-700 略降分（不会到一票否决）
            score -= 5
            reasons.append(f"credit_score {seller.credit_score} moderate")

        if seller.register_days < self.thresholds.register_days_min:
            score -= 20
            reasons.append(
                f"register_days {seller.register_days} < {self.thresholds.register_days_min}"
            )

        if seller.sold_count < 5:
            score -= 10
            reasons.append(f"low_sold_count {seller.sold_count}")

        return max(score, 0), reasons

    # ============== 3. 历史纠纷 ==============

    def _eval_dispute(self, seller: SellerProfile) -> tuple[int, list[str]]:
        score = 100
        reasons: list[str] = []

        if seller.bad_review_count > self.thresholds.bad_review_max:
            score -= 50
            reasons.append(
                f"bad_review {seller.bad_review_count} > {self.thresholds.bad_review_max}"
            )
        elif seller.bad_review_count > 0:
            score -= seller.bad_review_count * 5
            reasons.append(f"bad_review {seller.bad_review_count}")

        return max(score, 0), reasons

    # ============== 4. 价格与竞价异常 ==============

    def _eval_price(self, item: ItemDetail) -> tuple[int, list[str]]:
        """价格异常：仅作基础检查，复杂逻辑由 PriceStrategy 承担"""
        score = 100
        reasons: list[str] = []
        # 当前仅做价格合理性下限检查（< 1 元疑似引流）
        if item.price < 1.0:
            score -= 50
            reasons.append("price_suspicious_low")
        return max(score, 0), reasons
