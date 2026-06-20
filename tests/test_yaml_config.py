"""YAML Config 单元测试"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from xianyu_hunter.infra.yaml_config import (
    AppConfig,
    EvalConfig,
    EvalThresholds,
    EvalWeights,
    get_config,
    reload_config,
)


def test_default_config_loads() -> None:
    """无 config/ 目录时使用默认配置"""
    cfg = get_config()
    assert isinstance(cfg, AppConfig)
    assert cfg.server.port == 8000
    assert cfg.antidetect.qps == 1


def test_eval_weights_sum_to_100() -> None:
    """评估权重之和应为 100"""
    cfg = get_config()
    w = cfg.eval.weights
    assert w.professional + w.credit + w.dispute + w.price == 100


def test_reload_config() -> None:
    """reload_config 能重新加载"""
    cfg1 = get_config()
    cfg2 = reload_config()
    assert isinstance(cfg2, AppConfig)


def test_professional_keywords_default() -> None:
    """默认包含常见的职业卖家关键词"""
    cfg = get_config()
    assert "批发" in cfg.eval.professional_keywords
    assert "代购" in cfg.eval.professional_keywords


def test_eval_thresholds_have_sensible_values() -> None:
    """阈值合理"""
    cfg = get_config()
    t = cfg.eval.thresholds
    assert t.credit_score_min >= 500  # 不应太低
    assert t.on_sale_count >= 10      # 不应太宽松
    assert 0.0 <= t.top_category_ratio <= 1.0


def test_pass_score_lt_auto_buy_score() -> None:
    """pass_score < auto_buy_score（保守半自动 < 激进全自动）"""
    cfg = get_config()
    assert cfg.eval.pass_score < cfg.eval.auto_buy_score
