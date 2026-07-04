"""日志查看 + 搜索 + 标记 + 导出 API (P3-F-08)

Web 进程与 run 进程分离 → 此 API 读取：
- log 文件（run.stdout.log / run.stderr.log）：实时流
- events 表（结构化、含 task_id/item_id/payload/request_id）：可搜索/可标记/可链路追踪

设计要点：
- 搜索：大小写不敏感的子串匹配（message + payload）
- 等级过滤：复用 list_events(level=) 已有索引
- request_id 过滤：通过 list_events_by_request 精确检索同链路所有日志
- 标签：用 payload.tags 数组存（不引入新列，零迁移）
- 导出：CSV 格式（Excel/Numbers 友好）
- 全链路追踪：/api/logs/request/{request_id} 聚合 events + error_logs 两表
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

# request_id token 正则：从日志行中解析 [req=xxx] 标记，供 SSE 流过滤使用
# 日志格式：... | LEVEL | [req=req-20260701120000537-a3b2c1] | module:func:line - msg
_REQUEST_ID_PATTERN = re.compile(r"\[req=([^\]]+)\]")

# 运行日志文件名：多处端点共享，提取为常量避免散落修改
STDOUT_LOG_FILENAME = "run.stdout.log"
STDERR_LOG_FILENAME = "run.stderr.log"


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
    for fname in (STDOUT_LOG_FILENAME, STDERR_LOG_FILENAME):
        p = base / fname
        if p.exists():
            text = p.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()[-limit:]
            out.append({"file": fname, "lines": lines})
    return {"items": out, "count": len(out), "source": "file"}


# ============== F-08 日志搜索/过滤/标签（events 表） ==============
def _fetch_log_candidates(
    container: Container,
    request_id: str | None,
    level: str | None,
    task_id: str | None,
    limit: int,
    since_id: int | None,
) -> list[dict[str, Any]]:
    """拉取候选行：request_id 走索引查询，否则走 list_events 全量过滤

    request_id 优先级最高：单次请求触发的所有日志都通过此列关联，
    list_events_by_request 走索引性能优于全表扫描。
    """
    if request_id:
        rows, _ = container.repo.list_events_by_request(
            request_id=request_id, limit=min(limit * 10, 1000), offset=0
        )
        # 倒序输出便于人工查看最新记录
        return list(reversed(rows))
    # 用 db 自带过滤尽量减少 Python 侧扫描
    return container.repo.list_events(
        level=level, task_id=task_id, limit=min(limit * 10, 1000), since_id=since_id, ascending=False
    ) or []


def _filter_log_candidates(
    candidates: list[dict[str, Any]],
    q: str | None,
    tag: str | None,
    stage: str | None,
    start_dt: Any,
    end_dt: Any,
) -> list[dict[str, Any]]:
    """Python 侧过滤：关键字 / 标签 / stage / 时间范围

    DB 侧只能做 level/task_id 粗过滤，payload 内的 tag 和 message 子串匹配
    必须在 Python 侧完成（payload 是 JSON 字符串，SQLite 无原生 JSON 查询）。
    """
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
    return candidates


def _compute_log_histograms(
    candidates: list[dict[str, Any]],
) -> tuple[dict[str, int], dict[str, int]]:
    """统计命中行的等级和标签直方图，供前端展示分布

    level 缺失时归入 "info"：早期日志未写 level 字段，info 是最通用的兜底。
    """
    tag_counter: dict[str, int] = {}
    lvl_counter: dict[str, int] = {}
    for e in candidates:
        lvl_key = e.get("level") or "info"
        lvl_counter[lvl_key] = lvl_counter.get(lvl_key, 0) + 1
        for t in _event_tags(e):
            tag_counter[t] = tag_counter.get(t, 0) + 1
    return lvl_counter, tag_counter


@router.get("/search")
def search_logs(
    # 大小写都允许：前端 SPA 下拉用大写（ERROR/WARNING/INFO/DEBUG），
    # 旧版控制台/直接 API 调用可能用小写（err/warn/info/debug），
    # Python re 模块不支持 (?i) 顶层修饰符，Pydantic v2 同样不识别，
    # 这里用显式枚举，函数入口再归一化为小写匹配 DB 中的值。
    q: str | None = Query(None, description="关键字（大小写不敏感子串匹配 message/payload）"),
    level: str | None = Query(
        None,
        pattern=r"^(info|INFO|debug|DEBUG|err|ERR|error|ERROR|warn|WARN|warning|WARNING|trace|TRACE)$",
    ),
    tag: str | None = Query(None, description="标签名（payload.tags 含该标签）"),
    task_id: str | None = Query(None, description="按 task_id 过滤"),
    stage: str | None = Query(None, description="按 stage 过滤"),
    request_id: str | None = Query(None, description="按 request_id 过滤（全链路追踪）"),
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

    request_id 参数：精确匹配流水号，用于检索同链路所有关联日志。
    传入 request_id 时优先走 list_events_by_request 索引查询，性能优于全表扫描。
    """
    # 归一化 level 大小写：events 表中 level 统一存小写（"info"/"warn"/"err"），
    # 前端 SPA 下拉传大写（ERROR/WARNING/INFO/DEBUG），这里统一转小写
    if level:
        level = level.lower()
    # 解析时间范围参数
    start_dt = parse_iso_datetime(start)
    end_dt = parse_iso_datetime(end)

    # 1) 拉取候选行 + 2) Python 侧过滤
    candidates = _fetch_log_candidates(container, request_id, level, task_id, limit, since_id)
    candidates = _filter_log_candidates(candidates, q, tag, stage, start_dt, end_dt)

    # 3) 统计直方图（基于过滤后的结果）
    lvl_counter, tag_counter = _compute_log_histograms(candidates)

    # 4) 分页 + 返回
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
        # S5713: json.JSONDecodeError 是 ValueError 的子类，冗余已移除
        except (TypeError, ValueError):
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
        # S5713: json.JSONDecodeError 是 ValueError 的子类，移除冗余子类
        except (TypeError, ValueError):
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
    level: str | None = Query(
        None,
        pattern=r"^(info|INFO|debug|DEBUG|err|ERR|error|ERROR|warn|WARN|warning|WARNING|trace|TRACE)$",
    ),
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
    # 归一化 level 大小写（与 search_logs 保持一致）
    if level:
        level = level.lower()
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
    for fname in (STDOUT_LOG_FILENAME, STDERR_LOG_FILENAME):
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
    # S5713: json.JSONDecodeError 是 ValueError 的子类，移除冗余子类
    except (TypeError, ValueError):
        return []
    return list(p.get("tags") or [])


