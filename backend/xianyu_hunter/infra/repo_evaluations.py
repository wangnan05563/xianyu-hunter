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


class EvaluationsMixin:
    """Evaluations 领域的 Repository 方法"""

    def save_evaluation(self, eval_data: dict) -> int:
        with self.engine.begin() as conn:
            result = conn.execute(EvaluationRow.__table__.insert().values(**eval_data))
            return result.inserted_primary_key[0]

    def get_latest_evaluation(self, item_id: str, user_id: str | None = None) -> dict | None:
        with self.engine.connect() as conn:
            stmt = (
                select(EvaluationRow)
                .where(EvaluationRow.item_id == item_id)
                .order_by(EvaluationRow.created_at.desc())
                .limit(1)
            )
            if user_id is not None:
                stmt = stmt.where(EvaluationRow.user_id == user_id)
            row = conn.execute(stmt).first()
            return self._row_to_dict(row) if row else None

    def update_evaluation_dimension_scores(
        self, eval_id: int, dimension_scores: dict, user_id: str | None = None
    ) -> None:
        """更新评估记录的 dimension_scores 字段（用于 AI 成色评估缓存）

        Args:
            eval_id: evaluations 表主键
            dimension_scores: 完整的 dimension_scores dict（会序列化为 JSON）
            user_id: 不为 None 时附加 WHERE 过滤，防止跨用户更新（深度防御）
        """
        with self.engine.begin() as conn:
            stmt = (
                EvaluationRow.__table__.update()
                .where(EvaluationRow.id == eval_id)
                .values(dimension_scores=json.dumps(dimension_scores, ensure_ascii=False))
            )
            if user_id is not None:
                stmt = stmt.where(EvaluationRow.user_id == user_id)
            conn.execute(stmt)

    def delete_evaluations_by_task(self, task_id: str, user_id: str | None = None) -> int:
        """按任务删除评估记录（通过 item_id 间接关联）

        evaluations 表无 task_id 列，需通过子查询找出该任务下的所有 item_id，
        再删除这些 item 对应的评估记录。

        user_id 不为 None 时附加 WHERE 过滤，防止跨用户删除（深度防御）。
        同时过滤 evaluations.user_id 和子查询 items.user_id，确保两层隔离一致。
        """
        with self.engine.begin() as conn:
            # 子查询：找出该任务下的所有 item_id（同时按 user_id 过滤）
            item_ids_stmt = select(ItemRow.id).where(ItemRow.task_id == task_id)
            if user_id is not None:
                item_ids_stmt = item_ids_stmt.where(ItemRow.user_id == user_id)
            item_ids_subq = item_ids_stmt.scalar_subquery()
            del_stmt = delete(EvaluationRow).where(
                EvaluationRow.item_id.in_(item_ids_subq)
            )
            if user_id is not None:
                del_stmt = del_stmt.where(EvaluationRow.user_id == user_id)
            result = conn.execute(del_stmt)
            return result.rowcount or 0

    def delete_evaluation_by_item(self, item_id: str, user_id: str | None = None) -> int:
        """按 item_id 删除评估记录（删除商品时联动清理）

        闲鱼商品 ID 全局唯一，不会跨任务重复，按 item_id 删除安全。
        user_id 不为 None 时附加 WHERE 过滤，防止跨用户删除（深度防御）。
        """
        if not item_id:
            return 0
        with self.engine.begin() as conn:
            stmt = delete(EvaluationRow).where(EvaluationRow.item_id == item_id)
            if user_id is not None:
                stmt = stmt.where(EvaluationRow.user_id == user_id)
            result = conn.execute(stmt)
            return result.rowcount or 0
