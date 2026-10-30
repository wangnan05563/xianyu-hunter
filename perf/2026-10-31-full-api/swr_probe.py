"""stale_while_revalidate 行为取证（只读探针，不落库、不发请求）

问题：`_maybe_refresh_stale` 的 docstring 说「启动守护线程异步刷新」，但函数体是
直接 `func(*args, **kwargs)` —— 于是「过期立即返回旧值」这条快路径，实际是
先在同一请求线程里跑完整重算，再返回旧值。

探针量两个可观测后果：
  A) 同步 + SWR：过期后的那次调用，墙钟耗时 ≈ 重算耗时（而不是 ≈ 0）；
  B) 异步 + SWR：`asyncio.run()` 在已运行的事件循环里必然 RuntimeError，被
     `except Exception: pass` 吞掉 → 缓存永不刷新 → 之后每次调用都返回同一个旧值。
"""
import asyncio
import sys
import time

sys.path.insert(0, "backend")
from xianyu_hunter.web import cache as C  # noqa: E402
from xianyu_hunter.web.cache import cached_ttl  # noqa: E402


def reset():
    with C._cache_lock:
        C._cache_store.clear()
        C._flights.clear()
        C._flights_async.clear()
        C._refreshing.clear()


RECALC_SEC = 0.6

# ---------- A) 同步 + SWR ----------
sync_calls = []


@cached_ttl(1, key_fn=lambda: "probe:swr:sync", stale_while_revalidate=True)
def sync_heavy() -> int:
    sync_calls.append(1)
    time.sleep(RECALC_SEC)
    return len(sync_calls)


reset()
t0 = time.perf_counter()
first = sync_heavy()            # 冷路径：必然重算
cold = time.perf_counter() - t0
time.sleep(1.1)                 # 跨过 TTL，进入「stale 立即返回 + 后台刷新」分支
t0 = time.perf_counter()
second = sync_heavy()           # 期望：≈0（立即返回旧值），实际：?
warm_expired = time.perf_counter() - t0
t0 = time.perf_counter()
third = sync_heavy()            # 缓存已被上面的刷新写新 → 应 ≈0
after = time.perf_counter() - t0

print("A) 同步 + stale_while_revalidate")
print(f"   冷路径耗时        {cold:.3f}s  返回 {first}")
print(f"   过期后首次调用    {warm_expired:.3f}s  返回 {second}   "
      f"（docstring 承诺 ≈0，因为刷新该在后台）")
print(f"   再调用一次        {after:.3f}s  返回 {third}   （此时才吃到刷新后的值）")
print(f"   底层重算次数      {len(sync_calls)}")
print(f"   判定：过期请求被重算阻塞 = {warm_expired > RECALC_SEC * 0.8}")

# ---------- B) 异步 + SWR ----------
async_calls = []


@cached_ttl(1, key_fn=lambda: "probe:swr:async", stale_while_revalidate=True)
async def async_heavy() -> int:
    async_calls.append(1)
    await asyncio.sleep(0.01)
    return len(async_calls)


async def scenario_b():
    reset()
    v1 = await async_heavy()            # 冷路径
    await asyncio.sleep(1.1)            # 过期
    vals = [await async_heavy() for _ in range(6)]   # 每次都应触发「后台刷新」
    return v1, vals


v1, vals = asyncio.run(scenario_b())
print("\nB) 异步 + stale_while_revalidate（当前无此类端点，属潜在坑）")
print(f"   冷路径返回        {v1}")
print(f"   过期后连续 6 次    {vals}")
print(f"   底层重算次数      {len(async_calls)}")
print(f"   判定：值被冻结（永不刷新）= {vals == [v1] * len(vals) and len(async_calls) == 1}")
