"""Web 层 TTL 内存缓存工具

为什么需要：JMeter 压测显示 stats 接口在 100 并发下平均响应 >1.8s，
根因之一是每次请求都重新计算统计聚合。stats 类数据变化频率低（分钟级），
加 60s TTL 缓存可让命中率 >90% 时响应降到 <10ms。

设计要点：
- 进程内 dict + 单调时钟时间戳，无外部依赖（不引入 Redis 增加运维复杂度）
- 线程安全：FastAPI 默认同步路由用 anyio worker thread 池，dict 读写需加锁
- 主动过期：缓存项带 TTL，过期自动忽略（不主动清理，下次写入覆盖）
- 击穿合并（single-flight）：同一 key 的并发 miss 只重算一次，其余等待同一结果
- 可选跳过缓存：bypass_cache=True 强制刷新（管理员手动刷新场景）
- 同步/异步双支持：P3 改造后 stats 接口改 async def，装饰器自动识别协程函数
"""
from __future__ import annotations

import asyncio
import functools
import inspect
import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")

# 全局缓存 dict + 读写锁
# key 结构：(endpoint_name, args_tuple) → (timestamp, value)
_cache_store: dict[tuple, tuple[float, Any]] = {}
_cache_lock = threading.RLock()
# stale-while-revalidate：记录正在进行后台刷新的 key，避免重复刷新（惊群）
_refreshing: set[tuple] = set()
# 击穿合并：正在进行中的重算。同步/异步各一套——协程与 asyncio.Future 不跨事件循环，
# 线程等待用 Event，协程等待用 Future，不能共用一个等待原语。
_flights: dict[tuple, "_Flight"] = {}
# (注册时所在的事件循环, 该循环内的 Future) —— 记录循环是为了拒绝跨循环合并
_AFlight = tuple["asyncio.AbstractEventLoop", "asyncio.Future"]
_flights_async: dict[tuple, _AFlight] = {}


class _Flight:
    """一次正在进行的重算的共享结果，outcome 为 ("ok"|"err"|"gone", payload)。"""

    __slots__ = ("event", "outcome")

    def __init__(self) -> None:
        self.event = threading.Event()
        self.outcome: tuple[str, Any] | None = None


def _make_async_wrapper(func, ttl_seconds: int, key_fn, stale_while_revalidate: bool = False):
    """创建异步缓存包装器"""
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs) -> Any:
        bypass = kwargs.pop("bypass_cache", False)
        cache_key = _make_cache_key(func, key_fn, *args, **kwargs)

        if not bypass:
            hit, value = _try_get_cache(cache_key, ttl_seconds)
            if hit:
                return value
            # stale-while-revalidate：过期时立即返回旧值，后台异步刷新（避免请求被重算阻塞）
            if stale_while_revalidate:
                stale = _try_get_stale(cache_key)
                if stale is not None:
                    _maybe_refresh_stale_async(cache_key, func, args, kwargs)
                    return stale
            return await _single_flight_async(
                cache_key, lambda: func(*args, **kwargs), ttl_seconds
            )

        # 强制刷新：既不读缓存也不并入他人在途的重算，重算后写回
        result = await func(*args, **kwargs)
        _set_cache(cache_key, result)
        return result

    async_wrapper._cache_clear = lambda: _cache_store.clear()  # type: ignore[attr-defined]
    return async_wrapper


def _make_sync_wrapper(func, ttl_seconds: int, key_fn, stale_while_revalidate: bool = False):
    """创建同步缓存包装器"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> T:
        bypass = kwargs.pop("bypass_cache", False)
        cache_key = _make_cache_key(func, key_fn, *args, **kwargs)

        if not bypass:
            hit, value = _try_get_cache(cache_key, ttl_seconds)
            if hit:
                return value  # type: ignore[return-value]
            # stale-while-revalidate：过期时立即返回旧值，后台线程异步刷新（避免请求被重算阻塞）
            if stale_while_revalidate:
                stale = _try_get_stale(cache_key)
                if stale is not None:
                    _maybe_refresh_stale(cache_key, func, args, kwargs)
                    return stale
            return _single_flight(cache_key, lambda: func(*args, **kwargs), ttl_seconds)

        # 强制刷新：既不读缓存也不并入他人在途的重算，重算后写回
        result = func(*args, **kwargs)
        _set_cache(cache_key, result)
        return result

    wrapper._cache_clear = lambda: _cache_store.clear()  # type: ignore[attr-defined]
    return wrapper


def cached_ttl(
    ttl_seconds: int,
    key_fn: Callable[..., str] | None = None,
    stale_while_revalidate: bool = False,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """TTL 内存缓存装饰器（同步/异步双支持）

    stale_while_revalidate=True 时：缓存过期不阻塞请求，立即返回旧值并后台异步刷新，
    保证高延迟接口（如维护状态需扫描文件系统）在缓存窗口外也始终快速响应。
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        if inspect.iscoroutinefunction(func):
            return _make_async_wrapper(func, ttl_seconds, key_fn, stale_while_revalidate)  # type: ignore[return-value]
        return _make_sync_wrapper(func, ttl_seconds, key_fn, stale_while_revalidate)
    return decorator


