"""规则基类

所有具体规则继承 BaseRule，实现 check() 方法返回建议列表。
规则元数据优先从 param_rules.yaml 读取（可热更新），
YAML 未配置时回退到类属性 _default_meta（代码内兜底默认值）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from xianyu_hunter.domain.param_calculator import (
    RuleCategory,
    RuleMeta,
    Scenario,
    Suggestion,
    ValidationContext,
)
from xianyu_hunter.infra import repo_param_rules


class BaseRule(ABC):
    """规则抽象基类

    子类必须实现：
    - code: 规则唯一编码（如 "TASK_PRICE_RANGE_INVALID"）
    - _default_meta: YAML 未配置时的兜底元数据
    - check(): 核心校验逻辑，返回 Suggestion 列表（空列表表示通过）
    """

    code: str = ""
    # 兜底元数据：YAML 未配置时使用，避免规则引擎因配置缺失而失效
    _default_meta: RuleMeta = RuleMeta(
        code="",
        name="",
        category=RuleCategory.ACCURACY,
        scenarios=[],
        priority=100,
        enabled=True,
        description="",
    )

    def __init__(self) -> None:
        # 为什么用 self.__class__.code 而非 self.code：
        # 类属性在子类中被覆盖，实例访问时优先取子类值
        if not self.__class__.code:
            raise ValueError(f"{self.__class__.__name__} 必须定义 code 类属性")
        # 修复 _default_meta 共享问题：每个子类应有独立的 default meta
        if not self._default_meta.code:
            # 子类未设置 _default_meta.code 时，用类属性 code 填充
            self._default_meta = RuleMeta(
                code=self.__class__.code,
                name=self._default_meta.name or self.__class__.code,
                category=self._default_meta.category,
                scenarios=self._default_meta.scenarios,
                priority=self._default_meta.priority,
                enabled=self._default_meta.enabled,
                description=self._default_meta.description,
            )

    @property
    def meta(self) -> RuleMeta:
        """运行时元数据：优先 YAML 配置，回退代码默认值

        每次 access 都重新读取 YAML，支持配置热更新。
        """
        yaml_meta = repo_param_rules.get_rule_meta(self.__class__.code)
        if yaml_meta is not None:
            return yaml_meta
        return self._default_meta

    def applicable(self, context: ValidationContext) -> bool:
        """判断规则是否适用于当前上下文

        默认逻辑：规则 enabled 且 scenario 在规则 scenarios 列表中。
        子类可覆盖以实现更复杂的条件（如仅当某个字段存在时才校验）。
        """
        meta = self.meta
        if not meta.enabled:
            return False
        # scenarios 为空表示对所有场景生效（兜底）
        if not meta.scenarios:
            return True
        return context.scenario in meta.scenarios

    @abstractmethod
    def check(self, context: ValidationContext) -> list[Suggestion]:
        """执行校验，返回建议列表（空列表表示通过）"""
        raise NotImplementedError

    # ===== 子类工具方法 =====

    def _suggestion(
        self,
        severity: Any,
        category: RuleCategory,
        message: str,
        fix_hint: str = "",
        affected_fields: list[str] | None = None,
    ) -> Suggestion:
        """快速构造 Suggestion"""
        return Suggestion(
            code=self.__class__.code,
            severity=severity,
            category=category,
            message=message,
            fix_hint=fix_hint,
            affected_fields=affected_fields or [],
        )

    def _get_threshold(self, section: str, key: str, default: Any) -> Any:
        """从 param_rules.yaml 读取阈值，未配置时用 default 兜底

        配置化阈值原则：所有可调参数必须通过 YAML 读取，禁止硬编码。
        """
        thresholds = repo_param_rules.get_thresholds(section)
        value = thresholds.get(key, default)
        # 类型安全：YAML 可能返回错误类型，做基本转换
        if isinstance(default, int) and isinstance(value, (int, float)):
            return int(value)
        if isinstance(default, float) and isinstance(value, (int, float)):
            return float(value)
        return value
