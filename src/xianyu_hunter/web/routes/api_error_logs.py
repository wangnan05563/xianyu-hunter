"""后台错误日志 API

提供错误日志的 CRUD + AI 上下文导出 + 批量清理 + 批量状态更新功能。

设计要点：
- 列表支持按 status/error_type/request_path/时间范围 过滤
- AI 上下文导出支持 JSON 和 Markdown 两种格式
- 状态管理：new → resolved / ignored
- 批量清理：按天数清理已解决/已忽略的记录
- 批量操作：一次性对多条记录执行 删除/状态变更
"""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from xianyu_hunter.container import Container
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.services.search_services import (
    ErrorLogSearchParams,
    ErrorLogSearchService,
)
from xianyu_hunter.web.utils import parse_iso_datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/error-logs", tags=["error-logs"])


class BatchActionRequest(BaseModel):
    """批量操作请求体

    将删除与状态变更统一聚合为单一 action，避免前端为每种操作分别建路由
    """
    ids: list[int] = Field(..., min_length=1, max_length=500)
    action: str = Field(..., pattern="^(delete|resolve|ignore|new)$")


def _parse_json_fields(item: dict) -> dict:
    """将 error_log 中的 JSON 字符串字段解析为 dict，便于前端直接消费"""
    for field in ("request_params", "request_headers", "server_env", "ai_context_json"):
        if item.get(field) and isinstance(item[field], str):
            try:
                item[field] = json.loads(item[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return item


@router.get("")
def list_error_logs(
    status: str | None = Query(None, pattern="^(new|resolved|ignored)$"),
    error_type: str | None = Query(None, description="异常类型（模糊匹配）"),
    request_path: str | None = Query(None, description="请求路径（模糊匹配）"),
    request_id: str | None = Query(None, description="按全局流水号过滤（全链路追踪）"),
    start: str | None = Query(None, description="起始时间 ISO8601"),
    end: str | None = Query(None, description="结束时间 ISO8601"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """列出错误日志，支持多维度过滤"""
    start_dt = parse_iso_datetime(start) if start else None
    end_dt = parse_iso_datetime(end) if end else None

    # 使用 SearchService 统一处理分页/慢查询埋点
    service = ErrorLogSearchService(container.repo)
    result = service.search(ErrorLogSearchParams(
        status=status, error_type=error_type, request_path=request_path,
        request_id=request_id, start_dt=start_dt, end_dt=end_dt,
        limit=limit, offset=offset,
    ))
    items = [_parse_json_fields(item) for item in result["items"]]
    # status_counts 是全局状态分布，不依赖当前过滤条件，单独调用 repo 获取
    status_counts = container.repo.count_error_logs_by_status()
    return {
        "items": items,
        "count": len(items),
        "status_counts": status_counts,
    }


@router.get("/{error_log_id}")
def get_error_log(
    error_log_id: int,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """获取单条错误日志详情"""
    item = container.repo.get_error_log(error_log_id)
    if not item:
        raise HTTPException(status_code=404, detail="错误日志不存在")
    return _parse_json_fields(item)


@router.post("/batch")
def batch_action(
    payload: BatchActionRequest,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """批量操作错误日志

    支持一次性对多条记录执行删除或状态变更，减少前端循环请求次数
    action: delete | resolve | ignore | new
    """
    ids = payload.ids
    action = payload.action
    # 批量删除/状态变更是高危操作，记录操作类型与影响范围便于事后审计追溯
    logger.info("error_logs batch action=%s count=%d", action, len(ids))
    if action == "delete":
        affected = container.repo.batch_delete_error_logs(ids)
    else:
        # action 与 status 字段值一一对应（resolve/ignore/new）
        affected = container.repo.batch_update_error_log_status(ids, action)
    return {"affected": affected, "status": "ok"}


@router.get("/{error_log_id}/ai-context")
def get_ai_context(
    error_log_id: int,
    format: str = Query("json", pattern="^(json|markdown)$"),
    container: Container = Depends(get_container),
) -> PlainTextResponse:
    """导出 AI 诊断上下文（JSON 或 Markdown 格式）

    JSON 格式可直接作为 AI 系统输入；Markdown 格式可直接粘贴给 AI 对话
    """
    item = container.repo.get_error_log(error_log_id)
    if not item:
        raise HTTPException(status_code=404, detail="错误日志不存在")

    if format == "json":
        content = item.get("ai_context_json") or "{}"
        return PlainTextResponse(content=content, media_type="application/json")
    else:
        content = item.get("ai_context_md") or ""
        return PlainTextResponse(content=content, media_type="text/markdown")


@router.patch("/{error_log_id}/status")
def update_status(
    error_log_id: int,
    status: str = Query(..., pattern="^(new|resolved|ignored)$"),
    container: Container = Depends(get_container),
) -> dict[str, str]:
    """更新错误日志状态"""
    success = container.repo.update_error_log_status(error_log_id, status)
    if not success:
        raise HTTPException(status_code=404, detail="错误日志不存在")
    return {"status": "ok"}


@router.delete("/{error_log_id}")
def delete_error_log(
    error_log_id: int,
    container: Container = Depends(get_container),
) -> dict[str, str]:
    """删除单条错误日志"""
    success = container.repo.delete_error_log(error_log_id)
    if not success:
        raise HTTPException(status_code=404, detail="错误日志不存在")
    return {"status": "ok"}


@router.post("/cleanup")
def cleanup_error_logs(
    days: int = Query(30, ge=1, le=365),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """批量清理指定天数前的已解决/已忽略错误日志"""
    deleted = container.repo.cleanup_old_error_logs(days=days)
    return {"deleted": deleted, "status": "ok"}