def _make_cache_key(func: Callable, key_fn: Callable[..., str] | None, *args, **kwargs) -> tuple:
    """生成缓存 key（同步/异步共用）"""
    if key_fn is not None:
        return (func.__qualname__, key_fn(*args, **kwargs))
    safe_args = tuple(a for a in args if _is_hashable(a))
    safe_kwargs = tuple(sorted(
        (k, v) for k, v in kwargs.items() if _is_hashable(v)
    ))
    return (func.__qualname__, safe_args, safe_kwargs)


def _try_get_cache(cache_key: tuple, ttl_seconds: int) -> tuple[bool, Any]:
    """尝试从缓存读取，返回 (hit, value)"""
    with _cache_lock:
        cached = _cache_store.get(cache_key)
        if cached is not None:
            ts, value = cached
            if time.monotonic() - ts < ttl_seconds:
                return True, value
    return False, None


def _set_cache(cache_key: tuple, value: Any) -> None:
    """写入缓存"""
    with _cache_lock:
        _cache_store[cache_key] = (time.monotonic(), value)


def _single_flight(cache_key: tuple, compute: Callable[[], Any], ttl_seconds: int) -> Any:
    """同一 key 的并发 miss 只重算一次（缓存击穿合并，线程版）。

    抢到 lead 的调用执行 compute 并写缓存，其余调用等同一结果；lead 被中断
    （KeyboardInterrupt/SystemExit）时跟随者重新竞争，不继承其中断。
    compute 抛出的普通异常原样传给所有跟随者——不缓存错误结果，下一个请求仍是全新重算。
    """
    while True:
        with _cache_lock:
            # 锁内复查：上一个 lead 可能刚好发布完（它先写缓存、再摘掉 flight）
            hit, value = _try_get_cache(cache_key, ttl_seconds)
            if hit:
                return value
            flight = _flights.get(cache_key)
            if flight is None:
                flight = _Flight()
                _flights[cache_key] = flight
                leading = True
            else:
                leading = False

        if not leading:
            flight.event.wait()
            kind, payload = flight.outcome or ("gone", None)
            if kind == "ok":
                return payload
            if kind == "err":
                raise payload
            continue

        try:
            result = compute()
        except (KeyboardInterrupt, SystemExit):
            _end_flight(cache_key, flight, ("gone", None))
            raise
        except BaseException as exc:
            _end_flight(cache_key, flight, ("err", exc))
            raise
        _set_cache(cache_key, result)
        _end_flight(cache_key, flight, ("ok", result))
        return result


async def _single_flight_async(
    cache_key: tuple, coro_factory: Callable[[], Any], ttl_seconds: int
) -> Any:
    """同一 key 的并发 miss 只重算一次（缓存击穿合并，协程版）。

    结果经 Future 以 ("ok"|"err"|"gone", payload) 载荷传递而非 set_exception：
    无人取用的 Future 异常会打「exception was never retrieved」日志，且跟随者
    不该继承 lead 的取消。lead 与跟随者必须在同一事件循环，否则不合并、各自重算。
    """
    loop = asyncio.get_running_loop()
    while True:
        with _cache_lock:
            hit, value = _try_get_cache(cache_key, ttl_seconds)
            if hit:
                return value
            flight = _flights_async.get(cache_key)
            if flight is not None and flight[0] is loop:
                leading = False
            else:
                flight = (loop, loop.create_future())
                _flights_async[cache_key] = flight
                leading = True

        if not leading:
            kind, payload = await flight[1]
            if kind == "ok":
                return payload
            if kind == "err":
                raise payload
            continue

        try:
            result = await coro_factory()
        except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
            _end_async_flight(cache_key, flight, ("gone", None))
            raise
        except BaseException as exc:
            _end_async_flight(cache_key, flight, ("err", exc))
            raise
        _set_cache(cache_key, result)
        _end_async_flight(cache_key, flight, ("ok", result))
        return result


