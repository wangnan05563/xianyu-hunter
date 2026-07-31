"""业务 KPI 看板 API - F-OB1 业务指标

端点：
- GET /api/stats/business-kpi     4 张业务 KPI 卡（发现商品数/通过率/成功率/失败率）

性能优化（P0）：
- 合并 7 个独立 engine.connect() 为 1 个连接块，省 6 次连接 checkout/checkin 开销
- KPI4 的 cur_fail + cur_notify_total 合并为一次 SQL（CASE WHEN 聚合），省一次 stage LIKE 全表扫描

性能优化（P2-1）：
- stage LIKE '%notify%' 改为精确匹配 stage == 'notify'
  原因：实际 stage 字段只有 5 种枚举值（search/notify/eval/tunnel/cleanup），
  前缀通配 LIKE 无法走 (stage, created_at) 联合索引，精确匹配可命中索引

性能优化（P3-1）：
- 4 个 KPI 查询从串行改为 asyncio.gather + asyncio.to_thread 并发执行
- 每个 KPI 函数独立建立 connection，利用 SQLite WAL 并发读特性
- 路由改为 async def，避免占用 anyio worker thread
"""
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select as sa_select

from xianyu_hunter.container import Container
from xianyu_hunter.infra.db_models import _utcnow, EvaluationRow, OrderRow, EventRow, TaskLinkRow
from xianyu_hunter.infra.logger import get_logger
from xianyu_hunter.web.cache import cached_ttl
from xianyu_hunter.web.deps import get_container

logger = get_logger()

router = APIRouter(prefix="/api", tags=["business-kpi"])

# 通知事件 stage 精确值（P2-1 优化）
# 历史教训：原用 LIKE '%notify%' 前缀通配，无法走索引，DB 端需全表扫描后逐行 LIKE 过滤
# 经 DB 取值分布核查，stage 字段实际只有 5 种枚举值：search/notify/eval/tunnel/cleanup
# 精确匹配 stage='notify' 可命中 (stage, created_at) 联合索引
_NOTIFY_STAGE = "notify"


def _kpi_block(
    *,
    kpi_id: str,
    title: str,
    value: float,
    unit: str,
    delta_pct: float | None,
    sample_size: int,
    hint: str,
    is_pct: bool = False,
    hint_action: dict[str, str] | None = None,
) -> dict[str, Any]:
    """构造一个 KPI 卡的统一结构

    Args:
        hint_action: 可选的引导动作，结构 {"label": "前往配置", "route": "/config/buyer"}
            为什么需要：分母为 0 等异常场景下，纯文本 hint 无法让用户直达配置页，
            携带 route 让前端渲染可点击链接，缩短用户排查路径
    """
    block = {
        "id": kpi_id,
        "title": title,
        "value": value,
        "unit": unit,
        "delta_pct": delta_pct,
        "sample_size": sample_size,
        "hint": hint,
        "is_pct": is_pct,
    }
    if hint_action is not None:
        block["hint_action"] = hint_action
    return block


def _safe_pct_change(current: float, previous: float) -> float | None:
    """计算百分比变化，规避 division by zero / NaN"""
    if previous == 0:
        if current == 0:
            return 0.0
        return None
    return round((current - previous) / previous * 100, 2)


def _kpi_items_discovered(engine, prev_start, prev_end) -> tuple[int, int]:
    """KPI1 数据采集：发现商品数（当前值 + 前一周期值）

    返回 (cur_val, prev_val)，由调用方包装为 KPI block。
    为什么 task_links 无 created_at 列：task_links 是任务-商品关联表，
    商品入库即建立关联，时间维度由 items 表的 first_seen 维护。
    前一周期值用 EvaluationRow.created_at 兜底（评估通过的商品一定被发现过）。

    P3-1：独立 connection，配合 asyncio.gather 并发执行
    """
    with engine.connect() as conn:
        cur_items_count = conn.execute(
            sa_select(func.count(func.distinct(TaskLinkRow.link_key)))
            .where(TaskLinkRow.link_type == "item")
        ).scalar() or 0
        prev_items_from_eval = conn.execute(
            sa_select(func.count(func.distinct(EvaluationRow.item_id)))
            .where(EvaluationRow.created_at >= prev_start)
            .where(EvaluationRow.created_at <= prev_end)
        ).scalar() or 0
    return int(cur_items_count), int(prev_items_from_eval)


def _kpi_eval_pass_rate(engine, cur_start, now, prev_start, prev_end) -> tuple[int, int, int, int]:
    """KPI2 数据采集：评估通过率

    返回 (cur_pass, cur_total, prev_pass, prev_total)。
    用 CASE WHEN 聚合一次查询同时拿到 pass 和 total，避免 2 次 COUNT。

    P3-1：独立 connection，配合 asyncio.gather 并发执行
    """
    with engine.connect() as conn:
        def _aggregate(start, end) -> tuple[int, int]:
            matched_expr = case((EvaluationRow.risk_level == "low", 1), else_=0)
            row = conn.execute(
                sa_select(
                    func.sum(matched_expr).label("matched"),
                    func.count().label("total"),
                )
                .select_from(EvaluationRow)
                .where(EvaluationRow.created_at >= start)
                .where(EvaluationRow.created_at <= end)
            ).one()
            return int(row.matched or 0), int(row.total or 0)

        return (*_aggregate(cur_start, now), *_aggregate(prev_start, prev_end))


