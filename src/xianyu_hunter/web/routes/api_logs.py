"""日志查看 + 搜索 + 标记 + 导出 API (P3-F-08)

Web 进程与 run 进程分离 → 此 API 读取：
- log 文件（run.stdout.log / run.stderr.log）：实时流
- events 表（结构化、含 task_id/item_id/payload）：可搜索/可标记

设计要点：
- 搜索：大小写不敏感的子串匹配（message + payload）
- 等级过滤：复用 list_events(level=) 已有索引
- 标签：用 payload.tags 数组存（不引入新列，零迁移）
- 导出：CSV 格式（Excel/Numbers 友好）
"""
from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from xianyu_hunter.container import Container
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.utils import parse_iso_datetime, to_datetime, payload_text

router = APIRouter(prefix="/api/logs", tags=["logs"])


# ============== F-08 搜索/过滤 列表 ==============
@router.get("")
def list_logs(
    source: str = Query("file", pattern="^(file|db)$"),
    limit: int = Query(200, ge=1, le=2000),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """默认 file：读 run.stdout.log / run.stderr.log 尾部
    db：读 events 表（结构化，可被搜索接口进一步过滤）
    """
    if source == "db":
        rows = container.repo.list_events(limit=limit) or []
        return {"items": rows, "count": len(rows), "source": "db"}
    base = Path(os.getcwd())
    out: list[dict[str, Any]] = []
    for fname in ("run.stdout.log", "run.stderr.log"):
        p = base / fname
        if p.exists():
            text = p.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()[-limit:]
            out.append({"file": fname, "lines": lines})
    return {"items": out, "count": len(out), "source": "file"}


# ============== F-08 日志搜索/过滤/标签（events 表） ==============
@router.get("/search")
def search_logs(
    q: str | None = Query(None, description="关键字（大小写不敏感子串匹配 message/payload）"),
    level: str | None = Query(None, pattern="^(info|warn|err|debug|trace)$"),
    tag: str | None = Query(None, description="标签名（payload.tags 含该标签）"),
    task_id: str | None = Query(None, description="按 task_id 过滤"),
    stage: str | None = Query(None, description="按 stage 过滤"),
    start: str | None = Query(None, description="起始时间 ISO 格式（如 2026-06-08T00:00:00）"),
    end: str | None = Query(None, description="截止时间 ISO 格式"),
    since_id: int | None = Query(None, ge=0, description="增量查询起点（P3-O-09 SSE 回放同款）"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """在 events 表中搜索日志（F-08）。

    返回结构：
    - items: 命中行（按 created_at desc）
    - total: 当前查询条件下命中总数（粗略，扫描 limit=1000）
    - matched_tags: 命中的标签直方图（top 10）
    - matched_levels: 命中的等级直方图
    """
    # 解析时间范围参数
    start_dt = parse_iso_datetime(start)
    end_dt = parse_iso_datetime(end)

    # 1) 拉取候选行（用 db 自带过滤尽量减少 Python 侧扫描）
    candidates = container.repo.list_events(
        level=level, task_id=task_id, limit=min(limit * 10, 1000), since_id=since_id, ascending=False
    ) or []
    # 2) Python 侧：搜索 + 标签过滤 + stage 过滤 + 时间范围过滤
    if q:
        ql = q.lower()
        # 构造安全的搜索谓词（payload 可能是 dict，序列化后再 lower）
        candidates = [
            e for e in candidates
            if ql in (e.get("message") or "").lower()
            or ql in payload_text(e.get("payload")).lower()
        ]
    if tag:
        candidates = [e for e in candidates if tag in _event_tags(e)]
    if stage:
        candidates = [e for e in candidates if (e.get("stage") or "").lower() == stage.lower()]
    if start_dt:
        candidates = [e for e in candidates if to_datetime(e.get("created_at")) >= start_dt]
    if end_dt:
        candidates = [e for e in candidates if to_datetime(e.get("created_at")) <= end_dt]
    # 3) 统计直方图（基于当前结果）
    tag_counter: dict[str, int] = {}
    lvl_counter: dict[str, int] = {}
    for e in candidates:
        lvl_counter[e.get("level") or "info"] = lvl_counter.get(e.get("level") or "info", 0) + 1
        for t in _event_tags(e):
            tag_counter[t] = tag_counter.get(t, 0) + 1
    # 4) 分页 + 倒序
    candidates = candidates[offset: offset + limit]
    return {
        "items": candidates,
        "count": len(candidates),
        "total_estimate": len(candidates),  # 简化：与 count 同值；前端用 hasMore 翻页
        "matched_levels": dict(sorted(lvl_counter.items(), key=lambda x: -x[1])),
        "matched_tags": dict(sorted(tag_counter.items(), key=lambda x: -x[1])[:10]),
    }


# ============== F-08 行级"打标签" ==============
# （原 TagBody 误用 walrus 运算符赋值 None 作为基类，已移除 — 此路由的 body 直接走 Body(embed=True) 解析，不需要专门 model）


@router.post("/tag")
def tag_event(
    event_id: int = Query(..., ge=1, description="events 表主键 id"),
    tag: str = Body(..., embed=True, min_length=1, max_length=40,
                    description="标签名（仅字母数字_和-）"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """给某条事件打标签（F-08）

    标签存在 events.payload JSON 字段的 `tags` 数组中（避免迁移）。
    重复打同一标签 = 幂等。
    """
    if not re.match(r"^[A-Za-z0-9_\-]+$", tag):
        raise HTTPException(status_code=400, detail="标签只能含字母、数字、_ 和 -")
    ev = container.repo.get_event(event_id)
    if not ev:
        raise HTTPException(status_code=404, detail="事件不存在")
    payload = ev.get("payload")
    p: dict[str, Any] = {}
    if payload:
        try:
            p = json.loads(payload) if isinstance(payload, str) else (payload or {})
        except (json.JSONDecodeError, TypeError, ValueError):
            p = {}
    tags = list(p.get("tags") or [])
    if tag not in tags:
        tags.append(tag)
    p["tags"] = tags
    container.repo.update_event_payload(event_id, json.dumps(p, ensure_ascii=False))
    return {"ok": True, "event_id": event_id, "tags": tags}


@router.delete("/tag")
def untag_event(
    event_id: int = Query(..., ge=1, description="events 表主键 id"),
    tag: str = Query(..., min_length=1, max_length=40, description="要删除的标签名"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """删除某条事件的指定标签（F-08）

    标签不存在时幂等返回成功。
    """
    ev = container.repo.get_event(event_id)
    if not ev:
        raise HTTPException(status_code=404, detail="事件不存在")
    payload = ev.get("payload")
    p: dict[str, Any] = {}
    if payload:
        try:
            p = json.loads(payload) if isinstance(payload, str) else (payload or {})
        except (json.JSONDecodeError, TypeError, ValueError):
            p = {}
    tags = list(p.get("tags") or [])
    if tag in tags:
        tags.remove(tag)
    p["tags"] = tags
    container.repo.update_event_payload(event_id, json.dumps(p, ensure_ascii=False))
    return {"ok": True, "event_id": event_id, "tags": tags}


# ============== F-08 导出（CSV） ==============
@router.get("/export")
def export_logs(
    format: str = Query("csv", pattern="^(csv|log)$"),
    q: str | None = Query(None),
    level: str | None = Query(None, pattern="^(info|warn|err|debug|trace)$"),
    tag: str | None = Query(None),
    task_id: str | None = Query(None),
    stage: str | None = Query(None),
    start: str | None = Query(None, description="起始时间 ISO 格式"),
    end: str | None = Query(None, description="截止时间 ISO 格式"),
    limit: int = Query(1000, ge=1, le=10000),
    container: Container = Depends(get_container),
) -> StreamingResponse:
    """导出日志（F-08）

    - format=csv：Excel/Numbers 友好（id, created_at, level, stage, task_id, item_id, message, payload, tags）
    - format=log：原始文本流（run.stdout.log / run.stderr.log 拼接）
    """
    if format == "log":
        return _export_log_file()
    # csv：复用 search 逻辑拉数据，再序列化
    start_dt = parse_iso_datetime(start)
    end_dt = parse_iso_datetime(end)
    candidates = container.repo.list_events(level=level, task_id=task_id, limit=limit) or []
    if q:
        ql = q.lower()
        candidates = [e for e in candidates if ql in (e.get("message") or "").lower() or ql in payload_text(e.get("payload")).lower()]
    if tag:
        candidates = [e for e in candidates if tag in _event_tags(e)]
    if stage:
        candidates = [e for e in candidates if (e.get("stage") or "").lower() == stage.lower()]
    if start_dt:
        candidates = [e for e in candidates if to_datetime(e.get("created_at")) >= start_dt]
    if end_dt:
        candidates = [e for e in candidates if to_datetime(e.get("created_at")) <= end_dt]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "created_at", "level", "stage", "task_id", "item_id", "message", "tags"])
    for e in candidates:
        writer.writerow([
            e.get("id", ""),
            e.get("created_at", ""),
            e.get("level", ""),
            e.get("stage", ""),
            e.get("task_id", "") or "",
            e.get("item_id", "") or "",
            (e.get("message") or "")[:500],
            ",".join(_event_tags(e)),
        ])
    fname = f"xh-logs-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


def _export_log_file() -> StreamingResponse:
    """导出原始 log 文件拼接流"""
    base = Path(os.getcwd())
    chunks: list[str] = []
    for fname in ("run.stdout.log", "run.stderr.log"):
        p = base / fname
        if p.exists():
            chunks.append(f"===== {fname} =====\n")
            chunks.append(p.read_text(encoding="utf-8", errors="replace"))
    body = "\n".join(chunks)
    fname = f"xh-logs-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
    return StreamingResponse(
        iter([body]),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# ============== 工具：解析 event.tags ==============
def _event_tags(e: dict[str, Any]) -> list[str]:
    """从 event 的 payload JSON 中提取 tags 数组"""
    payload = e.get("payload")
    if not payload:
        return []
    try:
        p = json.loads(payload) if isinstance(payload, str) else (payload or {})
    except (json.JSONDecodeError, TypeError, ValueError):
        return []
    return list(p.get("tags") or [])


# ============== 既有：SSE 日志流 ==============
@router.get("/stream")
async def stream_logs() -> StreamingResponse:
    """SSE 日志流：轮询 run.stdout.log 文件尾部
    简单实现：2s 一次，diff 出新增行。
    """
    stdout_path = Path(os.getcwd()) / "run.stdout.log"
    last_size = stdout_path.stat().st_size if stdout_path.exists() else 0

    async def gen():
        nonlocal last_size
        while True:
            await asyncio.sleep(2)
            try:
                if not stdout_path.exists():
                    yield f"event: ping\ndata: {json.dumps({'ts': 0, 'empty': True})}\n\n"
                    continue
                cur_size = stdout_path.stat().st_size
                if cur_size > last_size:
                    with stdout_path.open("rb") as f:
                        f.seek(last_size)
                        chunk = f.read(cur_size - last_size).decode("utf-8", errors="replace")
                    for line in chunk.splitlines():
                        yield f"event: log\ndata: {json.dumps({'line': line}, ensure_ascii=False)}\n\n"
                    last_size = cur_size
                else:
                    yield f"event: ping\ndata: {json.dumps({'ts': cur_size, 'empty': True})}\n\n"
            except asyncio.CancelledError:
                break
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
