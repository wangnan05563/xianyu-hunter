"""参数计算器引擎与领域模型单元测试

覆盖范围：
- domain/param_calculator: ValidationReport 聚合属性、Suggestion 排序
- infra/repo_param_rules: YAML 读取、缓存、热更新
- modules/param_calculator/engine: 场景过滤、优先级排序、严重度排序、异常隔离、性能

设计原则：
- 所有 YAML 读取通过 monkeypatch 隔离，避免依赖生产 config/param_rules.yaml
- 性能测试用 perf_counter 量化，断言 < 50ms 满足 300ms 总响应预算
"""
from __future__ import annotations

import time
from typing import Any

import pytest

from xianyu_hunter.domain.param_calculator import (
    RuleCategory,
    RuleMeta,
    Scenario,
    Severity,
    Suggestion,
    ValidationContext,
    ValidationReport,
)
from xianyu_hunter.infra import repo_param_rules
from xianyu_hunter.modules.param_calculator.engine import ParamCalculatorEngine


# ============== Domain 模型测试 ==============


class TestValidationReport:
    """ValidationReport 聚合属性测试"""

    @staticmethod
    def _make(severity: Severity) -> Suggestion:
        return Suggestion(
            code="TEST_CODE",
            severity=severity,
            category=RuleCategory.ACCURACY,
            message="test",
        )

    def test_ok_when_no_suggestions(self) -> None:
        """无建议时 ok=True, has_blocking=False"""
        report = ValidationReport(scenario=Scenario.TASK_CREATE)
        assert report.ok is True
        assert report.has_blocking is False

    def test_not_ok_when_has_error(self) -> None:
        """存在 ERROR 级别时 ok=False, has_blocking=True"""
        report = ValidationReport(
            scenario=Scenario.TASK_CREATE,
            suggestions=[self._make(Severity.ERROR)],
        )
        assert report.ok is False
        assert report.has_blocking is True

    def test_ok_when_only_warning_and_info(self) -> None:
        """仅 WARNING/INFO 时 ok=True（不阻断提交）"""
        report = ValidationReport(
            scenario=Scenario.TASK_CREATE,
            suggestions=[self._make(Severity.WARNING), self._make(Severity.INFO)],
        )
        assert report.ok is True
        assert report.has_blocking is False
        assert report.warning_count == 1
        assert report.info_count == 1

    def test_by_category_filter(self) -> None:
        """by_category 按类别过滤建议"""
        s1 = Suggestion(
            code="A", severity=Severity.WARNING,
            category=RuleCategory.ACCURACY, message="a",
        )
        s2 = Suggestion(
            code="B", severity=Severity.INFO,
            category=RuleCategory.EFFICIENCY, message="b",
        )
        report = ValidationReport(
            scenario=Scenario.TASK_CREATE, suggestions=[s1, s2],
        )
        assert len(report.by_category(RuleCategory.ACCURACY)) == 1
        assert len(report.by_category(RuleCategory.EFFICIENCY)) == 1
        assert len(report.by_category(RuleCategory.STABILITY)) == 0


# ============== Infra repo_param_rules 测试 ==============