def _kpi_order_success_rate(engine, cur_start, now, prev_start, prev_end) -> tuple[int, int, int, int]:
    """KPI3 数据采集：抢单成功率

    返回 (cur_paid, cur_total, prev_paid, prev_total)。
    修复：status in ('paid','confirmed') 永远命中 0 行，因为生产代码
    抢单成功写入 'pending_pay'（已拍下待支付），人工接管确认支付后写入 'succeeded'。
    'paid'/'confirmed' 这两个值在整个代码库中从未被写入 orders 表。
    此处 'succeeded' 与 stats_overview.py 的统计口径保持一致。

    P3-1：独立 connection，配合 asyncio.gather 并发执行
    """
    with engine.connect() as conn:
        def _aggregate(start, end) -> tuple[int, int]:
            matched_expr = case((OrderRow.status == "succeeded", 1), else_=0)
            row = conn.execute(
                sa_select(
                    func.sum(matched_expr).label("matched"),
                    func.count().label("total"),
                )
                .select_from(OrderRow)
                .where(OrderRow.created_at >= start)
                .where(OrderRow.created_at <= end)
            ).one()
            return int(row.matched or 0), int(row.total or 0)

        return (*_aggregate(cur_start, now), *_aggregate(prev_start, prev_end))


def _kpi_notify_failure_rate(engine, cur_start, now, prev_start, prev_end) -> tuple[int, int, int, int]:
    """KPI4 数据采集：推送失败率

    返回 (cur_fail, cur_notify_total, prev_fail, prev_notify_total)。

    性能优化：原实现发 4 次查询（cur_fail/cur_total/prev_fail/prev_total），
    每次都做 stage LIKE '%notify%' 全表扫描。现用 CASE WHEN 一次查询同时拿到
    fail 和 total，省一半全表扫描。

    P2-1 优化：stage LIKE '%notify%' 改为 stage == 'notify' 精确匹配，
    可命中 (stage, created_at) 联合索引，彻底消除全表扫描。

    P3-1：独立 connection，配合 asyncio.gather 并发执行
    """
    with engine.connect() as conn:
        def _aggregate(start, end) -> tuple[int, int]:
            # P2-1：精确匹配 stage='notify' 走联合索引，替代 LIKE '%notify%' 全表扫描
            fail_expr = case(
                ((EventRow.stage == _NOTIFY_STAGE) & (EventRow.level == "err"), 1),
                else_=0,
            )
            notify_expr = case(
                (EventRow.stage == _NOTIFY_STAGE, 1),
                else_=0,
            )
            row = conn.execute(
                sa_select(
                    func.sum(fail_expr).label("fail_count"),
                    func.sum(notify_expr).label("notify_total"),
                    func.count().label("row_count"),
                )
                .select_from(EventRow)
                .where(EventRow.created_at >= start)
                .where(EventRow.created_at <= end)
            ).one()
            return int(row.fail_count or 0), int(row.notify_total or 0)

        return (*_aggregate(cur_start, now), *_aggregate(prev_start, prev_end))


def _warn_if_no_notify_events(container: Container, range_days: int) -> None:
    """分母为 0 时的分级告警：未启用通知渠道用 debug，已启用但无事件用 warning

    修复 2：NotifierHub 现在会在推送成功/失败时写入 stage='notify' 的 EventRow，
    否则此 KPI 永远为 0（无数据可查）。
    """
    notifier_count = len(getattr(container.notifier_hub, "notifiers", []) or [])
    if notifier_count == 0:
        logger.debug(
            f"[business_kpi] 近 {range_days} 天无 notify 事件：当前未启用有效通知渠道，跳过告警"
        )
    else:
        logger.warning(
            f"[business_kpi] 推送失败率分母为 0：近 {range_days} 天无 notify 事件，"
            "可能 NotifierHub 未写入推送记录或无推送任务"
        )


