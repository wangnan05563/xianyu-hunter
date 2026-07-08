"""调度器运行时治理防回归测试（meta-rules #48-#51 / step 194-197）

覆盖以下修复点，防止退化：
- P1-1: BatchRefreshScheduler.update_config(enabled=False) 必须调用 remove_job
- P1-2: CookieSyncScheduler.update_config(enabled=False) 必须立即生效（_enabled=False）
- P2-1: scheduler.py 的 retry_wait 必须从配置读取，禁止硬编码 300
- P2-2: scheduler.drop_task_state 必须清理 _resume_cooldown
- 配置类: TaskSchedulerConfig 默认含 4 个新子节点（meta-rules #48-#51 落地）
"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from xianyu_hunter.infra.yaml_config import (
    CronMinIntervalCheckConfig,
    LifecycleResourceCleanupConfig,
    SchedulerRuntimeToggleConfig,
    TaskSchedulerConfig,
    TimeParamConfigDrivenConfig,
)


# ============== 配置类测试（meta-rules #48-#51 落地）==============

def test_task_scheduler_config_has_four_new_subconfigs() -> None:
    """TaskSchedulerConfig 默认包含 4 个新子节点（meta-rules #48-#51）"""
    cfg = TaskSchedulerConfig()
    assert isinstance(cfg.scheduler_runtime_toggle, SchedulerRuntimeToggleConfig)
    assert isinstance(cfg.time_param_config_driven, TimeParamConfigDrivenConfig)
    assert isinstance(cfg.lifecycle_resource_cleanup, LifecycleResourceCleanupConfig)
    assert isinstance(cfg.cron_min_interval_check, CronMinIntervalCheckConfig)


def test_scheduler_runtime_toggle_defaults() -> None:
    """scheduler_runtime_toggle 默认值（meta-rule #48）"""
    cfg = SchedulerRuntimeToggleConfig()
    assert cfg.enabled is True
    assert cfg.require_enabled_field is True
    assert cfg.require_update_config_method is True
    assert cfg.require_remove_job_on_disable is True
    # 默认目标调度器列表
    assert "BatchRefreshScheduler" in cfg.target_schedulers
    assert "CookieSyncScheduler" in cfg.target_schedulers


def test_time_param_config_driven_defaults() -> None:
    """time_param_config_driven 默认值（meta-rule #49）"""
    cfg = TimeParamConfigDrivenConfig()
    assert cfg.enabled is True
    assert cfg.require_config_key is True
    # 默认禁止硬编码模式必须覆盖 time.sleep(300) / asyncio.sleep(300)
    assert any("time.sleep(300)" in p for p in cfg.forbidden_hardcoded_patterns)
    assert any("asyncio.sleep(300)" in p for p in cfg.forbidden_hardcoded_patterns)
    # 默认扫描范围必须包含 scheduler.py
    assert any("scheduler.py" in m for m in cfg.scan_modules)


def test_lifecycle_resource_cleanup_defaults() -> None:
    """lifecycle_resource_cleanup 默认值（meta-rule #50）"""
    cfg = LifecycleResourceCleanupConfig()
    assert cfg.enabled is True
    assert cfg.require_drop_method is True
    # 默认目标状态字段必须覆盖 _resume_cooldown
    assert "_resume_cooldown" in cfg.target_state_holders
    # 审计间隔默认 1 小时
    assert cfg.audit_interval_seconds == 3600


def test_cron_min_interval_check_defaults() -> None:
    """cron_min_interval_check 默认值（meta-rule #51，实验性）"""
    cfg = CronMinIntervalCheckConfig()
    assert cfg.enabled is True
    # 实验性标签必须为 true（1 季度观察期）
    assert cfg.experimental is True
    # 最小间隔默认 60 秒
    assert cfg.min_interval_seconds == 60
    # 默认拦截 * * * * * 与 */1 * * * *
    assert "* * * * *" in cfg.blocked_patterns
    assert "*/1 * * * *" in cfg.blocked_patterns


def test_cron_min_interval_check_field_validation() -> None:
    """字段范围校验：min_interval_seconds 1-86400"""
    with pytest.raises(Exception):
        CronMinIntervalCheckConfig(min_interval_seconds=0)
    with pytest.raises(Exception):
        CronMinIntervalCheckConfig(min_interval_seconds=86401)


