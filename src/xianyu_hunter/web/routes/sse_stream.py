"""SSE 事件流 API - Server-Sent Events 实时推送

端点：
- GET /api/events/stream     SSE 事件流（含断线回放）
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import StreamingResponse
from loguru import logger

from xianyu_hunter.container import Container
from xianyu_hunter.infra.db_models import _utcnow
from xianyu_hunter.web.deps import get_container

router = APIRouter(prefix="/api", tags=["sse-stream"])

# SSE 并发连接上限：防止多标签页/异常客户端耗尽服务端资源
_MAX_SSE_CONNECTIONS = 10
_sse_connection_count = 0
_sse_gate = asyncio.Lock()


def _format_sse_event(ev: dict, ev_id: int) -> str:
    """格式化一条事件为 SSE 帧（含 id 字段以启用断线回放）"""
    return (
        f"id: {ev_id}\n"
        f"event: app_event\n"
        f"data: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"
    )


@router.get("/events/stream")
async def events_stream(
    container: Container = Depends(get_container),
    last_event_id: int | None = Query(default=None, ge=0),
    last_event_id_header: int | None = Header(default=None, alias="Last-Event-ID", ge=0),
) -> StreamingResponse:
    """SSE 事件流：推送最近事件 + 实时新事件 + 断线回放"""
    client_provided_last = last_event_id is not None or last_event_id_header is not None
    effective_last_id = (
        last_event_id if last_event_id is not None
        else (last_event_id_header or 0)
    )
    should_replay = client_provided_last
    logger.debug(
        f"[SSE] connect: query.last_event_id={last_event_id} "
        f"header.Last-Event-ID={last_event_id_header} "
        f"effective={effective_last_id} should_replay={should_replay}"
    )

    async def gen():
        global _sse_connection_count
        # 连接数限制：超限则直接拒绝
        async with _sse_gate:
            if _sse_connection_count >= _MAX_SSE_CONNECTIONS:
                yield f"event: error\ndata: {json.dumps({'error': f'SSE connections limit ({_MAX_SSE_CONNECTIONS}) reached'})}\n\n"
                return
            _sse_connection_count += 1
        connected = True
        try:
            replayed = 0
            cursor = 0
            try:
                if should_replay:
                    replay_rows = (
                        container.repo.list_events(since_id=effective_last_id, ascending=True, limit=1000) or []
                    )
                    for ev in replay_rows:
                        ev_id = int(ev.get("id") or 0)
                        if ev_id <= effective_last_id:
                            continue
                        yield _format_sse_event(ev, ev_id)
                        cursor = ev_id
                        replayed += 1
            except Exception as e:
                yield f"event: warn\ndata: {json.dumps({'msg': 'replay_failed', 'error': str(e)})}\n\n"

            latest = container.repo.max_event_id()
            yield f"event: hello\ndata: {json.dumps({'ts': _utcnow().isoformat(timespec='seconds'), 'latest_id': latest, 'replayed': replayed, 'replay_requested': should_replay})}\n\n"

            while True:
                await asyncio.sleep(3)
                try:
                    cur = container.repo.max_event_id()
                    if cur > cursor:
                        new_rows = (
                            container.repo.list_events(since_id=cursor, ascending=True, limit=200) or []
                        )
                        for ev in new_rows:
                            ev_id = int(ev.get("id") or 0)
                            if ev_id <= cursor:
                                continue
                            yield _format_sse_event(ev, ev_id)
                            cursor = ev_id
                    yield f"event: ping\ndata: {json.dumps({'ts': _utcnow().isoformat(timespec='seconds')})}\n\n"
                except asyncio.CancelledError:
                    # SSE 客户端断开连接时生成器被取消，重新抛出符合 asyncio 取消标准模式（S7497）
                    raise
                except Exception as e:
                    yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        finally:
            if connected:
                async with _sse_gate:
                    _sse_connection_count = max(0, _sse_connection_count - 1)

    return StreamingResponse(gen(), media_type="text/event-stream")
