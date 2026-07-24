"""参数校验服务（web/services 层）

职责：将 API 请求体（任务/配置）转换为 ValidationContext，调用引擎校验。
作为 routes 与 engine 之间的适配层，屏蔽 API schema 与领域模型的差异。
"""
from __future__ import annotations

from typing import Any

from xianyu_hunter.domain.param_calculator import (
    Scenario,
    ValidationContext,
    ValidationReport,
)
from xianyu_hunter.modules.param_calculator import ParamCalculatorEngine


class ParamValidatorService:
    """参数校验服务

    生命周期：单例（与 Container 中其他服务一致）。
    引擎在 __init__ 中构造并缓存，避免每次校验重新加载规则。
    """

    def __init__(self) -> None:
        self._engine = ParamCalculatorEngine()

    @property
    def engine(self) -> ParamCalculatorEngine:
        """暴露引擎实例，供 routes 直接调用 reload_rules 等方法"""
        return self._engine

    def validate_task(
        self,
        task_fields: dict[str, Any],
        scenario: Scenario,
        global_config: dict[str, Any] | None = None,
    ) -> ValidationReport:
        """校验任务参数

        task_fields 为扁平化的任务字段字典，由 routes 从 TaskCreate body 提取。
        global_config 为当前 AppConfig 的 dict 快照，用于跨段交叉校验。
        """
        context = ValidationContext(
            scenario=scenario,
            fields=task_fields,
            global_config=global_config,
        )
        return self._engine.validate(context)

    def validate_config(
        self,
        config_fields: dict[str, Any],
        scenario: Scenario = Scenario.CONFIG_UPDATE,
    ) -> ValidationReport:
        """校验系统配置参数

        config_fields 为扁平化的配置字段字典，由 routes 从 ConfigSaveBody 提取。
        可包含跨段字段（如 cache.live_search_ttl 与 task_scheduler.default_interval_seconds）。
        """
        context = ValidationContext(
            scenario=scenario,
            fields=config_fields,
        )
        return self._engine.validate(context)

    def validate_batch(
        self,
        items: list[tuple[dict[str, Any], Scenario]],
        global_config: dict[str, Any] | None = None,
    ) -> list[ValidationReport]:
        """批量校验

        用于一次请求中校验多个配置段（如同时变更 task + search + eval）。
        """
        contexts = [
            ValidationContext(scenario=sc, fields=flds, global_config=global_config)
            for flds, sc in items
        ]
        return self._engine.validate_batch(contexts)

    def reload(self) -> None:
        """重新加载规则（配置变更后调用）"""
        # 先刷新 infra 层的 YAML 缓存，再重建引擎规则实例
        from xianyu_hunter.infra import repo_param_rules
        repo_param_rules.reload()
        self._engine.reload_rules()

    def list_rules(self) -> list[dict[str, Any]]:
        """列出所有规则元数据（用于前端展示与文档生成）"""
        result: list[dict[str, Any]] = []
        for rule in self._engine.get_rule_codes():
            # 通过规则实例获取运行时元数据
            for r in self._engine._rules:  # noqa: SLF001
                if r.__class__.code == rule:
                    meta = r.meta
                    result.append({
                        "code": meta.code,
                        "name": meta.name,
                        "category": meta.category.value,
                        "scenarios": [s.value for s in meta.scenarios],
                        "priority": meta.priority,
                        "enabled": meta.enabled,
                        "description": meta.description,
                    })
                    break
        return result
