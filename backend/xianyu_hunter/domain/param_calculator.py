"""参数计算器领域模型

定义参数校验的核心抽象：场景、上下文、规则结果、建议。
本模块为纯数据层，不依赖 IO，可被 engine / routes / tests 直接复用。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Scenario(str, Enum):
    """参数校验场景，对应三类触发时机"""
    TASK_CREATE = "task_create"      # 新增任务参数配置阶段
    TASK_EDIT = "task_edit"          # 编辑任务参数配置阶段
    CONFIG_UPDATE = "config_update"  # 系统配置提交前预览确认阶段


class Severity(str, Enum):
    """提示级别，对应前端三色提示

    顺序：ERROR > WARNING > INFO，便于按严重度排序展示
    """
    ERROR = "error"      # 红色：阻断性问题，提交前必须修正
    WARNING = "warning"  # 黄色：潜在风险，建议修正
    INFO = "info"         # 蓝色：优化建议，非强制


class RuleCategory(str, Enum):
    """规则分类，对应三类预防目标

    用于前端按类别折叠展示，也用于规则引擎按需加载
    """
    ACCURACY = "accuracy"      # 影响查询结果准确性
    STABILITY = "stability"    # 影响任务自动执行稳定性
    EFFICIENCY = "efficiency"  # 影响系统运行效率


@dataclass
class ValidationContext:
    """校验上下文：承载一次校验请求的全部输入

    fields 为扁平化的参数字典，由调用方从 Task / AppConfig 转换而来。
    保留 scenario 用于规则按场景过滤（部分规则只在特定场景生效）。
    """
    scenario: Scenario
    fields: dict[str, Any] = field(default_factory=dict)
    # 全局配置快照：任务级校验时引用全局配置做交叉验证（如任务间隔 vs 全局 QPS）
    global_config: dict[str, Any] | None = None


@dataclass
class Suggestion:
    """单条提示建议

    code 为规则唯一标识，前端可据此去重与折叠同类提示。
    fix_hint 提供可操作的修正建议（如"建议将 interval_seconds 调整为 60"）。
    """
    code: str               # 规则编码，如 "TASK_PRICE_RANGE_INVALID"
    severity: Severity
    category: RuleCategory
    message: str            # 面向用户的中文描述
    fix_hint: str = ""      # 可操作的修正建议
    # 关联字段列表：前端可据此高亮出问题的输入框
    affected_fields: list[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    """校验报告：一次校验的全部结果聚合

    suggestions 已按 severity 降序排列（ERROR 优先）。
    ok 字段表示是否无 ERROR 级别问题，便于前端决定是否允许提交。
    """
    scenario: Scenario
    suggestions: list[Suggestion] = field(default_factory=list)
    # 引擎耗时（毫秒），用于监控响应时间是否达标
    elapsed_ms: int = 0

    @property
    def ok(self) -> bool:
        """是否允许提交：无 ERROR 级别问题"""
        return not any(s.severity == Severity.ERROR for s in self.suggestions)

    @property
    def has_blocking(self) -> bool:
        return not self.ok

    @property
    def warning_count(self) -> int:
        return sum(1 for s in self.suggestions if s.severity == Severity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for s in self.suggestions if s.severity == Severity.INFO)

    def by_category(self, category: RuleCategory) -> list[Suggestion]:
        """按类别过滤建议"""
        return [s for s in self.suggestions if s.category == category]


@dataclass
class RuleMeta:
    """规则元数据：描述规则的适用范围与优先级

    priority 数值越大越先执行（同类问题的早停优化）。
    enabled=False 时规则被跳过，可在 param_rules.yaml 中配置。
    """
    code: str
    name: str
    category: RuleCategory
    scenarios: list[Scenario]            # 适用场景列表
    priority: int = 100                  # 默认优先级
    enabled: bool = True
    description: str = ""
