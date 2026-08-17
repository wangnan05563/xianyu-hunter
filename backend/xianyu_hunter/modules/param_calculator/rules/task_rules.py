"""任务参数规则集

校验任务创建/编辑时的参数合法性，覆盖三类预防目标：
- ACCURACY: 价格区间、过滤条件
- STABILITY: 调度间隔、cron 表达式、依赖关系
- EFFICIENCY: 资源占用、并发控制
"""
from __future__ import annotations

from typing import Any

from xianyu_hunter.domain.param_calculator import (
    RuleCategory,
    RuleMeta,
    Scenario,
    Severity,
    Suggestion,
    ValidationContext,
)
from xianyu_hunter.modules.param_calculator.rules.base import BaseRule


class TaskPriceRangeRule(BaseRule):
    """价格区间合法性校验

    预防：min_price > max_price 导致查询永远无结果（准确性）。
    """

    code = "TASK_PRICE_RANGE_INVALID"
    _default_meta = RuleMeta(
        code="TASK_PRICE_RANGE_INVALID",
        name="价格区间合法性",
        category=RuleCategory.ACCURACY,
        scenarios=[Scenario.TASK_CREATE, Scenario.TASK_EDIT],
        priority=200,
        description="min_price 必须 <= max_price，且均为正数",
    )

    def check(self, context: ValidationContext) -> list[Suggestion]:
        f = context.fields
        min_price = f.get("min_price")
        max_price = f.get("max_price")
        if min_price is None and max_price is None:
            return []
        # 两者都存在时校验区间
        if min_price is not None and max_price is not None:
            if min_price > max_price:
                return [self._suggestion(
                    Severity.ERROR, RuleCategory.ACCURACY,
                    f"最低价 {min_price} 大于最高价 {max_price}，查询将永远无结果",
                    "请调整使 min_price <= max_price",
                    ["min_price", "max_price"],
                )]
            # 区间过窄预警：低于 10 元的区间在闲鱼几乎无匹配
            # 为什么不阻断：用户可能有意设置极窄区间做精准监控
            min_span = self._get_threshold("task", "min_price_span", 10)
            if max_price - min_price < min_span:
                return [self._suggestion(
                    Severity.WARNING, RuleCategory.ACCURACY,
                    f"价格区间仅 {max_price - min_price} 元，可能匹配不到商品",
                    f"建议区间宽度 >= {min_span} 元",
                    ["min_price", "max_price"],
                )]
        # 单边校验：负数价格无意义
        results: list[Suggestion] = []
        if min_price is not None and min_price < 0:
            results.append(self._suggestion(
                Severity.ERROR, RuleCategory.ACCURACY,
                f"最低价 {min_price} 不能为负数",
                "请设置为正数",
                ["min_price"],
            ))
        if max_price is not None and max_price < 0:
            results.append(self._suggestion(
                Severity.ERROR, RuleCategory.ACCURACY,
                f"最高价 {max_price} 不能为负数",
                "请设置为正数",
                ["max_price"],
            ))
        return results


class TaskIntervalRule(BaseRule):
    """调度间隔与全局 QPS 对齐校验

    预防：任务间隔过短触发反爬，或与全局缓存 TTL 不匹配（稳定性/效率）。
    """

    code = "TASK_INTERVAL_TOO_SHORT"
    _default_meta = RuleMeta(
        code="TASK_INTERVAL_TOO_SHORT",
        name="调度间隔合理性",
        category=RuleCategory.STABILITY,
        scenarios=[Scenario.TASK_CREATE, Scenario.TASK_EDIT, Scenario.CONFIG_UPDATE],
        priority=180,
        description="任务间隔应 >= 全局默认间隔，避免触发反爬",
    )

    def check(self, context: ValidationContext) -> list[Suggestion]:
        f = context.fields
        # 仅在非 cron 模式下校验间隔
        if f.get("use_cron"):
            return []
        interval = f.get("interval_seconds")
        if interval is None:
            return []
        # 全局默认间隔作为基准（从 global_config 或阈值读取）
        default_interval = self._get_threshold(
            "task", "min_interval_seconds",
            self._get_global_default(context, "task_scheduler.default_interval_seconds", 60),
        )
        # 最小允许间隔（防止滥用，低于此值会触发反爬）
        hard_min = self._get_threshold("task", "hard_min_interval_seconds", 30)
        if interval < hard_min:
            return [self._suggestion(
                Severity.ERROR, RuleCategory.STABILITY,
                f"调度间隔 {interval}s 低于最小允许值 {hard_min}s，将触发反爬机制",
                f"建议设置为 >= {hard_min}s",
                ["interval_seconds"],
            )]
        if interval < default_interval:
            return [self._suggestion(
                Severity.WARNING, RuleCategory.STABILITY,
                f"调度间隔 {interval}s 低于全局默认 {default_interval}s，"
                f"可能导致缓存命中率下降与反爬触发",
                f"建议设置为 >= {default_interval}s",
                ["interval_seconds"],
            )]
        return []

    def _get_global_default(self, context: ValidationContext, path: str, fallback: Any) -> Any:
        """从 global_config 中按点分路径读取值"""
        gc = context.global_config
        if not gc:
            return fallback
        cur: Any = gc
        for part in path.split("."):
            if not isinstance(cur, dict):
                return fallback
            cur = cur.get(part)
            if cur is None:
                return fallback
        return cur


