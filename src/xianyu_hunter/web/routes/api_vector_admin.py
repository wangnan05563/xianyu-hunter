"""向量数据库维护 API - ChromaDB 运维操作

设计要点：
- 复用 chatbot 子容器的 VectorStore 与 ChatbotRepository
- chatbot 未启用时返回 403 CHATBOT_DISABLED（与 api_chatbot 一致）
- 危险操作（恢复/删除快照/清空/按来源删除）需 confirm_token=CONFIRM_DELETE
- 审计日志写入 chatbot_audit_logs 表，action 前缀 vector_admin.
- 快照目录与 KBManager 共享：data/chromadb/snapshots/{version_id}
  手动快照用 manual_{timestamp} 前缀，与 KB 版本快照区分

认证：由 BearerAuthMiddleware 统一处理。
"""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

from xianyu_hunter.web.deps import get_container

router = APIRouter(prefix="/api/vector-admin", tags=["vector-admin"])

CONFIRM_TOKEN = "CONFIRM_DELETE"


def _get_chatbot_or_403() -> dict[str, Any]:
    """获取 chatbot 子容器，未启用时抛 403

    VectorStore 是 chatbot 子容器的可选依赖（chromadb 未装时整个 chatbot 为 None），
    复用 api_chatbot 的 403 策略保持一致。
    """
    container = get_container()
    if container.chatbot is None:
        raise HTTPException(
            status_code=403,
            detail={"code": "CHATBOT_DISABLED", "message": "智能客服未启用，向量库不可用"},
        )
    return container.chatbot


def _require_confirm(token: str) -> None:
    """校验危险操作确认 token，不匹配抛 400"""
    if token != CONFIRM_TOKEN:
        raise HTTPException(
            status_code=400,
            detail=f"需要 confirm_token={CONFIRM_TOKEN}",
        )


def _log_audit(repo: Any, action: str, target: str) -> None:
    """审计日志：失败不阻塞主流程（与 api_db_admin._log_audit 策略一致）"""
    try:
        repo.add_audit_log(action=action, target=target, source="web")
    except Exception:
        logger.exception("写入向量库审计日志失败")


def _dir_size(path: Path) -> int:
    """递归计算目录总大小（字节）"""
    if not path.exists():
        return 0
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return total


def _format_size(n: int) -> str:
    """字节数转人类可读（KB/MB/GB）"""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _snapshot_dir(vector_store: Any) -> Path:
    """快照根目录：{persist_path}/snapshots"""
    return Path(vector_store.persist_path) / "snapshots"


def _list_snapshots(vector_store: Any) -> list[dict[str, Any]]:
    """列出所有快照，按创建时间 DESC 排序"""
    root = _snapshot_dir(vector_store)
    if not root.exists():
        return []
    items = []
    for d in root.iterdir():
        if not d.is_dir():
            continue
        stat = d.stat()
        # 目录的 mtime 作为创建时间近似值（快照创建后不再修改）
        created_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).astimezone()
        items.append({
            "id": d.name,
            "size_bytes": _dir_size(d),
            "size_display": _format_size(_dir_size(d)),
            "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "is_manual": d.name.startswith("manual_"),
        })
    items.sort(key=lambda x: x["created_at"], reverse=True)
    return items


# ============== 请求体模型 ==============

class CreateSnapshotBody(BaseModel):
    """手动创建快照（无 confirm_token 要求，是非破坏性操作）"""
    label: str | None = None  # 可选备注，拼入快照目录名


class RestoreSnapshotBody(BaseModel):
    """从快照恢复（覆盖当前集合，需 confirm_token）"""
    confirm_token: str


class CleanupBySourceBody(BaseModel):
    """按来源文件删除片段（需 confirm_token）"""
    source_file: str
    confirm_token: str


class CleanupAllBody(BaseModel):
    """清空集合（需 confirm_token）"""
    confirm_token: str


# ============== 状态监控 ==============

@router.get("/status")
async def get_status() -> dict[str, Any]:
    """向量库状态总览：片段数、目录大小、快照数、持久化路径、集合名"""
    chatbot = _get_chatbot_or_403()
    vector_store = chatbot["vector_store"]
    chunk_count = await vector_store.count()
    persist_path = Path(vector_store.persist_path)
    # 主数据目录大小（排除 snapshots 子目录，避免快照膨胀统计）
    main_size = 0
    if persist_path.exists():
        for item in persist_path.iterdir():
            if item.name == "snapshots":
                continue
            if item.is_dir():
                main_size += _dir_size(item)
            else:
                main_size += item.stat().st_size
    snapshots = _list_snapshots(vector_store)
    return {
        "collection_name": vector_store.collection_name,
        "persist_path": str(persist_path),
        "chunk_count": chunk_count,
        "data_size_bytes": main_size,
        "data_size_display": _format_size(main_size),
        "snapshot_count": len(snapshots),
        "last_snapshot_at": snapshots[0]["created_at"] if snapshots else None,
    }


# ============== 快照管理 ==============

@router.get("/snapshots")
def list_snapshots() -> dict[str, Any]:
    """列出所有快照"""
    chatbot = _get_chatbot_or_403()
    items = _list_snapshots(chatbot["vector_store"])
    return {"items": items, "total": len(items)}


