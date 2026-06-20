"""Orders 领域数据访问 - 订单 CRUD

提供：
- upsert_order / get_order / list_orders / find_order_by_task_item
"""
from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from xianyu_hunter.infra.db_models import OrderRow
from xianyu_hunter.infra.repository_base import RepositoryBase


class OrdersMixin:
    """Orders 领域的 Repository 方法"""

    def upsert_order(self, order: dict) -> None:
        with self.engine.begin() as conn:
            stmt = sqlite_insert(OrderRow).values(**order)
            update_cols = {c: stmt.excluded[c] for c in order.keys() if c != "id"}
            stmt = stmt.on_conflict_do_update(index_elements=["id"], set_=update_cols)
            conn.execute(stmt)

    def get_order(self, order_id: str) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(select(OrderRow).where(OrderRow.id == order_id)).first()
            return self._row_to_dict(row) if row else None

    def list_orders(self, status: str | None = None, limit: int = 50) -> list[dict]:
        with self.engine.connect() as conn:
            stmt = select(OrderRow).order_by(OrderRow.created_at.desc())
            if status:
                stmt = stmt.where(OrderRow.status == status)
            stmt = stmt.limit(limit)
            return [self._row_to_dict(r) for r in conn.execute(stmt).all()]

    def find_order_by_task_item(self, task_id: str, item_id: str) -> dict | None:
        """幂等查询：同 task 内该 item 是否已有非失败的订单"""
        with self.engine.connect() as conn:
            stmt = (
                select(OrderRow)
                .where(OrderRow.item_id == item_id)
                .where(OrderRow.task_id == task_id)
                .order_by(OrderRow.created_at.desc())
                .limit(1)
            )
            row = conn.execute(stmt).first()
            if not row:
                return None
            order = self._row_to_dict(row)
            if order.get("status") == "failed":
                return None
            return order

    def delete_orders_by_task(self, task_id: str) -> int:
        """按任务删除所有关联订单"""
        with self.engine.begin() as conn:
            result = conn.execute(
                OrderRow.__table__.delete().where(OrderRow.task_id == task_id)
            )
            return result.rowcount or 0
