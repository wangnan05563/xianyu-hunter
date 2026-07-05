"""智能客服知识库管理 API - 重建、状态、版本、回滚

设计要点：
- rebuild 用 asyncio.create_task 后台执行，立即返回 building 状态（前端轮询 /kb/status）
- 回滚是同步等待操作（KBManager.rollback 内部已加 _build_lock，会等待进行中构建完成）
- chatbot 子容器为 None 时统一返回 403 CHATBOT_DISABLED
- FAQ CRUD 已统一收敛到 api_chatbot_config.py（/api/chatbot/faq），避免路由重复

认证：由 BearerAuthMiddleware 统一处理。
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from xianyu_hunter.web.deps import get_container

router = APIRouter(prefix="/api/chatbot", tags=["chatbot-kb"])

# M-35 修复：保留后台任务引用，避免被 GC 回收导致任务中途消失
# Python 文档明确要求 create_task 的返回值需保存引用
_background_tasks: set[asyncio.Task] = set()


def _get_chatbot_or_403() -> dict[str, Any]:
    """获取 chatbot 子容器，未启用时抛 403"""
    container = get_container()
    if container.chatbot is None:
        raise HTTPException(
            status_code=403,
            detail={"code": "CHATBOT_DISABLED", "message": "智能客服未启用"},
        )
    return container.chatbot


def _log_audit(repo: Any, action: str, target: str) -> None:
    """审计日志：失败不阻塞主流程（与 api_vector_admin._log_audit 策略一致）"""
    try:
        repo.add_audit_log(action=action, target=target, source="web")
    except Exception:
        logger.exception("写入知识库审计日志失败")


# ============== 知识库版本管理 ==============
@router.post("/kb/rebuild", status_code=202)
async def rebuild_kb() -> dict[str, Any]:
    """触发全量重建（后台异步执行）

    立即返回 building 状态，前端通过 GET /kb/status 轮询进度。
    用 asyncio.create_task 而非 await：避免 HTTP 请求阻塞 30s+ 的构建过程。

    不预生成 version_id：build_all 内部会生成真实版本号并写入 DB，
    前端通过 /kb/status 轮询拿到的是真实版本，避免返回不一致的假 ID。
    """
    chatbot = _get_chatbot_or_403()
    kb_manager = chatbot["kb_manager"]
    repo = chatbot["repo"]

    async def _do_rebuild() -> None:
        try:
            version = await kb_manager.build_all()
            logger.info(
                f"知识库重建完成: version_id={version.version_id} chunks={version.chunk_count}"
            )
            _log_audit(
                repo,
                action="kb_rebuild",
                target=f"{version.version_id[:8]}|status:{version.status}|chunks:{version.chunk_count}",
            )
        except Exception as e:
            # 后台任务异常无 awaiter 接收，仅记录日志
            logger.exception(f"知识库重建失败: {e}")
            _log_audit(repo, action="kb_rebuild", target=f"failed:{type(e).__name__}")

    # 创建后台任务并立即返回，不阻塞 HTTP 响应
    # 保留引用避免 GC 回收（M-35），任务完成后自动从集合移除
    task = asyncio.create_task(_do_rebuild())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return {"status": "building"}


@router.get("/kb/status")
def kb_status() -> dict[str, Any]:
    """当前知识库状态

    字段名与前端 KBStatus 类型对齐：
    - chunk_count / last_build_at / building / status / progress
    - building 通过查询 status=building 的版本判断后台构建是否进行中
    - progress 来自 KBManager._progress，包含 phase/percent/message
    """
    chatbot = _get_chatbot_or_403()
    repo = chatbot["repo"]
    kb_manager = chatbot["kb_manager"]
    current = repo.get_current_kb_version()
    progress = kb_manager.get_progress()
    if current is None:
        return {
            "current_version": None,
            "chunk_count": 0,
            "last_build_at": None,
            "building": repo.has_building_kb_version(),
            "status": "empty",
            "progress": progress,
        }
    return {
        "current_version": current["id"],
        "chunk_count": current["chunk_count"],
        "last_build_at": current["created_at"],
        "building": repo.has_building_kb_version(),
        "status": current["status"],
        "progress": progress,
    }


@router.get("/kb/versions")
def list_kb_versions(limit: int = Query(20, ge=1, le=100)) -> dict[str, Any]:
    """知识库版本列表（按 created_at DESC）"""
    chatbot = _get_chatbot_or_403()
    repo = chatbot["repo"]
    items = repo.list_kb_versions(limit=limit)
    # M-36 修复：total 用真实计数，而非 len(items)（当前页条数）
    total = repo.count_kb_versions()
    return {"items": items, "total": total}


@router.post("/kb/rollback/{version_id}")
async def rollback_kb(version_id: str) -> dict[str, Any]:
    """回滚到指定版本"""
    chatbot = _get_chatbot_or_403()
    repo = chatbot["repo"]
    target = repo.get_kb_version(version_id)
    if target is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "KB_VERSION_NOT_FOUND", "message": "版本不存在"},
        )
    kb_manager = chatbot["kb_manager"]
    # rollback 内部加 _build_lock，会等待进行中的构建完成
    new_version = await kb_manager.rollback(version_id)
    _log_audit(
        repo,
        action="kb_rollback",
        target=f"from:{version_id[:8]}→to:{new_version.version_id[:8]}|status:{new_version.status}|chunks:{new_version.chunk_count}",
    )
    return {"ok": True, "current_version": new_version.version_id, "status": new_version.status}
