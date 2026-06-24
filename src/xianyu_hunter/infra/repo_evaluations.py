"""Evaluations 领域数据访问 - 评估记录 CRUD

提供：
- save_evaluation / get_latest_evaluation / delete_evaluations_by_task
- update_evaluation_dimension_scores

定位说明：
- evaluations 表是 AI 成色评估的缓存（dimension_scores.ai_condition_eval），
  仅由 F-06 AI 成色评估接口写入，不是评估明细的主数据源。
- 评估明细、分布、阈值建议等读取 events 表中 type=eval.* 的事件流。
"""
from __future__ import annotations

import json

from sqlalchemy import delete, select

from xianyu_hunter.infra.db_models import EvaluationRow, ItemRow
from xianyu_hunter.infra.repository_base import RepositoryBase


class EvaluationsMixin:
    """Evaluations 领域的 Repository 方法"""

    def save_evaluation(self, eval_data: dict) -> int:
        with self.engine.begin() as conn:
            result = conn.execute(EvaluationRow.__table__.insert().values(**eval_data))
            return result.inserted_primary_key[0]

    def get_latest_evaluation(self, item_id: str) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                select(EvaluationRow)
                .where(EvaluationRow.item_id == item_id)
                .order_by(EvaluationRow.created_at.desc())
                .limit(1)
            ).first()
            return self._row_to_dict(row) if row else None

    def update_evaluation_dimension_scores(self, eval_id: int, dimension_scores: dict) -> None:
        """更新评估记录的 dimension_scores 字段（用于 AI 成色评估缓存）

        Args:
            eval_id: evaluations 表主键
            dimension_scores: 完整的 dimension_scores dict（会序列化为 JSON）
        """
        with self.engine.begin() as conn:
            conn.execute(
                EvaluationRow.__table__.update()
                .where(EvaluationRow.id == eval_id)
                .values(dimension_scores=json.dumps(dimension_scores, ensure_ascii=False))
            )

    def delete_evaluations_by_task(self, task_id: str) -> int:
        """按任务删除评估记录（通过 item_id 间接关联）

        evaluations 表无 task_id 列，需通过子查询找出该任务下的所有 item_id，
        再删除这些 item 对应的评估记录。
        """
        with self.engine.begin() as conn:
            # 子查询：找出该任务下的所有 item_id
            item_ids_subq = (
                select(ItemRow.id)
                .where(ItemRow.task_id == task_id)
            ).scalar_subquery()
            result = conn.execute(
                delete(EvaluationRow).where(
                    EvaluationRow.item_id.in_(item_ids_subq)
                )
            )
            return result.rowcount or 0

    def delete_evaluation_by_item(self, item_id: str) -> int:
        """按 item_id 删除评估记录（删除商品时联动清理）

        闲鱼商品 ID 全局唯一，不会跨任务重复，按 item_id 删除安全。
        """
        if not item_id:
            return 0
        with self.engine.begin() as conn:
            result = conn.execute(
                delete(EvaluationRow).where(EvaluationRow.item_id == item_id)
            )
            return result.rowcount or 0
