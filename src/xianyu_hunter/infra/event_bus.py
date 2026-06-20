"""事件总线 - asyncio 实现的进程内事件分发

设计文档 §3.2 EventBus。
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable, Coroutine
from typing import Any

from xianyu_hunter.domain.events import Event, EventType
from xianyu_hunter.infra.logger import get_logger

logger = get_logger()

# 事件处理函数类型：async 函数，接收 Event 参数
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """基于 asyncio.Queue 的事件总线

    使用方式：
        bus = EventBus()
        bus.subscribe(EventType.EVAL_PASSED, my_handler)
        await bus.publish(event)
        await bus.run_forever()
    """

    def __init__(self) -> None:
        self._subscribers: dict[EventType, list[EventHandler]] = defaultdict(list)
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._running = False

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """订阅某类事件"""
        self._subscribers[event_type].append(handler)
        logger.debug(f"订阅 {event_type.value} → {handler.__name__}")

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """取消订阅"""
        if handler in self._subscribers.get(event_type, []):
            self._subscribers[event_type].remove(handler)

    async def publish(self, event: Event) -> None:
        """发布事件（异步入队）"""
        await self._queue.put(event)

    def publish_nowait(self, event: Event) -> None:
        """发布事件（同步入队，不阻塞）"""
        self._queue.put_nowait(event)

    async def run_forever(self) -> None:
        """主循环：消费队列，分发到订阅者"""
        self._running = True
        logger.info("EventBus 启动")
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            await self._dispatch(event)

    def stop(self) -> None:
        """停止主循环"""
        self._running = False

    async def _dispatch(self, event: Event) -> None:
        """分发事件到所有订阅者（异常隔离）"""
        handlers = self._subscribers.get(event.type, [])
        if not handlers:
            logger.debug(f"事件 {event.type.value} 无订阅者")
            return
        # 并发执行所有 handler，单个失败不影响其他
        results = await asyncio.gather(
            *(self._safe_call(h, event) for h in handlers),
            return_exceptions=False,
        )

    @staticmethod
    async def _safe_call(handler: EventHandler, event: Event) -> None:
        """安全调用 handler，捕获所有异常"""
        try:
            await handler(event)
        except Exception as e:
            logger.exception(f"Handler {handler.__name__} 处理 {event.type.value} 失败: {e}")


# 全局单例
_default_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """获取默认 EventBus 单例"""
    global _default_bus
    if _default_bus is None:
        _default_bus = EventBus()
    return _default_bus
