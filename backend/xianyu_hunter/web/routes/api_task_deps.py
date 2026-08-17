"""任务依赖关系 API（F-16）

支持任务 B 配置"依赖任务 A 成功才启动"，实现组合捡漏。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from xianyu_hunter.container import Container
from xianyu_hunter.web.deps import get_container

router = APIRouter(prefix="/api/tasks", tags=["task-deps"])


class DepBody(BaseModel):
    depends_on: str = Field(..., min_length=1, description="被依赖的上游任务 ID")


@router.post("/{task_id}/deps")
def add_dep(
    task_id: str,
    body: DepBody,
    request: Request,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """添加依赖：task_id 依赖 depends_on 成功后才启动"""
    # 多用户隔离：写入操作用 "default" 兜底
    user_id = getattr(request.state, "user_id", "default")
    # 两个任务都必须存在
    if not container.repo.get_task(task_id, user_id=user_id):
        # S3457: 字符串拼接改 f-string
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    if not container.repo.get_task(body.depends_on, user_id=user_id):
        raise HTTPException(status_code=404, detail=f"被依赖任务不存在: {body.depends_on}")
    if task_id == body.depends_on:
        raise HTTPException(status_code=400, detail="任务不能依赖自身")
    # 循环依赖检测
    if container.repo.check_circular_dep(task_id, body.depends_on):
        raise HTTPException(status_code=400, detail="添加此依赖会形成循环依赖")
    container.repo.add_task_dep(task_id, body.depends_on)
    return {"ok": True, "task_id": task_id, "depends_on": body.depends_on}


@router.delete("/{task_id}/deps")
def remove_dep(
    task_id: str,
    body: DepBody,
    request: Request,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """删除依赖关系"""
    # 多用户隔离：写入操作用 "default" 兜底
    user_id = getattr(request.state, "user_id", "default")
    if not container.repo.get_task(task_id, user_id=user_id):
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    removed = container.repo.remove_task_dep(task_id, body.depends_on)
    if not removed:
        raise HTTPException(status_code=404, detail="依赖关系不存在")
    return {"ok": True, "task_id": task_id, "depends_on": body.depends_on}


@router.get("/{task_id}/deps")
def list_deps(
    task_id: str,
    request: Request,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """列出 task_id 的所有上游依赖"""
    # 多用户隔离：查询操作用 None
    user_id = getattr(request.state, "user_id", None)
    if not container.repo.get_task(task_id, user_id=user_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    deps = container.repo.list_task_deps(task_id)
    # 附带上游任务的名称，方便前端展示
    items = []
    for d in deps:
        upstream = container.repo.get_task(d["depends_on"], user_id=user_id)
        items.append({
            "id": d["id"],
            "depends_on": d["depends_on"],
            "depends_on_name": upstream.get("name", "") if upstream else "(已删除)",
            "created_at": d.get("created_at"),
        })
    return {"task_id": task_id, "deps": items}


@router.get("/{task_id}/dependents")
def list_dependents(
    task_id: str,
    request: Request,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """列出依赖此任务的所有下游任务"""
    # 多用户隔离：查询操作用 None
    user_id = getattr(request.state, "user_id", None)
    if not container.repo.get_task(task_id, user_id=user_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    deps = container.repo.list_dependent_tasks(task_id)
    items = []
    for d in deps:
        downstream = container.repo.get_task(d["task_id"], user_id=user_id)
        items.append({
            "id": d["id"],
            "task_id": d["task_id"],
            "task_name": downstream.get("name", "") if downstream else "(已删除)",
            "created_at": d.get("created_at"),
        })
    return {"task_id": task_id, "dependents": items}
