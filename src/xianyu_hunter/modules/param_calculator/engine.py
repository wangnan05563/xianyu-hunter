"""参数计算器引擎（modules 层核心）

职责：
1. 加载并缓存所有规则实例（避免每次校验重新实例化）
2. 按场景过滤适用规则
3. 按优先级降序执行校验
4. 聚合结果为 ValidationReport

性能要求：单次校验耗时 < 50ms（前端 300ms 总响应时间扣除网络往返）。
通过纯内存计算 + 规则实例缓存达成。
"""
from __future__ import annotations

import time
from typing import Iterable

from xianyu_hunter.domain.param_calculator import (
    Severity,
    Suggestion,
    ValidationContext,
    ValidationReport,
)
from xianyu_hunter.modules.param_calculator.rules import (
    ConfigRules,
    EvalRules,
    SearchRules,
    TaskRules,
)
from xianyu_hunter.modules.param_calculator.rules.base import BaseRule


class ParamCalculatorEngine:
    """参数计算器引擎

    用法：
        engine = ParamCalculatorEngine()
        report = engine.validate(context)
        if report.has_blocking:
            # 阻断提交
    """

    def __init__(self) -> None:
        # 规则实例在构造时一次性创建并缓存
        # 为什么不用 @lru_cache：类实例化无参数，lru_cache 语义不清晰
        self._rules: list[BaseRule] = self._load_all_rules()

    def _load_all_rules(self) -> list[BaseRule]:
        """加载所有规则集的规则实例

        规则分类：
        - TaskRules: 任务参数（价格/调度/关键词/自动下单）
        - SearchRules: 搜索参数（页大小/超时/反爬/缓存）
        - EvalRules: 评估参数（权重/分数/信用）
        - ConfigRules: 系统配置（并发/批量/重试）
        """
        rules: list[BaseRule] = []
        rules.extend(TaskRules.all())
        rules.extend(SearchRules.all())
        rules.extend(EvalRules.all())
        rules.extend(ConfigRules.all())
        return rules

    def validate(self, context: ValidationContext) -> ValidationReport:
        """执行参数校验

        流程：
        1. 过滤适用规则（按场景 + enabled 状态）
        2. 按优先级降序排序（高优先级规则先执行，便于同类问题早停）
        3. 逐条执行规则，收集 Suggestion
        4. 按 severity 降序聚合结果
        """
        start = time.monotonic()
        applicable_rules = self._filter_applicable(context)
        sorted_rules = self._sort_by_priority(applicable_rules)
        suggestions = self._execute_rules(sorted_rules, context)
        ordered = self._sort_by_severity(suggestions)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return ValidationReport(
            scenario=context.scenario,
            suggestions=ordered,
            elapsed_ms=elapsed_ms,
        )

    def _filter_applicable(self, context: ValidationContext) -> list[BaseRule]:
        """过滤当前场景适用的规则"""
        return [r for r in self._rules if r.applicable(context)]

    @staticmethod
    def _sort_by_priority(rules: list[BaseRule]) -> list[BaseRule]:
        """按优先级降序排序，优先级相同的保持原顺序（稳定排序）"""
        return sorted(rules, key=lambda r: -r.meta.priority)

    @staticmethod
    def _execute_rules(
        rules: list[BaseRule], context: ValidationContext
    ) -> list[Suggestion]:
        """逐条执行规则，聚合所有 Suggestion

        为什么不并行执行：规则之间无依赖，但单条规则耗时极低（< 1ms），
        并行开销大于收益，串行更简单且可预测。
        """
        all_suggestions: list[Suggestion] = []
        for rule in rules:
            try:
                suggestions = rule.check(context)
                all_suggestions.extend(suggestions)
            except Exception:
                import logging
                logging.getLogger(__name__).warning(
                    "param_calculator_rule_failed code=%s",
                    rule.__class__.code,
                    exc_info=True,
                )
        return all_suggestions

    @staticmethod
    def _sort_by_severity(suggestions: list[Suggestion]) -> list[Suggestion]:
        """按严重度降序排序：ERROR > WARNING > INFO

        同级别保持原顺序（规则执行顺序），便于用户按严重度优先处理。
        """
        severity_order = {
            Severity.ERROR: 0,
            Severity.WARNING: 1,
            Severity.INFO: 2,
        }
        return sorted(
            suggestions,
            key=lambda s: severity_order.get(s.severity, 99),
        )

    def get_rule_codes(self) -> list[str]:
        """获取所有规则编码（用于诊断与文档生成）"""
        return [r.__class__.code for r in self._rules]

    def reload_rules(self) -> None:
        """重新加载规则实例

        场景：param_rules.yaml 变更后调用以使新规则生效。
        注意：BaseRule.meta 每次访问都读 YAML，无需重启即可更新阈值；
        此方法仅用于新增/删除规则代码后的热加载。
        """
        self._rules = self._load_all_rules()

    def validate_batch(
        self, contexts: Iterable[ValidationContext]
    ) -> list[ValidationReport]:
        """批量校验多个上下文

        用于提交前一次性校验多个配置段（如 task + search + eval 同时变更）。
        """
        return [self.validate(ctx) for ctx in contexts]