def test_lifecycle_resource_cleanup_audit_interval_validation() -> None:
    """字段范围校验：audit_interval_seconds 60-86400"""
    with pytest.raises(Exception):
        LifecycleResourceCleanupConfig(audit_interval_seconds=59)
    with pytest.raises(Exception):
        LifecycleResourceCleanupConfig(audit_interval_seconds=86401)


# ============== P1-1 防回归：BatchRefreshScheduler.update_config(enabled=False) ==============

def test_batch_refresh_update_config_disabled_removes_job() -> None:
    """P1-1 防回归：update_config(enabled=False) 必须调用 remove_job

    历史教训：原实现只设 _enabled=False 标志位未调用 remove_job，
    APScheduler 已注册的 job 仍按 trigger 触发，导致禁用后仍持续执行批量采集。
    """
    from xianyu_hunter.infra.yaml_config import BatchRefreshConfig
    from xianyu_hunter.modules.batch_refresh_scheduler import (
        BatchRefreshScheduler,
    )

    container = MagicMock()
    config = BatchRefreshConfig(enabled=True)
    scheduler = BatchRefreshScheduler(container, config)

    # 启动调度器让 _scheduler 实例化
    loop = asyncio.new_event_loop()
    try:
        scheduler.start(loop)
        # 用 spy 监控 remove_job 调用
        remove_job_spy = MagicMock(wraps=scheduler._scheduler.remove_job)
        scheduler._scheduler.remove_job = remove_job_spy

        # 执行禁用
        scheduler.update_config(enabled=False)

        # 验证 remove_job 被调用（核心防回归点）
        remove_job_spy.assert_called_with("batch_refresh")
        # 验证 config.enabled 也被同步
        assert config.enabled is False
    finally:
        scheduler.stop()
        loop.close()


def test_batch_refresh_update_config_enabled_does_not_remove_job() -> None:
    """P1-1 边界：update_config(enabled=True) 不应调用 remove_job"""
    from xianyu_hunter.infra.yaml_config import BatchRefreshConfig
    from xianyu_hunter.modules.batch_refresh_scheduler import (
        BatchRefreshScheduler,
    )

    container = MagicMock()
    config = BatchRefreshConfig(enabled=False)
    scheduler = BatchRefreshScheduler(container, config)

    loop = asyncio.new_event_loop()
    try:
        scheduler.start(loop)
        remove_job_spy = MagicMock(wraps=scheduler._scheduler.remove_job)
        scheduler._scheduler.remove_job = remove_job_spy

        # 启用时不应调用 remove_job
        scheduler.update_config(enabled=True)
        remove_job_spy.assert_not_called()
        assert config.enabled is True
    finally:
        scheduler.stop()
        loop.close()


# ============== P1-2 防回归：CookieSyncScheduler.update_config(enabled=False) ==============

def test_cookie_sync_update_config_disabled_sets_enabled_flag() -> None:
    """P1-2 防回归：update_config(enabled=False) 必须立即设置 _enabled=False

    CookieSyncScheduler 采用软禁用策略（_enabled=False + _run_sync_job 入口检查），
    与 BatchRefreshScheduler 的硬禁用（remove_job）不同但等效。
    关键约束：禁用后 _run_sync_job 入口必须立即 return，不再执行业务逻辑。
    """
    from xianyu_hunter.modules.cookie_sync_scheduler import (
        CookieSyncScheduler,
    )

    cookie_store = MagicMock()
    scheduler = CookieSyncScheduler(cookie_store)

    # 默认启用
    assert scheduler._enabled is True

    # 禁用
    scheduler.update_config(enabled=False)
    assert scheduler._enabled is False

    # 重新启用
    scheduler.update_config(enabled=True)
    assert scheduler._enabled is True