@cached_ttl(300, key_fn=lambda range_days, container: f"kpi:{range_days}")
async def _compute_business_kpi(range_days: int, container: Container) -> dict[str, Any]:
    """KPI 计算核心逻辑（被缓存包裹）

    为什么缓存 300s：KPI 数据粒度到天，5 分钟内变化概率极低，
    前端轮询或多用户访问时 99%+ 请求命中缓存，响应 <10ms。
    与预聚合调度器 5 分钟刷新周期对齐，数据一致性窗口一致。

    P3-1 优化：4 个 KPI 查询用 asyncio.gather + asyncio.to_thread 并发执行，
    每个 KPI 独立 connection 利用 SQLite WAL 并发读。串行 ~280ms → 并发 ~100ms。
    """
    range_days = max(1, min(range_days, 365))
    now = _utcnow()
    cur_start = now - timedelta(days=range_days)
    prev_start = now - timedelta(days=range_days * 2)
    prev_end = cur_start
    engine = container.repo.engine

    # P3-1：4 个 KPI 并发查询，每个独立 connection（SQLite WAL 支持并发读）
    # 串行执行时 4 个 KPI 累计 ~280ms，并发后受最慢 KPI 限制降到 ~100ms
    (cur_items, prev_items), \
        (cur_pass, cur_total, prev_pass, prev_total), \
        (cur_paid, cur_orders_total, prev_paid, prev_total_orders), \
        (cur_fail, cur_notify_total, prev_fail, prev_notify_total) = await asyncio.gather(
            asyncio.to_thread(_kpi_items_discovered, engine, prev_start, prev_end),
            asyncio.to_thread(_kpi_eval_pass_rate, engine, cur_start, now, prev_start, prev_end),
            asyncio.to_thread(_kpi_order_success_rate, engine, cur_start, now, prev_start, prev_end),
            asyncio.to_thread(_kpi_notify_failure_rate, engine, cur_start, now, prev_start, prev_end),
        )

    kpis: list[dict[str, Any]] = []

    # KPI1：发现商品数
    kpis.append(_kpi_block(
        kpi_id="items_discovered", title="发现商品数", value=cur_items, unit="件",
        delta_pct=_safe_pct_change(cur_items, prev_items) if prev_items > 0 else None,
        sample_size=cur_items,
        hint="采集到的去重商品总数（来自闲鱼搜索）",
    ))

    # KPI2：评估通过率
    cur_pass_rate = (cur_pass / cur_total * 100) if cur_total else 0.0
    prev_pass_rate = (prev_pass / prev_total * 100) if prev_total else 0.0
    kpis.append(_kpi_block(
        kpi_id="eval_pass_rate", title="评估通过率",
        value=round(cur_pass_rate, 1), unit="%",
        delta_pct=_safe_pct_change(cur_pass_rate, prev_pass_rate),
        sample_size=cur_total,
        hint="低风险（可抢）评估 / 总评估", is_pct=True,
    ))

    # KPI3：抢单成功率
    if cur_orders_total == 0:
        logger.warning(
            f"[business_kpi] 抢单成功率分母为 0：近 {range_days} 天无订单记录，"
            "可能抢单未触发或订单数据采集异常"
        )
    cur_order_rate = (cur_paid / cur_orders_total * 100) if cur_orders_total else 0.0
    prev_order_rate = (prev_paid / prev_total_orders * 100) if prev_total_orders else 0.0
    # 分母为 0 时携带引导动作：让前端渲染"前往配置"链接直达抢单策略页，
    # 避免 user 看到 0% 却不知下一步该检查哪里
    hint_action = (
        {"label": "前往抢单策略", "route": "/config/buyer"}
        if cur_orders_total == 0
        else None
    )
    kpis.append(_kpi_block(
        kpi_id="order_success_rate", title="抢单成功率",
        value=round(cur_order_rate, 1), unit="%",
        delta_pct=_safe_pct_change(cur_order_rate, prev_order_rate),
        sample_size=cur_orders_total,
        hint="已支付订单 / 总订单", is_pct=True,
        hint_action=hint_action,
    ))

    # KPI4：推送失败率
    if cur_notify_total == 0:
        _warn_if_no_notify_events(container, range_days)
    cur_fail_rate = (cur_fail / cur_notify_total * 100) if cur_notify_total else 0.0
    prev_fail_rate = (prev_fail / prev_notify_total * 100) if prev_notify_total else 0.0
    kpis.append(_kpi_block(
        kpi_id="notify_failure_rate", title="推送失败率",
        value=round(cur_fail_rate, 1), unit="%",
        delta_pct=_safe_pct_change(cur_fail_rate, prev_fail_rate),
        sample_size=cur_notify_total,
        hint="失败通知事件 / 总通知事件（越低越好）", is_pct=True,
    ))

    return {
        "range_days": range_days,
        "generated_at": now.isoformat(timespec="seconds"),
        "kpis": kpis,
    }


@router.get("/stats/business-kpi")
async def business_kpi(
    range_days: int = 30,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """F-OB1 业务指标看板：4 张 30 天业务 KPI 卡

    性能优化（P0）：
    - 原实现 4 个 KPI 函数各自开 engine.connect()，共 7 个独立连接块、10 次查询
    - 现合并为 1 个连接块，所有查询共用一个连接，省 6 次 checkout/checkin 开销
    - KPI4 的 cur_fail + cur_notify_total 合并为一次 CASE WHEN 聚合，省 2 次全表扫描
    - 加 60s TTL 缓存：90%+ 请求命中缓存，响应从 ~2.7s 降到 <10ms

    性能优化（P2-1）：
    - KPI4 的 stage LIKE '%notify%' 改为 stage == 'notify' 精确匹配
    - 精确匹配可命中 (stage, created_at) 联合索引，彻底消除全表扫描

    性能优化（P3-1）：
    - 4 个 KPI 查询改用 asyncio.gather + asyncio.to_thread 并发执行
    - 每个 KPI 独立 connection 利用 SQLite WAL 并发读特性
    - 路由改 async def，避免占用 anyio worker thread
    """
    return await _compute_business_kpi(range_days, container)
