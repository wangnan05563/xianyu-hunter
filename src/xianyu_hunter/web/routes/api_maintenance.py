"""系统维护 API - 缓存/数据库/日志清理"""
from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from xianyu_hunter.container import Container
from xianyu_hunter.paths import get_data_dir, get_log_dir
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
    return get_data_dir()


def _log_dir() -> Path:
    """获取日志目录（实际位于 data/logs/）"""
    return get_log_dir()


# 扫描 __pycache__ 时排除的目录：这些目录下的缓存不应被统计/清理
# .venv: 第三方依赖缓存，清理后首次导入变慢且无意义
# node_modules / dist / build: 前端依赖与构建产物
# .git: 版本控制元数据
# data: 运行时数据（chromadb 向量库等）
_EXCLUDE_SCAN_DIRS = frozenset({
    ".venv", "node_modules", ".git", "data",
    "dist", "build", "target", ".cache",
    "__pycache__",  # os.walk 进入 __pycache__ 内部无意义
})


def _iter_pycache_dirs(root: Path = Path(".")) -> list[Path]:
    """遍历项目源码目录下的 __pycache__，排除第三方依赖目录

    用 os.walk 而非 Path.rglob：os.walk 可在遍历时剪枝（修改 dirs[:]），
    避免 .venv（含数千个子目录）的无效遍历，将扫描时间从 30s+ 降至 <0.1s
    """
    result: list[Path] = []
    for dirpath, dirnames, _ in os.walk(str(root)):
        # 原地剪枝：跳过排除目录，避免递归进入 .venv 等
        dirnames[:] = [d for d in dirnames if d not in _EXCLUDE_SCAN_DIRS]
        if "__pycache__" in dirnames:
            result.append(Path(dirpath) / "__pycache__")
    return result


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
        for p in _iter_pycache_dirs():
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
def _cleanup_browser_data(dry_run: bool, cleaned: list, errors: list) -> None:
    """清理浏览器数据目录（webview_data_*）

    浏览器数据目录存放反检测指纹/cookies，清理后首次启动会重新生成。
    dry_run 模式只列出不删除。
    """
    try:
        for d in _data_dir().glob("webview_data_*"):
            if d.is_dir():
                if dry_run:
                    cleaned.append(f"[预览] 将删除 {d.name}")
                else:
                    shutil.rmtree(d, ignore_errors=True)
                    cleaned.append(f"已删除 {d.name}")
    except Exception as e:
        errors.append(f"浏览器数据清理失败: {e}")


def _cleanup_pycache(dry_run: bool, cleaned: list, errors: list) -> None:
    """清理 Python __pycache__ 缓存（仅项目源码目录）

    排除 .venv 等第三方依赖目录（由 _iter_pycache_dirs 处理），
    清理后首次导入会重新编译 .pyc，不影响功能。
    """
    try:
        for p in _iter_pycache_dirs():
            if dry_run:
                cleaned.append(f"[预览] 将删除 {p}")
            else:
                shutil.rmtree(p, ignore_errors=True)
                cleaned.append(f"已删除 {p}")
    except Exception as e:
        errors.append(f"临时文件清理失败: {e}")


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
        _cleanup_browser_data(req.dry_run, cleaned, errors)

    if target in ("temp", "all"):
        _cleanup_pycache(req.dry_run, cleaned, errors)

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
def _cleanup_old_events(conn, dry_run: bool, days: int, cutoff: datetime, cleaned: list) -> int:
    """清理 events 表中 N 天前的记录

    dry_run 模式只统计不删除，返回 0；非 dry_run 返回实际删除行数。
    cleaned 列表通过引用修改，追加预览/删除消息。
    """
    from sqlalchemy import text
    if dry_run:
        count = conn.execute(
            text("SELECT COUNT(*) FROM events WHERE created_at < :cutoff"),
            {"cutoff": cutoff},
        ).scalar()
        cleaned.append(f"[预览] 将删除 {count} 条 {days} 天前的事件")
        return 0
    result = conn.execute(
        text("DELETE FROM events WHERE created_at < :cutoff"),
        {"cutoff": cutoff},
    )
    deleted = result.rowcount or 0
    cleaned.append(f"已删除 {deleted} 条 {days} 天前的事件")
    return deleted


