"""评估参数规则集

校验 eval 段配置，预防评估逻辑参数不匹配与评估结果失真。
"""
from __future__ import annotations

from xianyu_hunter.domain.param_calculator import (
    RuleCategory,
    RuleMeta,
    Scenario,
    Severity,
    Suggestion,
    ValidationContext,
)
from xianyu_hunter.modules.param_calculator.rules.base import BaseRule


class EvalWeightsSumRule(BaseRule):
    """评估权重总和校验

    预防：权重总和偏离 100 导致评分失真（准确性）。
    """

    code = "EVAL_WEIGHTS_SUM_INVALID"
    _default_meta = RuleMeta(
        code="EVAL_WEIGHTS_SUM_INVALID",
        name="评估权重总和",
        category=RuleCategory.ACCURACY,
        scenarios=[Scenario.CONFIG_UPDATE],
        priority=170,
        description="四项权重总和应为 100（允许 ±5 浮动）",
    )

    def check(self, context: ValidationContext) -> list[Suggestion]:
        f = context.fields
        weights = f.get("weights")
        if not weights or not isinstance(weights, dict):
            return []
        # 期望的权重项
        expected_keys = {"professional", "credit", "dispute", "price"}
        actual_keys = set(weights.keys())
        # 检查缺失的权重项
        missing = expected_keys - actual_keys
        if missing:
            return [self._suggestion(
                Severity.ERROR, RuleCategory.ACCURACY,
                f"评估权重缺少字段：{', '.join(sorted(missing))}",
                "请补全 professional/credit/dispute/price 四项权重",
                ["weights"],
            )]
        total = 0
        for key in expected_keys:
            val = weights.get(key)
            if not isinstance(val, (int, float)) or val < 0:
                return [self._suggestion(
                    Severity.ERROR, RuleCategory.ACCURACY,
                    f"权重 {key}={val} 无效，必须为非负数",
                    "请设置为 0-100 之间的数字",
                    ["weights", f"weights.{key}"],
                )]
            total += val
        # 允许 ±5 浮动：用户可能微调但未精确到 100
        tolerance = self._get_threshold("eval", "weight_sum_tolerance", 5)
        if abs(total - 100) > tolerance:
            return [self._suggestion(
                Severity.ERROR, RuleCategory.ACCURACY,
                f"四项权重总和为 {total}，偏离 100 超过 {tolerance}，"
                "评分结果将失真",
                "请调整使权重总和为 100",
                ["weights"],
            )]
        return []


class EvalScoreThresholdRule(BaseRule):
    """评估分数阈值合理性校验

    预防：pass_score > auto_buy_score 导致自动下单逻辑矛盾（稳定性）。
    """

    code = "EVAL_SCORE_THRESHOLD_INVALID"
    _default_meta = RuleMeta(
        code="EVAL_SCORE_THRESHOLD_INVALID",
        name="评估分数阈值",
        category=RuleCategory.STABILITY,
        scenarios=[Scenario.CONFIG_UPDATE],
        priority=180,
        description="pass_score 应 <= auto_buy_score",
    )

    def check(self, context: ValidationContext) -> list[Suggestion]:
        f = context.fields
        pass_score = f.get("pass_score")
        auto_buy_score = f.get("auto_buy_score")
        if pass_score is None or auto_buy_score is None:
            return []
        if not isinstance(pass_score, (int, float)) or not isinstance(auto_buy_score, (int, float)):
            return []
        if pass_score > auto_buy_score:
            return [self._suggestion(
                Severity.ERROR, RuleCategory.STABILITY,
                f"pass_score={pass_score} > auto_buy_score={auto_buy_score}，"
                "评分达到通过线但未达到自动下单线，逻辑矛盾",
                "请调整使 pass_score <= auto_buy_score",
                ["pass_score", "auto_buy_score"],
            )]
        # 分数范围校验
        min_score = self._get_threshold("eval", "min_score", 0)
        max_score = self._get_threshold("eval", "max_score", 100)
        if not (min_score <= pass_score <= max_score):
            return [self._suggestion(
                Severity.ERROR, RuleCategory.ACCURACY,
                f"pass_score={pass_score} 超出有效范围 [{min_score}, {max_score}]",
                f"请设置在 {min_score}-{max_score} 之间",
                ["pass_score"],
            )]
        if not (min_score <= auto_buy_score <= max_score):
            return [self._suggestion(
                Severity.ERROR, RuleCategory.ACCURACY,
                f"auto_buy_score={auto_buy_score} 超出有效范围 [{min_score}, {max_score}]",
                f"请设置在 {min_score}-{max_score} 之间",
                ["auto_buy_score"],
            )]
        return []


class EvalCreditThresholdRule(BaseRule):
    """卖家信用阈值合理性校验

    预防：credit_score_min 设置过高（如 600）导致全部商品评估失败。
    复盘来源：2026-07 项目曾出现 600 vs 0-100 实际范围导致 0 分评估。
    """

    code = "EVAL_CREDIT_THRESHOLD_INVALID"
    _default_meta = RuleMeta(
        code="EVAL_CREDIT_THRESHOLD_INVALID",
        name="信用阈值范围",
        category=RuleCategory.ACCURACY,
        scenarios=[Scenario.CONFIG_UPDATE],
        priority=190,
        description="credit_score_min 应在 0-100 范围内（信用分实际范围）",
    )

    def check(self, context: ValidationContext) -> list[Suggestion]:
        f = context.fields
        credit_min = f.get("credit_score_min")
        if credit_min is None:
            return []
        if not isinstance(credit_min, (int, float)):
            return []
        # 闲鱼信用分实际范围 0-100，超过此范围表示配置错误
        hard_max = self._get_threshold("eval", "credit_score_hard_max", 100)
        hard_min = self._get_threshold("eval", "credit_score_hard_min", 0)
        if credit_min > hard_max:
            return [self._suggestion(
                Severity.ERROR, RuleCategory.ACCURACY,
                f"credit_score_min={credit_min} 超过闲鱼信用分最大值 {hard_max}，"
                "所有商品都将评估失败",
                f"请设置在 {hard_min}-{hard_max} 之间",
                ["credit_score_min"],
            )]
        if credit_min < hard_min:
            return [self._suggestion(
                Severity.ERROR, RuleCategory.ACCURACY,
                f"credit_score_min={credit_min} 低于最小值 {hard_min}",
                f"请设置在 {hard_min}-{hard_max} 之间",
                ["credit_score_min"],
            )]
        # 过高预警：60 以下基本通过不了
        warning_threshold = self._get_threshold("eval", "credit_score_warning", 80)
        if credit_min > warning_threshold:
            return [self._suggestion(
                Severity.WARNING, RuleCategory.ACCURACY,
                f"credit_score_min={credit_min} 过高，多数商品将被过滤",
                f"建议设置 <= {warning_threshold}",
                ["credit_score_min"],
            )]
        return []


class EvalRules:
    """评估参数规则集合"""

    @staticmethod
    def all() -> list[BaseRule]:
        return [
            EvalWeightsSumRule(),
            EvalScoreThresholdRule(),
            EvalCreditThresholdRule(),
        ]
