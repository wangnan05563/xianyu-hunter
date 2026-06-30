"""评估漏斗 + 命中率/误报率 API - O-08-26

端点：
- GET /api/stats/eval-funnel   评估漏斗（5 阶段）+ 关键转化指标

漏斗阶段（业务语义非严格子集，受策略与人工干预影响）：
1. discovered        采集到的去重商品数（task_links.link_type='item'）
2. evaluated         已评估商品数（EvaluationRow 总数）
3. eval_pass         评估通过数（risk_level='low'）
4. order_triggered   抢单触发数（OrderRow 总数）
5. order_succeeded   抢单成功数（OrderRow.status in paid/confirmed）

关键指标：
- hit_rate             评估通过率 = eval_pass / evaluated
- false_positive_rate  误报率 = 抢单失败数 / 抢单触发数
- conversion_rate      抢单成功率 = order_succeeded / order_triggered
- overall_rate         端到端成功率 = order_succeeded / discovered
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select as sa_select

from xianyu_hunter.container import Container
from xianyu_hunter.infra.db_models import (
    EvaluationRow, OrderRow, TaskLinkRow, _utcnow,
)
from xianyu_hunter.web.deps import get_container

router = APIRouter(prefix="/api", tags=["eval-funnel"])


def _stage(key: str, label: str, count: int, first_count: int) -> dict[str, Any]:
    """构造漏斗单阶段结构

    pct_of_first: 相对第一阶段（采集商品数）的占比，用于展示整体转化
    pct_of_prev:  相对上一阶段的占比，用于展示阶段间流失（由调用方事后填充）
    """
    pct_first = round(count / first_count * 100, 1) if first_count > 0 else 0.0
    return {
        "key": key,
        "label": label,
        "count": count,
        "pct_of_first": pct_first,
        "pct_of_prev": 0.0,  # 占位，后续填充
    }


def _safe_rate(numer: int, denom: int) -> float:
    """安全计算百分比，规避 division by zero"""
    return round(numer / denom * 100, 1) if denom > 0 else 0.0


@router.get("/stats/eval-funnel")
def eval_funnel(
    range_days: int = 30,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """O-08-26 评估漏斗 + 命中率/误报率"""
    range_days = max(1, min(range_days, 365))
    now = _utcnow()
    start = now - timedelta(days=range_days)
    repo = container.repo

    # 阶段1：采集商品数（task_links 内 link_type='item' 的去重 link_key）
    # 用 created_at 过滤时间窗，与 business_kpi 口径保持一致
    with repo.engine.connect() as conn:
        discovered = int(conn.execute(
            sa_select(func.count(func.distinct(TaskLinkRow.link_key)))
            .where(TaskLinkRow.link_type == "item")
            .where(TaskLinkRow.created_at >= start)
            .where(TaskLinkRow.created_at <= now)
        ).scalar() or 0)

    # 阶段2：已评估数（EvaluationRow 总数）
    evaluated, _ = repo.db_count_by_predicate(EvaluationRow, start, now)

    # 阶段3：评估通过数（risk_level='low'）
    eval_pass, _ = repo.db_count_by_predicate(
        EvaluationRow, start, now,
        extra_where=[EvaluationRow.risk_level == "low"],
    )

    # 阶段4：抢单触发数（OrderRow 总数）
    order_triggered, _ = repo.db_count_by_predicate(OrderRow, start, now)

    # 阶段5：抢单成功数（status in paid/confirmed/succeeded）
    # 注意：OrderRow.status 取值含 paid/confirmed/succeeded/failed/pending/takeover_pending
    order_succeeded, _ = repo.db_count_by_predicate(
        OrderRow, start, now,
        extra_where=[OrderRow.status.in_(["paid", "confirmed", "succeeded"])],
    )

    # 构造漏斗
    stages = [
        _stage("discovered", "采集商品", discovered, discovered),
        _stage("evaluated", "已评估", evaluated, discovered),
        _stage("eval_pass", "评估通过", eval_pass, discovered),
        _stage("order_triggered", "抢单触发", order_triggered, discovered),
        _stage("order_succeeded", "抢单成功", order_succeeded, discovered),
    ]
    # 填充 pct_of_prev：相对上一阶段的占比
    for i, s in enumerate(stages):
        if i == 0:
            s["pct_of_prev"] = 100.0
        else:
            prev = stages[i - 1]["count"]
            s["pct_of_prev"] = _safe_rate(s["count"], prev)

    # 关键指标
    order_failed = order_triggered - order_succeeded
    metrics = {
        "hit_rate": _safe_rate(eval_pass, evaluated),            # 评估通过率
        "false_positive_rate": _safe_rate(order_failed, order_triggered),  # 误报率
        "conversion_rate": _safe_rate(order_succeeded, order_triggered),   # 抢单成功率
        "overall_rate": _safe_rate(order_succeeded, discovered),           # 端到端成功率
    }

    return {
        "range_days": range_days,
        "generated_at": now.isoformat(timespec="seconds"),
        "stages": stages,
        "metrics": metrics,
    }
