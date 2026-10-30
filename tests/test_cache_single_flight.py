"""缓存击穿合并（single-flight）回归测试 —— 对应性能测试报告 OPTIMIZATIONS B1

背景：JMeter 压测显示 12 并发恒定负载下整体均值 200 ms，而单用户仅 50 ms；
根因是 `web/cache.py` 的 miss 路径没有合并 —— TTL 到期瞬间 N 个并发请求各自
重算同一个聚合（`stats_overview` / `kpi` / `trend` 这类全表扫）。

这里锁定的不是「快」，而是「同 key 并发只重算一次」这一条语义，以及它不能破坏的
三件事：不同 key 不互相合并、异常不被缓存、bypass_cache 仍然强制重算。
"""
from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

import pytest

from xianyu_hunter.web import cache as cache_mod
from xianyu_hunter.web.cache import cached_ttl


@pytest.fixture(autouse=True)
def _clean_cache_state():
    """每个用例前后把全局缓存与在途表清空，避免用例间串味。"""
    def _reset():
        with cache_mod._cache_lock:
            cache_mod._cache_store.clear()
            cache_mod._flights.clear()
            cache_mod._flights_async.clear()
            cache_mod._refreshing.clear()
    _reset()
    yield
    _reset()


def test_sync_concurrent_miss_computes_once():
    runs: list[str] = []

    @cached_ttl(60, key_fn=lambda tag: "sf:same-key")
    def heavy(tag: str) -> str:
        runs.append(tag)
        time.sleep(0.05)             # 拉长临界区，给跟随者排队的时间
        return f"value-for-{tag}"

    results: list[str] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def call():
        try:
            value = heavy("a")
        except BaseException as exc:  # noqa: BLE001 - 汇集给主线程断言
            with lock:
                errors.append(exc)
            return
        with lock:
            results.append(value)

    threads = [threading.Thread(target=call) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, errors
    assert runs == ["a"], f"同 key 并发 miss 应只重算一次，实际重算 {runs}"
    assert results == ["value-for-a"] * 8
    assert not cache_mod._flights, "在途表必须被清空，否则后续请求会等一个已死的 flight"


def test_sync_different_keys_are_not_merged():
    runs: list[str] = []

    @cached_ttl(60, key_fn=lambda tag: f"sf:{tag}")
    def heavy(tag: str) -> str:
        runs.append(tag)
        time.sleep(0.05)
        return f"value-for-{tag}"

    results: dict[str, str] = {}
    lock = threading.Lock()

    def call(tag: str):
        value = heavy(tag)
        with lock:
            results[tag] = value

    threads = [threading.Thread(target=call, args=(tag,)) for tag in ("x", "y", "z")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert sorted(runs) == ["x", "y", "z"], "不同 key 不能互相合并"
    assert results == {"x": "value-for-x", "y": "value-for-y", "z": "value-for-z"}


def test_sync_exception_propagates_and_is_not_cached():
    calls: list[int] = []

    @cached_ttl(60, key_fn=lambda: "sf:boom")
    def always_fails() -> None:
        calls.append(1)
        raise ValueError("重算失败")

    with pytest.raises(ValueError):
        always_fails()

    # 异常没有被写进缓存：下一次调用仍然会真正重算
    with pytest.raises(ValueError):
        always_fails()
    assert len(calls) == 2
    assert not cache_mod._cache_store, "错误结果不得入缓存"
    assert not cache_mod._flights


def test_sync_followers_receive_leaders_exception():
    started = threading.Event()
    release = threading.Event()

    @cached_ttl(60, key_fn=lambda: "sf:shared-error")
    def slow_fail() -> None:
        started.set()
        release.wait(timeout=5)
        raise RuntimeError("上游挂了")

    seen: list[BaseException] = []
    lock = threading.Lock()

    def call():
        try:
            slow_fail()
        except BaseException as exc:  # noqa: BLE001
            with lock:
                seen.append(exc)

    leader = threading.Thread(target=call)
    leader.start()
    assert started.wait(timeout=5)
    follower = threading.Thread(target=call)
    follower.start()
    time.sleep(0.1)          # 确认跟随者停在等待处，而不是各自重算
    release.set()
    for t in (leader, follower):
        t.join(timeout=10)

    assert len(seen) == 2
    assert all(isinstance(exc, RuntimeError) for exc in seen)
    assert not cache_mod._flights


def test_sync_refills_after_ttl_expiry():
    runs: list[int] = []

    @cached_ttl(1, key_fn=lambda: "sf:ttl")
    def heavy() -> int:
        runs.append(1)
        return len(runs)

    assert heavy() == 1
    assert heavy() == 1          # TTL 窗口内命中，不重算
    time.sleep(1.1)
    assert heavy() == 2          # 过期后重新重算一次


def test_bypass_cache_still_forces_recompute():
    runs: list[int] = []

    @cached_ttl(60, key_fn=lambda: "sf:bypass")
    def heavy() -> int:
        runs.append(1)
        return len(runs)

    assert heavy() == 1
    assert heavy(bypass_cache=True) == 2, "管理员强制刷新不得被单飞/缓存吸收"
    assert heavy() == 2          # 刷新结果已写回缓存


def test_async_concurrent_miss_computes_once():
    concurrency = 12
    runs: list[str] = []

    @cached_ttl(60, key_fn=lambda tag: f"sf-async:{tag}")
    async def heavy(tag: str) -> str:
        runs.append(tag)
        await asyncio.sleep(0.05)   # 让出循环，给其余任务排队的时间
        return f"value-for-{tag}"

    async def scenario() -> list[str]:
        return list(await asyncio.gather(*(heavy("a") for _ in range(concurrency))))

    values = asyncio.run(scenario())

    assert runs == ["a"], f"同 key 并发 miss 应只重算一次，实际 {runs}"
    assert values == ["value-for-a"] * concurrency
    assert not cache_mod._flights_async


def test_async_followers_receive_leaders_exception():
    @cached_ttl(60, key_fn=lambda: "sf-async:err")
    async def heavy_fail() -> None:
        await asyncio.sleep(0.02)
        raise ValueError("async 重算失败")

    async def scenario() -> list[BaseException]:
        results = await asyncio.gather(*(heavy_fail() for _ in range(4)),
                                       return_exceptions=True)
        return [r for r in results if isinstance(r, BaseException)]

    caught = asyncio.run(scenario())
    assert len(caught) == 4 and all(isinstance(exc, ValueError) for exc in caught)
    assert not cache_mod._flights_async
    assert not cache_mod._cache_store


def test_async_cross_loop_does_not_merge():
    """两个事件循环同时在途：协程不能跨循环等待，必须各算各的且都不挂死。"""
    runs: list[int] = []
    both_inside = threading.Barrier(2)
    lock = threading.Lock()

    @cached_ttl(60, key_fn=lambda: "sf-async:two-loops")
    async def heavy() -> int:
        with lock:
            runs.append(1)
            my_index = len(runs)
        both_inside.wait(timeout=5)   # 两个循环都进入 body 才放行（不合并才会发生）
        await asyncio.sleep(0.02)
        return my_index

    outcomes: list[Any] = []

    def run_in_new_loop():
        outcomes.append(asyncio.run(heavy()))

    threads = [threading.Thread(target=run_in_new_loop) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert sorted(outcomes) == [1, 2], f"跨循环应各算一次，实际结果 {outcomes}"
    assert not cache_mod._flights_async, "循环关闭后不得留下在途标记"
