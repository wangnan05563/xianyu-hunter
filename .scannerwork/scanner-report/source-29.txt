"""Orders 领域数据访问 - 订单 CRUD

提供：
- upsert_order / get_order / list_orders / find_order_by_task_item
"""
from __future__ import annotations

from sqlalchemy import desc, func, select, delete
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

    def list_orders(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
        task_id: str | None = None,
        item_id: str | None = None,
    ) -> list[dict]:
        with self.engine.connect() as conn:
            stmt = select(OrderRow).order_by(OrderRow.created_at.desc())
            if status:
                stmt = stmt.where(OrderRow.status == status)
            if task_id:
                stmt = stmt.where(OrderRow.task_id == task_id)
            if item_id:
                stmt = stmt.where(OrderRow.item_id == item_id)
            stmt = stmt.limit(limit).offset(offset)
            return [self._row_to_dict(r) for r in conn.execute(stmt).all()]

    def count_orders(
        self,
        status: str | None = None,
        task_id: str | None = None,
        item_id: str | None = None,
    ) -> int:
        with self.engine.connect() as conn:
            stmt = select(func.count(OrderRow.id))
            if status:
                stmt = stmt.where(OrderRow.status == status)
            if task_id:
                stmt = stmt.where(OrderRow.task_id == task_id)
            if item_id:
                stmt = stmt.where(OrderRow.item_id == item_id)
            return conn.execute(stmt).scalar() or 0

    def delete_order_by_id(self, order_id: str) -> int:
        with self.engine.begin() as conn:
            result = conn.execute(
                OrderRow.__table__.delete().where(OrderRow.id == order_id)
            )
            return result.rowcount or 0

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

    def list_orders_by_item_ids(
        self, item_ids: list[str], include_failed: bool = False
    ) -> dict[str, dict]:
        """批量查询多个商品的最新订单状态

        用于评估明细列表展示「订单状态」列，避免 N+1 查询。
        返回 {item_id: order_dict} 映射，每个 item 只保留最新一条订单。

        include_failed 控制是否包含 failed 订单：
        - False（默认）：跳过 failed 订单，用于「是否允许重新抢单」判断
        - True：保留 failed 订单，用于评估明细展示完整订单历史
        为什么需要 include_failed=True：评估明细需要展示失败记录，否则用户
        点击抢单失败后，刷新页面看到「—」会误以为没下过单而反复触发抢单。
        """
        if not item_ids:
            return {}
        result: dict[str, dict] = {}
        with self.engine.connect() as conn:
            stmt = (
                select(OrderRow)
                .where(OrderRow.item_id.in_(item_ids))
                .order_by(OrderRow.created_at.desc())
            )
            for row in conn.execute(stmt).all():
                order = self._row_to_dict(row)
                iid = order.get("item_id")
                if not iid or iid in result:
                    continue
                if not include_failed and order.get("status") == "failed":
                    continue
                result[iid] = order
        return result

    def delete_orders_by_task(self, task_id: str) -> int:
        """按任务删除所有关联订单"""
        with self.engine.begin() as conn:
            result = conn.execute(
                OrderRow.__table__.delete().where(OrderRow.task_id == task_id)
            )
            return result.rowcount or 0