@router.post("/snapshots")
async def create_snapshot(body: CreateSnapshotBody) -> dict[str, Any]:
    """手动创建快照

    快照目录名：manual_{timestamp}[_{label}]，与 KB 版本快照（version_id）区分。
    复用 VectorStore.export_snapshot（文件级复制，跳过 snapshots 子目录）。
    """
    chatbot = _get_chatbot_or_403()
    vector_store = chatbot["vector_store"]
    repo = chatbot["repo"]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    label_part = f"_{body.label}" if body.label else ""
    snapshot_id = f"manual_{ts}{label_part}"
    snapshot_path = str(_snapshot_dir(vector_store) / snapshot_id)
    try:
        await vector_store.export_snapshot(snapshot_path)
        _log_audit(repo, "vector_admin.snapshot_create", snapshot_id)
        return {"ok": True, "snapshot_id": snapshot_id}
    except Exception as e:
        logger.exception("创建快照失败")
        raise HTTPException(status_code=500, detail=f"创建快照失败: {e}")


@router.post("/snapshots/{snapshot_id}/restore")
async def restore_snapshot(snapshot_id: str, body: RestoreSnapshotBody) -> dict[str, Any]:
    """从快照恢复（覆盖当前集合数据）

    危险操作：当前集合数据会被快照内容替换，需 confirm_token。
    """
    _require_confirm(body.confirm_token)
    chatbot = _get_chatbot_or_403()
    vector_store = chatbot["vector_store"]
    repo = chatbot["repo"]
    # 校验快照存在，避免路径穿越（snapshot_id 不允许含路径分隔符）
    if "/" in snapshot_id or "\\" in snapshot_id or ".." in snapshot_id:
        raise HTTPException(status_code=400, detail="非法快照 ID")
    snapshot_path = _snapshot_dir(vector_store) / snapshot_id
    if not snapshot_path.exists():
        raise HTTPException(status_code=404, detail="快照不存在")
    try:
        await vector_store.restore_from_snapshot(str(snapshot_path))
        _log_audit(repo, "vector_admin.snapshot_restore", snapshot_id)
        return {"ok": True, "restored_from": snapshot_id}
    except Exception as e:
        logger.exception("从快照恢复失败")
        raise HTTPException(status_code=500, detail=f"恢复失败: {e}")


@router.delete("/snapshots/{snapshot_id}")
def delete_snapshot(
    snapshot_id: str,
    confirm_token: str = Query(..., description="必须为 CONFIRM_DELETE"),
) -> dict[str, Any]:
    """删除快照文件（不 affect 当前集合数据）"""
    _require_confirm(confirm_token)
    chatbot = _get_chatbot_or_403()
    vector_store = chatbot["vector_store"]
    repo = chatbot["repo"]
    if "/" in snapshot_id or "\\" in snapshot_id or ".." in snapshot_id:
        raise HTTPException(status_code=400, detail="非法快照 ID")
    snapshot_path = _snapshot_dir(vector_store) / snapshot_id
    if not snapshot_path.exists():
        raise HTTPException(status_code=404, detail="快照不存在")
    try:
        shutil.rmtree(snapshot_path)
        _log_audit(repo, "vector_admin.snapshot_delete", snapshot_id)
        return {"ok": True, "deleted": snapshot_id}
    except Exception as e:
        logger.exception("删除快照失败")
        raise HTTPException(status_code=500, detail=f"删除快照失败: {e}")


# ============== 数据清理 ==============

@router.post("/cleanup/all")
async def cleanup_all(body: CleanupAllBody) -> dict[str, Any]:
    """清空集合（删除并重建 collection）

    危险操作：所有片段将被删除，需 confirm_token。
    通常在 KB 全量重建前调用。
    """
    _require_confirm(body.confirm_token)
    chatbot = _get_chatbot_or_403()
    vector_store = chatbot["vector_store"]
    repo = chatbot["repo"]
    try:
        before = await vector_store.count()
        await vector_store.clear_collection()
        _log_audit(repo, "vector_admin.cleanup_all", f"cleared {before} chunks")
        return {"ok": True, "cleared": before}
    except Exception as e:
        logger.exception("清空集合失败")
        raise HTTPException(status_code=500, detail=f"清空集合失败: {e}")


@router.post("/cleanup/by-source")
async def cleanup_by_source(body: CleanupBySourceBody) -> dict[str, Any]:
    """按来源文件删除片段

    危险操作：需 confirm_token。
    用于删除某个文档对应的所有片段（文档过期/错误导入场景）。
    """
    _require_confirm(body.confirm_token)
    chatbot = _get_chatbot_or_403()
    vector_store = chatbot["vector_store"]
    repo = chatbot["repo"]
    if not body.source_file.strip():
        raise HTTPException(status_code=400, detail="source_file 不能为空")
    try:
        deleted = await vector_store.delete_by_source(body.source_file.strip())
        _log_audit(repo, "vector_admin.cleanup_by_source", f"{body.source_file} ({deleted} chunks)")
        return {"ok": True, "deleted": deleted}
    except Exception as e:
        logger.exception("按来源删除失败")
        raise HTTPException(status_code=500, detail=f"按来源删除失败: {e}")


# ============== 审计日志 ==============

@router.get("/audit-log")
def list_audit_log(limit: int = Query(100, ge=1, le=500)) -> dict[str, Any]:
    """向量库维护审计日志（action 前缀 vector_admin.）

    chatbot_audit_logs 表存储所有 chatbot 相关审计记录，
    这里只返回 vector_admin 前缀的记录。
    """
    chatbot = _get_chatbot_or_403()
    repo = chatbot["repo"]
    # list_audit_logs 不支持前缀过滤，取较多记录后内存过滤
    all_logs = repo.list_audit_logs(action=None, limit=limit * 3)
    items = [log for log in all_logs if log.get("action", "").startswith("vector_admin.")]
    return {"items": items[:limit], "total": len(items)}
