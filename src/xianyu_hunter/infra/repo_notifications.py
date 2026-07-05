"""Notifications 领域数据访问 - 业务通知 CRUD

提供：
- add_notification / list_notifications / count_notifications
- mark_notification_read / mark_all_notifications_read
- delete_notification / clear_notifications / get_notification
"""
from __future__ import annotations

from sqlalchemy import func, select

from xianyu_hunter.infra.db_models import NotificationRow, _utcnow


class NotificationsMixin:
    """Notifications 领域的 Repository 方法"""

    def add_notification(
        self,
        level: str,
        category: str,
        title: str,
        message: str,
        link: str | None,
        dedup_key: str,
        reset_read: bool = True,
        user_id: str = "default",
    ) -> dict:
        """创建或更新一条业务通知（同 dedup_key 视为同一业务事件）"""
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        with self.engine.begin() as conn:
            now = _utcnow()
            # INSERT 的 VALUES 中不能引用目标表本身的列（SQLite 限制，与 PostgreSQL 不同）。
            # 因此 read_at 始终用 None 占位；保留旧值的语义改由 ON CONFLICT DO UPDATE
            # 子句实现——该子句中允许引用 <table>.col（旧值）和 excluded.col（新值）。
            stmt = sqlite_insert(NotificationRow).values(
                level=level, category=category, title=title, message=message,
                link=link, dedup_key=dedup_key,
                read_at=None,
                created_at=now,
                user_id=user_id,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["dedup_key"],
                set_={
                    "level": stmt.excluded.level,
                    "category": stmt.excluded.category,
                    "title": stmt.excluded.title,
                    "message": stmt.excluded.message,
                    "link": stmt.excluded.link,
                    # reset_read=True → 用新值（None）重置为未读
                    # reset_read=False → 保留原值（引用现有行的 read_at）
                    "read_at": None if reset_read else NotificationRow.read_at,
                    "created_at": stmt.excluded.created_at,
                    # 不更新 user_id：避免不同用户触发同 dedup_key 时归属权被覆盖
                },
            )
            conn.execute(stmt)
            row = conn.execute(
                select(NotificationRow).where(NotificationRow.dedup_key == dedup_key)
            ).first()
        return self._row_to_dict(row) if row else {}

    def list_notifications(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
        user_id: str | None = None,
    ) -> list[dict]:
        """列出通知；status=unread|read|None(全部)"""
        from sqlalchemy import desc

        with self.engine.connect() as conn:
            stmt = select(NotificationRow)
            if status == "unread":
                stmt = stmt.where(NotificationRow.read_at.is_(None))
            elif status == "read":
                stmt = stmt.where(NotificationRow.read_at.is_not(None))
            if user_id is not None:
                stmt = stmt.where(NotificationRow.user_id == user_id)
            stmt = stmt.order_by(
                NotificationRow.read_at.is_(None).desc(),
                desc(NotificationRow.created_at),
            ).limit(limit).offset(offset)
            rows = conn.execute(stmt).all()
            return [self._row_to_dict(r) for r in rows]

    def count_notifications(self, status: str | None = None, user_id: str | None = None) -> int:
        """统计通知数（带 status 过滤）"""
        with self.engine.connect() as conn:
            stmt = select(func.count()).select_from(NotificationRow)
            if status == "unread":
                stmt = stmt.where(NotificationRow.read_at.is_(None))
            elif status == "read":
                stmt = stmt.where(NotificationRow.read_at.is_not(None))
            if user_id is not None:
                stmt = stmt.where(NotificationRow.user_id == user_id)
            return int(conn.execute(stmt).scalar() or 0)

    def mark_notification_read(self, notif_id: int, user_id: str | None = None) -> bool:
        """标记单条已读；幂等

        user_id 不为 None 时附加 WHERE 过滤，防止跨用户更新（深度防御）。
        """
        with self.engine.begin() as conn:
            stmt = (
                NotificationRow.__table__.update()
                .where(NotificationRow.id == notif_id)
                .where(NotificationRow.read_at.is_(None))
                .values(read_at=_utcnow())
            )
            if user_id is not None:
                stmt = stmt.where(NotificationRow.user_id == user_id)
            result = conn.execute(stmt)
            return (result.rowcount or 0) > 0

    def mark_all_notifications_read(self, user_id: str | None = None) -> int:
        """全部标记已读；返回更新条数

        user_id 不为 None 时仅标记该用户的通知（多用户隔离）；
        user_id=None 时跨用户标记（后台调度场景）。
        """
        with self.engine.begin() as conn:
            stmt = (
                NotificationRow.__table__.update()
                .where(NotificationRow.read_at.is_(None))
                .values(read_at=_utcnow())
            )
            if user_id is not None:
                stmt = stmt.where(NotificationRow.user_id == user_id)
            result = conn.execute(stmt)
            return result.rowcount or 0

    def delete_notification(self, notif_id: int, user_id: str | None = None) -> bool:
        """删除单条通知

        user_id 不为 None 时附加 WHERE 过滤，防止跨用户删除（深度防御）。
        """
        with self.engine.begin() as conn:
            stmt = NotificationRow.__table__.delete().where(NotificationRow.id == notif_id)
            if user_id is not None:
                stmt = stmt.where(NotificationRow.user_id == user_id)
            result = conn.execute(stmt)
            return (result.rowcount or 0) > 0

    def clear_notifications(self, status: str | None = None, user_id: str | None = None) -> int:
        """清空通知；status=unread 只清未读，None 全清

        user_id 不为 None 时仅清空该用户的通知（多用户隔离）；
        user_id=None 时跨用户清空（后台调度场景）。
        """
        with self.engine.begin() as conn:
            stmt = NotificationRow.__table__.delete()
            if status == "unread":
                stmt = stmt.where(NotificationRow.read_at.is_(None))
            elif status == "read":
                stmt = stmt.where(NotificationRow.read_at.is_not(None))
            if user_id is not None:
                stmt = stmt.where(NotificationRow.user_id == user_id)
            result = conn.execute(stmt)
            return result.rowcount or 0

    def get_notification(self, notif_id: int) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(select(NotificationRow).where(NotificationRow.id == notif_id)).first()
            return self._row_to_dict(row) if row else None
