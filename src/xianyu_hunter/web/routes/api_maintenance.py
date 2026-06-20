"""系统维护 API - 缓存/数据库/日志清理"""
from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from xianyu_hunter.container import Container
from xianyu_hunter.web.deps import get_container

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


class CleanupRequest(BaseModel):
    """清理请求通用模型"""
    target: str = ""  # 清理目标标识
    days: int = 30  # 保留天数（日志/数据库按时间清理时使用）
    dry_run: bool = False  # 仅预览不执行


def _data_dir() -> Path:
    """获取数据目录"""
    return Path("data")


def _log_dir() -> Path:
    """获取日志目录（实际位于 data/logs/）"""
    return Path("data/logs")


# ============== 清理前状态查询 ==============
@router.get("/status")
def maintenance_status(
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """获取系统当前存储状态，供清理前评估"""
    # 数据库表统计
    from sqlalchemy import text
    db_stats = {}
    try:
        with container.repo.engine.connect() as conn:
            for table in ("tasks", "items", "task_links", "events", "orders", "notifications"):
                try:
                    count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                    db_stats[table] = count
                except Exception:
                    db_stats[table] = 0
            # 数据库文件大小
            db_path = _data_dir() / "xianyu.db"
            db_stats["db_size_mb"] = round(db_path.stat().st_size / 1024 / 1024, 2) if db_path.exists() else 0
    except Exception as e:
        logger.warning("获取数据库状态失败: %s", e)

    # 日志文件统计
    log_stats = {"file_count": 0, "total_size_mb": 0, "oldest": None}
    try:
        log_dir = _log_dir()
        if log_dir.exists():
            log_files = list(log_dir.glob("*.log*"))
            log_stats["file_count"] = len(log_files)
            total_size = sum(f.stat().st_size for f in log_files if f.is_file())
            log_stats["total_size_mb"] = round(total_size / 1024 / 1024, 2)
            if log_files:
                oldest = min(f.stat().st_mtime for f in log_files if f.is_file())
                log_stats["oldest"] = datetime.fromtimestamp(oldest).strftime("%Y-%m-%d")
    except Exception:
        pass

    # 缓存统计（浏览器数据目录 + Python 缓存 + 临时文件）
    # 统计范围需与 cleanup_cache 实际清理范围保持一致，避免"显示0MB但清理271项"的不一致
    cache_stats = {
        "browser_data_mb": 0,
        "pycache_mb": 0,
        "pycache_count": 0,
        "temp_files": 0,
    }
    try:
        # 浏览器数据目录
        for d in _data_dir().glob("webview_data_*"):
            if d.is_dir():
                size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
                cache_stats["browser_data_mb"] += round(size / 1024 / 1024, 2)
        # Python __pycache__ 目录（与 cleanup_cache 的清理范围一致）
        pycache_total = 0
        pycache_count = 0
        for p in Path(".").rglob("__pycache__"):
            if p.is_dir():
                pycache_count += 1
                pycache_total += sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        cache_stats["pycache_mb"] = round(pycache_total / 1024 / 1024, 2)
        cache_stats["pycache_count"] = pycache_count
        # 临时文件
        cache_stats["temp_files"] = len(list(Path("/tmp").glob("xianyu_*"))) if Path("/tmp").exists() else 0
    except Exception:
        pass

    return {"db": db_stats, "logs": log_stats, "cache": cache_stats}


# ============== 缓存清理 ==============
@router.post("/cache")
def cleanup_cache(
    req: CleanupRequest,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """清理缓存数据（浏览器数据目录、临时文件）

    target 可选值：
    - browser_data: 清理浏览器数据目录（webview_data_*）
    - temp: 清理临时文件
    - all: 全部清理
    """
    target = req.target or "all"
    cleaned = []
    errors = []

    if target in ("browser_data", "all"):
        try:
            for d in _data_dir().glob("webview_data_*"):
                if d.is_dir():
                    if req.dry_run:
                        cleaned.append(f"[预览] 将删除 {d.name}")
                    else:
                        shutil.rmtree(d, ignore_errors=True)
                        cleaned.append(f"已删除 {d.name}")
        except Exception as e:
            errors.append(f"浏览器数据清理失败: {e}")

    if target in ("temp", "all"):
        try:
            # 清理 Python 缓存文件
            for p in Path(".").rglob("__pycache__"):
                if req.dry_run:
                    cleaned.append(f"[预览] 将删除 {p}")
                else:
                    shutil.rmtree(p, ignore_errors=True)
                    cleaned.append(f"已删除 {p}")
        except Exception as e:
            errors.append(f"临时文件清理失败: {e}")

    # 记录操作日志
    _log_cleanup_action("cache", target, cleaned, errors, container)

    return {
        "target": target,
        "dry_run": req.dry_run,
        "cleaned": cleaned,
        "errors": errors,
        "count": len(cleaned),
    }


# ============== 数据库清理 ==============
@router.post("/database")
def cleanup_database(
    req: CleanupRequest,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """清理数据库冗余数据

    target 可选值：
    - old_events: 清理 N 天前的事件记录
    - old_items: 清理 N 天前未关联的商品记录
    - sold_items: 清理已售商品记录
    - vacuum: VACUUM 压缩数据库
    - all: 以上全部
    """
    from sqlalchemy import text

    target = req.target or "all"
    days = max(1, req.days)
    cutoff = datetime.now() - timedelta(days=days)
    cleaned = []
    errors = []
    total_deleted = 0

    try:
        with container.repo.engine.begin() as conn:
            if target in ("old_events", "all"):
                if req.dry_run:
                    count = conn.execute(
                        text("SELECT COUNT(*) FROM events WHERE created_at < :cutoff"),
                        {"cutoff": cutoff},
                    ).scalar()
                    cleaned.append(f"[预览] 将删除 {count} 条 {days} 天前的事件")
                else:
                    result = conn.execute(
                        text("DELETE FROM events WHERE created_at < :cutoff"),
                        {"cutoff": cutoff},
                    )
                    total_deleted += result.rowcount or 0
                    cleaned.append(f"已删除 {result.rowcount or 0} 条 {days} 天前的事件")

            if target in ("old_items", "all"):
                # 清理 items 表中 N 天前且不在 task_links 中的记录
                if req.dry_run:
                    count = conn.execute(
                        text(
                            "SELECT COUNT(*) FROM items WHERE first_seen < :cutoff "
                            "AND id NOT IN (SELECT link_key FROM task_links WHERE link_type='item')"
                        ),
                        {"cutoff": cutoff},
                    ).scalar()
                    cleaned.append(f"[预览] 将删除 {count} 条 {days} 天前的未关联商品")
                else:
                    result = conn.execute(
                        text(
                            "DELETE FROM items WHERE first_seen < :cutoff "
                            "AND id NOT IN (SELECT link_key FROM task_links WHERE link_type='item')"
                        ),
                        {"cutoff": cutoff},
                    )
                    total_deleted += result.rowcount or 0
                    cleaned.append(f"已删除 {result.rowcount or 0} 条 {days} 天前的未关联商品")

            if target in ("sold_items", "all"):
                # 清理 task_links 中已售商品的 display JSON 含 is_sold=true 的记录
                # 注意：LIKE 模式中的冒号会被 SQLAlchemy 误判为绑定参数，必须用参数化查询
                sold_pattern = '%\"is_sold\":true%'
                if req.dry_run:
                    count = conn.execute(
                        text(
                            "SELECT COUNT(*) FROM task_links WHERE link_type='item' "
                            "AND display LIKE :pattern"
                        ),
                        {"pattern": sold_pattern},
                    ).scalar()
                    cleaned.append(f"[预览] 将删除 {count} 条已售商品关联")
                else:
                    result = conn.execute(
                        text(
                            "DELETE FROM task_links WHERE link_type='item' "
                            "AND display LIKE :pattern"
                        ),
                        {"pattern": sold_pattern},
                    )
                    total_deleted += result.rowcount or 0
                    cleaned.append(f"已删除 {result.rowcount or 0} 条已售商品关联")

            if target in ("vacuum", "all"):
                if req.dry_run:
                    cleaned.append("[预览] 将执行 VACUUM 压缩数据库")
                else:
                    # VACUUM 不能在事务中执行
                    pass

        # VACUUM 需要独立连接（不能在事务中）
        if target in ("vacuum", "all") and not req.dry_run:
            try:
                with container.repo.engine.connect() as conn:
                    conn.execute(text("VACUUM"))
                    cleaned.append("已执行 VACUUM 压缩数据库")
            except Exception as e:
                errors.append(f"VACUUM 失败: {e}")

    except Exception as e:
        errors.append(f"数据库清理失败: {e}")
        logger.exception("数据库清理失败")

    _log_cleanup_action("database", target, cleaned, errors, container)

    return {
        "target": target,
        "days": days,
        "dry_run": req.dry_run,
        "cleaned": cleaned,
        "errors": errors,
        "total_deleted": total_deleted,
    }


# ============== 日志清理 ==============
@router.post("/logs")
def cleanup_logs(
    req: CleanupRequest,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """清理日志文件

    target 可选值：
    - old_logs: 清理 N 天前的日志文件
    - large_logs: 清理超过 10MB 的日志文件
    - all: 全部清理
    """
    target = req.target or "old_logs"
    days = max(1, req.days)
    cutoff = datetime.now() - timedelta(days=days)
    cleaned = []
    errors = []
    total_freed_mb = 0

    log_dir = _log_dir()
    if not log_dir.exists():
        return {
            "target": target,
            "dry_run": req.dry_run,
            "cleaned": [],
            "errors": ["日志目录不存在"],
            "total_freed_mb": 0,
        }

    try:
        for f in log_dir.glob("*.log*"):
            if not f.is_file():
                continue
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            size_mb = f.stat().st_size / 1024 / 1024

            should_delete = False
            if target in ("old_logs", "all") and mtime < cutoff:
                should_delete = True
            elif target in ("large_logs", "all") and size_mb > 10:
                should_delete = True

            if should_delete:
                if req.dry_run:
                    cleaned.append(f"[预览] 将删除 {f.name} ({round(size_mb, 2)}MB, {mtime.strftime('%Y-%m-%d')})")
                else:
                    f.unlink()
                    total_freed_mb += size_mb
                    cleaned.append(f"已删除 {f.name} ({round(size_mb, 2)}MB)")
    except Exception as e:
        errors.append(f"日志清理失败: {e}")

    _log_cleanup_action("logs", target, cleaned, errors, container)

    return {
        "target": target,
        "days": days,
        "dry_run": req.dry_run,
        "cleaned": cleaned,
        "errors": errors,
        "total_freed_mb": round(total_freed_mb, 2),
    }


def _log_cleanup_action(category: str, target: str, cleaned: list, errors: list, container: Container) -> None:
    """将清理操作记录到 events 表，供审计追踪"""
    try:
        container.repo.save_event({
            "type": f"maintenance.{category}",
            "task_id": None,
            "stage": "cleanup",
            "level": "err" if errors else "info",
            "message": f"清理{category}({target}): {len(cleaned)} 项完成" + (f", {len(errors)} 错误" if errors else ""),
            "payload": json.dumps({
                "category": category,
                "target": target,
                "cleaned_count": len(cleaned),
                "error_count": len(errors),
                "cleaned_items": cleaned[:20],
                "errors": errors[:5],
            }, ensure_ascii=False),
        })
    except Exception:
        pass
