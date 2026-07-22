"""订单 API"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from xianyu_hunter.container import Container
from xianyu_hunter.infra.db_models import _utcnow
from xianyu_hunter.web.deps import get_container

router = APIRouter(prefix="/api/orders", tags=["orders"])

# 人工接管超时：从 YAML 配置 buyer.takeover_timeout_min 读取，默认 30 分钟。
# 为什么 30min：闲鱼"待付款"订单默认 30 分钟自动关闭，
# 留足时间给用户切到 App 完成支付，又不至于无限等待
# 把订单卡在 takeover_pending 让异常雷达"超时"列永远有数据。
def _get_takeover_timeout_min() -> int:
    """从全局配置读取人工接管超时（分钟）

    每次调用实时读取：用户可在前端修改后立即生效，无需重启。
    """
    from xianyu_hunter.infra.yaml_config import get_config
    return get_config().buyer.takeover_timeout_min


# S1192: 提取重复的错误消息常量
_ORDER_NOT_FOUND = "订单不存在"


def _parse_takeover_ts(ts: Any) -> datetime | None:
    """把 confirmed_at 多种存储形态统一解析为 datetime，None 表示无法解析

    SQLite 同一列可能返回 ISO 字符串、datetime 对象或空值，
    集中处理避免每个调用点重复 isinstance + try/except 拉高认知复杂度。
    """
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts)
        except ValueError:
            return None
    if isinstance(ts, datetime):
        return ts
    return None


def _apply_takeover_deadline(o: dict, now: datetime) -> None:
    """为 takeover_pending 订单附加 deadline/remaining_sec 两个字段

    SQLite 读回的 confirmed_at 是 naive datetime，_utcnow() 须同步去时区，
    否则 deadline(naive) - now(aware) 会抛 TypeError（与 repo_chatbot.recall_message 同根因）。
    为什么不后端算 deadline_at 再返回：少一个字段耦合，deadline_sec 已经够用，
    前端按需自己拼 deadline_at 字符串展示。
    """
    ts_dt = _parse_takeover_ts(o.get("confirmed_at"))
    if ts_dt is not None:
        deadline = ts_dt + timedelta(minutes=_get_takeover_timeout_min())
        remaining = int((deadline - now).total_seconds())
        o["takeover_deadline"] = deadline.isoformat(timespec="seconds")
        o["takeover_remaining_sec"] = max(0, remaining)
    else:
        o["takeover_deadline"] = None
        o["takeover_remaining_sec"] = None


@router.get("")
def list_orders(
    request: Request,
    status: str | None = None,
    limit: int = 100,
    page_num: int = Query(1, ge=1, description="页码（从1开始）"),
    page_size: int = Query(20, ge=1, le=200, description="每页条数"),
    task_id: str | None = Query(None, description="任务 ID 精确匹配"),
    item_id: str | None = Query(None, description="商品 ID 精确匹配"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    # 后端分页：page_num/page_size 优先于 limit（limit 为旧版兼容参数）
    # 当使用分页参数时，offset 由 page_num 计算；否则用旧版 limit 直出
    use_pagination = page_num > 1 or page_size != 20
    if use_pagination:
        offset = (page_num - 1) * page_size
        actual_limit = page_size
    else:
        offset = 0
        actual_limit = limit

    # 多用户隔离：仅查询当前账号的订单
    user_id = getattr(request.state, "user_id", None)
    rows = container.repo.list_orders(
        status=status, limit=actual_limit, offset=offset,
        task_id=task_id, item_id=item_id, user_id=user_id,
    )
    total = container.repo.count_orders(status=status, task_id=task_id, item_id=item_id, user_id=user_id)

    # 给 takeover_pending 订单附加"剩余倒计时秒数"，前端 modal 直接读 deadline。
    now = _utcnow().replace(tzinfo=None)
    for o in rows:
        if o.get("status") == "takeover_pending":
            _apply_takeover_deadline(o, now)
    # H-05 修复：通知扫描从 list_orders 移至按需端点，避免每次列表请求都触发全量扫描。
    # scan_and_notify 现在仅由 /api/notifications/scan 显式触发或定时任务调用，
    # 不再随订单列表请求自动执行（消除不必要的 DB 开销）。
    return {"items": rows, "count": len(rows), "total": total}


@router.get("/{order_id}")
def get_order(
    order_id: str,
    request: Request,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    # 多用户隔离：仅查询当前账号的订单
    user_id = getattr(request.state, "user_id", None)
    o = container.repo.get_order(order_id, user_id=user_id)
    if not o:
        raise HTTPException(status_code=404, detail=_ORDER_NOT_FOUND)
    return o


@router.delete("/{order_id}")
def delete_order(
    order_id: str,
    request: Request,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """删除订单记录

    为什么允许删除而非仅软删除：
    1. 失败/测试订单无审计价值，用户需要清理
    2. 删除后 buyer._task_item_set 仍在内存中（进程未重启时幂等仍生效）
    3. DB 层 hard delete 保持简单，与 delete_orders_by_task 一致
    """
    # 多用户隔离：写入操作用 "default" 兜底
    user_id = getattr(request.state, "user_id", "default")
    deleted = container.repo.delete_order_by_id(order_id, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=_ORDER_NOT_FOUND)
    return {"ok": True, "id": order_id, "deleted": deleted}


@router.post("/{order_id}/takeover")
def takeover_order(
    order_id: str,
    request: Request,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """人工接管：把订单状态置为 takeover_pending，等待用户在闲鱼 App 手动支付。

    - 复用 upsert_order 写库，但只写 OrderRow 实际存在的列。
    - confirmed_at 记录"用户已确认接管"的时间点。
    - 返回 deadline 让前端 modal 启动倒计时，无需再拉一次详情。

    状态机白名单：仅 pending_pay 可被接管。
    - 拒绝 takeover_pending → takeover_pending：避免用户无限点击重置 30 分钟倒计时，
      违背"30 分钟内必须完成支付"的业务约束
    - 拒绝 succeeded/failed/cancelled → takeover_pending：终态订单不可复活
    - 用户若需重新接管已 cancel 的订单，需先确保状态回退到 pending_pay
    """
    # 多用户隔离：写入操作用 "default" 兜底
    user_id = getattr(request.state, "user_id", "default")
    o = container.repo.get_order(order_id, user_id=user_id)
    if not o:
        raise HTTPException(status_code=404, detail=_ORDER_NOT_FOUND)
    current_status = o.get("status")
    if current_status != "pending_pay":
        raise HTTPException(
            status_code=409,
            detail=(
                f"订单当前状态 {current_status}，无法接管（仅 pending_pay 可接管）。"
                f"如需重新接管，请先通过状态修改回退到 pending_pay"
            ),
        )
    now = _utcnow()
    o["status"] = "takeover_pending"
    # 写库用 datetime（SQLAlchemy DateTime 字段不接受 string），
    # 返回时再把字符串给前端，避免污染其他读取方。
    o["confirmed_at"] = now
    container.repo.upsert_order(o, user_id=user_id)
    timeout_min = _get_takeover_timeout_min()
    deadline = now + timedelta(minutes=timeout_min)
    return {
        "ok": True,
        "id": order_id,
        "status": "takeover_pending",
        "takeover_at": now.isoformat(timespec="seconds"),
        "takeover_deadline": deadline.isoformat(timespec="seconds"),
        "timeout_min": timeout_min,
    }


@router.post("/{order_id}/takeover/confirm")
def takeover_confirm(
    order_id: str,
    request: Request,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """用户反馈"已在闲鱼 App 完成支付"，把订单标记为 succeeded。

    状态机：takeover_pending → succeeded
    """
    # 多用户隔离：写入操作用 "default" 兜底
    user_id = getattr(request.state, "user_id", "default")
    o = container.repo.get_order(order_id, user_id=user_id)
    if not o:
        raise HTTPException(status_code=404, detail=_ORDER_NOT_FOUND)
    if o.get("status") != "takeover_pending":
        raise HTTPException(
            status_code=409,
            detail=f"订单当前状态 {o.get('status')}，不能确认支付（仅 takeover_pending 可确认）",
        )
    now = _utcnow()
    o["status"] = "succeeded"
    o["paid_at"] = now
    container.repo.upsert_order(o, user_id=user_id)
    # F-16：订单成功后触发下游依赖任务
    _trigger_dependent_tasks(container, o, user_id=user_id)
    return {"ok": True, "id": order_id, "status": "succeeded", "paid_at": now.isoformat(timespec="seconds")}


@router.post("/{order_id}/takeover/cancel")
def takeover_cancel(
    order_id: str,
    request: Request,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """用户放弃接管：把订单状态回退到 pending，清空 confirmed_at。

    设计选择：保留订单而非删除。
    1) 用户可能只是误点；2) 留作审计；3) 避免数据丢失。
    """
    # 多用户隔离：写入操作用 "default" 兜底
    user_id = getattr(request.state, "user_id", "default")
    o = container.repo.get_order(order_id, user_id=user_id)
    if not o:
        raise HTTPException(status_code=404, detail=_ORDER_NOT_FOUND)
    if o.get("status") != "takeover_pending":
        raise HTTPException(
            status_code=409,
            detail=f"订单当前状态 {o.get('status')}，不能取消接管（仅 takeover_pending 可取消）",
        )
    o["status"] = "pending_pay"
    o["confirmed_at"] = None
    container.repo.upsert_order(o, user_id=user_id)
    return {"ok": True, "id": order_id, "status": "pending_pay"}


@router.patch("/{order_id}/status")
def update_order_status(
    order_id: str,
    payload: dict[str, Any],
    request: Request,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """修改订单状态

    用户在闲鱼官网完成支付后，可手动将订单从 pending_pay 改为 succeeded。
    评估明细页面的 order_status 实时关联 orders 表，状态会自动联动更新。

    支持的目标状态：pending_pay / succeeded / cancelled / failed
    """
    new_status = str(payload.get("status") or "").strip()
    # takeover_pending 是流程中间态，不允许手动设置（必须走 takeover 端点）
    valid_statuses = {"pending_pay", "succeeded", "cancelled", "failed"}
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=422,
            detail=f"无效状态值: {new_status}，允许: {', '.join(sorted(valid_statuses))}",
        )

    # 多用户隔离：写入操作用 "default" 兜底
    user_id = getattr(request.state, "user_id", "default")
    o = container.repo.get_order(order_id, user_id=user_id)
    if not o:
        raise HTTPException(status_code=404, detail=_ORDER_NOT_FOUND)

    old_status = o.get("status", "")
    if old_status == new_status:
        return {"ok": True, "id": order_id, "old_status": old_status, "new_status": new_status, "changed": False}

    o["status"] = new_status
    # succeeded 时记录支付时间，与 takeover_confirm 行为一致
    if new_status == "succeeded":
        o["paid_at"] = _utcnow()
    container.repo.upsert_order(o, user_id=user_id)

    # 状态变为 succeeded 时触发下游依赖任务（与 takeover_confirm 一致）
    if new_status == "succeeded" and old_status != "succeeded":
        _trigger_dependent_tasks(container, o, user_id=user_id)

    return {"ok": True, "id": order_id, "old_status": old_status, "new_status": new_status, "changed": True}


def _trigger_dependent_tasks(container: Container, order: dict, user_id: str | None = None) -> None:
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
    item = container.repo.get_item(item_id, user_id=user_id)
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

        container.repo.update_task_status(downstream_task_id, "running", user_id=user_id or "default")
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


def _parse_takeover_payload(payload: dict[str, Any]) -> tuple[str, str]:
    """提取并校验 item_id/task_id，返回 (item_id, task_id)"""
    item_id = str(payload.get("item_id") or "").strip()
    task_id = str(payload.get("task_id") or "").strip()
    if not item_id:
        raise HTTPException(status_code=422, detail="item_id 不能为空")
    return item_id, task_id


def _ensure_takeover_prerequisites(container: Container) -> None:
    """前置校验：buyer 注入态 + 闲鱼登录态，任一缺失直接抛 HTTPException

    未登录时点击「立即购买」会跳转到登录页，导致找不到「提交订单」按钮，
    浪费一次浏览器自动化流程，因此在抢单前就拦截。
    """
    # 检查 buyer 是否注入：Web 进程默认 with_browser=False，buyer 为 None
    if container.buyer is None:
        raise HTTPException(
            status_code=503,
            detail="抢单功能未启用：需要以 XH_WITH_SCHEDULER=1 模式启动服务以注入浏览器实例",
        )

    from xianyu_hunter.web.services.cookie_store import get_cookie_store

    cookie_store = get_cookie_store()
    cookie_store.invalidate_cache()
    if not cookie_store.has_valid_cookies():
        raise HTTPException(
            status_code=403,
            detail="闲鱼登录已过期，请先在「Cookie 注入」页面重新登录闲鱼",
        )


def _resolve_takeover_item(
    container: Container, item_id: str, task_id: str, user_id: str | None = None,
) -> tuple[float, str]:
    """查询商品并补全 task_id，返回 (expected_price, resolved_task_id)"""
    item = container.repo.get_item(item_id, user_id=user_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"商品 {item_id} 不存在于数据库中")

    expected_price = float(item.get("price") or 0)
    if not task_id:
        task_id = str(item.get("task_id") or "")
    return expected_price, task_id


def _check_existing_takeover_order(
    container: Container, task_id: str, item_id: str, user_id: str | None = None,
) -> dict[str, Any] | None:
    """幂等检查：已存在订单时返回提前响应 dict，否则返回 None 继续抢单"""
    if not task_id:
        return None
    existing = container.repo.find_order_by_task_item(task_id, item_id, user_id=user_id)
    if not existing:
        return None
    return {
        "ok": True,
        "outcome": "skipped_duplicate",
        "order": existing,
        "message": f"商品已存在订单 {existing.get('id')}，状态：{existing.get('status')}",
    }


def _format_takeover_result(result: Any) -> dict[str, Any]:
    """把 buyer.buy() 返回值转换为 HTTP 响应体

    success/skipped_duplicate 返回正常 dict；其它 outcome 抛 502 HTTPException，
    让上层异常处理统一兜底。buyer._save_failed_order 已写库，这里只组装响应。
    """
    if result.outcome.value == "success" and result.order:
        return {
            "ok": True,
            "outcome": "success",
            "order": {
                "order_no": result.order.order_no,
                "price": result.order.price,
                "status": result.order.status.value,
            },
            "message": "抢单成功，订单已创建",
        }
    if result.outcome.value == "skipped_duplicate":
        return {
            "ok": True,
            "outcome": "skipped_duplicate",
            "message": "商品已下过单，幂等跳过",
        }
    # 失败：buyer._save_failed_order 已写库，这里只返回结果
    raise HTTPException(
        status_code=502,
        detail=f"抢单失败：{result.error or '未知原因'}",
    )


@router.post("/manual-takeover")
async def manual_takeover(
    payload: dict[str, Any],
    request: Request,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """手动触发抢单：突破纯自动模式限制，让用户在评估明细页面主动触发

    为什么需要手动抢单：
    1. 自动抢单要求 with_browser=True（XH_WITH_SCHEDULER=1 模式），用户可能未启用
    2. 评分>=80 但风险等级非 LOW 时不会自动抢单，用户可能仍想尝试
    3. 提供半自动模式，让用户保留决策权

    前置条件：
    - buyer 已注入（with_browser=True）
    - 商品存在于 items 表（用于读取价格）
    """
    from loguru import logger

    item_id, task_id = _parse_takeover_payload(payload)
    _ensure_takeover_prerequisites(container)

    # 多用户隔离：写入操作用 "default" 兜底
    user_id = getattr(request.state, "user_id", "default")
    expected_price, task_id = _resolve_takeover_item(container, item_id, task_id, user_id=user_id)

    # 幂等检查：避免重复抢单
    existing_response = _check_existing_takeover_order(container, task_id, item_id, user_id=user_id)
    if existing_response is not None:
        return existing_response

    logger.info(f"[ManualTakeover] 用户手动触发抢单：task={task_id} item={item_id} price={expected_price}")

    from xianyu_hunter.domain.order import ItemSoldError

    acquired_browser_lock = False
    try:
        await asyncio.wait_for(
            container.browser_lock.acquire(priority="high"),
            timeout=10.0,
        )
        acquired_browser_lock = True
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=503,
            detail="系统正在执行后台浏览器任务，请稍后重试手动抢单",
        )

    try:
        try:
            from xianyu_hunter.web.services.cookie_runtime_sync import inject_cookie_store_to_worker_browser

            await inject_cookie_store_to_worker_browser("手动抢单前 Cookie 同步", force_refresh_m5tk=False)
        except Exception as e:
            logger.debug(f"[ManualTakeover] Cookie 同步到 Worker 浏览器失败: {e}")

        result = await container.buyer.buy(
            task_id=task_id,
            item_id=item_id,
            expected_price=expected_price,
        )
    except ItemSoldError as e:
        # 已售出：返回 409 而非 500，区分业务错误与系统异常
        logger.info(f"[ManualTakeover] 商品已售出 item={item_id}: {e}")
        raise HTTPException(status_code=409, detail="商品已售出")
    except Exception as e:
        logger.exception("[ManualTakeover] 抢单异常：")
        raise HTTPException(status_code=500, detail=f"抢单失败：{e}")
    finally:
        if acquired_browser_lock:
            container.browser_lock.release()

    return _format_takeover_result(result)
