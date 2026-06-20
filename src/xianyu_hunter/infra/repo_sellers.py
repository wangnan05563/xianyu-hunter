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
