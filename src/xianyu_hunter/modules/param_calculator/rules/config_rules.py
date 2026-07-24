"""系统配置规则集

校验跨段配置的一致性与资源占用，预防系统级问题。
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


class EmptyResultSkipRule(BaseRule):
    """空结果缓存策略校验

    预防：empty_result_skip=true 导致反爬返回的空结果被缓存，
    掩盖实时数据恢复后仍返回空列表。
    复盘来源：2026-07-24 排查发现该配置加剧反爬。
    """

    code = "CACHE_EMPTY_RESULT_SKIP_INVALID"
    _default_meta = RuleMeta(
        code="CACHE_EMPTY_RESULT_SKIP_INVALID",
        name="空结果缓存策略",
        category=RuleCategory.STABILITY,
        scenarios=[Scenario.CONFIG_UPDATE],
        priority=170,
        description="empty_result_skip 应为 false，避免掩盖实时数据恢复",
    )

    def check(self, context: ValidationContext) -> list[Suggestion]:
        f = context.fields
        skip = f.get("empty_result_skip")
        if skip is None:
            return []
        if skip is True:
            return [self._suggestion(
                Severity.WARNING, RuleCategory.STABILITY,
                "empty_result_skip=true 会缓存反爬返回的空结果，"
                "即使实时数据已恢复，缓存期内仍返回空列表，加剧反爬触发",
                "建议设置为 false，让反爬空结果不被缓存",
                ["empty_result_skip"],
            )]
        return []


class AutoSearchConcurrencyRule(BaseRule):
    """自动搜索并发合理性校验

    预防：并发过高导致浏览器锁竞争与内存压力（效率/稳定性）。
    """

    code = "AUTO_SEARCH_CONCURRENCY_INVALID"
    _default_meta = RuleMeta(
        code="AUTO_SEARCH_CONCURRENCY_INVALID",
        name="自动搜索并发",
        category=RuleCategory.EFFICIENCY,
        scenarios=[Scenario.CONFIG_UPDATE],
        priority=150,
        description="auto_search_concurrency 应在 1-3 之间",
    )

    def check(self, context: ValidationContext) -> list[Suggestion]:
        f = context.fields
        concurrency = f.get("auto_search_concurrency")
        if concurrency is None:
            return []
        if not isinstance(concurrency, int):
            return []
        max_conc = self._get_threshold("scheduler", "max_auto_search_concurrency", 3)
        if concurrency < 1:
            return [self._suggestion(
                Severity.ERROR, RuleCategory.STABILITY,
                f"auto_search_concurrency={concurrency} 不能小于 1",
                "请设置为 >= 1",
                ["auto_search_concurrency"],
            )]
        if concurrency > max_conc:
            return [self._suggestion(
                Severity.WARNING, RuleCategory.EFFICIENCY,
                f"auto_search_concurrency={concurrency} 超过建议最大值 {max_conc}，"
                "将导致浏览器锁竞争与内存压力",
                f"建议设置为 <= {max_conc}",
                ["auto_search_concurrency"],
            )]
        return []


class BatchRefreshResourceRule(BaseRule):
    """批量刷新资源占用校验

    预防：batch_size 与 max_items_per_run 过大导致单次刷新资源耗尽（效率）。
    """

    code = "BATCH_REFRESH_RESOURCE_INVALID"
    _default_meta = RuleMeta(
        code="BATCH_REFRESH_RESOURCE_INVALID",
        name="批量刷新资源",
        category=RuleCategory.EFFICIENCY,
        scenarios=[Scenario.CONFIG_UPDATE],
        priority=140,
        description="batch_size 与 max_items_per_run 应在合理范围",
    )

    def check(self, context: ValidationContext) -> list[Suggestion]:
        f = context.fields
        batch_size = f.get("batch_size")
        max_items = f.get("max_items_per_run")
        results: list[Suggestion] = []
        max_bs = self._get_threshold("batch_refresh", "max_batch_size", 100)
        max_mi = self._get_threshold("batch_refresh", "max_max_items_per_run", 500)
        if batch_size is not None and isinstance(batch_size, int) and batch_size > max_bs:
            results.append(self._suggestion(
                Severity.WARNING, RuleCategory.EFFICIENCY,
                f"batch_size={batch_size} 超过建议最大值 {max_bs}，"
                "单批浏览器实例过多可能导致内存溢出",
                f"建议设置为 <= {max_bs}",
                ["batch_size"],
            ))
        if max_items is not None and isinstance(max_items, int) and max_items > max_mi:
            results.append(self._suggestion(
                Severity.WARNING, RuleCategory.EFFICIENCY,
                f"max_items_per_run={max_items} 超过建议最大值 {max_mi}，"
                "单次刷新耗时过长可能影响其他任务",
                f"建议设置为 <= {max_mi}",
                ["max_items_per_run"],
            ))
        return results


class ErrorRetryWaitRule(BaseRule):
    """错误重试等待时间校验

    预防：error_retry_wait_seconds 过短导致错误任务频繁重试（稳定性）。
    """

    code = "ERROR_RETRY_WAIT_INVALID"
    _default_meta = RuleMeta(
        code="ERROR_RETRY_WAIT_INVALID",
        name="错误重试等待",
        category=RuleCategory.STABILITY,
        scenarios=[Scenario.CONFIG_UPDATE],
        priority=130,
        description="error_retry_wait_seconds 应 >= 60s",
    )

    def check(self, context: ValidationContext) -> list[Suggestion]:
        f = context.fields
        wait = f.get("error_retry_wait_seconds")
        if wait is None:
            return []
        if not isinstance(wait, (int, float)):
            return []
        min_wait = self._get_threshold("scheduler", "min_error_retry_wait", 60)
        if wait < min_wait:
            return [self._suggestion(
                Severity.WARNING, RuleCategory.STABILITY,
                f"error_retry_wait_seconds={wait}s 过短，"
                "错误任务会频繁重试，加剧系统负载与反爬触发",
                f"建议设置为 >= {min_wait}s",
                ["error_retry_wait_seconds"],
            )]
        return []


class ConfigRules:
    """系统配置规则集合"""

    @staticmethod
    def all() -> list[BaseRule]:
        return [
            EmptyResultSkipRule(),
            AutoSearchConcurrencyRule(),
            BatchRefreshResourceRule(),
            ErrorRetryWaitRule(),
        ]
