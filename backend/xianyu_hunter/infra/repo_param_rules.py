"""参数规则配置存储（infra 层）

从 config/param_rules.yaml 加载规则元数据与阈值，提供内存缓存。
规则引擎通过此模块读取运行时配置，无需修改代码即可调整阈值。
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import yaml

from xianyu_hunter.domain.param_calculator import (
    RuleCategory,
    RuleMeta,
    Scenario,
)
from xianyu_hunter.paths import get_config_dir

_RULES_FILE = "param_rules.yaml"

# 模块级缓存：避免每次校验都读盘
# 加锁保证多线程（FastAPI 线程池）下只加载一次
_rules_cache: dict[str, Any] | None = None
_lock = threading.Lock()


def _load_yaml(path: Path) -> dict[str, Any]:
    """读取 YAML 文件，文件不存在或为空时返回空 dict

    使用自实现加载避免依赖 infra/yaml_config 的 AppConfig 模型，
    规则配置的 schema 独立于业务配置，便于独立演进。
    """
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def _load_rules_config() -> dict[str, Any]:
    """加载规则配置并缓存

    首次调用读盘，后续直接返回缓存。reload() 可强制刷新。
    """
    global _rules_cache
    if _rules_cache is not None:
        return _rules_cache
    with _lock:
        if _rules_cache is None:
            _rules_cache = _load_yaml(get_config_dir() / _RULES_FILE)
        return _rules_cache


def reload() -> None:
    """强制重新加载规则配置（配置变更后调用）"""
    global _rules_cache
    with _lock:
        _rules_cache = None


def get_rule_meta(code: str) -> RuleMeta | None:
    """根据规则编码读取元数据

    YAML 中未配置的规则返回 None，调用方使用代码内默认元数据。
    """
    data = _load_rules_config()
    rules_section = data.get("rules", {})
    raw = rules_section.get(code)
    if not raw or not isinstance(raw, dict):
        return None
    # 逐项容错：跳过无效 scenario 值，保留合法项
    # 为什么不用列表推导 + try/except：单个无效值会导致整个列表被丢弃，合法项也被误删
    scenarios: list[Scenario] = []
    for s in raw.get("scenarios", []):
        try:
            scenarios.append(Scenario(s))
        except ValueError:
            continue
    try:
        category = RuleCategory(raw.get("category", ""))
    except ValueError:
        return None
    return RuleMeta(
        code=code,
        name=raw.get("name", code),
        category=category,
        scenarios=scenarios,
        priority=int(raw.get("priority", 100)),
        enabled=bool(raw.get("enabled", True)),
        description=raw.get("description", ""),
    )


def get_thresholds(section: str) -> dict[str, Any]:
    """读取指定段落的阈值配置

    例：get_thresholds("task") 返回 {min_interval_seconds: 60, ...}
    未配置的段落返回空 dict，调用方需提供默认值兜底。
    """
    data = _load_rules_config()
    thresholds = data.get("thresholds", {})
    section_data = thresholds.get(section, {})
    return section_data if isinstance(section_data, dict) else {}


def get_all_rule_codes() -> list[str]:
    """获取所有已配置的规则编码（用于诊断与监控）"""
    data = _load_rules_config()
    rules_section = data.get("rules", {})
    return list(rules_section.keys()) if isinstance(rules_section, dict) else []
