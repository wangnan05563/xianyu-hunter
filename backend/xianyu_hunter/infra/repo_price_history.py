"""PriceHistory 领域数据访问 - 价格快照 CRUD（PRD FR-F1-1）

提供：
- record_price_snapshots：批量写快照（同值去重：与最新快照同价不重复写）
- record_price_snapshot：单条写快照
- list_price_history：按商品取近 N 天快照（走势图消费）
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from xianyu_hunter.infra.db_models import PriceHistoryRow


class PriceHistoryMixin:
    """PriceHistory 领域的 Repository 方法"""

    def record_price_snapshots(
        self, items: list[dict], source: str, user_id: str | None = None
    ) -> int:
        """批量写价格快照，同值去重（与该商品最新快照同价不重复写）

        采集批量落库路径（FR-F1-1）：一次查询所有商品的最新快照价，
        内存过滤同值后单事务批量插入，避免 N 次独立查询+写入。

        Args:
            items: 商品 dict 列表（需含 id / price）
            source: 快照来源（collect / live_search / detail）
            user_id: 归属用户（批量链路调用方已知 user_id 时传入）

        Returns:
            实际写入的快照条数
        """
        candidates = [
            (it["id"], float(it["price"]))
            for it in items
            if it.get("id") and isinstance(it.get("price"), (int, float))
        ]
        if not candidates:
            return 0

        item_ids = [cid for cid, _ in candidates]
        latest = self._latest_prices(item_ids, user_id=user_id)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        # 同值去重：与最新快照价相同（浮点容差 1e-6）则跳过
        rows = [
            {
                "item_id": cid, "price": price, "source": source, "captured_at": now,
                # user_id 不传时交给列默认值（'default'）；显式 None 会撞 NOT NULL。
                # 写入侧必须落归属，否则降价检测按 user_id 读不到自己的历史价（T02815）。
                **({"user_id": user_id} if user_id is not None else {}),
            }
            for cid, price in candidates
            if cid not in latest or abs(latest[cid] - price) > 1e-6
        ]
        if not rows:
            return 0
        with self.engine.begin() as conn:
            conn.execute(sqlite_insert(PriceHistoryRow).values(rows))
        return len(rows)

    def record_price_snapshot(
        self, item_id: str, price: float, source: str, user_id: str | None = None
    ) -> bool:
        """单条写快照（详情采集路径），同值去重

        Returns:
            True 表示写入了新快照，False 表示同值被去重跳过
        """
        if not isinstance(price, (int, float)):
            return False
        latest = self._latest_prices([item_id], user_id=user_id)
        if item_id in latest and abs(latest[item_id] - float(price)) <= 1e-6:
            return False
        row = {
            "item_id": item_id, "price": float(price), "source": source,
            "captured_at": datetime.now(timezone.utc).replace(tzinfo=None),
        }
        if user_id is not None:
            row["user_id"] = user_id
        with self.engine.begin() as conn:
            conn.execute(sqlite_insert(PriceHistoryRow).values(**row))
        return True

    def _latest_prices(
        self, item_ids: list[str], user_id: str | None = None
    ) -> dict[str, float]:
        """查询每个商品当前最新的快照价（一次查询覆盖整批）

        user_id 不为 None 时只看该用户自己的快照：同一商品可能被多个账号采集，
        跨用户取「最新价」会让同值去重把本用户的快照吞掉，进而读不到自己的降价基线。
        """
        if not item_ids:
            return {}
        with self.engine.connect() as conn:
            stmt = (
                select(
                    PriceHistoryRow.item_id,
                    PriceHistoryRow.price,
                    func.max(PriceHistoryRow.captured_at),
                )
                .where(PriceHistoryRow.item_id.in_(item_ids))
                .group_by(PriceHistoryRow.item_id)
            )
            if user_id is not None:
                stmt = stmt.where(PriceHistoryRow.user_id == user_id)
            rows = conn.execute(stmt).fetchall()
        # 注意：max(captured_at) 与配对 price 在极端同秒写入时可能不严格配对，
        # 但价格快照精度到秒级足够；若需严格可改窗口函数（当前规模无必要）
        return {item_id: float(price) for item_id, price, _ in rows}

    def list_price_history(
        self, item_id: str, days: int = 30, user_id: str | None = None
    ) -> list[dict]:
        """取商品近 N 天快照（时间升序，走势图直接消费）"""
        since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
        with self.engine.connect() as conn:
            stmt = (
                select(PriceHistoryRow)
                .where(PriceHistoryRow.item_id == item_id)
                .where(PriceHistoryRow.captured_at >= since)
                .order_by(PriceHistoryRow.captured_at.asc())
            )
            if user_id is not None:
                stmt = stmt.where(PriceHistoryRow.user_id == user_id)
            rows = conn.execute(stmt).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_min_price(self, item_id: str, user_id: str | None = None) -> float | None:
        """取商品历史最低价（降价检测与推送文案消费）"""
        with self.engine.connect() as conn:
            stmt = select(func.min(PriceHistoryRow.price)).where(
                PriceHistoryRow.item_id == item_id
            )
            if user_id is not None:
                stmt = stmt.where(PriceHistoryRow.user_id == user_id)
            val = conn.execute(stmt).scalar()
        return float(val) if val is not None else None