def _cleanup_old_items(conn, dry_run: bool, days: int, cutoff: datetime, cleaned: list) -> int:
    """清理 items 表中 N 天前且未关联 task_links 的记录

    排除已关联商品避免删掉用户仍在监控的数据；
    dry_run 模式只统计不删除。
    """
    from sqlalchemy import text
    # 关联检查子查询：排除仍在 task_links 中的商品
    not_linked = "AND id NOT IN (SELECT link_key FROM task_links WHERE link_type='item')"
    if dry_run:
        count = conn.execute(
            text(f"SELECT COUNT(*) FROM items WHERE first_seen < :cutoff {not_linked}"),
            {"cutoff": cutoff},
        ).scalar()
        cleaned.append(f"[预览] 将删除 {count} 条 {days} 天前的未关联商品")
        return 0
    result = conn.execute(
        text(f"DELETE FROM items WHERE first_seen < :cutoff {not_linked}"),
        {"cutoff": cutoff},
    )
    deleted = result.rowcount or 0
    cleaned.append(f"已删除 {deleted} 条 {days} 天前的未关联商品")
    return deleted


def _cleanup_sold_items(conn, dry_run: bool, cleaned: list) -> int:
    """清理 task_links 中已售商品关联（display JSON 含 is_sold=true）

    注意：LIKE 模式中的冒号会被 SQLAlchemy 误判为绑定参数，必须用参数化查询。
    """
    from sqlalchemy import text
    # display 字段是 JSON 字符串，匹配 "is_sold":true
    sold_pattern = '%\"is_sold\":true%'
    if dry_run:
        count = conn.execute(
            text(
                "SELECT COUNT(*) FROM task_links WHERE link_type='item' "
                "AND display LIKE :pattern"
            ),
            {"pattern": sold_pattern},
        ).scalar()
        cleaned.append(f"[预览] 将删除 {count} 条已售商品关联")
        return 0
    result = conn.execute(
        text(
            "DELETE FROM task_links WHERE link_type='item' "
            "AND display LIKE :pattern"
        ),
        {"pattern": sold_pattern},
    )
    deleted = result.rowcount or 0
    cleaned.append(f"已删除 {deleted} 条已售商品关联")
    return deleted


def _vacuum_database(engine, dry_run: bool, cleaned: list, errors: list) -> None:
    """执行 VACUUM 压缩数据库

    VACUUM 不能在事务中执行，需通过 execution_options(isolation_level="AUTOCOMMIT")
    显式关闭 SQLAlchemy 2.0 的隐式事务。
    """
    from sqlalchemy import text
    if dry_run:
        cleaned.append("[预览] 将执行 VACUUM 压缩数据库")
        return
    try:
        with engine.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as conn:
            conn.execute(text("VACUUM"))
            cleaned.append("已执行 VACUUM 压缩数据库")
    except Exception as e:
        errors.append(f"VACUUM 失败: {e}")


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
                total_deleted += _cleanup_old_events(conn, req.dry_run, days, cutoff, cleaned)

            if target in ("old_items", "all"):
                total_deleted += _cleanup_old_items(conn, req.dry_run, days, cutoff, cleaned)

            if target in ("sold_items", "all"):
                total_deleted += _cleanup_sold_items(conn, req.dry_run, cleaned)

            if target in ("vacuum", "all"):
                if req.dry_run:
                    cleaned.append("[预览] 将执行 VACUUM 压缩数据库")
                else:
                    # VACUUM 不能在事务中执行
                    pass

        # VACUUM 必须在 AUTOCOMMIT 模式下执行（不能在事务中）
        # SQLAlchemy 2.0 的 engine.connect() 默认开启隐式事务，
        # 需通过 execution_options(isolation_level="AUTOCOMMIT") 显式关闭事务
        if target in ("vacuum", "all") and not req.dry_run:
            _vacuum_database(container.repo.engine, False, cleaned, errors)

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

            # S1871: 两个分支都设置 should_delete=True，合并条件简化逻辑
            should_delete = (
                (target in ("old_logs", "all") and mtime < cutoff)
                or (target in ("large_logs", "all") and size_mb > 10)
            )

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
