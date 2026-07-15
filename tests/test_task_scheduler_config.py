"""TaskSchedulerConfig 配置块测试"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

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
    try:
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
    finally:
        # 恢复全局 _config 到原 cwd 的配置，避免污染后续测试
        # 为什么放 finally：断言失败时也能恢复，防止测试失败连锁影响
        # 为什么用 undo：当前 pytest 的 chdir 需要显式 path 参数，undo 会自动恢复 cwd
        monkeypatch.undo()
        reload_config()


from xianyu_hunter.web.routes.api_tasks import TaskCreate


def test_task_create_interval_seconds_defaults_to_none() -> None:
    """TaskCreate.interval_seconds 默认值为 None（让 create_task 从全局配置取）"""
    body = TaskCreate(keyword="测试")
    assert body.interval_seconds is None


def test_task_create_interval_seconds_accepts_explicit_value() -> None:
    """TaskCreate.interval_seconds 显式传入时使用传入值"""
    body = TaskCreate(keyword="测试", interval_seconds=120)
    assert body.interval_seconds == 120


def test_task_create_interval_seconds_rejects_out_of_range() -> None:
    """TaskCreate.interval_seconds 范围校验 30-3600"""
    with pytest.raises(Exception):
        TaskCreate(keyword="测试", interval_seconds=29)
    with pytest.raises(Exception):
        TaskCreate(keyword="测试", interval_seconds=3601)


def test_create_task_falls_back_to_global_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """body.interval_seconds=None 时 create_task 从全局配置 task_scheduler.default_interval_seconds 取值

    端到端验证兜底逻辑：若未来误删 create_task 中的 get_config 兜底分支，本测试失败。
    """
    from xianyu_hunter.infra.repository import Repository
    from xianyu_hunter.web.routes.api_tasks import create_task

    # mock 全局配置：default_interval_seconds=90（与默认 60 区分，便于断言取的是配置值）
    fake_cfg = AppConfig()
    fake_cfg.task_scheduler.default_interval_seconds = 90
    # 为什么 patch api_tasks.get_config 而非 yaml_config.get_config：
    # I2 修复后 create_task 通过模块顶层 `from ... import get_config` 绑定名称，
    # patch 源模块不影响已绑定引用，必须 patch 调用点所在模块
    monkeypatch.setattr(
        "xianyu_hunter.web.routes.api_tasks.get_config", lambda: fake_cfg
    )

    # 用临时 sqlite 构造 repo + 最小 container
    # 为什么用 _FakeContainer 而非真实 Container：create_task 仅依赖 container.repo，
    # 真实 Container 需注入 collector/evaluator/buyer 等重依赖，与本项目测试惯例不符
    db_path = str(tmp_path / "test.db")
    repo = Repository(db_path)

    class _FakeContainer:
        def __init__(self, repo):
            self.repo = repo

    try:
        container = _FakeContainer(repo)
        body = TaskCreate(keyword="测试自动搜索")
        request = SimpleNamespace(state=SimpleNamespace(user_id="default"))
        result = create_task(body, request=request, container=container)
        assert result["ok"] is True
        assert result["task"]["interval_seconds"] == 90
    finally:
        # Windows 下释放 SQLAlchemy 文件句柄，避免 tmp_path 清理失败
        repo.engine.dispose()
