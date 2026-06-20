"""业务 KPI 看板 API - F-OB1 业务指标

端点：
- GET /api/stats/business-kpi     4 张业务 KPI 卡（发现商品数/通过率/成功率/失败率）
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends

from xianyu_hunter.container import Container
from xianyu_hunter.infra.db_models import _utcnow, EvaluationRow, OrderRow, EventRow, ItemRow, TaskLinkRow
from xianyu_hunter.web.deps import get_container

router = APIRouter(prefix="/api", tags=["business-kpi"])


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
    kpis: list[dict[str, Any]] = []

    # 1) 发现商品数
    # 优先从 task_links 表统计（包含所有采集到的商品，无论是否通过评估），
    # 因为 EvaluationRow 仅在评估通过后才写入，阶段初期可能为空。
    from sqlalchemy import func, select as sa_select, cast, String
    from datetime import datetime as dt
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
    kpis.append(_kpi_block(
        kpi_id="items_discovered", title="发现商品数", value=cur_val, unit="件",
        delta_pct=_safe_pct_change(cur_val, prev_val) if prev_val > 0 else None, sample_size=cur_val,
        hint=f"采集到的去重商品总数（来自闲鱼搜索）",
    ))

    # 2) 评估通过率
    cur_eval_pass, cur_eval_total = repo.db_count_by_predicate(
        EvaluationRow, cur_start, now, extra_where=[EvaluationRow.risk_level == "low"],
    )
    prev_eval_pass, prev_eval_total = repo.db_count_by_predicate(
        EvaluationRow, prev_start, prev_end, extra_where=[EvaluationRow.risk_level == "low"],
    )
    cur_pass_rate = (cur_eval_pass / cur_eval_total * 100) if cur_eval_total else 0.0
    prev_pass_rate = (prev_eval_pass / prev_eval_total * 100) if prev_eval_total else 0.0
    kpis.append(_kpi_block(
        kpi_id="eval_pass_rate", title="评估通过率", value=round(cur_pass_rate, 1), unit="%",
        delta_pct=_safe_pct_change(cur_pass_rate, prev_pass_rate), sample_size=cur_eval_total,
        hint="低风险（可抢）评估 / 总评估", is_pct=True,
    ))

    # 3) 抢单成功率
    cur_paid, cur_total = repo.db_count_by_predicate(
        OrderRow, cur_start, now, extra_where=[OrderRow.status.in_(["paid", "confirmed"])],
    )
    prev_paid, prev_total = repo.db_count_by_predicate(
        OrderRow, prev_start, prev_end, extra_where=[OrderRow.status.in_(["paid", "confirmed"])],
    )
    cur_order_rate = (cur_paid / cur_total * 100) if cur_total else 0.0
    prev_order_rate = (prev_paid / prev_total * 100) if prev_total else 0.0
    kpis.append(_kpi_block(
        kpi_id="order_success_rate", title="抢单成功率", value=round(cur_order_rate, 1), unit="%",
        delta_pct=_safe_pct_change(cur_order_rate, prev_order_rate), sample_size=cur_total,
        hint="已支付/已确认订单 / 总订单", is_pct=True,
    ))

    # 4) 推送失败率
    cur_fail, cur_total = repo.db_count_by_predicate(
        EventRow, cur_start, now, extra_where=[EventRow.stage.like("%notify%"), EventRow.level == "err"],
    )
    prev_fail, prev_total = repo.db_count_by_predicate(
        EventRow, prev_start, prev_end, extra_where=[EventRow.stage.like("%notify%"), EventRow.level == "err"],
    )
    cur_fail_rate = (cur_fail / cur_total * 100) if cur_total else 0.0
    prev_fail_rate = (prev_fail / prev_total * 100) if prev_total else 0.0
    kpis.append(_kpi_block(
        kpi_id="notify_failure_rate", title="推送失败率", value=round(cur_fail_rate, 1), unit="%",
        delta_pct=_safe_pct_change(cur_fail_rate, prev_fail_rate), sample_size=cur_total,
        hint="失败通知事件 / 总通知事件（越低越好）", is_pct=True,
    ))

    return {
        "range_days": range_days,
        "generated_at": now.isoformat(timespec="seconds"),
        "kpis": kpis,
    }
