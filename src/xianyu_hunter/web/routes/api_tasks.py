"""任务 API - 增删改查、启停控制"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from xianyu_hunter.domain.task import TaskMode
from xianyu_hunter.container import Container
from xianyu_hunter.web.deps import get_container

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class TaskCreate(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=80)
    name: str = ""
    min_price: float | None = None
    max_price: float | None = None
    # 仅展示最近 N 天内发布的商品（None 表示不过滤）
    max_publish_days: int | None = None
    mode: str = "notify"
    region: str | None = None
    exclude_words: list[str] = []
    # 闲鱼筛选标签（与 goofish.com 搜索页复选框一致）
    # 可选值：personal_idle, verified, account_guarantee, free_shipping,
    #         super_shop, brand_new, strict_select, resale
    search_filters: list[str] = []


class TaskUpdate(BaseModel):
    name: str | None = None
    keyword: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    max_publish_days: int | None = None
    mode: str | None = None
    status: str | None = None
    region: str | None = None
    # 与 TaskCreate 对齐：允许编辑闲鱼筛选标签和排除词（JSON 序列化存入 DB）
    search_filters: list[str] | None = None
    exclude_words: list[str] | None = None


@router.get("")
def list_tasks(
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """列出任务；支持 status 过滤 + limit/offset 分页。

    - 默认 limit=50：百级任务列表一次性够用，避免前端渲染 1k+ 节点
    - 客户端渲染器会自己再细分页（前端 pageSize=20）
    - 同时返回 total 字段，前端用来算总页数
    """
    # 防滥用：限制 limit 上限，避免一次性拉 1w 行拖垮 sqlite
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    # repo 层已默认排除 deleted 任务，统一由 SQL 层过滤以保证 limit/offset 准确性
    effective_status = status
    rows = container.repo.list_tasks_with_last_seen(status=effective_status, limit=limit, offset=offset)
    total = container.repo.count_tasks(status=effective_status)
    return {
        "items": rows,
        "count": len(rows),
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("")
def create_task(
    body: TaskCreate,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    if body.min_price is not None and body.max_price is not None and body.min_price > body.max_price:
        raise HTTPException(status_code=400, detail="min_price 不能大于 max_price")
    try:
        mode = TaskMode(body.mode)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"未知 mode: {body.mode}")
    tid = f"t{uuid.uuid4().hex[:8]}"
    task = {
        "id": tid,
        "name": body.name or body.keyword,
        "keyword": body.keyword,
        "min_price": body.min_price,
        "max_price": body.max_price,
        "max_publish_days": body.max_publish_days,
        "mode": mode.value,
        "region": body.region,
        "exclude_words": json.dumps(body.exclude_words, ensure_ascii=False),
        "search_filters": json.dumps(body.search_filters, ensure_ascii=False),
    }
    container.repo.upsert_task(task)
    return {"ok": True, "id": tid, "task": task}


@router.get("/{task_id}")
def get_task(
    task_id: str,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    t = container.repo.get_task(task_id)
    if not t:
        raise HTTPException(status_code=404, detail="任务不存在")
    return t


@router.patch("/{task_id}")
def update_task(
    task_id: str,
    body: TaskUpdate,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    t = container.repo.get_task(task_id)
    if not t:
        raise HTTPException(status_code=404, detail="任务不存在")
    updates = body.model_dump(exclude_none=True)
    if "mode" in updates:
        try:
            updates["mode"] = TaskMode(updates["mode"]).value
        except ValueError:
            raise HTTPException(status_code=400, detail=f"未知 mode: {updates['mode']}")
    # search_filters 和 exclude_words 需 JSON 序列化后存入 DB（与 create_task 保持一致）
    if "search_filters" in updates:
        updates["search_filters"] = json.dumps(updates["search_filters"], ensure_ascii=False)
    if "exclude_words" in updates:
        updates["exclude_words"] = json.dumps(updates["exclude_words"], ensure_ascii=False)
    t.update(updates)
    container.repo.upsert_task(t)
    return {"ok": True, "task": t}


@router.delete("/{task_id}")
def delete_task(
    task_id: str,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """删除任务及所有关联数据（task_links、items、events、orders、deps）

    不再使用软删除，直接物理删除避免垃圾数据积累。
    """
    t = container.repo.get_task(task_id)
    if not t:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 级联删除所有关联数据
    cascade = container.repo.delete_task_cascade(task_id)

    # 最后删除任务本身
    container.repo.update_task_status(task_id, "deleted")

    return {
        "ok": True,
        "id": task_id,
        "cascade": cascade,
    }


@router.get("/{task_id}/runs")
def get_task_runs(
    task_id: str,
    range_hours: int = 24,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """F-09 任务运行历史：按时间窗聚合 events 表中的运行记录

    返回格式：
    {
        "task_id": "t1234",
        "runs": [
            {
                "start": "2026-06-08T10:00:00",
                "end": "2026-06-08T10:05:00",
                "event_count": 12,
                "hit_count": 3,
                "err_count": 0,
                "warn_count": 1,
                "duration_s": 12.5,
                "first_event_type": "search"
            }
        ],
        "idle_gaps": [
            {"from": "...", "to": "...", "duration_s": 2700}
        ],
        "total_runs": 5,
        "total_events": 60,
        "total_hits": 15
    }

    参数约束：
    - range_hours: 1~720（1 小时到 30 天），超出返回 422
    """
    # 参数校验
    if range_hours < 1 or range_hours > 720:
        raise HTTPException(status_code=422, detail="range_hours 须在 1~720 之间")
    # 任务存在性校验
    t = container.repo.get_task(task_id)
    if not t:
        raise HTTPException(status_code=404, detail="任务不存在")
    return container.repo.get_task_runs(task_id, range_hours=range_hours)


@router.post("/{task_id}/control")
def control_task(
    task_id: str,
    action: str = "pause",
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """控制任务：pause / resume / stop / restart

    注意：Web 进程无法直接控制 run 进程内的 scheduler 内存对象。
    这里只改 DB 中的 status 字段，run 进程下次重启会读取新状态。
    """
    t = container.repo.get_task(task_id)
    if not t:
        raise HTTPException(status_code=404, detail="任务不存在")
    valid = {"pause": "paused", "resume": "running", "stop": "stopped", "restart": "running"}
    if action not in valid:
        raise HTTPException(status_code=400, detail=f"未知 action: {action}")
    new_status = valid[action]
    container.repo.update_task_status(task_id, new_status)
    return {
        "ok": True,
        "id": task_id,
        "status": new_status,
        "note": "状态已写入数据库；如需立即生效请重启 run 调度器",
    }


# ============== F-03 任务批量控制 ==============
class BatchControlBody(BaseModel):
    """批量操作入参：task_ids + action

    action 取值与单任务 control 一致：pause / resume / stop / restart / delete
    - delete 走"软删除"路径：status='deleted'，与单任务 DELETE 行为对齐
    """
    task_ids: list[str] = Field(..., min_length=1, max_length=200)
    action: str = Field(..., description="pause/resume/stop/restart/delete")


@router.post("/batch-control")
def batch_control_tasks(
    body: BatchControlBody,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """批量控制任务（F-03）：N 个任务一次完成 1 个动作

    设计要点：
    - 不抛错"中断整批"：单个任务失败（如不存在）只影响 successes/failures 计数，整体请求仍返回 200
    - 原因：用户选了 5 个任务，其中 1 个被别人删了，剩下 4 个必须还能成功
    - 失败原因存到 results[].reason，前端可下钻展示
    - 上限 200 个：避免前端"全选 1k 任务"瞬间打爆 DB
    """
    valid = {"pause": "paused", "resume": "running", "stop": "stopped", "restart": "running", "delete": "deleted"}
    if body.action not in valid:
        raise HTTPException(status_code=400, detail=f"未知 action: {body.action}")
    new_status = valid[body.action]
    successes: list[str] = []
    failures: list[dict[str, str]] = []
    for tid in body.task_ids:
        try:
            t = container.repo.get_task(tid)
            if not t:
                failures.append({"id": tid, "reason": "not_found"})
                continue
            if body.action == "delete":
                container.repo.delete_task_cascade(tid)
                container.repo.update_task_status(tid, "deleted")
            else:
                container.repo.update_task_status(tid, new_status)
            successes.append(tid)
        except Exception as e:
            failures.append({"id": tid, "reason": str(e)[:120]})
    return {
        "ok": True,
        "action": body.action,
        "new_status": new_status,
        "success_count": len(successes),
        "failure_count": len(failures),
        "successes": successes,
        "failures": failures,
    }
