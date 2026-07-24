"""规则集子包

按业务场景分组：
- task_rules: 任务参数规则（价格区间、调度间隔、依赖关系）
- search_rules: 搜索参数规则（页大小、超时、并发）
- eval_rules: 评估参数规则（权重、阈值、AI 评估）
- config_rules: 系统配置规则（缓存、反爬、调度器开关）
"""
from xianyu_hunter.modules.param_calculator.rules.base import BaseRule
from xianyu_hunter.modules.param_calculator.rules.config_rules import ConfigRules
from xianyu_hunter.modules.param_calculator.rules.eval_rules import EvalRules
from xianyu_hunter.modules.param_calculator.rules.search_rules import SearchRules
from xianyu_hunter.modules.param_calculator.rules.task_rules import TaskRules

__all__ = [
    "BaseRule",
    "TaskRules",
    "SearchRules",
    "EvalRules",
    "ConfigRules",
]
