"""搜索参数规则集

校验 search / antidetect 段配置，预防系统运行效率与反爬问题。
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


class SearchPageSizeRule(BaseRule):
    """搜索页大小合理性校验

    预防：page_size 过大导致单次请求超时或被反爬识别（效率）。
    """

    code = "SEARCH_PAGE_SIZE_INVALID"
    _default_meta = RuleMeta(
        code="SEARCH_PAGE_SIZE_INVALID",
        name="搜索页大小合理性",
        category=RuleCategory.EFFICIENCY,
        scenarios=[Scenario.CONFIG_UPDATE],
        priority=160,
        description="page_size 应在 10-100 之间",
    )

    def check(self, context: ValidationContext) -> list[Suggestion]:
        f = context.fields
        page_size = f.get("page_size")
        if page_size is None:
            return []
        min_ps = self._get_threshold("search", "min_page_size", 10)
        max_ps = self._get_threshold("search", "max_page_size", 100)
        if not isinstance(page_size, (int, float)):
            return [self._suggestion(
                Severity.ERROR, RuleCategory.EFFICIENCY,
                f"page_size 必须为数字，当前为 {type(page_size).__name__}",
                "请设置为数字",
                ["page_size"],
            )]
        if page_size < min_ps:
            return [self._suggestion(
                Severity.ERROR, RuleCategory.EFFICIENCY,
                f"page_size={page_size} 低于最小值 {min_ps}，单次请求结果过少",
                f"建议设置为 >= {min_ps}",
                ["page_size"],
            )]
        if page_size > max_ps:
            return [self._suggestion(
                Severity.WARNING, RuleCategory.EFFICIENCY,
                f"page_size={page_size} 超过 {max_ps}，单次请求耗时增加且易触发反爬",
                f"建议设置为 <= {max_ps}",
                ["page_size"],
            )]
        return []


class SearchTimeoutRule(BaseRule):
    """搜索超时合理性校验

    预防：timeout 过短导致频繁超时失败，过长导致任务堆积（效率）。
    """

    code = "SEARCH_TIMEOUT_INVALID"
    _default_meta = RuleMeta(
        code="SEARCH_TIMEOUT_INVALID",
        name="搜索超时合理性",
        category=RuleCategory.EFFICIENCY,
        scenarios=[Scenario.CONFIG_UPDATE],
        priority=150,
        description="timeout 应在 30-180 秒之间",
    )

    def check(self, context: ValidationContext) -> list[Suggestion]:
        f = context.fields
        timeout = f.get("timeout")
        if timeout is None:
            return []
        if not isinstance(timeout, (int, float)):
            return []
        min_to = self._get_threshold("search", "min_timeout", 30)
        max_to = self._get_threshold("search", "max_timeout", 180)
        if timeout < min_to:
            return [self._suggestion(
                Severity.WARNING, RuleCategory.EFFICIENCY,
                f"timeout={timeout}s 过短，闲鱼页面加载较慢时易超时失败",
                f"建议设置为 >= {min_to}s",
                ["timeout"],
            )]
        if timeout > max_to:
            return [self._suggestion(
                Severity.WARNING, RuleCategory.EFFICIENCY,
                f"timeout={timeout}s 过长，任务堆积时影响整体吞吐",
                f"建议设置为 <= {max_to}s",
                ["timeout"],
            )]
        return []


class AntiDetectQpsRule(BaseRule):
    """反爬 QPS 与延迟对齐校验

    预防：min_delay 与 max_delay 不匹配，或 QPS 与延迟换算不一致（效率/稳定性）。
    """

    code = "ANTIDETECT_DELAY_MISMATCH"
    _default_meta = RuleMeta(
        code="ANTIDETECT_DELAY_MISMATCH",
        name="反爬延迟一致性",
        category=RuleCategory.STABILITY,
        scenarios=[Scenario.CONFIG_UPDATE],
        priority=140,
        description="min_delay_ms < max_delay_ms 且 QPS 与延迟换算一致",
    )

    def check(self, context: ValidationContext) -> list[Suggestion]:
        f = context.fields
        min_delay = f.get("min_delay_ms")
        max_delay = f.get("max_delay_ms")
        qps = f.get("qps")
        if min_delay is None or max_delay is None:
            return []
        if min_delay > max_delay:
            return [self._suggestion(
                Severity.ERROR, RuleCategory.STABILITY,
                f"min_delay_ms={min_delay} > max_delay_ms={max_delay}，"
                "最小延迟不能大于最大延迟",
                "请调整使 min_delay_ms <= max_delay_ms",
                ["min_delay_ms", "max_delay_ms"],
            )]
        # QPS 与延迟换算一致性校验：qps 应约等于 60000 / 平均延迟
        if qps is not None and isinstance(qps, (int, float)) and qps > 0:
            avg_delay = (min_delay + max_delay) / 2
            expected_qps = 60000 / avg_delay if avg_delay > 0 else 0
            # 允许 20% 偏差（人工微调空间）
            tolerance = self._get_threshold("antidetect", "qps_tolerance", 0.2)
            if expected_qps > 0 and abs(qps - expected_qps) / expected_qps > tolerance:
                return [self._suggestion(
                    Severity.INFO, RuleCategory.EFFICIENCY,
                    f"qps={qps} 与延迟换算值 {expected_qps:.1f} 偏差超过 {tolerance:.0%}，"
                    "建议对齐以避免反爬策略不一致",
                    f"建议 qps 设为 {int(expected_qps)} 或调整延迟",
                    ["qps", "min_delay_ms", "max_delay_ms"],
                )]
        return []


class CacheTtlAlignmentRule(BaseRule):
    """缓存 TTL 与调度间隔对齐校验

    预防：live_search_ttl 远小于调度间隔导致缓存形同虚设（效率）。
    复盘来源：2026-07-24 排查发现 5s 缓存对 60s 轮询无效。
    """

    code = "CACHE_TTL_MISMATCH"
    _default_meta = RuleMeta(
        code="CACHE_TTL_MISMATCH",
        name="缓存TTL对齐",
        category=RuleCategory.EFFICIENCY,
        scenarios=[Scenario.CONFIG_UPDATE],
        priority=180,
        description="live_search_ttl 应 >= 调度间隔，避免缓存形同虚设",
    )

    def check(self, context: ValidationContext) -> list[Suggestion]:
        f = context.fields
        ttl = f.get("live_search_ttl")
        interval = f.get("default_interval_seconds")
        # 同时存在才校验
        if ttl is None or interval is None:
            return []
        if not isinstance(ttl, (int, float)) or not isinstance(interval, (int, float)):
            return []
        # TTL < 间隔：缓存命中率低，每次轮询都 miss
        if ttl < interval:
            return [self._suggestion(
                Severity.WARNING, RuleCategory.EFFICIENCY,
                f"live_search_ttl={ttl}s 低于调度间隔 {interval}s，"
                "每次轮询都缓存 miss，形同虚设",
                f"建议设置 live_search_ttl >= {int(interval)}s",
                ["live_search_ttl", "default_interval_seconds"],
            )]
        # TTL 远大于间隔的 3 倍：数据过期风险
        max_ratio = self._get_threshold("cache", "max_ttl_ratio", 3)
        if interval > 0 and ttl > interval * max_ratio:
            return [self._suggestion(
                Severity.INFO, RuleCategory.EFFICIENCY,
                f"live_search_ttl={ttl}s 超过调度间隔的 {max_ratio} 倍，"
                "缓存数据可能过期",
                f"建议设置 live_search_ttl <= {int(interval * max_ratio)}s",
                ["live_search_ttl"],
            )]
        return []


class SearchRules:
    """搜索参数规则集合"""

    @staticmethod
    def all() -> list[BaseRule]:
        return [
            SearchPageSizeRule(),
            SearchTimeoutRule(),
            AntiDetectQpsRule(),
            CacheTtlAlignmentRule(),
        ]
