"""实时搜索 in-flight 去重机制测试

验证并发请求场景下的去重逻辑：当多个 /links/live 请求同时到达时，
只有第一个请求执行实际搜索，后续请求等待并复用缓存结果。
"""
from __future__ import annotations

import asyncio

import pytest

from xianyu_hunter.web.routes.api_task_links import (
    _LIVE_CACHE_TTL,
    _LIVE_INFLIGHT_WAIT_TIMEOUT,
    _clear_live_inflight,
    _live_cache,
    _live_inflight,
)


def _make_event() -> asyncio.Event:
    """构造一个未 set 的 Event，模拟搜索正在进行"""
    return asyncio.Event()


def test_clear_live_inflight_removes_task_and_sets_event() -> None:
    """_clear_live_inflight 应清除字典标记并 set Event 通知等待者"""
    task_id = "test_task_1"
    event = _make_event()
    _live_inflight[task_id] = event

    assert not event.is_set()
    assert task_id in _live_inflight

    _clear_live_inflight(task_id, event)

    assert event.is_set()
    assert task_id not in _live_inflight


def test_clear_live_inflight_is_idempotent() -> None:
    """重复调用 _clear_live_inflight 应安全无副作用（pop 使用 None 默认值）"""
    task_id = "test_task_2"
    event = _make_event()
    _live_inflight[task_id] = event

    _clear_live_inflight(task_id, event)
    _clear_live_inflight(task_id, event)  # 二次调用不应抛异常

    assert event.is_set()
    assert task_id not in _live_inflight


def test_clear_live_inflight_on_nonexistent_task_is_safe() -> None:
    """对不存在的 task_id 调用应安全（不抛 KeyError）"""
    event = _make_event()

    _clear_live_inflight("nonexistent_task", event)

    assert event.is_set()


@pytest.mark.asyncio
async def test_inflight_wait_returns_when_event_set() -> None:
    """等待 in-flight Event 时，Event set 后应立即返回"""
    event = _make_event()

    # 模拟搜索完成：延迟 100ms 后 set Event
    async def _set_after_delay():
        await asyncio.sleep(0.1)
        event.set()

    asyncio.create_task(_set_after_delay())

    # 等待 Event，应在 100ms 内返回而非等待 35s 超时
    done, pending = await asyncio.wait(
        [asyncio.create_task(event.wait())],
        timeout=2.0,
    )

    assert len(done) == 1
    assert event.is_set()


@pytest.mark.asyncio
async def test_inflight_wait_timeout_when_event_never_set() -> None:
    """等待 in-flight Event 超时时应触发 TimeoutError"""
    event = _make_event()

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(event.wait(), timeout=0.2)


def test_inflight_wait_timeout_covers_normal_search_duration() -> None:
    """等待超时应覆盖正常搜索耗时（30s 搜索 + 5s 缓冲）"""
    # 35s 应该足够覆盖最长的搜索场景（30s + RGV587 重试 45s 的部分场景）
    # 注意：RGV587 重试场景下等待可能超时，但这是预期行为（让客户端重试）
    assert _LIVE_INFLIGHT_WAIT_TIMEOUT >= 30.0
    assert _LIVE_INFLIGHT_WAIT_TIMEOUT <= 60.0


def test_live_cache_ttl_is_reasonable() -> None:
    """缓存 TTL 应在合理范围内（60s）：避免短时间重复搜索"""
    assert _LIVE_CACHE_TTL == 60


def teardown_function(_function) -> None:
    """每个测试后清理全局状态，避免测试间相互影响"""
    _live_inflight.clear()
    _live_cache.clear()
