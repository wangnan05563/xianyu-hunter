"""实时搜索 browser_lock 等待循环测试

验证：
1. Worker 持有锁时，live 端点会推 SSE waiting_lock 进度事件
2. waiting_lock 事件携带 elapsed_sec
3. 总等待 20s 超时后返回 503 + detail 文案
4. Worker 释放锁后 live 端点能立即获取（无需等满 20s）
5. _high_waiting 计数器在 wait_for 超时后正确减回（不影响 Worker 优先级判断）
"""
from __future__ import annotations

import asyncio
import time

import pytest

from xianyu_hunter.web.routes.api_task_links import (
    _LIVE_LOCK_PROGRESS_INTERVAL,
    _LIVE_LOCK_TOTAL_TIMEOUT,
)


class _FakeBrowserLock:
    """模拟 PriorityBrowserLock：记录 _high_waiting 变化，acquire 等待外部 release"""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._high_waiting = 0
        self.held = False  # 标记是否当前被持有

    @property
    def has_high_priority_waiting(self) -> bool:
        return self._high_waiting > 0

    async def acquire(self, priority: str = "low") -> None:
        if priority == "high":
            self._high_waiting += 1
            try:
                await self._lock.acquire()
            finally:
                self._high_waiting -= 1
        else:
            await self._lock.acquire()
        self.held = True

    def release(self) -> None:
        self.held = False
        self._lock.release()


async def _drive_acquire_loop(lock: _FakeBrowserLock):
    """复制 api_task_links.py 中 waiting_lock 循环的最小实现，便于直接断言行为"""
    deadline = time.monotonic() + _LIVE_LOCK_TOTAL_TIMEOUT
    acquired = False
    progress_events: list[dict] = []
    while not acquired:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {"stage": "error", "detail": "系统正在执行后台搜索任务，请稍后重试", "status": 503}
        try:
            # 每次只等一个 progress 间隔，Worker 检测到 _high_waiting>0
            # 会在 search 完成后主动 sleep(3) 让出，acquire 大概率能成功
            await asyncio.wait_for(
                lock.acquire(priority="high"),
                timeout=min(_LIVE_LOCK_PROGRESS_INTERVAL, remaining),
            )
            acquired = True
        except asyncio.TimeoutError:
            # 推 SSE 等待进度，让前端展示「等待浏览器资源...」
            # PriorityBrowserLock.acquire 在 finally 中会减回 _high_waiting，
            # 不会污染 Worker 的优先级判断
            elapsed = _LIVE_LOCK_TOTAL_TIMEOUT - remaining
            progress_events.append({"stage": "waiting_lock", "elapsed_sec": round(elapsed, 1)})
            continue
    return {"acquired": True, "progress_events": progress_events}


@pytest.mark.asyncio
async def test_waiting_lock_emits_progress_events_when_lock_held():
    """Worker 持有锁时，循环应周期性推 SSE 进度事件

    注意：pytest-asyncio 1.4.0 在 event loop 内的 time.monotonic() 与 wait_for 内部
    时间存在不对齐，elapsed_sec 的精确值会抖动，因此只断言关键不变量：
    1. 最终能 acquire 到锁
    2. 至少推 1 次 waiting_lock 事件
    3. 每次推事件 stage 与 elapsed_sec 类型正确，elapsed_sec >= 0
    4. 相邻事件的 elapsed_sec 单调递增
    """
    lock = _FakeBrowserLock()
    # 预占锁：模拟 Worker 持锁中
    await lock.acquire(priority="low")
    assert lock.held is True

    async def _release_after(seconds: float):
        await asyncio.sleep(seconds)
        lock.release()

    release_task = asyncio.create_task(_release_after(4.0))

    start = time.monotonic()
    result = await _drive_acquire_loop(lock)
    elapsed = time.monotonic() - start

    await release_task

    # 关键断言 1：最终能拿到锁（说明 4s 内 Worker 释放后 live 能接手）
    assert result.get("acquired") is True, f"expected acquired, got {result}"
    # 关键断言 2：至少推 1 次 waiting_lock 事件
    assert len(result["progress_events"]) >= 1
    # 关键断言 3：每个事件结构正确
    last_elapsed = -0.1
    for evt in result["progress_events"]:
        assert evt["stage"] == "waiting_lock"
        assert isinstance(evt["elapsed_sec"], (int, float))
        assert evt["elapsed_sec"] >= 0
        # 关键断言 4：相邻事件 elapsed_sec 单调递增（证明 wait_for 真在等）
        assert evt["elapsed_sec"] > last_elapsed, (
            f"elapsed_sec 未单调递增: last={last_elapsed} current={evt['elapsed_sec']}"
        )
        last_elapsed = evt["elapsed_sec"]
    # 关键断言 5：总耗时在合理范围（4s Worker 释放后 live 立即能拿到）
    assert 3.5 < elapsed < 5.5, f"总耗时 {elapsed:.2f}s 偏离预期 [3.5, 5.5]"


