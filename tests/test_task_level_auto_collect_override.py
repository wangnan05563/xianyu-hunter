"""Task 13: 任务级 auto_collect_official / auto_collect_max_per_run 覆盖全局配置的合并逻辑测试

验证 worker._effective_eval_cfg 正确合并 task.eval_config 与全局 AppConfig.eval：
- 任务级字段优先于全局配置
- None 值字段被忽略（沿用全局）
- 未知字段被忽略（避免污染 EvalConfig）
- 全局 EvalConfig 单例不被修改

并验证两个端到端场景：
1. 全局 auto_collect_official=True，任务级 False → 该任务不触发采集
2. 全局 auto_collect_max_per_run=3，任务级 10 → 该任务单轮最多采集 10 个

设计要点：
- 复用 test_worker_auto_collect.py 的 Fakes 与 patch_eval_config 模式
- 直接在 worker.task 上设置 eval_config，不修改 build_worker 签名
- 单元测试用 mock EvalConfig 避免依赖全局单例
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from xianyu_hunter.infra.yaml_config import AppConfig
from xianyu_hunter.modules.worker import TaskWorker

# 复用 test_worker_auto_collect 的工厂与 patch_eval_config 模式，保持测试风格统一
from tests.test_worker_auto_collect import (
    build_worker,
    make_eval_config,
    patch_eval_config,
)


# ============== SubTask 13.2 单元测试：_effective_eval_cfg 合并逻辑 ==============


def _make_worker_with_eval_config(eval_config: dict[str, Any] | None) -> TaskWorker:
    """构造带任务级 eval_config 的 worker

    直接复用 build_worker 创建默认 worker，再设置 task.eval_config，
    避免修改 build_worker 签名影响 test_worker_auto_collect.py。
    """
    worker = build_worker(item_count=0)
    worker.task.eval_config = eval_config
    return worker


def test_effective_eval_cfg_no_override_returns_global():
    """task.eval_config=None → 直接返回全局 eval_cfg，无合并开销

    覆盖绝大多数任务的常见路径：未设置任务级覆盖时不应有任何合并开销。
    """
    global_eval = make_eval_config(auto_collect_official=True, auto_collect_max_per_run=5)
    app_cfg = AppConfig(eval=global_eval)
    worker = _make_worker_with_eval_config(None)
    with patch("xianyu_hunter.modules.worker.get_config", return_value=app_cfg):
        result = worker._effective_eval_cfg()
    # 未设置覆盖时返回的就是全局对象本身（无副本开销）
    assert result is global_eval
    assert result.auto_collect_official is True
    assert result.auto_collect_max_per_run == 5


def test_effective_eval_cfg_override_applied():
    """task.eval_config 非空 → 任务级字段覆盖全局

    全局 auto_collect_official=True / max=3，
    任务级 auto_collect_official=False / max=10，
    期望合并后 auto_collect_official=False / max=10。
    """
    global_eval = make_eval_config(auto_collect_official=True, auto_collect_max_per_run=3)
    app_cfg = AppConfig(eval=global_eval)
    worker = _make_worker_with_eval_config({
        "auto_collect_official": False,
        "auto_collect_max_per_run": 10,
    })
    with patch("xianyu_hunter.modules.worker.get_config", return_value=app_cfg):
        result = worker._effective_eval_cfg()
    assert result.auto_collect_official is False
    assert result.auto_collect_max_per_run == 10
    # 合并后应返回新对象，而非原全局对象
    assert result is not global_eval


def test_effective_eval_cfg_override_none_value_ignored():
    """task.eval_config 中值为 None 的字段被忽略，沿用全局

    任务级 {"auto_collect_official": None} 表示"不覆盖此字段"，
    期望合并后 auto_collect_official 沿用全局 True。
    这与"传 False 关闭"语义不同，避免前端删除字段时误把 None 写入。
    """
    global_eval = make_eval_config(auto_collect_official=True, auto_collect_max_per_run=3)
    app_cfg = AppConfig(eval=global_eval)
    worker = _make_worker_with_eval_config({"auto_collect_official": None})
    with patch("xianyu_hunter.modules.worker.get_config", return_value=app_cfg):
        result = worker._effective_eval_cfg()
    assert result.auto_collect_official is True
    assert result.auto_collect_max_per_run == 3


def test_effective_eval_cfg_override_unknown_key_ignored():
    """task.eval_config 中未知字段被忽略，不污染 EvalConfig

    前端可能误传非 EvalConfig 字段（如 typo 或废弃字段），
    期望合并逻辑静默忽略，不抛异常也不创建未知属性。
    """
    global_eval = make_eval_config(auto_collect_official=True)
    app_cfg = AppConfig(eval=global_eval)
    worker = _make_worker_with_eval_config({
        "unknown_field_xyz": 123,
        "auto_collect_max_per_run": 7,
    })
    with patch("xianyu_hunter.modules.worker.get_config", return_value=app_cfg):
        result = worker._effective_eval_cfg()
    # 未知字段被忽略，已知字段被覆盖
    assert result.auto_collect_max_per_run == 7
    assert not hasattr(result, "unknown_field_xyz")


def test_effective_eval_cfg_does_not_mutate_global():
    """合并后全局 EvalConfig 单例不被修改

    关键防回归：_effective_eval_cfg 必须返回副本而非原地修改，
    否则一个任务设置覆盖后，全局单例被污染，影响后续所有任务。
    """
    global_eval = make_eval_config(auto_collect_official=True, auto_collect_max_per_run=3)
    app_cfg = AppConfig(eval=global_eval)
    worker = _make_worker_with_eval_config({
        "auto_collect_official": False,
        "auto_collect_max_per_run": 10,
    })
    with patch("xianyu_hunter.modules.worker.get_config", return_value=app_cfg):
        merged = worker._effective_eval_cfg()

    # 合并后的副本反映了任务级覆盖
    assert merged.auto_collect_official is False
    assert merged.auto_collect_max_per_run == 10
    # 全局单例保持原值不变
    assert global_eval.auto_collect_official is True
    assert global_eval.auto_collect_max_per_run == 3


def test_effective_eval_cfg_empty_dict_returns_global():
    """task.eval_config={} → 视为无覆盖，直接返回全局 eval_cfg

    空字典与 None 语义一致：前端清除覆盖时会传空 dict 或 None，
    合并逻辑应统一处理，避免空 dict 触发不必要的 model_copy。
    """
    global_eval = make_eval_config(auto_collect_official=True)
    app_cfg = AppConfig(eval=global_eval)
    worker = _make_worker_with_eval_config({})
    with patch("xianyu_hunter.modules.worker.get_config", return_value=app_cfg):
        result = worker._effective_eval_cfg()
    # 空字典过滤后 updates 为空，直接返回全局对象
    assert result is global_eval


# ============== SubTask 13.2 集成测试：端到端覆盖场景 ==============


@pytest.mark.asyncio
async def test_task_level_disable_overrides_global_enable():
    """全局 auto_collect_official=True，任务级 auto_collect_official=False → 不触发采集

    场景：管理员在全局配置开启了自动官方采集，
    但某个高频任务为避免触发反爬，任务级关闭采集。
    断言该任务的 official_collect_fn 不被调用。
    """
    collect_fn = AsyncMock(return_value={"ok": True})
    worker = build_worker(item_count=1, official_collect_fn=collect_fn)
    # 任务级覆盖：关闭自动官方采集
    worker.task.eval_config = {"auto_collect_official": False}
    # 全局配置：开启自动官方采集
    with patch_eval_config(make_eval_config(auto_collect_official=True, auto_collect_max_per_run=3)):
        result = await worker.run_once()
    collect_fn.assert_not_awaited()
    assert result.stats.official_collected == 0


@pytest.mark.asyncio
async def test_task_level_enable_overrides_global_disable():
    """全局 auto_collect_official=False，任务级 auto_collect_official=True → 触发采集

    场景：全局默认关闭自动官方采集（避免所有任务都触发），
    某个高价值任务单独开启采集做深度验证。
    断言该任务的 official_collect_fn 被调用。
    """
    collect_fn = AsyncMock(return_value={"ok": True})
    worker = build_worker(item_count=1, official_collect_fn=collect_fn)
    # 任务级覆盖：开启自动官方采集
    worker.task.eval_config = {"auto_collect_official": True}
    # 全局配置：关闭自动官方采集
    with patch_eval_config(make_eval_config(auto_collect_official=False, auto_collect_max_per_run=3)):
        result = await worker.run_once()
    collect_fn.assert_awaited_once_with("i0", "t1")
    assert result.stats.official_collected == 1


@pytest.mark.asyncio
async def test_task_level_max_per_run_overrides_global():
    """全局 auto_collect_max_per_run=3，任务级 auto_collect_max_per_run=10 → 采集 10 个

    场景：全局限制每轮采集 3 条避免反爬，
    某个低频任务（如每天一次）放宽到 10 条做深度扫描。
    提供 10 个商品，断言全部触发采集（若沿用全局 3 则只会采集 3 个）。
    """
    collect_fn = AsyncMock(return_value={"ok": True})
    worker = build_worker(item_count=10, official_collect_fn=collect_fn)
    # 任务级覆盖：放宽到 10 条
    worker.task.eval_config = {"auto_collect_max_per_run": 10}
    # 全局配置：限制 3 条
    with patch_eval_config(make_eval_config(auto_collect_official=True, auto_collect_max_per_run=3)):
        result = await worker.run_once()
    # 任务级 max=10 覆盖全局 3，10 个商品全部触发采集
    assert collect_fn.await_count == 10
    assert result.stats.official_collected == 10
    # 验证所有商品都被采集，无遗漏
    called_ids = [call.args[0] for call in collect_fn.await_args_list]
    assert called_ids == [f"i{i}" for i in range(10)]


@pytest.mark.asyncio
async def test_task_level_max_per_run_shrinks_global():
    """全局 auto_collect_max_per_run=10，任务级 auto_collect_max_per_run=2 → 只采集 2 个

    场景：全局放宽到 10 条，某个高频任务为避免反爬收紧到 2 条。
    提供 5 个商品，断言只采集前 2 个，验证任务级覆盖可双向生效（放大或缩小）。
    """
    collect_fn = AsyncMock(return_value={"ok": True})
    worker = build_worker(item_count=5, official_collect_fn=collect_fn)
    # 任务级覆盖：收紧到 2 条
    worker.task.eval_config = {"auto_collect_max_per_run": 2}
    # 全局配置：放宽到 10 条
    with patch_eval_config(make_eval_config(auto_collect_official=True, auto_collect_max_per_run=10)):
        result = await worker.run_once()
    # 任务级 max=2 覆盖全局 10，只采集前 2 个
    assert collect_fn.await_count == 2
    assert result.stats.official_collected == 2
    called_ids = [call.args[0] for call in collect_fn.await_args_list]
    assert called_ids == ["i0", "i1"]


@pytest.mark.asyncio
async def test_no_override_falls_back_to_global():
    """task.eval_config=None → 完全沿用全局配置（回归测试）

    确保新增 eval_config 字段后，未设置覆盖的任务行为与之前一致：
    全局 auto_collect_official=True / max=2，5 个商品 → 只采集 2 个。
    """
    collect_fn = AsyncMock(return_value={"ok": True})
    worker = build_worker(item_count=5, official_collect_fn=collect_fn)
    # 不设置 task.eval_config（默认 None）
    with patch_eval_config(make_eval_config(auto_collect_official=True, auto_collect_max_per_run=2)):
        result = await worker.run_once()
    assert collect_fn.await_count == 2
    assert result.stats.official_collected == 2
