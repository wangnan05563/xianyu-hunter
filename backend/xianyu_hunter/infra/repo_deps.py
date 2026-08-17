"""Task Dependencies 领域数据访问 - 任务依赖关系 CRUD

提供：
- add_task_dep / remove_task_dep / list_task_deps / list_dependent_tasks / check_circular_dep
"""
from __future__ import annotations

from sqlalchemy import select, text as sa_text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from xianyu_hunter.infra.db_models import TaskDepRow


class TaskDepsMixin:
    """Task Dependencies 领域的 Repository 方法"""

    def add_task_dep(self, task_id: str, depends_on: str, user_id: str = "default") -> None:
        """添加依赖：task_id 依赖 depends_on 成功后才启动"""
        with self.engine.begin() as conn:
            stmt = sqlite_insert(TaskDepRow).values(
                task_id=task_id, depends_on=depends_on, user_id=user_id
            )
            stmt = stmt.on_conflict_do_nothing(index_elements=["task_id", "depends_on"])
            conn.execute(stmt)

    def remove_task_dep(
        self, task_id: str, depends_on: str, user_id: str | None = None
    ) -> bool:
        """删除依赖关系，返回是否实际删除了行

        user_id 不为 None 时附加 WHERE 过滤，防止跨用户删除（深度防御）。
        """
        with self.engine.begin() as conn:
            stmt = (
                TaskDepRow.__table__.delete()
                .where(TaskDepRow.task_id == task_id)
                .where(TaskDepRow.depends_on == depends_on)
            )
            if user_id is not None:
                stmt = stmt.where(TaskDepRow.user_id == user_id)
            result = conn.execute(stmt)
            return (result.rowcount or 0) > 0

    def list_task_deps(self, task_id: str, user_id: str | None = None) -> list[dict]:
        """列出 task_id 的所有上游依赖（即 task_id 依赖谁）"""
        with self.engine.connect() as conn:
            stmt = select(TaskDepRow).where(TaskDepRow.task_id == task_id)
            if user_id is not None:
                stmt = stmt.where(TaskDepRow.user_id == user_id)
            rows = conn.execute(stmt).all()
            return [self._row_to_dict(r) for r in rows]

    def list_dependent_tasks(self, task_id: str, user_id: str | None = None) -> list[dict]:
        """列出依赖 task_id 的所有下游任务（即谁依赖 task_id）"""
        with self.engine.connect() as conn:
            stmt = select(TaskDepRow).where(TaskDepRow.depends_on == task_id)
            if user_id is not None:
                stmt = stmt.where(TaskDepRow.user_id == user_id)
            rows = conn.execute(stmt).all()
            return [self._row_to_dict(r) for r in rows]

    def check_circular_dep(
        self, task_id: str, depends_on: str, user_id: str | None = None
    ) -> bool:
        """检查添加 task_id → depends_on 依赖是否会产生循环

        从 depends_on 向上追溯所有祖先，如果 task_id 出现在祖先链中则存在循环。
        使用递归 CTE 替代全表加载，避免内存浪费。

        user_id 不为 None 时在 CTE 中附加 WHERE 过滤，确保循环检测不跨用户追溯。
        """
        with self.engine.connect() as conn:
            # 递归CTE：从 depends_on 开始向上追溯所有祖先
            # user_id 过滤同时作用于初始查询和递归查询，确保依赖链不跨用户
            if user_id is not None:
                initial_where = "WHERE user_id = :user_id AND task_id = :start"
                recursive_where = "WHERE td.user_id = :user_id"
                params: dict = {"start": depends_on, "target": task_id, "user_id": user_id}
            else:
                initial_where = "WHERE task_id = :start"
                recursive_where = ""
                params = {"start": depends_on, "target": task_id}
            result = conn.execute(sa_text(f"""
                WITH RECURSIVE ancestors AS (
                    SELECT depends_on FROM task_deps {initial_where}
                    UNION ALL
                    SELECT td.depends_on FROM task_deps td
                    INNER JOIN ancestors a ON td.task_id = a.depends_on
                    {recursive_where}
                )
                SELECT COUNT(*) FROM ancestors WHERE depends_on = :target
            """), params).scalar()
            return result > 0

    def delete_deps_by_task(self, task_id: str, user_id: str | None = None) -> int:
        """按任务删除所有依赖关系（作为依赖方和被依赖方）

        user_id 不为 None 时附加 WHERE 过滤，防止跨用户删除（深度防御）。
        """
        with self.engine.begin() as conn:
            stmt1 = TaskDepRow.__table__.delete().where(TaskDepRow.task_id == task_id)
            if user_id is not None:
                stmt1 = stmt1.where(TaskDepRow.user_id == user_id)
            r1 = conn.execute(stmt1)
            stmt2 = TaskDepRow.__table__.delete().where(TaskDepRow.depends_on == task_id)
            if user_id is not None:
                stmt2 = stmt2.where(TaskDepRow.user_id == user_id)
            r2 = conn.execute(stmt2)
            return (r1.rowcount or 0) + (r2.rowcount or 0)
