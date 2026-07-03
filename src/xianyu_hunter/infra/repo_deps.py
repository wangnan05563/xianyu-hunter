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

    def add_task_dep(self, task_id: str, depends_on: str) -> None:
        """添加依赖：task_id 依赖 depends_on 成功后才启动"""
        with self.engine.begin() as conn:
            stmt = sqlite_insert(TaskDepRow).values(task_id=task_id, depends_on=depends_on)
            stmt = stmt.on_conflict_do_nothing(index_elements=["task_id", "depends_on"])
            conn.execute(stmt)

    def remove_task_dep(self, task_id: str, depends_on: str) -> bool:
        """删除依赖关系，返回是否实际删除了行"""
        with self.engine.begin() as conn:
            result = conn.execute(
                TaskDepRow.__table__.delete()
                .where(TaskDepRow.task_id == task_id)
                .where(TaskDepRow.depends_on == depends_on)
            )
            return (result.rowcount or 0) > 0

    def list_task_deps(self, task_id: str) -> list[dict]:
        """列出 task_id 的所有上游依赖（即 task_id 依赖谁）"""
        with self.engine.connect() as conn:
            rows = conn.execute(select(TaskDepRow).where(TaskDepRow.task_id == task_id)).all()
            return [self._row_to_dict(r) for r in rows]

    def list_dependent_tasks(self, task_id: str) -> list[dict]:
        """列出依赖 task_id 的所有下游任务（即谁依赖 task_id）"""
        with self.engine.connect() as conn:
            rows = conn.execute(select(TaskDepRow).where(TaskDepRow.depends_on == task_id)).all()
            return [self._row_to_dict(r) for r in rows]

    def check_circular_dep(self, task_id: str, depends_on: str) -> bool:
        """检查添加 task_id → depends_on 依赖是否会产生循环

        从 depends_on 向上追溯所有祖先，如果 task_id 出现在祖先链中则存在循环。
        使用递归 CTE 替代全表加载，避免内存浪费。
        """
        with self.engine.connect() as conn:
            # 递归CTE：从 depends_on 开始向上追溯所有祖先
            result = conn.execute(sa_text("""
                WITH RECURSIVE ancestors AS (
                    SELECT depends_on FROM task_deps WHERE task_id = :start
                    UNION ALL
                    SELECT td.depends_on FROM task_deps td
                    INNER JOIN ancestors a ON td.task_id = a.depends_on
                )
                SELECT COUNT(*) FROM ancestors WHERE depends_on = :target
            """), {"start": depends_on, "target": task_id}).scalar()
            return result > 0

    def delete_deps_by_task(self, task_id: str) -> int:
        """按任务删除所有依赖关系（作为依赖方和被依赖方）"""
        with self.engine.begin() as conn:
            r1 = conn.execute(
                TaskDepRow.__table__.delete().where(TaskDepRow.task_id == task_id)
            )
            r2 = conn.execute(
                TaskDepRow.__table__.delete().where(TaskDepRow.depends_on == task_id)
            )
            return (r1.rowcount or 0) + (r2.rowcount or 0)