def _end_flight(cache_key: tuple, flight: _Flight, outcome: tuple[str, Any]) -> None:
    """先摘走在途标记（新到达者据此改走缓存命中），再唤醒等待同一结果的调用。"""
    with _cache_lock:
        if _flights.get(cache_key) is flight:
            _flights.pop(cache_key, None)
    flight.outcome = outcome
    flight.event.set()


def _end_async_flight(cache_key: tuple, flight: _AFlight, outcome: tuple[str, Any]) -> None:
    with _cache_lock:
        if _flights_async.get(cache_key) is flight:
            _flights_async.pop(cache_key, None)
    if not flight[1].done():
        flight[1].set_result(outcome)


def _try_get_stale(cache_key: tuple) -> Any | None:
    """返回缓存值（不论是否过期），无则返回 None。供 stale-while-revalidate 使用。"""
    with _cache_lock:
        cached = _cache_store.get(cache_key)
        if cached is not None:
            return cached[1]
    return None


def _maybe_refresh_stale(cache_key: tuple, func, args, kwargs) -> None:
    """同步函数：若当前无进行中的后台刷新，则启动守护线程异步刷新缓存。"""
    with _cache_lock:
        if cache_key in _refreshing:
            return
        _refreshing.add(cache_key)
    try:
        result = func(*args, **kwargs)
        _set_cache(cache_key, result)
    except Exception:
        # 刷新失败：保留旧值，下次 TTL 窗口再试；不缓存错误结果
        pass
    finally:
        with _cache_lock:
            _refreshing.discard(cache_key)


def _maybe_refresh_stale_async(cache_key: tuple, func, args, kwargs) -> None:
    """异步函数：在独立线程中用新事件循环运行协程刷新缓存。"""
    with _cache_lock:
        if cache_key in _refreshing:
            return
        _refreshing.add(cache_key)
    try:
        result = asyncio.run(func(*args, **kwargs))
        _set_cache(cache_key, result)
    except Exception:
        # 刷新失败：保留旧值，下次 TTL 窗口再试；不缓存错误结果
        pass
    finally:
        with _cache_lock:
            _refreshing.discard(cache_key)


def _is_hashable(obj: Any) -> bool:
    """判断对象是否可哈希（用于过滤 container 等不可哈希的 Depends 注入对象）"""
    try:
        hash(obj)
        return True
    except TypeError:
        return False


def invalidate_stats_cache() -> None:
    """手动失效所有 stats 缓存（用于写入操作后强制刷新）"""
    with _cache_lock:
        _cache_store.clear()


def invalidate_cache_prefixes(*prefixes: str) -> int:
    """按 key_fn 生成的前缀失效缓存，返回删除条数

    key 结构为 (func.__qualname__, key_fn 结果) 或 (qualname, args, kwargs)；
    仅匹配第二段为字符串且命中前缀的项（即显式 key_fn 的缓存），
    无 key_fn 的旧式 key 不会被误删。
    """
    if not prefixes:
        return 0
    with _cache_lock:
        doomed = [
            key for key in _cache_store
            if len(key) == 2 and isinstance(key[1], str) and key[1].startswith(prefixes)
        ]
        for key in doomed:
            _cache_store.pop(key, None)
    return len(doomed)


# 订单写操作影响的统计缓存（均为 300s TTL）：
# trend 曲线 / 今日异常雷达（含 alerts 与今日计数）/ 总览卡 / 业务 KPI（含订单成功率）
_ORDER_STATS_CACHE_PREFIXES = ("trend:", "stats_today", "stats_overview", "kpi:")


def invalidate_order_stats_cache() -> int:
    """订单写操作成功后失效相关统计缓存

    为什么不用 invalidate_stats_cache 全清：会把 eval_funnel / maintenance 等
    与订单无关的缓存一并打掉，高频写反而放大读库压力。
    """
    return invalidate_cache_prefixes(*_ORDER_STATS_CACHE_PREFIXES)
