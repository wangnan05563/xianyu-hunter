"""Evaluations 领域数据访问 - 评估记录 CRUD

提供：
- save_evaluation / get_latest_evaluation / delete_evaluations_by_task
"""
from __future__ import annotations

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