# ============== 既有：SSE 日志流 ==============
def _format_sse(event: str, data: dict[str, Any]) -> str:
    """格式化 SSE 消息：event 行 + data 行 + 空行结尾

    SSE 协议要求消息以 \n\n 分隔，data 字段统一用 JSON 字符串，
    ensure_ascii=False 保留中文便于前端调试时直接阅读。
    """
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _match_request_id(line: str, request_id: str | None) -> bool:
    """检查日志行是否匹配 request_id

    日志行格式含 [req=xxx] token；request_id 为 None 时不过滤（返回 True）。
    """
    if not request_id:
        return True
    m = _REQUEST_ID_PATTERN.search(line)
    return bool(m and m.group(1) == request_id)


def _read_log_chunk(stdout_path: Path, last_size: int) -> tuple[str | None, int]:
    """读取日志文件增量

    返回 (chunk, cur_size)：
    - 文件不存在：(None, 0) —— 调用方据此发 ts=0 的 ping
    - 无新增：(None, cur_size) —— 调用方据此发 ts=cur_size 的 ping
    - 有新增：(chunk_text, cur_size) —— 调用方按行处理 chunk
    """
    if not stdout_path.exists():
        return None, 0
    cur_size = stdout_path.stat().st_size
    if cur_size <= last_size:
        return None, cur_size
    with stdout_path.open("rb") as f:
        f.seek(last_size)
        chunk = f.read(cur_size - last_size).decode("utf-8", errors="replace")
    return chunk, cur_size