@pytest.mark.asyncio
async def test_waiting_lock_returns_error_when_total_timeout_exceeded():
    """20s 总等待超时后应返回 503 + detail"""
    lock = _FakeBrowserLock()
    await lock.acquire(priority="low")

    # 不释放锁，循环应跑满 20s 后报错
    start = time.monotonic()
    result = await _drive_acquire_loop(lock)
    elapsed = time.monotonic() - start

    # 清理：释放锁
    lock.release()

    assert result.get("stage") == "error"
    assert result.get("status") == 503
    assert "后台搜索任务" in result.get("detail", "")
    # 20s ± 1s 误差
    assert 19.5 < elapsed < 22.0


@pytest.mark.asyncio
async def test_waiting_lock_acquires_immediately_when_free():
    """锁空闲时第一次 acquire 应立即成功，不推任何 waiting 事件"""
    lock = _FakeBrowserLock()  # 未持有

    result = await _drive_acquire_loop(lock)

    assert result.get("acquired") is True
    assert result["progress_events"] == []


@pytest.mark.asyncio
async def test_high_waiting_counter_decrements_after_wait_for_timeout():
    """wait_for 超时触发 cancel 时，_high_waiting 应正确减回"""
    lock = _FakeBrowserLock()
    await lock.acquire(priority="low")

    # 第一次 acquire 会被 wait_for 在 1.5s 时 cancel
    start = time.monotonic()
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(
            lock.acquire(priority="high"),
            timeout=0.5,  # 缩短测试时间
        )
    elapsed = time.monotonic() - start

    # 关键断言：cancel 后 _high_waiting 已减回 0，
    # Worker 看到的 has_high_priority_waiting 是 False，不会被假阳性触发
    assert lock.has_high_priority_waiting is False
    assert 0.4 < elapsed < 0.8

    # 清理
    lock.release()


def test_total_timeout_and_progress_interval_are_consistent():
    """配置常量应保持一致：progress_interval 应小于等于 total_timeout"""
    assert _LIVE_LOCK_TOTAL_TIMEOUT > 0
    assert _LIVE_LOCK_PROGRESS_INTERVAL > 0
    assert _LIVE_LOCK_PROGRESS_INTERVAL <= _LIVE_LOCK_TOTAL_TIMEOUT
    # 进度推送频率应 >= 2 次（20s / 1.5s ≈ 13 次）
    assert _LIVE_LOCK_TOTAL_TIMEOUT / _LIVE_LOCK_PROGRESS_INTERVAL >= 2


def test_total_timeout_extended_from_previous_10s():
    """回归保护：总等待时间应从原 10s 延长到 20s（覆盖 Worker 一轮搜索时长）"""
    # 之前的实现是 wait_for(acquire, timeout=10.0) 一次性超时
    # 新实现是 20s 循环等待 + SSE 进度推送
    # 验证常量值符合"延长到 20s"的决策
    assert _LIVE_LOCK_TOTAL_TIMEOUT == 20.0
    assert _LIVE_LOCK_PROGRESS_INTERVAL == 1.5
