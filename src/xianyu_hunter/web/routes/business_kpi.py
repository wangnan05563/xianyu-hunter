"""业务 KPI 看板 API - F-OB1 业务指标

端点：
- GET /api/stats/business-kpi     4 张业务 KPI 卡（发现商品数/通过率/成功率/失败率）
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends

from xianyu_hunter.container import Container
from xianyu_hunter.infra.db_models import _utcnow, EvaluationRow, OrderRow, EventRow, TaskLinkRow
from xianyu_hunter.infra.logger import get_logger
from xianyu_hunter.web.deps import get_container

logger = get_logger()

router = APIRouter(prefix="/api", tags=["business-kpi"])

# 通知事件 stage 字段匹配模式：notify_success/notify_fail 等推送事件均含 notify 子串
_NOTIFY_TAG = "%notify%"


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
) -> dict[str, Any]:
    """构造一个 KPI 卡的统一结构"""
    return {
        "id": kpi_id,
        "title": title,
        "value": value,
        "unit": unit,
        "delta_pct": delta_pct,
        "sample_size": sample_size,
        "hint": hint,
        "is_pct": is_pct,
    }


def _safe_pct_change(current: float, previous: float) -> float | None:
    """计算百分比变化，规避 division by zero / NaN"""
    if previous == 0:
        if current == 0:
            return 0.0
        return None
    return round((current - previous) / previous * 100, 2)


def _kpi_items_discovered(
    repo, container: Container, prev_start, prev_end
) -> dict[str, Any]:
    """KPI1：发现商品数

    优先从 task_links 表统计（包含所有采集到的商品，无论是否通过评估），
    因为 EvaluationRow 仅在评估通过后才写入，阶段初期可能为空。
    """
    from sqlalchemy import func, select as sa_select
    with container.repo.engine.connect() as conn:
        cur_items_count = conn.execute(
            sa_select(func.count(func.distinct(TaskLinkRow.link_key)))
            .where(TaskLinkRow.link_type == "item")
        ).scalar() or 0
        # 前一周期统计（无 created_at 列，用 EvaluationRow 兜底）
        prev_items_from_eval = repo.db_distinct_items_in_window(EvaluationRow, "created_at", prev_start, prev_end)
        # 合并：task_links 当前值 + EvaluationRow 历史值
        prev_val = len(prev_items_from_eval)
    cur_val = cur_items_count
    return _kpi_block(
        kpi_id="items_discovered", title="发现商品数", value=cur_val, unit="件",
        delta_pct=_safe_pct_change(cur_val, prev_val) if prev_val > 0 else None, sample_size=cur_val,
        hint="采集到的去重商品总数（来自闲鱼搜索）",
    )


def _kpi_eval_pass_rate(repo, cur_start, now, prev_start, prev_end) -> dict[str, Any]:
    """KPI2：评估通过率（低风险评估 / 总评估）"""
    cur_eval_pass, cur_eval_total = repo.db_count_by_predicate(
        EvaluationRow, cur_start, now, extra_where=[EvaluationRow.risk_level == "low"],
    )
    prev_eval_pass, prev_eval_total = repo.db_count_by_predicate(
        EvaluationRow, prev_start, prev_end, extra_where=[EvaluationRow.risk_level == "low"],
    )
    cur_pass_rate = (cur_eval_pass / cur_eval_total * 100) if cur_eval_total else 0.0
    prev_pass_rate = (prev_eval_pass / prev_eval_total * 100) if prev_eval_total else 0.0
    return _kpi_block(
        kpi_id="eval_pass_rate", title="评估通过率", value=round(cur_pass_rate, 1), unit="%",
        delta_pct=_safe_pct_change(cur_pass_rate, prev_pass_rate), sample_size=cur_eval_total,
        hint="低风险（可抢）评估 / 总评估", is_pct=True,
    )


def _kpi_order_success_rate(
    repo, range_days: int, cur_start, now, prev_start, prev_end
) -> dict[str, Any]:
    """KPI3：抢单成功率

    修复：原查询 status in ('paid','confirmed') 永远命中 0 行，因为生产代码
    抢单成功写入 'pending_pay'（已拍下待支付），人工接管确认支付后写入 'succeeded'。
    'paid'/'confirmed' 这两个值在整个代码库中从未被写入 orders 表。
    此处 'succeeded' 与 stats_overview.py 的统计口径保持一致。
    """
    cur_paid, cur_total = repo.db_count_by_predicate(
        OrderRow, cur_start, now, extra_where=[OrderRow.status == "succeeded"],
    )
    prev_paid, prev_total = repo.db_count_by_predicate(
        OrderRow, prev_start, prev_end, extra_where=[OrderRow.status == "succeeded"],
    )
    if cur_total == 0:
        logger.warning(
            f"[business_kpi] 抢单成功率分母为 0：近 {range_days} 天无订单记录，"
            "可能抢单未触发或订单数据采集异常"
        )
    cur_order_rate = (cur_paid / cur_total * 100) if cur_total else 0.0
    prev_order_rate = (prev_paid / prev_total * 100) if prev_total else 0.0
    return _kpi_block(
        kpi_id="order_success_rate", title="抢单成功率", value=round(cur_order_rate, 1), unit="%",
        delta_pct=_safe_pct_change(cur_order_rate, prev_order_rate), sample_size=cur_total,
        hint="已支付订单 / 总订单", is_pct=True,
    )


def _query_notify_total(conn, start, end) -> int:
    """查询 [start, end] 区间内 stage 含 notify 的事件总数（与 hint 文案口径一致）"""
    from sqlalchemy import func as sa_func, select as sa_select
    return int(conn.execute(
        sa_select(sa_func.count()).select_from(EventRow)
        .where(EventRow.created_at >= start)
        .where(EventRow.created_at <= end)
        .where(EventRow.stage.like(_NOTIFY_TAG))
    ).scalar() or 0)


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


def _kpi_notify_failure_rate(
    repo, container: Container, range_days: int, cur_start, now, prev_start, prev_end
) -> dict[str, Any]:
    """KPI4：推送失败率（失败通知事件 / 总通知事件）

    修复 1：原分母用 EventRow 全量事件数，与 hint 文案"总通知事件"不符。
    现分母单独查询 stage like '%notify%' 的事件总数，保证分子分母口径一致。
    """
    cur_fail, _ = repo.db_count_by_predicate(
        EventRow, cur_start, now, extra_where=[EventRow.stage.like(_NOTIFY_TAG), EventRow.level == "err"],
    )
    prev_fail, _ = repo.db_count_by_predicate(
        EventRow, prev_start, prev_end, extra_where=[EventRow.stage.like(_NOTIFY_TAG), EventRow.level == "err"],
    )
    # 分母：stage 含 notify 的事件总数（成功+失败），与 hint 文案一致
    with repo.engine.connect() as conn:
        cur_notify_total = _query_notify_total(conn, cur_start, now)
        prev_notify_total = _query_notify_total(conn, prev_start, prev_end)
    if cur_notify_total == 0:
        _warn_if_no_notify_events(container, range_days)
    cur_fail_rate = (cur_fail / cur_notify_total * 100) if cur_notify_total else 0.0
    prev_fail_rate = (prev_fail / prev_notify_total * 100) if prev_notify_total else 0.0
    return _kpi_block(
        kpi_id="notify_failure_rate", title="推送失败率", value=round(cur_fail_rate, 1), unit="%",
        delta_pct=_safe_pct_change(cur_fail_rate, prev_fail_rate), sample_size=cur_notify_total,
        hint="失败通知事件 / 总通知事件（越低越好）", is_pct=True,
    )


@router.get("/stats/business-kpi")
def business_kpi(
    range_days: int = 30,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """F-OB1 业务指标看板：4 张 30 天业务 KPI 卡"""
    range_days = max(1, min(range_days, 365))
    now = _utcnow()
    cur_start = now - timedelta(days=range_days)
    prev_start = now - timedelta(days=range_days * 2)
    prev_end = cur_start

    repo = container.repo
    kpis: list[dict[str, Any]] = [
        _kpi_items_discovered(repo, container, prev_start, prev_end),
        _kpi_eval_pass_rate(repo, cur_start, now, prev_start, prev_end),
        _kpi_order_success_rate(repo, range_days, cur_start, now, prev_start, prev_end),
        _kpi_notify_failure_rate(repo, container, range_days, cur_start, now, prev_start, prev_end),
    ]

    return {
        "range_days": range_days,
        "generated_at": now.isoformat(timespec="seconds"),
        "kpis": kpis,
    }
