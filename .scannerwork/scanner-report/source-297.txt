"""batch_refresh_scheduler 模块单元测试

覆盖：
- 调度器启动/停止（含幂等性）
- 批量采集逻辑（成功/跳过/已售标记）
- 失败重试与熔断（连续失败超阈值暂停当前批次）
- 变更日志记录（字段差异比较 + 内存上限）
- 配置热更新
- 手动触发（冲突检测）
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xianyu_hunter.domain.item import ItemDetail
from xianyu_hunter.infra.yaml_config import BatchRefreshConfig
from xianyu_hunter.modules.batch_refresh_scheduler import (
    BatchRefreshScheduler,
    _MAX_CHANGE_LOG,
)


def _make_config(**kwargs) -> BatchRefreshConfig:
    return BatchRefreshConfig(**kwargs)


def _make_detail(
    item_id: str = "i1",
    *,
    is_sold: bool = False,
    price: float = 100.0,
    title: str | None = None,
) -> ItemDetail:
    """构造测试用 ItemDetail"""
    return ItemDetail(
        id=item_id,
        title=title if title is not None else f"商品{item_id}",
        price=price,
        is_sold=is_sold,
    )


def _make_container(
    items: list[dict] | None = None,
    detail_map: dict | None = None,
) -> MagicMock:
    """创建 mock container

    Args:
        items: list_unsold_items 返回的商品列表
        detail_map: {item_id: ItemDetail | None | Exception} 控制每个商品的采集结果
    """
    container = MagicMock()
    container.repo = MagicMock()
    container.collector = MagicMock()

    container.repo.list_unsold_items.return_value = items or []
    # sync_item_display_from_detail 会调用 list_link_displays_by_keys，
    # 默认返回空 dict 避免 MagicMock.get() 返回非 dict 导致合并逻辑出错
    container.repo.list_link_displays_by_keys.return_value = {}

    async def _detail(item_id: str):
        if detail_map and item_id in detail_map:
            result = detail_map[item_id]
            if isinstance(result, Exception):
                raise result
            return result
        return None

    container.collector.detail = _detail
    return container


@pytest.fixture(autouse=True)
def _mock_cookie_sync():
    """屏蔽批量采集前的 Cookie 同步（避免访问真实 cookie_store）"""
    with patch(
        "xianyu_hunter.web.services.cookie_runtime_sync.inject_cookie_store_to_worker_browser",
        new=AsyncMock(),
    ):
        yield


# ========== 启动/停止测试 ==========


def test_start_stop() -> None:
    """调度器能正常启动和停止"""
    container = _make_container()
    scheduler = BatchRefreshScheduler(container, _make_config(interval_minutes=1))

    loop = asyncio.new_event_loop()
    scheduler.start(loop)
    assert scheduler._scheduler is not None
    assert scheduler._main_loop is loop

    scheduler.stop()
    assert scheduler._scheduler is None
    assert scheduler._main_loop is None
    loop.close()


def test_start_idempotent() -> None:
    """重复调用 start 不会创建多个调度器"""
    container = _make_container()
    scheduler = BatchRefreshScheduler(container, _make_config())

    loop = asyncio.new_event_loop()
    scheduler.start(loop)
    first = scheduler._scheduler
    scheduler.start(loop)
    assert scheduler._scheduler is first
    scheduler.stop()
    loop.close()


def test_stop_when_not_started() -> None:
    """未启动时 stop 不抛异常"""
    container = _make_container()
    scheduler = BatchRefreshScheduler(container, _make_config())
    scheduler.stop()  # 不应抛异常


# ========== 批量采集逻辑测试 ==========


async def test_batch_refresh_success() -> None:
    """成功采集多个商品"""
    items = [
        {"id": "i1", "task_id": "t1", "title": "old1", "price": 50, "is_sold": 0},
        {"id": "i2", "task_id": "t1", "title": "old2", "price": 60, "is_sold": 0},
    ]
    detail_map = {
        "i1": _make_detail("i1", price=100),
        "i2": _make_detail("i2", price=200),
    }
    container = _make_container(items=items, detail_map=detail_map)
    scheduler = BatchRefreshScheduler(container, _make_config())

    await scheduler._run_batch_async(task_id=1)

    assert scheduler._last_result == {"success": 2, "failed": 0, "skipped": 0, "stopped": False}
    assert scheduler._last_run_at is not None
    assert scheduler.is_running() is False
    # upsert_item 被调用 2 次
    assert container.repo.upsert_item.call_count == 2


async def test_batch_refresh_detail_none_skipped() -> None:
    """detail 返回 None 时记为 skipped"""
    items = [{"id": "i1", "task_id": "t1", "title": "old", "price": 50, "is_sold": 0}]
    detail_map = {"i1": None}
    container = _make_container(items=items, detail_map=detail_map)
    scheduler = BatchRefreshScheduler(container, _make_config())

    await scheduler._run_batch_async(task_id=1)

    assert scheduler._last_result == {"success": 0, "failed": 0, "skipped": 1, "stopped": False}
    # 不应写库
    container.repo.upsert_item.assert_not_called()


async def test_batch_refresh_mark_sold() -> None:
    """采集到已售商品时调用 mark_sold"""
    items = [{"id": "i1", "task_id": "t1", "title": "old", "price": 50, "is_sold": 0}]
    detail_map = {"i1": _make_detail("i1", is_sold=True)}
    container = _make_container(items=items, detail_map=detail_map)
    scheduler = BatchRefreshScheduler(container, _make_config())

    await scheduler._run_batch_async(task_id=1)

    assert scheduler._last_result == {"success": 1, "failed": 0, "skipped": 0, "stopped": False}
    container.repo.mark_sold.assert_called_once_with("i1")


async def test_batch_refresh_failure_records_and_continues() -> None:
    """单个商品失败时记录并继续下一个"""
    items = [
        {"id": "i1", "task_id": "t1", "title": "old1", "price": 50, "is_sold": 0},
        {"id": "i2", "task_id": "t1", "title": "old2", "price": 60, "is_sold": 0},
    ]
    detail_map = {
        "i1": RuntimeError("network error"),
        "i2": _make_detail("i2", price=100),
    }
    container = _make_container(items=items, detail_map=detail_map)
    scheduler = BatchRefreshScheduler(container, _make_config(), fail_pause_threshold=3)

    await scheduler._run_batch_async(task_id=1)

    # i1 失败，i2 成功
    assert scheduler._last_result == {"success": 1, "failed": 1, "skipped": 0, "stopped": False}


async def test_batch_refresh_circuit_breaker() -> None:
    """连续失败超过阈值时暂停当前批次，剩余商品记为 skipped"""
    items = [
        {"id": f"i{n}", "task_id": "t1", "title": f"old{n}", "price": 50, "is_sold": 0}
        for n in range(5)
    ]
    # 所有商品都失败
    detail_map = {f"i{n}": RuntimeError("browser crash") for n in range(5)}
    container = _make_container(items=items, detail_map=detail_map)
    scheduler = BatchRefreshScheduler(container, _make_config(), fail_pause_threshold=3)

    await scheduler._run_batch_async(task_id=1)

    # 连续失败 3 次后暂停，剩余 2 个记为 skipped
    assert scheduler._last_result == {"success": 0, "failed": 3, "skipped": 2, "stopped": False}


async def test_batch_refresh_failure_reset_on_success() -> None:
    """成功后连续失败计数归零（避免偶发失败累积误触发熔断）"""
    items = [
        {"id": "i1", "task_id": "t1", "title": "old1", "price": 50, "is_sold": 0},
        {"id": "i2", "task_id": "t1", "title": "old2", "price": 60, "is_sold": 0},
        {"id": "i3", "task_id": "t1", "title": "old3", "price": 70, "is_sold": 0},
        {"id": "i4", "task_id": "t1", "title": "old4", "price": 80, "is_sold": 0},
    ]
    detail_map = {
        "i1": RuntimeError("fail"),  # 失败 1
        "i2": _make_detail("i2"),     # 成功，计数归零
        "i3": RuntimeError("fail"),  # 失败 1
        "i4": _make_detail("i4"),     # 成功
    }
    container = _make_container(items=items, detail_map=detail_map)
    scheduler = BatchRefreshScheduler(container, _make_config(), fail_pause_threshold=3)

    await scheduler._run_batch_async(task_id=1)

    # 不会触发熔断，全部处理完
    assert scheduler._last_result == {"success": 2, "failed": 2, "skipped": 0, "stopped": False}


async def test_batch_refresh_skips_when_running() -> None:
    """已有批次在运行时跳过新批次"""
    container = _make_container()
    scheduler = BatchRefreshScheduler(container, _make_config())
    scheduler._status = "running"

    await scheduler._run_batch_async(task_id=1)

    # 不应查询商品
    container.repo.list_unsold_items.assert_not_called()
    assert scheduler._last_result is None


async def test_batch_refresh_empty_items() -> None:
    """无在售商品时正常完成（success=0）"""
    container = _make_container(items=[])
    scheduler = BatchRefreshScheduler(container, _make_config())

    await scheduler._run_batch_async(task_id=1)

    assert scheduler._last_result == {"success": 0, "failed": 0, "skipped": 0, "stopped": False}
    assert scheduler._last_run_at is not None


async def test_batch_refresh_max_items_per_run() -> None:
    """max_items_per_run 限制单次运行的商品数"""
    items = [
        {"id": f"i{n}", "task_id": "t1", "title": f"old{n}", "price": 50, "is_sold": 0}
        for n in range(10)
    ]
    detail_map = {f"i{n}": _make_detail(f"i{n}") for n in range(10)}
    container = _make_container(items=items[:3], detail_map=detail_map)  # repo 只返回前 3 个
    scheduler = BatchRefreshScheduler(container, _make_config(max_items_per_run=3))

    await scheduler._run_batch_async(task_id=1)

    # 验证 list_unsold_items 用 max_items_per_run 作为 limit
    container.repo.list_unsold_items.assert_called_once_with(limit=3)
    assert scheduler._last_result == {"success": 3, "failed": 0, "skipped": 0, "stopped": False}


# ========== 变更日志测试 ==========


async def test_change_log_recorded() -> None:
    """字段变更时记录到 change_log"""
    items = [{"id": "i1", "task_id": "t1", "title": "old", "price": 50, "is_sold": 0}]
    detail_map = {"i1": _make_detail("i1", price=100, title="new")}
    container = _make_container(items=items, detail_map=detail_map)
    scheduler = BatchRefreshScheduler(container, _make_config())

    await scheduler._run_batch_async(task_id=1)

    assert len(scheduler._change_log) == 1
    entry = scheduler._change_log[0]
    assert entry["item_id"] == "i1"
    assert "title" in entry["changed_fields"]
    assert "price" in entry["changed_fields"]
    assert "timestamp" in entry


async def test_change_log_not_recorded_when_no_change() -> None:
    """无字段变更时不记录日志"""
    items = [{
        "id": "i1", "task_id": "t1", "title": "same", "price": 100, "is_sold": 0,
        "seller_id": "", "region": "", "want_cnt": 0, "view_cnt": 0, "thumb_url": "",
    }]
    detail_map = {"i1": _make_detail("i1", price=100, title="same")}
    container = _make_container(items=items, detail_map=detail_map)
    scheduler = BatchRefreshScheduler(container, _make_config())

    await scheduler._run_batch_async(task_id=1)

    assert len(scheduler._change_log) == 0
    assert scheduler._last_result == {"success": 1, "failed": 0, "skipped": 0, "stopped": False}


def test_diff_fields_detects_changes() -> None:
    """_diff_fields 正确识别变更字段"""
    existing = {
        "title": "old", "price": 50, "seller_id": "s1", "region": "北京",
        "want_cnt": 5, "view_cnt": 10, "thumb_url": "url1", "is_sold": 0,
    }
    new_row = {
        "title": "new", "price": 100, "seller_id": "s1", "region": "北京",
        "want_cnt": 5, "view_cnt": 20, "thumb_url": "url1", "is_sold": 0,
    }
    scheduler = BatchRefreshScheduler(MagicMock(), _make_config())
    changed = scheduler._diff_fields(existing, new_row)
    assert set(changed) == {"title", "price", "view_cnt"}


def test_diff_fields_none_vs_empty() -> None:
    """None 与空字符串视为等价，不误报变更"""
    existing = {
        "title": None, "price": 0, "seller_id": "", "region": None,
        "want_cnt": 0, "view_cnt": 0, "thumb_url": None, "is_sold": 0,
    }
    new_row = {
        "title": "", "price": 0, "seller_id": "", "region": "",
        "want_cnt": 0, "view_cnt": 0, "thumb_url": "", "is_sold": 0,
    }
    scheduler = BatchRefreshScheduler(MagicMock(), _make_config())
    changed = scheduler._diff_fields(existing, new_row)
    assert changed == []


def test_change_log_capped() -> None:
    """变更日志超过上限时丢弃最旧的（FIFO）"""
    scheduler = BatchRefreshScheduler(MagicMock(), _make_config())
    # 写入超过上限的记录
    for i in range(_MAX_CHANGE_LOG + 100):
        scheduler._record_change(f"i{i}", ["price"])
    assert len(scheduler._change_log) == _MAX_CHANGE_LOG
    # 保留的是最新的记录（尾部）
    assert scheduler._change_log[-1]["item_id"] == f"i{_MAX_CHANGE_LOG + 99}"


# ========== 配置热更新测试 ==========


def test_update_config_interval() -> None:
    """更新 interval_minutes 后 reschedule job"""
    container = _make_container()
    config = _make_config(interval_minutes=30)
    scheduler = BatchRefreshScheduler(container, config)

    loop = asyncio.new_event_loop()
    scheduler.start(loop)
    scheduler.update_config(interval_minutes=15)
    assert config.interval_minutes == 15
    scheduler.stop()
    loop.close()


def test_update_config_enabled() -> None:
    """更新 enabled 标志"""
    container = _make_container()
    config = _make_config(enabled=True)
    scheduler = BatchRefreshScheduler(container, config)

    scheduler.update_config(enabled=False)
    assert config.enabled is False


def test_get_status() -> None:
    """get_status 返回完整状态"""
    container = _make_container()
    config = _make_config(interval_minutes=45)
    scheduler = BatchRefreshScheduler(container, config)

    status = scheduler.get_status()
    assert status["status"] == "idle"
    assert status["enabled"] is True
    assert status["interval_minutes"] == 45
    assert status["last_run_at"] is None
    assert status["last_result"] is None
    assert status["change_log"] == []


# ========== 手动触发测试 ==========


def test_trigger_now_returns_minus_one_when_no_loop() -> None:
    """未启动时触发返回 -1"""
    container = _make_container()
    scheduler = BatchRefreshScheduler(container, _make_config())
    assert scheduler.trigger_now() == -1


async def test_trigger_now_returns_minus_one_when_running() -> None:
    """正在运行时触发返回 -1"""
    container = _make_container()
    scheduler = BatchRefreshScheduler(container, _make_config())
    scheduler._status = "running"
    assert scheduler.trigger_now() == -1


# ========== 状态转换测试 ==========


async def test_status_transitions_to_idle_on_exception() -> None:
    """批量采集异常时 status 恢复为 idle（避免锁死）"""
    container = _make_container()
    # list_unsold_items 抛异常
    container.repo.list_unsold_items.side_effect = RuntimeError("db error")
    scheduler = BatchRefreshScheduler(container, _make_config())

    with pytest.raises(RuntimeError):
        await scheduler._run_batch_async(task_id=1)

    # finally 块应恢复 status
    assert scheduler.is_running() is False
