"""Notifications 领域数据访问 - 业务通知 CRUD

提供：
- add_notification / list_notifications / count_notifications
- mark_notification_read / mark_all_notifications_read
- delete_notification / clear_notifications / get_notification
"""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import func, select

from xianyu_hunter.infra.db_models import NotificationRow, _utcnow
from xianyu_hunter.infra.repository_base import RepositoryBase


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
    ) -> dict:
        """创建或更新一条业务通知（同 dedup_key 视为同一业务事件）"""
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        with self.engine.begin() as conn:
            now = _utcnow()
            stmt = sqlite_insert(NotificationRow).values(
                level=level, category=category, title=title, message=message,
                link=link, dedup_key=dedup_key,
                read_at=None if reset_read else NotificationRow.read_at,
                created_at=now,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["dedup_key"],
                set_={
                    "level": stmt.excluded.level,
                    "category": stmt.excluded.category,
                    "title": stmt.excluded.title,
                    "message": stmt.excluded.message,
                    "link": stmt.excluded.link,
                    "read_at": None if reset_read else NotificationRow.read_at,
                    "created_at": stmt.excluded.created_at,
                },
            )
            result = conn.execute(stmt)
            row = conn.execute(
                select(NotificationRow).where(NotificationRow.dedup_key == dedup_key)
            ).first()
        return self._row_to_dict(row) if row else {}

    def list_notifications(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """列出通知；status=unread|read|None(全部)"""
        from sqlalchemy import desc

        with self.engine.connect() as conn:
            stmt = select(NotificationRow)
            if status == "unread":
                stmt = stmt.where(NotificationRow.read_at.is_(None))
            elif status == "read":
                stmt = stmt.where(NotificationRow.read_at.is_not(None))
            stmt = stmt.order_by(
                NotificationRow.read_at.is_(None).desc(),
                desc(NotificationRow.created_at),
            ).limit(limit).offset(offset)
            rows = conn.execute(stmt).all()
            return [self._row_to_dict(r) for r in rows]

    def count_notifications(self, status: str | None = None) -> int:
        """统计通知数（带 status 过滤）"""
        with self.engine.connect() as conn:
            stmt = select(func.count()).select_from(NotificationRow)
            if status == "unread":
                stmt = stmt.where(NotificationRow.read_at.is_(None))
            elif status == "read":
                stmt = stmt.where(NotificationRow.read_at.is_not(None))
            return int(conn.execute(stmt).scalar() or 0)

    def mark_notification_read(self, notif_id: int) -> bool:
        """标记单条已读；幂等"""
        with self.engine.begin() as conn:
            result = conn.execute(
                NotificationRow.__table__.update()
                .where(NotificationRow.id == notif_id)
                .where(NotificationRow.read_at.is_(None))
                .values(read_at=_utcnow())
            )
            return (result.rowcount or 0) > 0

    def mark_all_notifications_read(self) -> int:
        """全部标记已读；返回更新条数"""
        with self.engine.begin() as conn:
            result = conn.execute(
                NotificationRow.__table__.update()
                .where(NotificationRow.read_at.is_(None))
                .values(read_at=_utcnow())
            )
            return result.rowcount or 0

    def delete_notification(self, notif_id: int) -> bool:
        """删除单条通知"""
        with self.engine.begin() as conn:
            result = conn.execute(
                NotificationRow.__table__.delete().where(NotificationRow.id == notif_id)
            )
            return (result.rowcount or 0) > 0

    def clear_notifications(self, status: str | None = None) -> int:
        """清空通知；status=unread 只清未读，None 全清"""
        with self.engine.begin() as conn:
            stmt = NotificationRow.__table__.delete()
            if status == "unread":
                stmt = stmt.where(NotificationRow.read_at.is_(None))
            elif status == "read":
                stmt = stmt.where(NotificationRow.read_at.is_not(None))
            result = conn.execute(stmt)
            return result.rowcount or 0

    def get_notification(self, notif_id: int) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(select(NotificationRow).where(NotificationRow.id == notif_id)).first()
            return self._row_to_dict(row) if row else None