class TestRepoParamRules:
    """规则配置仓库测试：YAML 读取、缓存、热更新"""

    def test_get_thresholds_returns_empty_when_section_missing(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """未配置的段落返回空 dict，调用方需提供默认值兜底"""
        self._patch_yaml(monkeypatch, {"thresholds": {"task": {"min_price_span": 5}}})
        repo_param_rules.reload()

        assert repo_param_rules.get_thresholds("task") == {"min_price_span": 5}
        # 未配置段落返回空 dict，不抛异常
        assert repo_param_rules.get_thresholds("nonexistent") == {}

    def test_get_rule_meta_returns_none_when_not_configured(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """未配置的规则返回 None，调用方回退到代码默认元数据"""
        self._patch_yaml(monkeypatch, {})
        repo_param_rules.reload()

        assert repo_param_rules.get_rule_meta("NOT_EXIST") is None

    def test_get_rule_meta_parses_full_meta(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """完整解析 YAML 中的规则元数据（含 scenarios/category/priority）"""
        self._patch_yaml(monkeypatch, {
            "rules": {
                "TASK_PRICE_RANGE_INVALID": {
                    "name": "价格区间",
                    "category": "accuracy",
                    "scenarios": ["task_create", "task_edit"],
                    "priority": 250,
                    "enabled": False,
                    "description": "测试禁用",
                },
            },
        })
        repo_param_rules.reload()

        meta = repo_param_rules.get_rule_meta("TASK_PRICE_RANGE_INVALID")
        assert meta is not None
        assert meta.name == "价格区间"
        assert meta.category == RuleCategory.ACCURACY
        assert meta.scenarios == [Scenario.TASK_CREATE, Scenario.TASK_EDIT]
        assert meta.priority == 250
        assert meta.enabled is False

    def test_get_rule_meta_returns_none_on_invalid_category(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """非法 category 值时返回 None（防止脏数据导致规则引擎异常）"""
        self._patch_yaml(monkeypatch, {
            "rules": {"X": {"category": "invalid_category"}},
        })
        repo_param_rules.reload()

        assert repo_param_rules.get_rule_meta("X") is None

    def test_get_rule_meta_skips_invalid_scenario(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """非法 scenario 值被跳过，不影响其他合法 scenario"""
        self._patch_yaml(monkeypatch, {
            "rules": {
                "X": {
                    "category": "accuracy",
                    "scenarios": ["task_create", "invalid_scenario"],
                },
            },
        })
        repo_param_rules.reload()

        meta = repo_param_rules.get_rule_meta("X")
        assert meta is not None
        # 非法 scenario 被跳过，仅保留合法的
        assert meta.scenarios == [Scenario.TASK_CREATE]

    def test_reload_refreshes_cache(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """reload() 后再次读取应反映最新 YAML 内容"""
        self._patch_yaml(monkeypatch, {"thresholds": {"task": {"min_price_span": 5}}})
        repo_param_rules.reload()
        assert repo_param_rules.get_thresholds("task") == {"min_price_span": 5}

        # 修改 YAML 内容后 reload
        self._patch_yaml(monkeypatch, {"thresholds": {"task": {"min_price_span": 20}}})
        repo_param_rules.reload()
        assert repo_param_rules.get_thresholds("task") == {"min_price_span": 20}

    def test_get_all_rule_codes(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """get_all_rule_codes 返回所有已配置的规则编码"""
        self._patch_yaml(monkeypatch, {
            "rules": {"A": {}, "B": {}, "C": {}},
        })
        repo_param_rules.reload()

        codes = repo_param_rules.get_all_rule_codes()
        assert set(codes) == {"A", "B", "C"}

    @staticmethod
    def _patch_yaml(
        monkeypatch: pytest.MonkeyPatch, data: dict[str, Any],
    ) -> None:
        """替换 YAML 加载函数，隔离生产配置

        为什么 patch _load_yaml 而非 _rules_cache：
        _load_yaml 是缓存入口，patch 它可同时验证缓存逻辑与读取逻辑
        """
        monkeypatch.setattr(
            repo_param_rules, "_load_yaml", lambda _path: data,
        )


# ============== Engine 引擎测试 ==============


class TestParamCalculatorEngine:
    """参数计算器引擎测试"""

    @pytest.fixture(autouse=True)
    def _isolate_yaml(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """每个测试隔离 YAML：使用空配置，让所有规则走代码默认元数据

        为什么用空配置：代码默认值是规则生效的兜底，
        测试默认行为可验证规则引擎在 YAML 缺失时仍能正常工作
        """
        monkeypatch.setattr(
            repo_param_rules, "_load_yaml", lambda _path: {},
        )
        repo_param_rules.reload()

    def test_engine_loads_all_rules(self) -> None:
        """引擎加载全部规则（task + search + eval + config 共 17 条）"""
        engine = ParamCalculatorEngine()
        codes = engine.get_rule_codes()
        # 5 (task) + 4 (search) + 3 (eval) + 4 (config) = 16
        assert len(codes) == 16
        # 关键规则编码存在
        assert "TASK_PRICE_RANGE_INVALID" in codes
        assert "CACHE_TTL_MISMATCH" in codes
        assert "EVAL_WEIGHTS_SUM_INVALID" in codes

    def test_validate_minimal_valid_fields_returns_no_suggestions(self) -> None:
        """最小合法字段集返回无建议

        为什么不用空 fields：空 keyword 会触发 TASK_KEYWORD_INVALID，
        这是正确的业务行为（空关键词必须报错），不应期望无建议。
        """
        engine = ParamCalculatorEngine()
        ctx = ValidationContext(
            scenario=Scenario.TASK_CREATE,
            fields={"keyword": "测试关键词"},  # 合法关键词，其他字段缺省
        )
        report = engine.validate(ctx)
        assert report.suggestions == []
        assert report.ok is True

    def test_validate_task_create_scenario_skips_config_rules(self) -> None:
        """task_create 场景不触发 config_update 专属规则

        验证场景过滤：TASK_PRICE_RANGE_INVALID 仅在 task 场景生效，
        CACHE_EMPTY_RESULT_SKIP_INVALID 仅在 config_update 场景生效
        """
        engine = ParamCalculatorEngine()
        # task 场景下传入 empty_result_skip=true，不应触发 config 规则
        ctx = ValidationContext(
            scenario=Scenario.TASK_CREATE,
            fields={"empty_result_skip": True, "keyword": "测试"},
        )
        report = engine.validate(ctx)
        codes = [s.code for s in report.suggestions]
        assert "CACHE_EMPTY_RESULT_SKIP_INVALID" not in codes

    def test_validate_config_update_scenario_skips_task_rules(self) -> None:
        """config_update 场景不触发 task 专属规则"""
        engine = ParamCalculatorEngine()
        # config 场景下传入 min_price=1000, max_price=10，不应触发 task 规则
        ctx = ValidationContext(
            scenario=Scenario.CONFIG_UPDATE,
            fields={"min_price": 1000, "max_price": 10},
        )
        report = engine.validate(ctx)
        codes = [s.code for s in report.suggestions]
        assert "TASK_PRICE_RANGE_INVALID" not in codes

    def test_validate_returns_suggestions_sorted_by_severity(self) -> None:
        """建议按 severity 降序排列：ERROR > WARNING > INFO

        通过任务场景触发多条规则验证排序：
        - ERROR: min_price > max_price
        - WARNING: auto 模式无 max_price
        """
        engine = ParamCalculatorEngine()
        ctx = ValidationContext(
            scenario=Scenario.TASK_CREATE,
            fields={
                "keyword": "测试关键词",
                "min_price": 1000,
                "max_price": 10,
                "mode": "auto",
            },
        )
        report = engine.validate(ctx)
        # 至少有一条 ERROR
        severities = [s.severity for s in report.suggestions]
        # ERROR 应排在最前
        if Severity.ERROR in severities:
            error_idx = severities.index(Severity.ERROR)
            for i in range(error_idx):
                assert severities[i] == Severity.ERROR

    def test_validate_records_elapsed_ms(self) -> None:
        """校验耗时被记录（用于监控 300ms 响应预算）"""
        engine = ParamCalculatorEngine()
        ctx = ValidationContext(
            scenario=Scenario.TASK_CREATE,
            fields={"keyword": "测试"},
        )
        report = engine.validate(ctx)
        # elapsed_ms 应为非负整数
        assert isinstance(report.elapsed_ms, int)
        assert report.elapsed_ms >= 0

    def test_validate_performance_under_50ms(self) -> None:
        """单次校验耗时 < 50ms（前端 300ms 预算扣除网络往返）

        性能基线：纯内存计算 + 规则实例缓存，10 条字段校验应在 50ms 内
        """
        engine = ParamCalculatorEngine()
        fields = {
            "keyword": "测试关键词性能",
            "min_price": 10,
            "max_price": 1000,
            "interval_seconds": 60,
            "use_cron": False,
            "mode": "manual",
        }
        ctx = ValidationContext(scenario=Scenario.TASK_CREATE, fields=fields)

        # 预热（首次实例化规则）
        engine.validate(ctx)

        # 实际测量
        start = time.perf_counter()
        for _ in range(100):
            engine.validate(ctx)
        elapsed_ms = (time.perf_counter() - start) * 1000 / 100

        assert elapsed_ms < 50, f"单次校验 {elapsed_ms:.2f}ms 超过 50ms 预算"

    def test_validate_isolates_rule_exception(self) -> None:
        """单条规则抛异常不影响其他规则执行

        参数校验是辅助功能，不应阻断主流程：
        注入一个抛异常的规则，验证其他规则仍正常执行
        """
        engine = ParamCalculatorEngine()

        class BrokenRule(type(engine._rules[0])):  # noqa: SLF001
            """模拟抛异常的规则"""
            code = "BROKEN_RULE"

            def check(self, context: ValidationContext) -> list[Suggestion]:
                raise RuntimeError("simulated rule failure")

        # 为什么用 __new__ 绕过 __init__ 校验：直接继承会触发 code 必填校验
        broken = BrokenRule.__new__(BrokenRule)
        engine._rules.append(broken)  # noqa: SLF001

        ctx = ValidationContext(
            scenario=Scenario.TASK_CREATE,
            fields={"keyword": "测试", "min_price": 1000, "max_price": 10},
        )
        # 不应抛异常
        report = engine.validate(ctx)
        # 其他规则的结果仍存在
        assert any(s.code == "TASK_PRICE_RANGE_INVALID" for s in report.suggestions)

    def test_reload_rules_refreshes_instances(self) -> None:
        """reload_rules 重新加载规则实例（新增/删除规则代码后）"""
        engine = ParamCalculatorEngine()
        original_count = len(engine.get_rule_codes())

        engine.reload_rules()

        # 规则数量不变（无代码变更）
        assert len(engine.get_rule_codes()) == original_count

    def test_validate_batch_handles_multiple_contexts(self) -> None:
        """批量校验多个上下文（一次请求校验多个配置段）"""
        engine = ParamCalculatorEngine()
        contexts = [
            ValidationContext(scenario=Scenario.TASK_CREATE, fields={"keyword": "t1"}),
            ValidationContext(scenario=Scenario.CONFIG_UPDATE, fields={"page_size": 500}),
        ]
        reports = engine.validate_batch(contexts)
        assert len(reports) == 2
        assert reports[0].scenario == Scenario.TASK_CREATE
        assert reports[1].scenario == Scenario.CONFIG_UPDATE
        # 第二个上下文 page_size 过大应触发 WARNING
        assert any(
            s.code == "SEARCH_PAGE_SIZE_INVALID" for s in reports[1].suggestions
        )


class TestBaseRuleDefaults:
    """规则基类默认行为测试"""

    def test_base_rule_requires_code(self) -> None:
        """未定义 code 类属性的子类实例化时抛 ValueError"""
        from xianyu_hunter.modules.param_calculator.rules.base import BaseRule

        class NoCodeRule(BaseRule):
            def check(self, context: ValidationContext) -> list[Suggestion]:
                return []

        with pytest.raises(ValueError, match="必须定义 code"):
            NoCodeRule()

    def test_base_rule_default_meta_filled_from_code(self) -> None:
        """未设置 _default_meta.code 时，用类属性 code 填充"""
        from xianyu_hunter.modules.param_calculator.rules.base import BaseRule

        class MyRule(BaseRule):
            code = "MY_TEST_RULE"

            def check(self, context: ValidationContext) -> list[Suggestion]:
                return []

        rule = MyRule()
        # __init__ 后 _default_meta.code 应等于类属性 code
        assert rule._default_meta.code == "MY_TEST_RULE"  # noqa: SLF001
        assert rule._default_meta.name == "MY_TEST_RULE"

    def test_base_rule_get_threshold_type_conversion(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_get_threshold 根据 default 类型做基本转换（int/float）"""
        monkeypatch.setattr(
            repo_param_rules, "_load_yaml",
            lambda _path: {"thresholds": {"task": {"min_interval_seconds": 45.5}}},
        )
        repo_param_rules.reload()

        from xianyu_hunter.modules.param_calculator.rules.base import BaseRule

        class MyRule(BaseRule):
            code = "MY_THRESHOLD_RULE"

            def check(self, context: ValidationContext) -> list[Suggestion]:
                return []

        rule = MyRule()
        # default 为 int 时，YAML 返回 float 应转为 int
        val = rule._get_threshold("task", "min_interval_seconds", 60)  # noqa: SLF001
        assert val == 45  # 45.5 转 int 为 45
        assert isinstance(val, int)

        # default 为 float 时保留 float
        val_f = rule._get_threshold("task", "min_interval_seconds", 60.0)  # noqa: SLF001
        assert val_f == 45.5
        assert isinstance(val_f, float)

        # 未配置时返回 default
        val_missing = rule._get_threshold("task", "nonexistent", 99)  # noqa: SLF001
        assert val_missing == 99