class TaskCronRule(BaseRule):
    """cron 表达式合法性校验

    预防：无效 cron 导致调度器异常或高频触发（稳定性）。
    """

    code = "TASK_CRON_INVALID"
    _default_meta = RuleMeta(
        code="TASK_CRON_INVALID",
        name="cron 表达式合法性",
        category=RuleCategory.STABILITY,
        scenarios=[Scenario.TASK_CREATE, Scenario.TASK_EDIT],
        priority=190,
        description="cron 表达式必须合法且间隔 >= 60s",
    )

    # 阻断的滥用模式：每秒一次会击穿反爬
    _BLOCKED_PATTERNS = {"* * * * *", "*/1 * * * *"}

    def check(self, context: ValidationContext) -> list[Suggestion]:
        f = context.fields
        if not f.get("use_cron"):
            return []
        cron = f.get("cron")
        if not cron or not isinstance(cron, str):
            return [self._suggestion(
                Severity.ERROR, RuleCategory.STABILITY,
                "cron 模式下必须提供 cron 表达式",
                "请填写合法的 5 段 cron 表达式",
                ["cron"],
            )]
        cron_str = cron.strip()
        if cron_str in self._BLOCKED_PATTERNS:
            return [self._suggestion(
                Severity.ERROR, RuleCategory.STABILITY,
                f"cron 表达式 '{cron_str}' 会每秒触发，将击穿反爬机制",
                "建议使用 '*/1 * * * *' 以上的间隔",
                ["cron"],
            )]
        # 基本格式校验：5 段
        parts = cron_str.split()
        if len(parts) != 5:
            return [self._suggestion(
                Severity.ERROR, RuleCategory.STABILITY,
                f"cron 表达式 '{cron_str}' 应为 5 段（分 时 日 月 周），当前 {len(parts)} 段",
                "请使用标准 5 段格式，如 '0 */2 * * *'",
                ["cron"],
            )]
        return []


class TaskKeywordRule(BaseRule):
    """关键词合法性校验

    预防：空关键词或过短关键词导致查询无意义（准确性）。
    """

    code = "TASK_KEYWORD_INVALID"
    _default_meta = RuleMeta(
        code="TASK_KEYWORD_INVALID",
        name="关键词合法性",
        category=RuleCategory.ACCURACY,
        scenarios=[Scenario.TASK_CREATE, Scenario.TASK_EDIT],
        priority=210,
        description="关键词不能为空且长度 >= 2",
    )

    def check(self, context: ValidationContext) -> list[Suggestion]:
        f = context.fields
        keyword = f.get("keyword")
        if not keyword or not isinstance(keyword, str):
            return [self._suggestion(
                Severity.ERROR, RuleCategory.ACCURACY,
                "关键词不能为空",
                "请输入搜索关键词",
                ["keyword"],
            )]
        kw = keyword.strip()
        min_len = self._get_threshold("task", "min_keyword_length", 2)
        max_len = self._get_threshold("task", "max_keyword_length", 100)
        if len(kw) < min_len:
            return [self._suggestion(
                Severity.ERROR, RuleCategory.ACCURACY,
                f"关键词 '{kw}' 长度仅 {len(kw)}，低于最小长度 {min_len}",
                f"请输入至少 {min_len} 个字符的关键词",
                ["keyword"],
            )]
        if len(kw) > max_len:
            return [self._suggestion(
                Severity.WARNING, RuleCategory.ACCURACY,
                f"关键词长度 {len(kw)} 超过 {max_len}，可能匹配不到商品",
                f"建议精简到 {max_len} 字符以内",
                ["keyword"],
            )]
        return []


class TaskAutoBuyRiskRule(BaseRule):
    """自动下单风险校验

    预防：auto 模式下未设置价格区间，可能导致误购高价商品（稳定性）。
    """

    code = "TASK_AUTO_BUY_NO_PRICE_LIMIT"
    _default_meta = RuleMeta(
        code="TASK_AUTO_BUY_NO_PRICE_LIMIT",
        name="自动下单价格保护",
        category=RuleCategory.STABILITY,
        scenarios=[Scenario.TASK_CREATE, Scenario.TASK_EDIT],
        priority=170,
        description="auto 模式下必须设置价格上限",
    )

    def check(self, context: ValidationContext) -> list[Suggestion]:
        f = context.fields
        mode = f.get("mode")
        # 仅 auto 模式需要价格保护（semi_auto/confirm 有人工介入）
        if mode != "auto":
            return []
        max_price = f.get("max_price")
        if max_price is None:
            return [self._suggestion(
                Severity.WARNING, RuleCategory.STABILITY,
                "全自动模式下未设置最高价，存在误购高价商品的风险",
                "建议设置 max_price 限制自动下单的价格上限",
                ["max_price", "mode"],
            )]
        return []


class TaskRules:
    """任务参数规则集合

    引擎通过此类批量获取任务相关的所有规则实例。
    """

    @staticmethod
    def all() -> list[BaseRule]:
        return [
            TaskPriceRangeRule(),
            TaskIntervalRule(),
            TaskCronRule(),
            TaskKeywordRule(),
            TaskAutoBuyRiskRule(),
        ]
