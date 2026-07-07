"""批量采集调度器 API

提供以下端点：
- GET  /api/batch-refresh/status — 当前状态、上次执行时间、结果统计、变更日志
- POST /api/batch-refresh/trigger — 手动触发一次批量采集，返回任务 ID
- PATCH /api/batch-refresh/config — 运行时热更新配置（interval_minutes、enabled）
- POST /api/batch-refresh/pause|resume|stop — 任务控制（立即返回，延迟生效）
- GET  /api/batch-refresh/history — 分页查询执行历史（支持筛选/排序）
- GET  /api/batch-refresh/history/stats — 按 task_id 聚合统计执行次数
- GET  /api/batch-refresh/history/{history_id} — 单条历史详情
- DELETE /api/batch-refresh/history/{history_id} — 删除单条历史
- DELETE /api/batch-refresh/history — 按天数清理过期历史

认证：由 BearerAuthMiddleware 统一处理（/api/batch-refresh/* 不在 PUBLIC_PREFIXES 中），
路由内部不再做 token 校验，避免重复逻辑。
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from xianyu_hunter.container import Container
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.utils import parse_iso_datetime

router = APIRouter(prefix="/api/batch-refresh", tags=["batch-refresh"])


class BatchRefreshConfigPatch(BaseModel):
    """PATCH /config 请求体（所有字段可选）"""
    interval_minutes: int | None = Field(default=None, ge=1, le=1440)
    enabled: bool | None = None


def _get_scheduler():
    """获取调度器实例（延迟导入避免循环依赖）

    调度器实例由 startup.py 在启动时创建并维护为模块级变量。
    """
    from xianyu_hunter.web.startup import get_batch_refresh_scheduler
    return get_batch_refresh_scheduler()


@router.get("/status")
def get_status() -> dict[str, Any]:
    """返回调度器当前状态、上次执行结果和最近变更日志

    调度器未启动时返回 status=unavailable，便于前端区分"未启动"与"空闲"。
    返回字段与 scheduler.get_status() 保持一致，避免前端类型断层。
    """
    scheduler = _get_scheduler()
    if scheduler is None:
        # 调度器未启动时仍从全局 config 读取 enabled/interval_minutes，
        # 让前端能显示配置值；progress/control_available 给默认值避免前端类型断层
        from xianyu_hunter.infra.yaml_config import get_config
        cfg = get_config().batch_refresh
        return {
            "status": "unavailable",
            "last_run_at": None,
            "last_result": None,
            "change_log": [],
            "enabled": cfg.enabled,
            "interval_minutes": cfg.interval_minutes,
            "progress": None,
            "control_available": False,
        }
    return scheduler.get_status()


@router.post("/trigger")
def trigger_batch() -> dict[str, Any]:
    """手动触发一次批量采集

    返回 task_id（正整数）。如果调度器未启动或已有批次在运行，返回 409/503。
    """
    scheduler = _get_scheduler()
    if scheduler is None:
        raise HTTPException(
            status_code=503,
            detail="批量采集调度器未启动（需 XH_WITH_SCHEDULER=1 且 batch_refresh.enabled=true）",
        )
    task_id = scheduler.trigger_now()
    if task_id < 0:
        raise HTTPException(
            status_code=409,
            detail="已有批量采集任务正在运行，请稍后重试",
        )
    return {"ok": True, "task_id": task_id}


@router.patch("/config")
def patch_config(body: BatchRefreshConfigPatch) -> dict[str, Any]:
    """运行时热更新配置

    - interval_minutes: 修改后立即 reschedule 定时任务
    - enabled: False 时立即移除定时 job（停止自动触发），True 时恢复定时 job
    """
    scheduler = _get_scheduler()

    # 调度器未启动时，仍允许更新全局 config 单例，下次启动时生效
    from xianyu_hunter.infra.yaml_config import get_config
    cfg = get_config().batch_refresh

    if body.interval_minutes is not None:
        cfg.interval_minutes = body.interval_minutes
    if body.enabled is not None:
        cfg.enabled = body.enabled

    if scheduler is not None:
        scheduler.update_config(
            interval_minutes=body.interval_minutes,
            enabled=body.enabled,
        )

    return {
        "ok": True,
        "enabled": cfg.enabled,
        "interval_minutes": cfg.interval_minutes,
        "batch_size": cfg.batch_size,
        "max_items_per_run": cfg.max_items_per_run,
    }


# ============== 任务控制端点（pause/resume/stop） ==============
# 三个端点均立即返回（<500ms），实际暂停/停止在当前 item 处理完成后生效。
# 这样保证当前 item 的数据库写入完整，避免数据不一致。


@router.post("/pause")
def pause_batch() -> dict[str, Any]:
    """暂停当前批次

    立即更新状态为 paused 并 clear event，但实际暂停在当前 item 处理完成
    后生效（await event.wait() 阻塞）。
    """
    scheduler = _get_scheduler()
    if scheduler is None:
        raise HTTPException(
            status_code=503,
            detail="批量采集调度器未启动（需 XH_WITH_SCHEDULER=1 且 batch_refresh.enabled=true）",
        )
    if not scheduler.pause():
        raise HTTPException(
            status_code=409,
            detail="当前状态不允许暂停（仅 running 态可暂停）",
        )
    return {"ok": True, "status": "paused"}


@router.post("/resume")
def resume_batch() -> dict[str, Any]:
    """继续执行已暂停的批次"""
    scheduler = _get_scheduler()
    if scheduler is None:
        raise HTTPException(
            status_code=503,
            detail="批量采集调度器未启动",
        )
    if not scheduler.resume():
        raise HTTPException(
            status_code=409,
            detail="当前状态不允许继续（仅 paused 态可继续）",
        )
    return {"ok": True, "status": "running"}


@router.post("/stop")
def stop_batch() -> dict[str, Any]:
    """停止当前批次

    立即更新状态为 stopping 并 set event（解除暂停阻塞），未处理的 items
    会持久化以便下次续传。
    """
    scheduler = _get_scheduler()
    if scheduler is None:
        raise HTTPException(
            status_code=503,
            detail="批量采集调度器未启动",
        )
    if not scheduler.stop_current():
        raise HTTPException(
            status_code=409,
            detail="当前状态不允许停止（仅 running/paused 态可停止）",
        )
    return {"ok": True, "status": "stopping"}


# ============== 任务执行历史端点 ==============
# 与状态/控制端点分工：
# - 上方端点：操作「当前批次」的实时状态
# - 下方端点：查询「历史批次」的执行记录（持久化在 batch_refresh_history 表）


def _serialize_history(row: dict) -> dict:
    """将历史记录 row 序列化为 JSON 友好的响应结构

    - datetime → ISO 字符串
    - error_messages JSON 字符串 → 解析为 list[dict]
    """
    result = dict(row)
    for field in ("started_at", "completed_at", "created_at"):
        v = result.get(field)
        if isinstance(v, str):
            continue  # 已是字符串
        if v is not None:
            result[field] = v.isoformat()
    # error_messages 是 JSON 字符串，解析后前端直接消费
    err = result.get("error_messages")
    if isinstance(err, str) and err:
        try:
            result["error_messages"] = json.loads(err)
        except (json.JSONDecodeError, TypeError):
            # 残留无效 JSON 时降级为空列表，避免前端渲染崩溃
            result["error_messages"] = []
    elif err is None:
        result["error_messages"] = []
    return result


@router.get("/history")
def list_history(
    request: Request,
    task_id: int | None = Query(None, description="按 task_id 精确过滤"),
    status: str | None = Query(
        None, pattern="^(running|completed|cancelled|failed)$",
        description="按状态过滤",
    ),
    trigger_source: str | None = Query(
        None, pattern="^(manual|scheduler)$", description="按触发来源过滤",
    ),
    start: str | None = Query(None, description="起始时间 ISO8601"),
    end: str | None = Query(None, description="结束时间 ISO8601"),
    order_by: str = Query(
        "started_at", pattern="^(started_at|task_id|status|duration_ms)$",
        description="排序字段",
    ),
    order_dir: str = Query("desc", pattern="^(asc|desc)$", description="排序方向"),
    limit: int = Query(20, ge=1, le=200, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """分页查询批量采集执行历史

    支持按 task_id / status / trigger_source / 时间范围过滤，
    支持多字段排序。响应包含 items 列表和 total 总数，供前端分页。
    """
    # 多用户隔离：查询操作用 None
    user_id = getattr(request.state, "user_id", None)
    start_dt = parse_iso_datetime(start) if start else None
    end_dt = parse_iso_datetime(end) if end else None

    items = container.repo.list_batch_refresh_history(
        task_id=task_id,
        status=status,
        trigger_source=trigger_source,
        start_dt=start_dt,
        end_dt=end_dt,
        order_by=order_by,
        order_dir=order_dir,
        limit=limit,
        offset=offset,
        user_id=user_id,
    )
    total = container.repo.count_batch_refresh_history(
        task_id=task_id,
        status=status,
        trigger_source=trigger_source,
        start_dt=start_dt,
        end_dt=end_dt,
        user_id=user_id,
    )
    # 状态聚合：供前端概览卡片展示各状态记录数
    status_counts = container.repo.count_batch_refresh_history_by_status(user_id=user_id)
    return {
        "items": [_serialize_history(it) for it in items],
        "total": total,
        "limit": limit,
        "offset": offset,
        "status_counts": status_counts,
    }


@router.get("/history/stats")
def get_history_stats(
    request: Request,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """按 task_id 聚合统计执行次数

    用于「检查某 task_id 执行过几次」与「最近执行时间」的需求。
    返回 list[{task_id, run_count, last_run_at, total_success, total_failed}]。
    """
    # 多用户隔离：查询操作用 None
    user_id = getattr(request.state, "user_id", None)
    stats = container.repo.count_batch_refresh_history_by_task(user_id=user_id)
    return {"items": stats, "count": len(stats)}


@router.get("/history/{history_id}")
def get_history_detail(
    history_id: int,
    request: Request,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """查询单条历史记录详情（含完整错误消息列表）"""
    # 多用户隔离：查询操作用 None
    user_id = getattr(request.state, "user_id", None)
    row = container.repo.get_batch_refresh_history(history_id, user_id=user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="历史记录不存在")
    return _serialize_history(row)


@router.delete("/history/{history_id}")
def delete_history(
    history_id: int,
    request: Request,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """删除单条历史记录"""
    # 多用户隔离：写入操作用 "default" 兜底
    user_id = getattr(request.state, "user_id", "default")
    ok = container.repo.delete_batch_refresh_history(history_id, user_id=user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="历史记录不存在")
    return {"ok": True}


@router.delete("/history")
def cleanup_history(
    request: Request,
    days: int = Query(..., ge=0, le=3650, description="清理 N 天前的记录，0=清理全部"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """按天数清理过期历史记录

    days=0 时清理全部历史（前端"清空"按钮使用），days>0 时清理 N 天前的记录。
    与启动时自动清理逻辑共用 cleanup_old_batch_refresh_history，days=0 走特殊分支
    直接 DELETE FROM table。
    """
    # 多用户隔离：写入操作用 "default" 兜底
    user_id = getattr(request.state, "user_id", "default")
    if days == 0:
        # 清理全部：直接删除表内所有记录
        # 为什么不分用户：days=0 是全局清空操作，与启动时自动清理逻辑一致
        with container.repo.engine.begin() as conn:
            from xianyu_hunter.infra.db_models import BatchRefreshHistoryRow
            result = conn.execute(BatchRefreshHistoryRow.__table__.delete())
            deleted = result.rowcount
    else:
        deleted = container.repo.cleanup_old_batch_refresh_history(days, user_id=user_id)
    return {"ok": True, "deleted": deleted}
