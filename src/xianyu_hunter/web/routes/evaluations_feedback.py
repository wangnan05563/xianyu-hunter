"""评估反馈 API — P3 反馈闭环

从 api_evaluations.py 拆分。
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from loguru import logger

from xianyu_hunter.container import Container
from xianyu_hunter.infra.db_models import _utcnow
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.routes.evaluations_common import _EVAL_SCORED_TYPE, _EVAL_TYPE_PREFIX

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])


# ============== 评估反馈（P3: 反馈闭环） ==============

def _parse_eval_feedback(r: dict) -> str:
    """从评估事件 payload 解析反馈类型，无效 payload 返回空字符串

    payload 可能是 str（旧数据，需 json.loads）或 dict（新数据）或 None。
    拆分自 feedback_stats：把 try/except 嵌套抽离，主循环只剩分支统计"""
    payload = r.get("payload")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            payload = {}
    return (payload or {}).get("feedback", "")


def _accumulate_feedback_stats(rows: list[dict]) -> dict[str, int]:
    """聚合评估反馈统计：遍历 eval.scored 事件统计各反馈类型计数

    拆分自 feedback_stats：把 for + try/except + if/else 嵌套收敛到独立函数"""
    stats: dict[str, int] = {"accurate": 0, "inaccurate": 0, "partial": 0, "no_feedback": 0}
    for r in rows:
        fb = _parse_eval_feedback(r)
        if fb in stats:
            stats[fb] += 1
        else:
            stats["no_feedback"] += 1
    return stats


@router.get("/feedback/stats")
def feedback_stats(
    request: Request,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """评估反馈统计

    返回各反馈类型的数量和准确率，用于监控评估系统整体表现。
    """
    # 多用户隔离：仅统计当前账号的评估反馈
    user_id = getattr(request.state, "user_id", None)
    rows, _ = container.repo.list_events_by_type_prefix(_EVAL_SCORED_TYPE, limit=50000, user_id=user_id)
    stats = _accumulate_feedback_stats(rows)

    total_feedback = stats["accurate"] + stats["inaccurate"] + stats["partial"]
    accuracy_rate = stats["accurate"] / total_feedback if total_feedback > 0 else 0

    return {
        "stats": stats,
        "total_feedback": total_feedback,
        "accuracy_rate": round(accuracy_rate, 4),
    }


@router.post("/{item_id}/feedback")
def submit_eval_feedback(
    item_id: str,
    request: Request,
    feedback: str = Query(..., description="反馈类型: accurate / inaccurate / partial"),
    note: str | None = Query(None, description="可选反馈备注"),
    task_id: str | None = Query(None, description="可选：指定任务 ID（多任务同 item_id 时）"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """提交评估准确率反馈

    用户在评估明细页面标记评估结果是否准确，
    反馈数据写入 eval.scored 事件的 payload.feedback 字段，
    供后续分析评估准确率和优化阈值使用。

    反馈类型：
    - accurate：评估准确（评分与实际一致）
    - inaccurate：评估不准确（评分偏差大）
    - partial：部分准确（方向对但幅度偏）
    """
    if feedback not in ("accurate", "inaccurate", "partial"):
        raise HTTPException(status_code=400, detail="feedback 必须为 accurate/inaccurate/partial")

    # 多用户隔离：写入操作用 "default" 兜底
    user_id = getattr(request.state, "user_id", "default")
    # 查找该商品最新的评估事件
    event_type = _EVAL_SCORED_TYPE
    payload_updates: dict[str, Any] = {
        "feedback": feedback,
        "feedback_note": note or "",
        "feedback_at": _utcnow().isoformat(),
    }

    # 如果有 task_id，按 task_id + item_id 精确查找
    if task_id:
        updated = container.repo.update_eval_payload_by_keys(
            task_id, item_id, event_type, payload_updates, user_id=user_id,
        )
    else:
        # 无 task_id 时，查找该 item_id 最新的 eval.scored 事件
        payload = container.repo.get_eval_payload_by_item(item_id, user_id=user_id)
        if not payload:
            raise HTTPException(status_code=404, detail=f"未找到商品 {item_id} 的评估记录")
        # 获取 task_id 后更新
        task_id_in_payload = payload.get("task_id", "")
        if task_id_in_payload:
            updated = container.repo.update_eval_payload_by_keys(
                task_id_in_payload, item_id, event_type, payload_updates, user_id=user_id,
            )
        else:
            raise HTTPException(status_code=404, detail="评估记录缺少 task_id，无法更新")

    if not updated:
        raise HTTPException(status_code=404, detail=f"未找到商品 {item_id} 的评估记录")

    logger.info("评估反馈: item=%s feedback=%s note=%s", item_id, feedback, note or "")

    return {"ok": True, "item_id": item_id, "feedback": feedback}
