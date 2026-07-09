"""YAML Config 单元测试"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from xianyu_hunter.infra.yaml_config import (
    AppConfig,
    EvalConfig,
    EvalThresholds,
    EvalWeights,
    _deep_merge_yaml,
    get_config,
    reload_config,
)


def test_default_config_loads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """无 config/ 目录时使用 Pydantic 默认值"""
    # 切到空目录确保没有真实 config/ 被加载
    monkeypatch.chdir(tmp_path)
    reload_config()
    cfg = get_config()
    assert isinstance(cfg, AppConfig)
    assert cfg.server.port == 8001
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
    # 闲鱼信用分范围 0-100（非芝麻信用 350-950），60 为合理阈值
    assert 50 <= t.credit_score_min <= 100  # 不应太低也不应超出闲鱼范围
    assert t.on_sale_count >= 10      # 不应太宽松
    assert 0.0 <= t.top_category_ratio <= 1.0


def test_pass_score_lt_auto_buy_score() -> None:
    """pass_score < auto_buy_score（保守半自动 < 激进全自动）"""
    cfg = get_config()
    assert cfg.eval.pass_score < cfg.eval.auto_buy_score


# ============== 抢单策略保存覆盖测试 ==============
# 回归：修复前 bug：config.yaml 的 pass_score/auto_buy_score 修改保存后
# 被 eval.yaml 整体覆盖回默认值，表现为"页面保存后刷新参数被重置"。

def test_deep_merge_yaml_basic() -> None:
    """_deep_merge_yaml：source 覆盖 target 同名 dict 字段的细分 key"""
    target = {"a": 1, "b": {"x": 10, "y": 20}}
    source = {"b": {"y": 200, "z": 300}, "c": 3}
    _deep_merge_yaml(target, source)
    # 同名字段细分 key 被 source 覆盖
    assert target["b"]["x"] == 10  # target 独有，保留
    assert target["b"]["y"] == 200  # 被 source 覆盖
    assert target["b"]["z"] == 300  # source 新增
    # 顶层新增
    assert target["c"] == 3
    # 未被覆盖的字段
    assert target["a"] == 1


def test_deep_merge_yaml_replaces_non_dict() -> None:
    """非 dict 类型被 source 直接覆盖"""
    target = {"a": [1, 2, 3], "b": "old"}
    source = {"a": [4, 5], "b": "new"}
    _deep_merge_yaml(target, source)
    assert target["a"] == [4, 5]
    assert target["b"] == "new"


def test_main_config_overrides_eval_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """主配置（config.yaml）的 eval 字段应优先于子配置（eval.yaml）

    模拟抢单策略页面 bug：用户在 config.yaml 中改 pass_score/auto_buy_score 后
    重新加载，期望读到 config.yaml 的值，而非 eval.yaml 的默认值。
    """
    # 隔离到临时目录避免污染真实 config/
    monkeypatch.chdir(tmp_path)
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()

    # eval.yaml 提供默认值（80 / 60）
    (cfg_dir / "eval.yaml").write_text(
        "eval:\n"
        "  weights:\n"
        "    professional: 30\n"
        "    credit: 30\n"
        "    dispute: 25\n"
        "    price: 15\n"
        "  thresholds:\n"
        "    on_sale_count: 30\n"
        "    post_count_30d: 15\n"
        "    top_category_ratio: 0.8\n"
        "    credit_score_min: 600\n"
        "    bad_review_max: 3\n"
        "    register_days_min: 30\n"
        "  pass_score: 60\n"
        "  auto_buy_score: 80\n",
        encoding="utf-8",
    )

    # config.yaml 提供用户修改后的值（75 / 65）
    (cfg_dir / "config.yaml").write_text(
        "eval:\n"
        "  pass_score: 65\n"
        "  auto_buy_score: 75\n"
        "  ai_auto_eval: false\n"
        "  ai_auto_deep_analyze: false\n",
        encoding="utf-8",
    )

    reload_config()
    cfg = get_config()
    # 关键断言：主配置覆盖子配置
    assert cfg.eval.pass_score == 65
    assert cfg.eval.auto_buy_score == 75
    # eval.yaml 的 weights / thresholds 仍然生效（深度合并而非整体替换）
    assert cfg.eval.weights.professional == 30
    assert cfg.eval.thresholds.credit_score_min == 600
    # config.yaml 独有的 ai_auto_eval 不被丢失（旧 bug 会因整体替换而丢失）
    assert cfg.eval.ai_auto_eval is False
    assert cfg.eval.ai_auto_deep_analyze is False


def test_eval_yaml_alone_uses_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """只有 eval.yaml、没有 config.yaml 时仍能加载（向后兼容）"""
    monkeypatch.chdir(tmp_path)
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    (cfg_dir / "eval.yaml").write_text(
        "eval:\n"
        "  weights:\n"
        "    professional: 30\n"
        "    credit: 30\n"
        "    dispute: 25\n"
        "    price: 15\n"
        "  pass_score: 50\n"
        "  auto_buy_score: 70\n",
        encoding="utf-8",
    )
    reload_config()
    cfg = get_config()
    assert cfg.eval.pass_score == 50
    assert cfg.eval.auto_buy_score == 70


def test_no_config_dir_uses_pydantic_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """完全没有 config/ 目录时使用 AppConfig 的 Pydantic 默认值"""
    monkeypatch.chdir(tmp_path)
    reload_config()
    cfg = get_config()
    # 验证未抛出异常且返回合法 AppConfig
    assert isinstance(cfg, AppConfig)
    # 默认 pass_score=60, auto_buy_score=80
    assert cfg.eval.pass_score == 60
    assert cfg.eval.auto_buy_score == 80
