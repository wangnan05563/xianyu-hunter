"""批量采集执行历史领域数据访问

提供：
- save_batch_refresh_history / get_batch_refresh_history / update_batch_refresh_history
- list_batch_refresh_history / count_batch_refresh_history
- count_batch_refresh_history_by_task / get_max_batch_refresh_task_id
- cleanup_old_batch_refresh_history
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select

from xianyu_hunter.infra.db_models import BatchRefreshHistoryRow
from xianyu_hunter.infra.repository_base import RepositoryBase


class BatchRefreshHistoryMixin:
    """批量采集执行历史的 Repository 方法"""

    def save_batch_refresh_history(self, data: dict) -> int:
        """插入一条历史记录，返回主键 id

        data 字段与 BatchRefreshHistoryRow 对齐，调用方负责构造。
        """
        with self.engine.begin() as conn:
            result = conn.execute(
                BatchRefreshHistoryRow.__table__.insert().values(**data)
            )
            return result.inserted_primary_key[0]

    def get_batch_refresh_history(self, history_id: int) -> dict | None:
        """按主键查询单条历史记录"""
        with self.engine.connect() as conn:
            row = conn.execute(
                select(BatchRefreshHistoryRow).where(
                    BatchRefreshHistoryRow.id == history_id
                )
            ).first()
            return RepositoryBase._row_to_dict(row) if row else None

    def update_batch_refresh_history(self, history_id: int, values: dict) -> bool:
        """更新单条历史记录字段

        调度器在批次结束时调用，写入 completed_at/status/统计数/error_messages 等终态字段。
        """
        if not values:
            return False
        with self.engine.begin() as conn:
            result = conn.execute(
                BatchRefreshHistoryRow.__table__.update()
                .where(BatchRefreshHistoryRow.id == history_id)
                .values(**values)
            )
            return result.rowcount > 0

    def list_batch_refresh_history(
        self,
        task_id: int | None = None,
        status: str | None = None,
        trigger_source: str | None = None,
        start_dt: datetime | None = None,
        end_dt: datetime | None = None,
        order_by: str = "started_at",
        order_dir: str = "desc",
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        """列出历史记录，支持多维度过滤与排序

        order_by 仅允许 started_at/task_id/status/duration_ms（白名单防注入）。
        """
        # 排序字段白名单：列名固定，防止外部输入拼 SQL
        allowed_order = {
            "started_at": BatchRefreshHistoryRow.started_at,
            "task_id": BatchRefreshHistoryRow.task_id,
            "status": BatchRefreshHistoryRow.status,
            "duration_ms": BatchRefreshHistoryRow.duration_ms,
        }
        order_col = allowed_order.get(order_by, BatchRefreshHistoryRow.started_at)
        order_expr = order_col.desc() if order_dir.lower() == "desc" else order_col.asc()

        with self.engine.connect() as conn:
            stmt = select(BatchRefreshHistoryRow).order_by(order_expr)
            if task_id is not None:
                stmt = stmt.where(BatchRefreshHistoryRow.task_id == task_id)
            if status:
                stmt = stmt.where(BatchRefreshHistoryRow.status == status)
            if trigger_source:
                stmt = stmt.where(BatchRefreshHistoryRow.trigger_source == trigger_source)
            if start_dt:
                stmt = stmt.where(BatchRefreshHistoryRow.started_at >= start_dt)
            if end_dt:
                stmt = stmt.where(BatchRefreshHistoryRow.started_at <= end_dt)
            stmt = stmt.limit(limit).offset(offset)
            return [RepositoryBase._row_to_dict(r) for r in conn.execute(stmt).all()]

    def count_batch_refresh_history(
        self,
        task_id: int | None = None,
        status: str | None = None,
        trigger_source: str | None = None,
        start_dt: datetime | None = None,
        end_dt: datetime | None = None,
    ) -> int:
        """统计符合条件的记录总数（分页用）"""
        with self.engine.connect() as conn:
            stmt = select(func.count(BatchRefreshHistoryRow.id))
            if task_id is not None:
                stmt = stmt.where(BatchRefreshHistoryRow.task_id == task_id)
            if status:
                stmt = stmt.where(BatchRefreshHistoryRow.status == status)
            if trigger_source:
                stmt = stmt.where(BatchRefreshHistoryRow.trigger_source == trigger_source)
            if start_dt:
                stmt = stmt.where(BatchRefreshHistoryRow.started_at >= start_dt)
            if end_dt:
                stmt = stmt.where(BatchRefreshHistoryRow.started_at <= end_dt)
            return int(conn.execute(stmt).scalar() or 0)

    def count_batch_refresh_history_by_status(self) -> dict[str, int]:
        """按状态聚合统计，供前端概览卡片展示"""
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(
                    BatchRefreshHistoryRow.status,
                    func.count(BatchRefreshHistoryRow.id),
                ).group_by(BatchRefreshHistoryRow.status)
            ).all()
            return {row[0]: row[1] for row in rows}

    def count_batch_refresh_history_by_task(self) -> list[dict]:
        """按 task_id 聚合执行次数与最近执行时间

        用于「检查某 task_id 执行过几次」的需求。
        """
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(
                    BatchRefreshHistoryRow.task_id,
                    func.count(BatchRefreshHistoryRow.id).label("run_count"),
                    func.max(BatchRefreshHistoryRow.started_at).label("last_run_at"),
                    func.sum(BatchRefreshHistoryRow.success).label("total_success"),
                    func.sum(BatchRefreshHistoryRow.failed).label("total_failed"),
                ).group_by(BatchRefreshHistoryRow.task_id)
            ).all()
            return [
                {
                    "task_id": row[0],
                    "run_count": row[1],
                    "last_run_at": row[2].isoformat() if row[2] else None,
                    "total_success": int(row[3] or 0),
                    "total_failed": int(row[4] or 0),
                }
                for row in rows
            ]

    def get_max_batch_refresh_task_id(self) -> int:
        """查询历史表中最大的 task_id，用于调度器启动时初始化自增计数器

        无记录时返回 0，调度器据此 +1 作为下个 task_id。
        """
        with self.engine.connect() as conn:
            value = conn.execute(
                select(func.max(BatchRefreshHistoryRow.task_id))
            ).scalar()
            return int(value or 0)

    def cleanup_old_batch_refresh_history(self, days: int) -> int:
        """清理超过指定天数的执行历史记录

        days=0 时不清理（与配置 history_retention_days=0 语义一致）。
        """
        if days <= 0:
            return 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        with self.engine.begin() as conn:
            result = conn.execute(
                BatchRefreshHistoryRow.__table__.delete().where(
                    BatchRefreshHistoryRow.started_at < cutoff
                )
            )
            return result.rowcount

    def delete_batch_refresh_history(self, history_id: int) -> bool:
        """删除单条历史记录"""
        with self.engine.begin() as conn:
            result = conn.execute(
                BatchRefreshHistoryRow.__table__.delete().where(
                    BatchRefreshHistoryRow.id == history_id
                )
            )
            return result.rowcount > 0
