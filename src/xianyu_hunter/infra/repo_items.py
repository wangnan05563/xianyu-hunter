"""Items 领域数据访问 - 商品 CRUD

提供：
- upsert_item / get_item / list_items / items_exist
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from xianyu_hunter.infra.db_models import ItemRow
from xianyu_hunter.infra.repository_base import RepositoryBase


class ItemsMixin:
    """Items 领域的 Repository 方法"""

    def upsert_item(self, item: dict) -> None:
        with self.engine.begin() as conn:
            stmt = sqlite_insert(ItemRow).values(**item)
            update_cols = {
                c: stmt.excluded[c] for c in item.keys() if c not in ("id", "first_seen")
            }
            stmt = stmt.on_conflict_do_update(index_elements=["id"], set_=update_cols)
            conn.execute(stmt)

    def batch_upsert_items(self, items: list[dict]) -> int:
        """批量 upsert：单次事务内完成所有 INSERT ON CONFLICT

        为什么不直接在循环中调 upsert_item：每次调用都开启/提交独立事务，
        N 条商品会产生 N 次事务开销。合并为一次事务可减少 ~60% DB I/O。
        """
        if not items:
            return 0
        # 取第一条的 key 集合作为模板（假设所有 item 结构相同）
        sample = items[0]
        update_cols = {
            c: sqlite_insert(ItemRow).excluded[c]
            for c in sample.keys() if c not in ("id", "first_seen")
        }
        with self.engine.begin() as conn:
            stmt = sqlite_insert(ItemRow).values(items)
            stmt = stmt.on_conflict_do_update(index_elements=["id"], set_=update_cols)
            conn.execute(stmt)
        return len(items)

    def get_item(self, item_id: str) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(select(ItemRow).where(ItemRow.id == item_id)).first()
            return self._row_to_dict(row) if row else None

    def list_items(
        self,
        task_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        with self.engine.connect() as conn:
            stmt = select(ItemRow).order_by(ItemRow.first_seen.desc())
            if task_id:
                stmt = stmt.where(ItemRow.task_id == task_id)
            stmt = stmt.limit(limit).offset(offset)
            rows = conn.execute(stmt).all()
            return [self._row_to_dict(r) for r in rows]

    def list_items_by_seller(
        self,
        seller_id: str,
        limit: int = 20,
    ) -> list[dict]:
        """按卖家 ID 查询商品列表（P1-4 贩子识别需要）"""
        with self.engine.connect() as conn:
            stmt = (
                select(ItemRow)
                .where(ItemRow.seller_id == seller_id)
                .order_by(ItemRow.first_seen.desc())
                .limit(limit)
            )
            rows = conn.execute(stmt).all()
            return [self._row_to_dict(r) for r in rows]

    def items_exist(self, item_ids: list[str]) -> set[str]:
        """批量检查商品ID是否已存在（分批查询避免SQLite IN子句参数上限）"""
        if not item_ids:
            return set()
        result: set[str] = set()
        batch_size = 500
        with self.engine.connect() as conn:
            for i in range(0, len(item_ids), batch_size):
                batch = item_ids[i:i + batch_size]
                rows = conn.execute(select(ItemRow.id).where(ItemRow.id.in_(batch))).all()
                result.update(row[0] for row in rows)
        return result

    def delete_items_by_task(self, task_id: str) -> int:
        """按任务删除所有关联商品"""
        with self.engine.begin() as conn:
            result = conn.execute(
                ItemRow.__table__.delete().where(ItemRow.task_id == task_id)
            )
            return result.rowcount or 0
