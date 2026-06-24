"""卖家评估器（设计文档 §3.5 / §4.4）

4 维评分模型：
1. 职业卖家识别（权重 30）
2. 信用与资质（权重 30）
3. 历史纠纷与黑名单（权重 25）
4. 价格与竞价异常（权重 15）

输出 EvalResult，含一票否决逻辑。

数据质量三级分级策略（P0 优化）：
- full：3+ 维度有效 → 正常 4 维加权评估
- partial：1-2 维度有效 → 仅有效维度评估，按有效维度权重归一化
- insufficient：0 维度有效 → 不评估，返回 UNKNOWN

P1 优化：
- 职业卖家识别：Sigmoid 渐进式扣分替代硬阈值，避免阈值附近的评分跳变
- 防高分掩盖：基于维度方差的动态缓冲，离散度越大缓冲越小
"""
from __future__ import annotations

import logging
import math
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
        """评估卖家 + 价格

        数据质量三级分级：
        - full：卖家数据完整（3+ 维度有效）→ 正常 4 维加权
        - partial：卖家数据部分有效（1-2 维度）→ 仅有效维度归一化加权
        - insufficient：卖家数据全缺失 → 仅价格维度保守评分
        """
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

        # 0. 数据质量分级：检测卖家数据有效性，决定评估策略
        valid_dims = self._get_valid_dimensions(seller)
        # 价格维度始终有效（来自 item，不依赖卖家数据）
        valid_dims.add("price")

        if len(valid_dims) >= 4:
            # full：4 维都有效 → 正常评估
            return self._evaluate_full(item, seller)
        elif len(valid_dims) >= 2:
            # partial：1-3 维有效 → 仅有效维度归一化评估
            return self._evaluate_partial(item, seller, valid_dims)
        else:
            # insufficient：仅价格有效 → 保守评分
            return self._evaluate_insufficient(item)

    def _evaluate_full(self, item: ItemDetail, seller: SellerProfile) -> EvalResult:
        """完整 4 维评估（卖家数据充足）"""
        # 1. 一票否决
        veto_reasons = self._veto(seller)
        if veto_reasons:
            return EvalResult(
                score=0,
                risk_level=RiskLevel.EXTREME,
                reject_reasons=veto_reasons,
                data_quality="full",
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

        price_score, price_reasons = self._eval_price(item)
        scores["price"] = price_score
        reasons.extend(price_reasons)

        # 3. 加权汇总 + 防高分掩盖（P1 优化：基于维度方差的动态缓冲）
        weight_sum = sum(self.weights.values())
        if weight_sum == 0:
            weighted_total = sum(scores.values()) // len(scores) if scores else 0
        else:
            weighted_total = sum(
                scores[k] * self.weights[k] for k in scores
            ) // weight_sum

        # 动态缓冲：维度间离散度越大，缓冲越小（风险暴露越充分）
        # - 各维度分数接近时（std 小）→ buffer=50，允许高分
        # - 某维度远低于其他时（std 大）→ buffer=30，严格拉低总分
        min_dim = min(scores.values()) if scores else 100
        score_values = list(scores.values())
        if len(score_values) >= 2:
            mean_score = sum(score_values) / len(score_values)
            variance = sum((s - mean_score) ** 2 for s in score_values) / len(score_values)
            std = math.sqrt(variance)
            # std 范围约 0-50，映射到 buffer 50→30
            buffer = max(30, int(50 - std * 0.4))
        else:
            buffer = 40  # 单维度时回退到固定值
        total = min(weighted_total, min_dim + buffer)

        # 4. 风险等级
        risk = self._score_to_risk(total)

        return EvalResult(
            score=total,
            risk_level=risk,
            dimension_scores=scores,
            reject_reasons=reasons,
            data_quality="full",
        )

    def _evaluate_partial(
        self, item: ItemDetail, seller: SellerProfile, valid_dims: set[str]
    ) -> EvalResult:
        """部分维度评估（卖家数据不完整）

        仅计算有效维度的得分，按有效维度权重归一化加权，
        避免缺失维度恒定扣分导致评分趋同。
        """
        scores: dict[str, int] = {}
        reasons: list[str] = ["insufficient_seller_data"]

        # 仅评估有效维度
        if "professional" in valid_dims:
            s, r = self._eval_professional(seller)
            scores["professional"] = s
            reasons.extend(r)
        if "credit" in valid_dims:
            s, r = self._eval_credit(seller)
            scores["credit"] = s
            reasons.extend(r)
        if "dispute" in valid_dims:
            s, r = self._eval_dispute(seller)
            scores["dispute"] = s
            reasons.extend(r)
        # 价格维度始终有效
        s, r = self._eval_price(item)
        scores["price"] = s
        reasons.extend(r)

        # 按有效维度权重归一化（而非用全部权重，避免缺失维度拉低总分）
        valid_weight_sum = sum(self.weights[k] for k in scores if k in self.weights)
        if valid_weight_sum == 0:
            weighted_total = sum(scores.values()) // len(scores) if scores else 0
        else:
            weighted_total = sum(
                scores[k] * self.weights[k] for k in scores
            ) // valid_weight_sum

        # partial 模式：防高分掩盖 + partial 惩罚
        # 1. 防高分掩盖：任一有效维度低分时拉低总分（buffer=30，比 full 的 40 更严格）
        min_dim = min(scores.values()) if scores else 100
        capped = min(weighted_total, min_dim + 30)
        # 2. partial 惩罚：数据不完整时施加 0.8 系数，最高不超过 80 分
        #    这样满分卖家在 partial 模式下得 80 分（不会触发 auto_buy），有区分度
        total = min(int(capped * 0.8), 80)

        risk = self._score_to_risk(total)

        return EvalResult(
            score=total,
            risk_level=risk,
            dimension_scores=scores,
            reject_reasons=reasons,
            data_quality="partial",
        )

    def _evaluate_insufficient(self, item: ItemDetail) -> EvalResult:
        """数据严重不足时的保守评估（仅价格维度）"""
        price_score, price_reasons = self._eval_price(item)
        # 保守评分上限 40 分
        total = min(40, int(price_score * 0.4))
        return EvalResult(
            score=total,
            risk_level=RiskLevel.HIGH,
            dimension_scores={"price": price_score},
            reject_reasons=["insufficient_seller_data", *price_reasons],
            data_quality="insufficient",
        )

    def _score_to_risk(self, total: int) -> RiskLevel:
        """分数转风险等级"""
        if total >= self.thresholds.auto_buy_score:
            return RiskLevel.LOW
        elif total >= self.thresholds.pass_score:
            return RiskLevel.MEDIUM
        elif total >= 40:
            return RiskLevel.HIGH
        else:
            return RiskLevel.EXTREME

    def apply_ai_eval(self, result: EvalResult, ai_verdict: str, ai_condition_score: int) -> EvalResult:
        """将 AI 成色评估结果集成到规则评估结果中（P2 优化）

        AI 评估使用 1-10 分制，规则评估使用 0-100 分制。
        本方法将 AI 评估结果映射到 0-100 并调整总分：

        - ai_verdict="reject" → 总分降至 0，风险等级 EXTREME
        - ai_verdict="caution" → 总分 * 0.85，风险等级至少 MEDIUM
        - ai_condition_score >= 8 → 总分 +5（奖励，最高 100）
        - ai_condition_score <= 3 → 总分 * 0.7（惩罚）

        返回新的 EvalResult（不修改原始对象）。
        """
        # 记录 AI 维度分数到 dimension_scores
        new_dim_scores = dict(result.dimension_scores)
        new_dim_scores["ai_condition"] = ai_condition_score
        new_dim_scores["ai_verdict"] = ai_verdict

        new_reasons = list(result.reject_reasons)

        # AI 拒绝 → 直接 0 分
        if ai_verdict == "reject":
            new_reasons.append(f"ai_reject(score={ai_condition_score})")
            return EvalResult(
                score=0,
                risk_level=RiskLevel.EXTREME,
                dimension_scores=new_dim_scores,
                reject_reasons=new_reasons,
                data_quality=result.data_quality,
            )

        total = result.score or 0

        # AI 谨慎 → 总分 * 0.85
        if ai_verdict == "caution":
            total = int(total * 0.85)
            new_reasons.append(f"ai_caution(score={ai_condition_score})")

        # AI 成色评分极端值调整
        if ai_condition_score >= 8:
            # 高分成色奖励（+5，最高 100）
            total = min(100, total + 5)
        elif ai_condition_score <= 3:
            # 低分成色惩罚（* 0.7）
            total = int(total * 0.7)
            new_reasons.append(f"ai_low_condition(score={ai_condition_score})")

        # 重新计算风险等级
        risk = self._score_to_risk(total)
        # AI caution 时风险等级至少为 MEDIUM
        if ai_verdict == "caution" and risk == RiskLevel.LOW:
            risk = RiskLevel.MEDIUM

        return EvalResult(
            score=total,
            risk_level=risk,
            dimension_scores=new_dim_scores,
            reject_reasons=new_reasons,
            data_quality=result.data_quality,
        )

    def _get_valid_dimensions(self, seller: SellerProfile) -> set[str]:
        """检测卖家数据哪些维度有效，返回有效维度名集合

        维度有效性判定标准：
        - professional：on_sale_count >= 1 或 post_count_30d >= 1
        - credit：credit_score >= 400 或 register_days >= 1
        - dispute：bad_review_count >= 0（闲鱼不公开差评，默认有效）
        - price：始终有效（来自 item）

        闲鱼平台不公开信用分和差评数，但 on_sale_count 通常可从搜索结果获取，
        因此 professional 维度在多数情况下有效，避免评分趋同。
        """
        valid: set[str] = set()
        thresholds = self.thresholds

        # professional 维度：在售数或发布数有效
        if seller.on_sale_count >= thresholds.min_on_sale_for_valid:
            valid.add("professional")
        elif seller.post_count_30d >= 1:
            valid.add("professional")

        # credit 维度：信用分或注册天数有效
        if seller.credit_score is not None and seller.credit_score >= thresholds.min_credit_score_for_valid:
            valid.add("credit")
        elif seller.register_days >= thresholds.min_register_days_for_valid:
            valid.add("credit")

        # dispute 维度：需要至少有在售数或注册天数才认为有效
        # 闲鱼不公开差评数，但完全空对象（on_sale=0, register=0）不应判定 dispute 有效
        if seller.on_sale_count >= 1 or seller.register_days >= 1:
            valid.add("dispute")

        return valid

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

    @staticmethod
    def _sigmoid_deduction(value: float, threshold: float, max_deduction: float, k: float = 0.15) -> float:
        """Sigmoid 渐进式扣分

        在阈值附近平滑过渡，避免硬阈值导致的评分跳变。
        - value << threshold 时扣分趋近 0
        - value == threshold 时扣分 = max_deduction / 2
        - value >> threshold 时扣分趋近 max_deduction

        k 控制过渡陡峭度：k 越小过渡越平缓
        """
        return max_deduction / (1 + math.exp(-k * (value - threshold)))

    def _eval_professional(self, seller: SellerProfile) -> tuple[int, list[str]]:
        score = 100
        reasons: list[str] = []

        # 在售数：Sigmoid 渐进式扣分（阈值 30，最大扣 40）
        # on_sale=10 → 扣 ~1 分，on_sale=30 → 扣 20 分，on_sale=50 → 扣 ~38 分
        if seller.on_sale_count > 0:
            ded = self._sigmoid_deduction(
                seller.on_sale_count, self.thresholds.on_sale_count, 40
            )
            if ded >= 1:
                score -= int(ded)
                reasons.append(
                    f"on_sale {seller.on_sale_count} (ded={int(ded)})"
                )

        # 30 天发布数：Sigmoid 渐进式扣分（阈值 15，最大扣 30）
        if seller.post_count_30d > 0:
            ded = self._sigmoid_deduction(
                seller.post_count_30d, self.thresholds.post_count_30d, 30
            )
            if ded >= 1:
                score -= int(ded)
                reasons.append(
                    f"30d_post {seller.post_count_30d} (ded={int(ded)})"
                )

        # 类目集中度：保持硬阈值（ratio 是比例值，0.8 是明确的职业信号）
        if (
            seller.top_category_ratio > 0
            and seller.top_category_ratio > self.thresholds.top_category_ratio
        ):
            score -= 20
            reasons.append(
                f"top_category_ratio {seller.top_category_ratio:.0%} > {self.thresholds.top_category_ratio:.0%}"
            )

        # 描述关键词：保持硬扣分（关键词命中是明确的职业信号）
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
        """价格异常检测（P0 增强：多维度检查）

        检查项：
        1. 引流价格（< 1 元）→ 重扣 50 分
        2. 异常低价（< 10 元且非配件类）→ 扣 30 分
        3. 价格诱饵检测（标题含"不单卖""打包"等限制词）→ 扣 20 分
        4. 邮费陷阱（标题含"到付""邮费自理"等）→ 扣 15 分
        5. 图片数量风险（无图片 → 扣 10 分）
        """
        score = 100
        reasons: list[str] = []

        # 1. 引流价格（< 1 元疑似虚假商品）
        if item.price < 1.0:
            score -= 50
            reasons.append("price_suspicious_low")

        # 2. 异常低价（< 10 元且非配件类，可能是假货或骗局）
        # 配件类商品（壳/膜/线/充等）低价是正常的，不扣分
        accessory_keywords = ("壳", "膜", "线", "充", "支架", "贴", "扣", "绳", "套")
        is_accessory = any(kw in item.title for kw in accessory_keywords)
        if 1.0 <= item.price < 10.0 and not is_accessory:
            score -= 30
            reasons.append(f"price_abnormal_low({item.price})")

        # 3. 价格诱饵检测（标题含限制性词汇，可能不是真实售价）
        bait_keywords = ("不单卖", "打包", "不拆卖", "套装", "一起出", "搭配")
        for kw in bait_keywords:
            if kw in item.title:
                score -= 20
                reasons.append(f"price_bait:{kw}")
                break

        # 4. 邮费陷阱（到付/邮费自理可能实际成本更高）
        shipping_keywords = ("到付", "邮费自理", "运费到付", "邮费自付")
        for kw in shipping_keywords:
            if kw in item.title or kw in (item.description or ""):
                score -= 15
                reasons.append(f"shipping_trap:{kw}")
                break

        # 5. 无图片风险（无图商品成色无法判断）
        if not item.image_urls:
            score -= 10
            reasons.append("no_image_for_condition")

        return max(score, 0), reasons
