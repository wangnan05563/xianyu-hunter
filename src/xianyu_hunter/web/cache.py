"""Web 层 TTL 内存缓存工具

为什么需要：JMeter 压测显示 stats 接口在 100 并发下平均响应 >1.8s，
根因之一是每次请求都重新计算统计聚合。stats 类数据变化频率低（分钟级），
加 60s TTL 缓存可让命中率 >90% 时响应降到 <10ms。

设计要点：
- 进程内 dict + 单调时钟时间戳，无外部依赖（不引入 Redis 增加运维复杂度）
- 线程安全：FastAPI 默认同步路由用 anyio worker thread 池，dict 读写需加锁
- 主动过期：缓存项带 TTL，过期自动忽略（不主动清理，下次写入覆盖）
- 可选跳过缓存：bypass_cache=True 强制刷新（管理员手动刷新场景）
- 同步/异步双支持：P3 改造后 stats 接口改 async def，装饰器自动识别协程函数
"""
from __future__ import annotations

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


def cached_ttl(ttl_seconds: int, key_fn: Callable[..., str] | None = None) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """TTL 内存缓存装饰器（同步/异步双支持）

    Args:
        ttl_seconds: 缓存存活时间（秒），过期后下次调用重新执行被装饰函数
        key_fn: 可选的自定义缓存 key 生成函数，接收与被装饰函数相同的参数
            默认用函数名 + args + kwargs 排序后生成 key

    同步使用示例：
        @cached_ttl(60)
        def business_kpi(range_days: int = 30, container=...):
            ...

    异步使用示例（P3 改造后）：
        @cached_ttl(60)
        async def _compute_business_kpi(range_days: int, container=...):
            ...

    # 管理员手动刷新
    result = await business_kpi(range_days=30, container=..., bypass_cache=True)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        is_async = inspect.iscoroutinefunction(func)

        def _make_key(*args, **kwargs) -> tuple:
            """生成缓存 key（同步/异步共用）"""
            if key_fn is not None:
                return (func.__qualname__, key_fn(*args, **kwargs))
            # 排除 container 等 Depends 注入的对象（不可哈希且每次不同）
            safe_args = tuple(a for a in args if _is_hashable(a))
            safe_kwargs = tuple(sorted(
                (k, v) for k, v in kwargs.items() if _is_hashable(v)
            ))
            return (func.__qualname__, safe_args, safe_kwargs)

        def _try_get(cache_key: tuple) -> tuple[bool, Any]:
            """尝试从缓存读取，返回 (hit, value)"""
            with _cache_lock:
                cached = _cache_store.get(cache_key)
                if cached is not None:
                    ts, value = cached
                    if time.monotonic() - ts < ttl_seconds:
                        return True, value
            return False, None

        def _set(cache_key: tuple, value: Any) -> None:
            """写入缓存"""
            with _cache_lock:
                _cache_store[cache_key] = (time.monotonic(), value)

        if is_async:
            # 异步分支：返回 coroutine wrapper
            async def async_wrapper(*args, **kwargs) -> Any:
                bypass = kwargs.pop("bypass_cache", False)
                cache_key = _make_key(*args, **kwargs)

                if not bypass:
                    hit, value = _try_get(cache_key)
                    if hit:
                        return value

                # 缓存未命中或被跳过，执行原函数
                result = await func(*args, **kwargs)
                _set(cache_key, result)
                return result

            async_wrapper._cache_clear = lambda: _cache_store.clear()  # type: ignore[attr-defined]
            return async_wrapper  # type: ignore[return-value]

        # 同步分支：保持原有行为不变
        def wrapper(*args, **kwargs) -> T:
            bypass = kwargs.pop("bypass_cache", False)
            cache_key = _make_key(*args, **kwargs)

            if not bypass:
                hit, value = _try_get(cache_key)
                if hit:
                    return value  # type: ignore[return-value]

            result = func(*args, **kwargs)
            _set(cache_key, result)
            return result

        wrapper._cache_clear = lambda: _cache_store.clear()  # type: ignore[attr-defined]
        return wrapper

    return decorator


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
