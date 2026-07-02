"""TaskSchedulerConfig 配置块测试"""
from __future__ import annotations

from pathlib import Path

import pytest

from xianyu_hunter.infra.yaml_config import (
    AppConfig,
    TaskSchedulerConfig,
    get_config,
    reload_config,
)


def test_task_scheduler_config_defaults() -> None:
    """默认值：60 秒 / 关闭自动搜索 / 并发 1"""
    cfg = TaskSchedulerConfig()
    assert cfg.default_interval_seconds == 60
    assert cfg.auto_search_enabled is False
    assert cfg.auto_search_concurrency == 1


def test_task_scheduler_config_field_validation() -> None:
    """字段范围校验：default_interval_seconds 30-3600"""
    with pytest.raises(Exception):
        TaskSchedulerConfig(default_interval_seconds=29)
    with pytest.raises(Exception):
        TaskSchedulerConfig(default_interval_seconds=3601)
    with pytest.raises(Exception):
        TaskSchedulerConfig(auto_search_concurrency=0)
    with pytest.raises(Exception):
        TaskSchedulerConfig(auto_search_concurrency=6)


def test_app_config_has_task_scheduler_default() -> None:
    """AppConfig 默认包含 task_scheduler 段"""
    cfg = AppConfig()
    assert isinstance(cfg.task_scheduler, TaskSchedulerConfig)
    assert cfg.task_scheduler.default_interval_seconds == 60


def test_app_config_loads_task_scheduler_from_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """从 yaml 加载 task_scheduler 段"""
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    (cfg_dir / "config.yaml").write_text(
        "task_scheduler:\n"
        "  default_interval_seconds: 120\n"
        "  auto_search_enabled: true\n"
        "  auto_search_concurrency: 2\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    reload_config()
    cfg = get_config()
    assert cfg.task_scheduler.default_interval_seconds == 120
    assert cfg.task_scheduler.auto_search_enabled is True
    assert cfg.task_scheduler.auto_search_concurrency == 2
