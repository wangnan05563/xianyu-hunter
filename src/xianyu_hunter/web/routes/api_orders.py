"""订单 API"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from xianyu_hunter.container import Container
from xianyu_hunter.infra.db_models import _utcnow
from xianyu_hunter.web.deps import get_container

router = APIRouter(prefix="/api/orders", tags=["orders"])

# 人工接管默认超时：30 分钟。
# 为什么 30min：闲鱼"待付款"订单默认 30 分钟自动关闭，
# 留足时间给用户切到 App 完成支付，又不至于无限等待
# 把订单卡在 takeover_pending 让异常雷达"超时"列永远有数据。
TAKEOVER_TIMEOUT_MIN = 30


@router.get("")
def list_orders(
    status: str | None = None,
    limit: int = 100,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    rows = container.repo.list_orders(status=status, limit=limit)
    # 给 takeover_pending 订单附加"剩余倒计时秒数"，前端 modal 直接读 deadline。
    # 为什么不后端算 deadline_at 再返回：少一个字段耦合，deadline_sec 已经够用，
    # 前端按需自己拼 deadline_at 字符串展示。
    now = _utcnow()
    for o in rows:
        if o.get("status") == "takeover_pending":
            ts = o.get("confirmed_at")
            if isinstance(ts, str):
                try:
                    ts_dt = datetime.fromisoformat(ts)
                except ValueError:
                    ts_dt = None
            elif isinstance(ts, datetime):
                ts_dt = ts
            else:
                ts_dt = None
            if ts_dt is not None:
                deadline = ts_dt + timedelta(minutes=TAKEOVER_TIMEOUT_MIN)
                remaining = int((deadline - now).total_seconds())
                o["takeover_deadline"] = deadline.isoformat(timespec="seconds")
                o["takeover_remaining_sec"] = max(0, remaining)
            else:
                o["takeover_deadline"] = None
                o["takeover_remaining_sec"] = None
    # H-05 修复：通知扫描从 list_orders 移至按需端点，避免每次列表请求都触发全量扫描。
    # scan_and_notify 现在仅由 /api/notifications/scan 显式触发或定时任务调用，
    # 不再随订单列表请求自动执行（消除不必要的 DB 开销）。
    return {"items": rows, "count": len(rows)}


@router.get("/{order_id}")
def get_order(
    order_id: str,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    o = container.repo.get_order(order_id)
    if not o:
        raise HTTPException(status_code=404, detail="订单不存在")
    return o


@router.post("/{order_id}/takeover")
def takeover_order(
    order_id: str,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """人工接管：把订单状态置为 takeover_pending，等待用户在闲鱼 App 手动支付。

    - 复用 upsert_order 写库，但只写 OrderRow 实际存在的列。
    - confirmed_at 记录"用户已确认接管"的时间点。
    - 返回 deadline 让前端 modal 启动倒计时，无需再拉一次详情。
    """
    o = container.repo.get_order(order_id)
    if not o:
        raise HTTPException(status_code=404, detail="订单不存在")
    if o.get("status") in ("succeeded", "failed"):
        raise HTTPException(
            status_code=409,
            detail=f"订单已 {o['status']}，无法接管",
        )
    now = _utcnow()
    o["status"] = "takeover_pending"
    # 写库用 datetime（SQLAlchemy DateTime 字段不接受 string），
    # 返回时再把字符串给前端，避免污染其他读取方。
    o["confirmed_at"] = now
    container.repo.upsert_order(o)
    deadline = now + timedelta(minutes=TAKEOVER_TIMEOUT_MIN)
    return {
        "ok": True,
        "id": order_id,
        "status": "takeover_pending",
        "takeover_at": now.isoformat(timespec="seconds"),
        "takeover_deadline": deadline.isoformat(timespec="seconds"),
        "timeout_min": TAKEOVER_TIMEOUT_MIN,
    }


@router.post("/{order_id}/takeover/confirm")
def takeover_confirm(
    order_id: str,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """用户反馈"已在闲鱼 App 完成支付"，把订单标记为 succeeded。

    状态机：takeover_pending → succeeded
    """
    o = container.repo.get_order(order_id)
    if not o:
        raise HTTPException(status_code=404, detail="订单不存在")
    if o.get("status") != "takeover_pending":
        raise HTTPException(
            status_code=409,
            detail=f"订单当前状态 {o.get('status')}，不能确认支付（仅 takeover_pending 可确认）",
        )
    now = _utcnow()
    o["status"] = "succeeded"
    o["paid_at"] = now
    container.repo.upsert_order(o)
    # F-16：订单成功后触发下游依赖任务
    _trigger_dependent_tasks(container, o)
    return {"ok": True, "id": order_id, "status": "succeeded", "paid_at": now.isoformat(timespec="seconds")}


@router.post("/{order_id}/takeover/cancel")
def takeover_cancel(
    order_id: str,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """用户放弃接管：把订单状态回退到 pending，清空 confirmed_at。

    设计选择：保留订单而非删除。
    1) 用户可能只是误点；2) 留作审计；3) 避免数据丢失。
    """
    o = container.repo.get_order(order_id)
    if not o:
        raise HTTPException(status_code=404, detail="订单不存在")
    if o.get("status") != "takeover_pending":
        raise HTTPException(
            status_code=409,
            detail=f"订单当前状态 {o.get('status')}，不能取消接管（仅 takeover_pending 可取消）",
        )
    o["status"] = "pending"
    o["confirmed_at"] = None
    container.repo.upsert_order(o)
    return {"ok": True, "id": order_id, "status": "pending"}


def _trigger_dependent_tasks(container: Container, order: dict) -> None:
    """F-16：订单成功后，检查是否有下游任务依赖此订单所属任务，自动激活它们

    触发条件：
    1. 订单状态变为 succeeded
    2. 订单关联了一个 task_id（通过 item_id 反查 items 表）
    3. 该 task_id 有下游依赖任务
    4. 下游任务当前状态为 paused（等待上游成功）

    只改 DB 状态；如果 run 进程在运行，它会在下次轮询时读取新状态。
    """
    from loguru import logger

    item_id = order.get("item_id", "")
    if not item_id:
        return

    # 从 item 反查 task_id
    item = container.repo.get_item(item_id)
    if not item or not item.get("task_id"):
        return

    upstream_task_id = item["task_id"]

    # 查询所有依赖此任务的下游任务
    dependents = container.repo.list_dependent_tasks(upstream_task_id)
    if not dependents:
        return

    for dep in dependents:
        downstream_task_id = dep["task_id"]
        downstream_task = container.repo.get_task(downstream_task_id)
        if not downstream_task:
            continue
        # 仅 paused 状态的下游任务需要激活（其他状态保持不变）
        if downstream_task.get("status") != "paused":
            logger.info(
                f"[F-16] 下游任务 {downstream_task_id} 状态为 {downstream_task.get('status')}，跳过激活"
            )
            continue

        container.repo.update_task_status(downstream_task_id, "running")
        # 记录事件，方便追溯"谁触发了谁"
        container.repo.save_event({
            "task_id": downstream_task_id,
            "stage": "dep_triggered",
            "level": "info",
            "message": f"上游任务 {upstream_task_id} 订单成功，自动激活下游任务",
            "payload": f'{{"upstream_task": "{upstream_task_id}", "order_id": "{order.get("id", "")}", "triggered_by": "dep_chain"}}',
        })
        logger.info(
            f"[F-16] 上游任务 {upstream_task_id} 订单成功 → 自动激活下游任务 {downstream_task_id}"
        )
