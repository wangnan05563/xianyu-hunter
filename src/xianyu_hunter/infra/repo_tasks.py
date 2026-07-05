"""Tasks 领域数据访问 - 任务 CRUD

提供：
- upsert_task / get_task / list_tasks / list_tasks_with_last_seen / count_tasks / update_task_status
"""
from __future__ import annotations

from sqlalchemy import desc, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from xianyu_hunter.infra.db_models import _utcnow, ItemRow, TaskRow


class TasksMixin:
    """Tasks 领域的 Repository 方法"""

    def upsert_task(self, task: dict) -> None:
        """插入或更新任务"""
        with self.engine.begin() as conn:
            stmt = sqlite_insert(TaskRow).values(**task)
            update_cols = {c: stmt.excluded[c] for c in task.keys() if c != "id"}
            stmt = stmt.on_conflict_do_update(index_elements=["id"], set_=update_cols)
            conn.execute(stmt)

    def get_task(self, task_id: str, user_id: str | None = None) -> dict | None:
        # user_id 多用户隔离：与 list_tasks 保持一致
        # 路由层（api_task_links/api_task_deps）已普遍传入 user_id，
        # 缺失此参数会抛 TypeError 被全局异常处理器兜底为 500 "内部服务器错误"
        with self.engine.connect() as conn:
            stmt = select(TaskRow).where(TaskRow.id == task_id)
            if user_id is not None:
                stmt = stmt.where(TaskRow.user_id == user_id)
            row = conn.execute(stmt).first()
            return self._row_to_dict(row) if row else None

    def list_tasks(self, status: str | None = None, limit: int | None = None, offset: int = 0,
                   user_id: str | None = None) -> list[dict]:
        with self.engine.connect() as conn:
            stmt = select(TaskRow)
            if status:
                stmt = stmt.where(TaskRow.status == status)
            else:
                # 未指定状态时默认排除软删除任务
                stmt = stmt.where(TaskRow.status != "deleted")
            if user_id is not None:
                stmt = stmt.where(TaskRow.user_id == user_id)
            stmt = stmt.order_by(desc(TaskRow.created_at))
            if limit is not None:
                stmt = stmt.limit(limit).offset(offset)
            rows = conn.execute(stmt).all()
            return [self._row_to_dict(r) for r in rows]

    def list_tasks_with_last_seen(self, status: str | None = None, limit: int | None = None,
                                   offset: int = 0, user_id: str | None = None) -> list[dict]:
        """列出任务 + 每个任务最后一次抓到商品的时间（LEFT JOIN + GROUP BY 一次性聚合）"""
        last_seen_subq = (
            select(ItemRow.task_id, func.max(ItemRow.last_seen).label("last_seen_at"))
            .where(ItemRow.task_id.is_not(None))
            .group_by(ItemRow.task_id)
            .subquery()
        )
        with self.engine.connect() as conn:
            stmt = (
                select(*TaskRow.__table__.c, last_seen_subq.c.last_seen_at)
                .outerjoin(last_seen_subq, last_seen_subq.c.task_id == TaskRow.id)
            )
            if status:
                stmt = stmt.where(TaskRow.status == status)
            else:
                # 未明确指定状态时，默认排除已软删除的任务
                # 必须在 SQL 层排除，否则 limit/offset 在内存过滤前已截断
                stmt = stmt.where(TaskRow.status != "deleted")
            if user_id is not None:
                stmt = stmt.where(TaskRow.user_id == user_id)
            stmt = stmt.order_by(desc(TaskRow.created_at))
            if limit is not None:
                stmt = stmt.limit(limit).offset(offset)
            rows = conn.execute(stmt).all()
            out: list[dict] = []
            for r in rows:
                d = self._row_to_dict(r)
                if d.get("last_seen_at") is not None:
                    d["last_seen_at"] = d["last_seen_at"].isoformat()
                out.append(d)
            return out

    def count_tasks(self, status: str | None = None, user_id: str | None = None) -> int:
        """统计任务数（带 status 过滤）。不传 status = 排除已删除"""
        with self.engine.connect() as conn:
            stmt = select(func.count()).select_from(TaskRow)
            if status:
                stmt = stmt.where(TaskRow.status == status)
            else:
                # 默认排除软删除任务
                stmt = stmt.where(TaskRow.status != "deleted")
            if user_id is not None:
                stmt = stmt.where(TaskRow.user_id == user_id)
            return int(conn.execute(stmt).scalar() or 0)

    def update_task_status(self, task_id: str, status: str, user_id: str | None = None) -> None:
        """更新任务状态

        user_id 不为 None 时附加 WHERE 过滤，确保不会跨用户更新（深度防御）。
        为什么需要兜底：API 层已校验 task 归属权，但调用方若遗漏校验，
        repo 层仍能阻止越权写入。SQLAlchemy 的 .where() 可链式追加条件。
        """
        with self.engine.begin() as conn:
            stmt = TaskRow.__table__.update().where(TaskRow.id == task_id)
            if user_id is not None:
                stmt = stmt.where(TaskRow.user_id == user_id)
            conn.execute(stmt.values(status=status, updated_at=_utcnow()))

    def delete_task_cascade(self, task_id: str) -> dict[str, int]:
        """级联删除任务的所有关联数据（不含任务行本身）

        删除顺序与原 api_tasks.py 路由保持一致：links → items → events → orders → deps → evaluations。
        任务行本身由调用方通过 update_task_status("deleted") 单独处理，
        以便单任务删除接口能在级联完成后仍返回计数统计。

        返回各表删除行数，供单任务删除接口回填 cascade 响应字段；
        批量删除接口可忽略返回值。
        """
        return {
            "links": self.delete_task_links_by_task(task_id),
            "items": self.delete_items_by_task(task_id),
            "events": self.delete_events_by_task(task_id),
            "orders": self.delete_orders_by_task(task_id),
            "deps": self.delete_deps_by_task(task_id),
            "evaluations": self.delete_evaluations_by_task(task_id),
        }
