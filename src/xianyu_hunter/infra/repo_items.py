"""Items 领域数据访问 - 商品 CRUD

提供：
- upsert_item / get_item / list_items / items_exist
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from xianyu_hunter.infra.db_models import ItemRow


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

    def get_item(self, item_id: str, user_id: str | None = None) -> dict | None:
        with self.engine.connect() as conn:
            stmt = select(ItemRow).where(ItemRow.id == item_id)
            if user_id is not None:
                stmt = stmt.where(ItemRow.user_id == user_id)
            row = conn.execute(stmt).first()
            return self._row_to_dict(row) if row else None

    def list_items(
        self,
        task_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
        user_id: str | None = None,
    ) -> list[dict]:
        with self.engine.connect() as conn:
            stmt = select(ItemRow).order_by(ItemRow.first_seen.desc())
            if task_id:
                stmt = stmt.where(ItemRow.task_id == task_id)
            if user_id is not None:
                stmt = stmt.where(ItemRow.user_id == user_id)
            stmt = stmt.limit(limit).offset(offset)
            rows = conn.execute(stmt).all()
            return [self._row_to_dict(r) for r in rows]

    def list_items_by_seller(
        self,
        seller_id: str,
        limit: int = 20,
        user_id: str | None = None,
    ) -> list[dict]:
        """按卖家 ID 查询商品列表（P1-4 贩子识别需要）"""
        with self.engine.connect() as conn:
            stmt = (
                select(ItemRow)
                .where(ItemRow.seller_id == seller_id)
                .order_by(ItemRow.first_seen.desc())
                .limit(limit)
            )
            if user_id is not None:
                stmt = stmt.where(ItemRow.user_id == user_id)
            rows = conn.execute(stmt).all()
            return [self._row_to_dict(r) for r in rows]

    def list_unsold_items(self, limit: int = 100, user_id: str | None = None) -> list[dict]:
        """查询所有在售（is_sold=0）商品，按首见时间倒序

        为什么单独提供此方法：批量采集调度器需要定期刷新在售商品详情，
        之前用 list_items(limit=N) 再过滤会扫描已售商品浪费 IO，
        且无法保证返回的全是 is_sold=0 的记录。
        索引 ix_items_is_sold（init_db 中创建）覆盖此查询。
        """
        with self.engine.connect() as conn:
            stmt = (
                select(ItemRow)
                .where(ItemRow.is_sold == 0)
                .order_by(ItemRow.first_seen.desc())
                .limit(limit)
            )
            if user_id is not None:
                stmt = stmt.where(ItemRow.user_id == user_id)
            rows = conn.execute(stmt).all()
            return [self._row_to_dict(r) for r in rows]

    def list_items_by_ids(self, item_ids: list[str], user_id: str | None = None) -> list[dict]:
        """按 item_id 批量查询商品（避免 list_items(limit=N) 在大数据量下遗漏）

        评估明细相关接口需要按评估事件涉及的 item_id 精确查询，
        之前用 list_items(limit=5000/10000) 全量加载再过滤，既浪费内存又可能遗漏。
        """
        if not item_ids:
            return []
        result: list[dict] = []
        batch_size = 500  # 与 items_exist 保持一致，避免 SQLite IN 子句参数上限
        with self.engine.connect() as conn:
            for i in range(0, len(item_ids), batch_size):
                batch = item_ids[i:i + batch_size]
                stmt = select(ItemRow).where(ItemRow.id.in_(batch))
                if user_id is not None:
                    stmt = stmt.where(ItemRow.user_id == user_id)
                rows = conn.execute(stmt).all()
                result.extend(self._row_to_dict(r) for r in rows)
        return result

    def items_exist(self, item_ids: list[str], user_id: str | None = None) -> set[str]:
        """批量检查商品ID是否已存在（分批查询避免SQLite IN子句参数上限）"""
        if not item_ids:
            return set()
        result: set[str] = set()
        batch_size = 500
        with self.engine.connect() as conn:
            for i in range(0, len(item_ids), batch_size):
                batch = item_ids[i:i + batch_size]
                stmt = select(ItemRow.id).where(ItemRow.id.in_(batch))
                if user_id is not None:
                    stmt = stmt.where(ItemRow.user_id == user_id)
                rows = conn.execute(stmt).all()
                result.update(row[0] for row in rows)
        return result

    def get_recently_collected_item_ids(
        self, item_ids: list[str], window_minutes: int, user_id: str | None = None,
    ) -> set[str]:
        """查询最近 window_minutes 分钟内已采集（last_seen 更新）的 item_id 集合

        用于自动官方采集去重，避免短时间内重复采集同一商品。

        为什么用 last_seen 而非 updated_at 或 first_seen：
        - items 表无 updated_at 字段
        - first_seen 是商品首次入库时间，无法反映"最近是否被处理过"
        - last_seen 配置了 onupdate=_utcnow，upsert_item 每次写入都会刷新，
          是判断"最近是否被采集过"的可靠信号

        为什么复用 list_items_by_ids 的分批模式：
        - SQLite IN 子句默认参数上限 999，大列表必须分批
        - 与现有方法保持一致的 batch_size=500 留足余量
        """
        if not item_ids:
            return set()
        if window_minutes <= 0:
            return set()
        threshold = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        result: set[str] = set()
        batch_size = 500
        with self.engine.connect() as conn:
            for i in range(0, len(item_ids), batch_size):
                batch = item_ids[i:i + batch_size]
                stmt = (
                    select(ItemRow.id)
                    .where(ItemRow.id.in_(batch))
                    .where(ItemRow.last_seen >= threshold)
                )
                if user_id is not None:
                    stmt = stmt.where(ItemRow.user_id == user_id)
                rows = conn.execute(stmt).all()
                result.update(row[0] for row in rows)
        return result

    def delete_items_by_task(self, task_id: str, user_id: str | None = None) -> int:
        """按任务删除所有关联商品

        user_id 不为 None 时附加 WHERE 过滤，防止跨用户删除（深度防御）。
        """
        with self.engine.begin() as conn:
            stmt = ItemRow.__table__.delete().where(ItemRow.task_id == task_id)
            if user_id is not None:
                stmt = stmt.where(ItemRow.user_id == user_id)
            result = conn.execute(stmt)
            return result.rowcount or 0

    def update_data_source(self, item_id: str, source: str, user_id: str | None = None) -> bool:
        """更新商品的采集来源标记

        Args:
            item_id: 商品 ID
            source: 采集来源，必须是 'search' / 'official' / 'live' 之一
            user_id: 不为 None 时附加 WHERE 过滤，防止跨用户更新（深度防御）

        Returns:
            是否更新成功（受影响行数 > 0）

        Raises:
            ValueError: source 取值非法
        """
        # 白名单校验：防止非法值写入造成数据污染
        valid_sources = {"search", "official", "live"}
        if source not in valid_sources:
            raise ValueError(
                f"非法的 data_source 取值: {source!r}，必须是 {valid_sources} 之一"
            )
        with self.engine.begin() as conn:
            stmt = (
                ItemRow.__table__.update()
                .where(ItemRow.id == item_id)
                .values(data_source=source)
            )
            if user_id is not None:
                stmt = stmt.where(ItemRow.user_id == user_id)
            result = conn.execute(stmt)
            return (result.rowcount or 0) > 0

    def mark_sold(self, item_id: str, user_id: str | None = None) -> None:
        """标记商品为已售出，同步更新 items 表 + task_links.display

        为什么同步 task_links：前端列表读 task_links.display.is_sold，
        DB 模式下旧数据缺失该字段会导致显示"在售"，需同步修正。

        原子性保证：items 更新和 task_links 更新在同一事务中执行，
        避免中间崩溃导致 items.is_sold=1 但 task_links.display.is_sold 仍为 False。

        user_id 不为 None 时附加 WHERE 过滤，防止跨用户更新（深度防御）。
        items 与 task_links 的 user_id 来自同一 task，过滤后仍能保持原子性一致。
        """
        import json as _json
        from xianyu_hunter.infra.db_models import _utcnow, TaskLinkRow

        now = _utcnow()
        with self.engine.begin() as conn:
            # 1. 更新 items 表
            items_stmt = (
                ItemRow.__table__.update()
                .where(ItemRow.id == item_id)
                .values(is_sold=1, sold_detected_at=now)
            )
            if user_id is not None:
                items_stmt = items_stmt.where(ItemRow.user_id == user_id)
            conn.execute(items_stmt)
            # 2. 同步 task_links.display.is_sold（同一事务内，保证原子性）
            links_stmt = (
                select(TaskLinkRow)
                .where(TaskLinkRow.link_type == "item")
                .where(TaskLinkRow.link_key == item_id)
            )
            if user_id is not None:
                links_stmt = links_stmt.where(TaskLinkRow.user_id == user_id)
            links = conn.execute(links_stmt).all()
            for link in links:
                display = link.display
                if isinstance(display, str):
                    try:
                        display = _json.loads(display) if display else {}
                    except _json.JSONDecodeError:
                        display = {}
                elif display is None:
                    display = {}
                else:
                    # SQLAlchemy 可能已解析为 dict
                    pass
                display["is_sold"] = True
                link_update = (
                    TaskLinkRow.__table__.update()
                    .where(TaskLinkRow.id == link.id)
                    .values(display=_json.dumps(display, ensure_ascii=False))
                )
                if user_id is not None:
                    link_update = link_update.where(TaskLinkRow.user_id == user_id)
                conn.execute(link_update)
