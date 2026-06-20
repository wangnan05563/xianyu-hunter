"""EventBus 单元测试"""
from __future__ import annotations

import asyncio

import pytest

from xianyu_hunter.domain.events import Event, EventType
from xianyu_hunter.infra.event_bus import EventBus


@pytest.mark.asyncio
async def test_publish_and_dispatch() -> None:
    """事件被正确分发给订阅者"""
    bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe(EventType.EVAL_PASSED, handler)
    bus.publish_nowait(Event(type=EventType.EVAL_PASSED, task_id="t1"))

    # 启动一个短生命周期的事件循环
    task = asyncio.create_task(_run_briefly(bus, duration=0.3))
    await asyncio.sleep(0.4)
    bus.stop()
    await task

    assert len(received) == 1
    assert received[0].task_id == "t1"


@pytest.mark.asyncio
async def test_multiple_subscribers() -> None:
    """多个订阅者都能收到"""
    bus = EventBus()
    counter = {"a": 0, "b": 0}

    async def h_a(event: Event) -> None:
        counter["a"] += 1

    async def h_b(event: Event) -> None:
        counter["b"] += 1

    bus.subscribe(EventType.ITEM_DISCOVERED, h_a)
    bus.subscribe(EventType.ITEM_DISCOVERED, h_b)
    bus.publish_nowait(Event(type=EventType.ITEM_DISCOVERED))
    bus.publish_nowait(Event(type=EventType.ITEM_DISCOVERED))

    task = asyncio.create_task(_run_briefly(bus, duration=0.3))
    await asyncio.sleep(0.4)
    bus.stop()
    await task

    assert counter == {"a": 2, "b": 2}


@pytest.mark.asyncio
async def test_handler_exception_isolated() -> None:
    """一个 handler 抛错不影响其他"""
    bus = EventBus()
    results = {"ok": 0}

    async def bad_handler(event: Event) -> None:
        raise RuntimeError("intentional")

    async def good_handler(event: Event) -> None:
        results["ok"] += 1

    bus.subscribe(EventType.BUY_FAILED, bad_handler)
    bus.subscribe(EventType.BUY_FAILED, good_handler)
    bus.publish_nowait(Event(type=EventType.BUY_FAILED))

    task = asyncio.create_task(_run_briefly(bus, duration=0.3))
    await asyncio.sleep(0.4)
    bus.stop()
    await task

    assert results["ok"] == 1


@pytest.mark.asyncio
async def test_no_subscribers_is_safe() -> None:
    """无订阅者不报错"""
    bus = EventBus()
    bus.publish_nowait(Event(type=EventType.WAF_TRIGGERED))

    task = asyncio.create_task(_run_briefly(bus, duration=0.2))
    await asyncio.sleep(0.3)
    bus.stop()
    await task


async def _run_briefly(bus: EventBus, duration: float) -> None:
    """短暂运行 EventBus 主循环"""
    original_run = bus._running  # noqa: SLF001
    bus._running = True  # noqa: SLF001
    try:
        while bus._running:  # noqa: SLF001
            try:
                event = await asyncio.wait_for(bus._queue.get(), timeout=0.1)  # noqa: SLF001
                await bus._dispatch(event)  # noqa: SLF001
            except asyncio.TimeoutError:
                continue
    finally:
        bus._running = original_run  # noqa: SLF001
