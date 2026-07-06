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


def _load_replay_events(container, should_replay: bool, effective_last_id: int) -> list[dict]:
    """加载断线回放事件，返回已过滤掉 <= effective_last_id 的事件列表

    主生成器只需遍历列表 yield，无需在 for 内 if continue 拉高嵌套复杂度。
    """
    if not should_replay:
        return []
    raw_rows = container.repo.list_events(since_id=effective_last_id, ascending=True, limit=1000) or []
    return [ev for ev in raw_rows if int(ev.get("id") or 0) > effective_last_id]


def _load_new_events(container, cursor: int) -> list[dict]:
    """加载增量事件，返回已过滤掉 <= cursor 的事件列表"""
    raw_rows = container.repo.list_events(since_id=cursor, ascending=True, limit=200) or []
    return [ev for ev in raw_rows if int(ev.get("id") or 0) > cursor]


async def _acquire_sse_slot() -> bool:
    """尝试获取 SSE 连接槽位，成功返回 True，超限返回 False"""
    global _sse_connection_count
    async with _sse_gate:
        if _sse_connection_count >= _MAX_SSE_CONNECTIONS:
            return False
        _sse_connection_count += 1
        return True


async def _release_sse_slot() -> None:
    """释放 SSE 连接槽位"""
    global _sse_connection_count
    async with _sse_gate:
        _sse_connection_count = max(0, _sse_connection_count - 1)


def _build_replay_frames(
    container, should_replay: bool, effective_last_id: int
) -> tuple[list[str], int, int, str | None]:
    """构建回放帧序列

    Returns:
        (frames, cursor, replayed, error_msg)
        - 正常: (frames, cursor, replayed, None)
        - 异常: (partial_frames, cursor, partial_replayed, error_str)
    """
    frames: list[str] = []
    cursor = 0
    replayed = 0
    try:
        for ev in _load_replay_events(container, should_replay, effective_last_id):
            ev_id = int(ev.get("id") or 0)
            frames.append(_format_sse_event(ev, ev_id))
            cursor = ev_id
            replayed += 1
        return frames, cursor, replayed, None
    except Exception as e:
        return frames, cursor, replayed, str(e)


def _build_polling_frames(container, cursor: int) -> tuple[list[str], int, str | None]:
    """构建一轮轮询的帧序列

    正常时 frames 含增量事件帧 + ping 帧；异常时 frames 为空，error_msg 非空。
    """
    try:
        frames: list[str] = []
        cur = container.repo.max_event_id()
        if cur > cursor:
            for ev in _load_new_events(container, cursor):
                ev_id = int(ev.get("id") or 0)
                frames.append(_format_sse_event(ev, ev_id))
                cursor = ev_id
        frames.append(f"event: ping\ndata: {json.dumps({'ts': _utcnow().isoformat(timespec='seconds')})}\n\n")
        return frames, cursor, None
    except Exception as e:
        return [], cursor, str(e)


def _resolve_last_event_id(
    last_event_id: int | None,
    last_event_id_header: int | None,
) -> tuple[int, bool]:
    """合并 query 和 header 的 Last-Event-ID

    返回 (effective_id, should_replay)。query 优先于 header，均缺失时 effective=0 且不回放。
    独立为辅助函数以避免在路由中嵌套三元表达式拉高认知复杂度（S3776）。
    """
    if last_event_id is not None:
        return last_event_id, True
    if last_event_id_header is not None:
        return last_event_id_header, True
    return 0, False


@router.get("/events/stream")
async def events_stream(
    container: Container = Depends(get_container),
    last_event_id: int | None = Query(default=None, ge=0),
    last_event_id_header: int | None = Header(default=None, alias="Last-Event-ID", ge=0),
) -> StreamingResponse:
    """SSE 事件流：推送最近事件 + 实时新事件 + 断线回放"""
    effective_last_id, should_replay = _resolve_last_event_id(last_event_id, last_event_id_header)
    logger.debug(
        f"[SSE] connect: query.last_event_id={last_event_id} "
        f"header.Last-Event-ID={last_event_id_header} "
        f"effective={effective_last_id} should_replay={should_replay}"
    )

    async def gen():
        if not await _acquire_sse_slot():
            yield f"event: error\ndata: {json.dumps({'error': f'SSE connections limit ({_MAX_SSE_CONNECTIONS}) reached'})}\n\n"
            return
        try:
            # 回放阶段：构建帧列表后逐条 yield，避免 try/for 嵌套拉高复杂度
            frames, cursor, replayed, replay_err = _build_replay_frames(
                container, should_replay, effective_last_id
            )
            for frame in frames:
                yield frame
            if replay_err:
                yield f"event: warn\ndata: {json.dumps({'msg': 'replay_failed', 'error': replay_err})}\n\n"

            latest = container.repo.max_event_id()
            yield f"event: hello\ndata: {json.dumps({'ts': _utcnow().isoformat(timespec='seconds'), 'latest_id': latest, 'replayed': replayed, 'replay_requested': should_replay})}\n\n"

            # 轮询阶段：CancelledError 只会从 await asyncio.sleep 抛出，
            # 因 _build_polling_frames 的 except Exception 不捕获 BaseException 子类，
            # 故 CancelledError 会自然传播到 finally 触发槽位释放（符合 S7497）
            while True:
                await asyncio.sleep(3)
                frames, cursor, err = _build_polling_frames(container, cursor)
                for frame in frames:
                    yield frame
                if err:
                    yield f"event: error\ndata: {json.dumps({'error': err})}\n\n"
        finally:
            await _release_sse_slot()

    return StreamingResponse(gen(), media_type="text/event-stream")
