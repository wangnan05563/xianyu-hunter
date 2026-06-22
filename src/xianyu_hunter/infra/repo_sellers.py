"""Sellers 领域数据访问 - 卖家 CRUD

提供：
- upsert_seller / get_seller
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from xianyu_hunter.infra.db_models import SellerRow
from xianyu_hunter.infra.repository_base import RepositoryBase


class SellersMixin:
    """Sellers 领域的 Repository 方法"""

    def upsert_seller(self, seller: dict) -> None:
        with self.engine.begin() as conn:
            stmt = sqlite_insert(SellerRow).values(**seller)
            update_cols = {c: stmt.excluded[c] for c in seller.keys() if c != "id"}
            stmt = stmt.on_conflict_do_update(index_elements=["id"], set_=update_cols)
            conn.execute(stmt)

    def get_seller(self, seller_id: str) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(select(SellerRow).where(SellerRow.id == seller_id)).first()
            return self._row_to_dict(row) if row else None

    def list_sellers_by_ids(self, seller_ids: list[str]) -> list[dict]:
        """按 seller_id 批量查询卖家（避免 N+1 查询）

        recompute_evaluations 之前对每个 item 的 seller_id 单独调用 get_seller，
        当 item 数量多时会产生大量数据库查询。这里提供批量查询方法。
        """
        if not seller_ids:
            return []
        result: list[dict] = []
        batch_size = 500  # 避免 SQLite IN 子句参数上限
        with self.engine.connect() as conn:
            for i in range(0, len(seller_ids), batch_size):
                batch = seller_ids[i:i + batch_size]
                rows = conn.execute(select(SellerRow).where(SellerRow.id.in_(batch))).all()
                result.extend(self._row_to_dict(r) for r in rows)
        return result