def test_cookie_sync_run_sync_job_skips_when_disabled() -> None:
    """P1-2 防回归：_enabled=False 时 _run_sync_job 必须立即 return

    验证软禁用入口检查生效，不执行任何业务逻辑（_should_sync 不被调用）。
    """
    from xianyu_hunter.modules.cookie_sync_scheduler import (
        CookieSyncScheduler,
    )

    cookie_store = MagicMock()
    scheduler = CookieSyncScheduler(cookie_store)
    scheduler.update_config(enabled=False)

    # _run_sync_job 应在入口立即 return，不调用 _should_sync
    with patch.object(scheduler, "_should_sync") as should_sync_mock:
        scheduler._run_sync_job()
        should_sync_mock.assert_not_called()


# ============== P2-1 防回归：scheduler.py 时间参数配置化 ==============

def test_scheduler_error_retry_wait_reads_from_config() -> None:
    """P2-1 防回归：error_retry_wait_seconds 必须从配置读取，禁止硬编码 300

    历史教训：原实现用 hardcoded `await asyncio.sleep(300)`，
    用户配置 task_scheduler.error_retry_wait_seconds=30 不生效。
    """
    from xianyu_hunter.infra.yaml_config import AppConfig
    from xianyu_hunter.modules.scheduler import TaskScheduler

    # 验证 _get_error_retry_wait_seconds 静态方法能正确读取配置
    # get_config 在 _get_error_retry_wait_seconds 函数内部 import，需 patch 源模块
    test_cfg = AppConfig()
    test_cfg.task_scheduler.error_retry_wait_seconds = 42

    with patch(
        "xianyu_hunter.infra.yaml_config.get_config",
        return_value=test_cfg,
    ):
        # _get_error_retry_wait_seconds 是静态方法
        result = TaskScheduler._get_error_retry_wait_seconds()
        assert result == 42


def test_scheduler_error_retry_wait_no_hardcoded_300() -> None:
    """P2-1 防回归：scheduler.py 源码中禁止出现硬编码 sleep(300)

    通过 grep 检查源码，确保 time.sleep(300) / asyncio.sleep(300) 已消除。
    """
    import re
    from pathlib import Path

    scheduler_path = (
        Path(__file__).parent.parent
        / "src"
        / "xianyu_hunter"
        / "modules"
        / "scheduler.py"
    )
    source = scheduler_path.read_text(encoding="utf-8")

    # 禁止硬编码 sleep(300)（注释中的 300 不算违规，需排除注释行）
    forbidden_patterns = [
        r"^\s*await\s+asyncio\.sleep\(300\)",  # await asyncio.sleep(300)
        r"^\s*time\.sleep\(300\)",  # time.sleep(300)
    ]
    for line_number, line in enumerate(source.splitlines(), start=1):
        # 跳过注释行
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        for pattern in forbidden_patterns:
            assert not re.search(pattern, line), (
                f"scheduler.py:{line_number} 含硬编码 sleep(300)：{line}"
            )


# ============== P2-2 防回归：drop_task_state 清理 _resume_cooldown ==============

def test_scheduler_drop_task_state_clears_resume_cooldown() -> None:
    """P2-2 防回归：drop_task_state 必须从 _resume_cooldown 中删除条目

    历史教训：DELETE /api/tasks/{task_id} 不调用 drop_task_state，
    导致 _resume_cooldown 字典长期运行后无限增长（内存泄漏）。
    """
    from xianyu_hunter.modules.scheduler import TaskScheduler

    scheduler = TaskScheduler.__new__(TaskScheduler)
    # 手动构造 _resume_cooldown 字典
    scheduler._resume_cooldown = {
        "task_a": 1000.0,
        "task_b": 2000.0,
    }

    # 删除 task_a
    scheduler.drop_task_state("task_a")

    assert "task_a" not in scheduler._resume_cooldown
    assert "task_b" in scheduler._resume_cooldown


def test_scheduler_drop_task_state_idempotent() -> None:
    """P2-2 边界：drop_task_state 对不存在的 task_id 应幂等（不抛错）"""
    from xianyu_hunter.modules.scheduler import TaskScheduler

    scheduler = TaskScheduler.__new__(TaskScheduler)
    scheduler._resume_cooldown = {}

    # 对不存在的 task_id 调用应不抛错
    scheduler.drop_task_state("non_existent_task")
    assert scheduler._resume_cooldown == {}