@router.get("/stream")
async def stream_logs(
    request_id: str | None = Query(None, description="按 request_id 过滤实时日志流"),
) -> StreamingResponse:
    """SSE 日志流：轮询 run.stdout.log 文件尾部

    简单实现：2s 一次，diff 出新增行。
    request_id 参数：从日志行中解析 [req=xxx] token 过滤，
    只推送同链路的日志行，便于前端实时追踪单次请求的执行过程。
    """
    stdout_path = Path(os.getcwd()) / STDOUT_LOG_FILENAME
    last_size = stdout_path.stat().st_size if stdout_path.exists() else 0

    async def gen():
        nonlocal last_size
        while True:
            await asyncio.sleep(2)
            try:
                chunk, cur_size = _read_log_chunk(stdout_path, last_size)
                if chunk is None:
                    # 文件不存在或无新增：发 ping 维持连接
                    yield _format_sse("ping", {"ts": cur_size, "empty": True})
                    continue
                for line in chunk.splitlines():
                    # 按 request_id 过滤：从 [req=xxx] token 解析匹配
                    if not _match_request_id(line, request_id):
                        continue
                    yield _format_sse("log", {"line": line})
                last_size = cur_size
            except asyncio.CancelledError:
                # SSE 客户端断开连接时生成器被取消，重新抛出符合 asyncio 取消标准模式（S7497）
                raise
            except Exception as e:
                yield _format_sse("error", {"error": str(e)})

    return StreamingResponse(gen(), media_type="text/event-stream")


# ============== 全链路追踪聚合查询端点 ==============
@router.get("/request/{request_id}")
def get_request_chain(
    request_id: str,
    limit: int = Query(1000, ge=1, le=5000, description="单表最大返回数"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """按全局流水号聚合查询同链路所有日志记录

    全链路追踪核心端点：返回单次请求触发的所有 events + error_logs，
    按时间正序合并，便于展示完整调用链路：

    HTTP 请求
      ├─ 中间件日志
      ├─ 业务逻辑日志（events）
      ├─ 数据库操作日志（events）
      ├─ 外部服务调用日志（events）
      ├─ 子请求/联动请求日志（events）
      └─ 异常日志（error_logs）

    request_id 必须符合 req-<17位数字>-<6位hex> 格式，否则返回 400。
    """
    from xianyu_hunter.infra.request_context import is_valid_request_id
    if not is_valid_request_id(request_id):
        raise HTTPException(status_code=400, detail="request_id 格式不合法")

    # 分别从 events 和 error_logs 表查询
    events, events_total = container.repo.list_events_by_request(
        request_id=request_id, limit=limit, offset=0
    )
    error_logs = container.repo.list_error_logs(
        request_id=request_id, limit=limit, offset=0
    )

    # 标记来源表，便于前端区分日志类型
    for ev in events:
        ev["_source"] = "event"
    for el in error_logs:
        el["_source"] = "error_log"

    # 合并后按时间正序排序，呈现完整调用链路
    def _parse_ts(item: dict, key: str = "created_at") -> datetime:
        v = item.get(key)
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v)
            except ValueError:
                return datetime.min
        return datetime.min

    chain = events + error_logs
    # error_logs 表时间字段是 timestamp，events 是 created_at，统一取值
    chain.sort(key=lambda x: _parse_ts(x, "timestamp") if x.get("_source") == "error_log" else _parse_ts(x))

    return {
        "request_id": request_id,
        "total": len(chain),
        "events_total": events_total,
        "error_logs_total": len(error_logs),
        "chain": chain,
    }
