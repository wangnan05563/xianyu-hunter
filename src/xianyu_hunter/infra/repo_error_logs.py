"""错误日志领域数据访问 - 异常记录 CRUD + 统计聚合

提供：
- save_error_log / list_error_logs / get_error_log / update_error_log_status / delete_error_log
- count_error_logs_by_status（状态统计）
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select

from xianyu_hunter.infra.db_models import ErrorLogRow
from xianyu_hunter.infra.repository_base import RepositoryBase


class ErrorLogsMixin:
    """错误日志领域的 Repository 方法"""

    def save_error_log(self, error_log: dict) -> int:
        """插入一条错误日志，返回主键 id"""
        with self.engine.begin() as conn:
            result = conn.execute(ErrorLogRow.__table__.insert().values(**error_log))
            return result.inserted_primary_key[0]

    def list_error_logs(
        self,
        status: str | None = None,
        error_type: str | None = None,
        request_path: str | None = None,
        start_dt: datetime | None = None,
        end_dt: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """列出错误日志，支持多维度过滤"""
        with self.engine.connect() as conn:
            stmt = select(ErrorLogRow).order_by(ErrorLogRow.timestamp.desc())
            if status:
                stmt = stmt.where(ErrorLogRow.status == status)
            if error_type:
                # 模糊匹配：用户可能只输入部分类型名
                stmt = stmt.where(ErrorLogRow.error_type.like(f"%{error_type}%"))
            if request_path:
                stmt = stmt.where(ErrorLogRow.request_path.like(f"%{request_path}%"))
            if start_dt:
                stmt = stmt.where(ErrorLogRow.timestamp >= start_dt)
            if end_dt:
                stmt = stmt.where(ErrorLogRow.timestamp <= end_dt)
            stmt = stmt.limit(limit).offset(offset)
            return [RepositoryBase._row_to_dict(r) for r in conn.execute(stmt).all()]

    def get_error_log(self, error_log_id: int) -> dict | None:
        """获取单条错误日志"""
        with self.engine.connect() as conn:
            row = conn.execute(
                select(ErrorLogRow).where(ErrorLogRow.id == error_log_id)
            ).first()
            return RepositoryBase._row_to_dict(row) if row else None

    def update_error_log_status(self, error_log_id: int, status: str) -> bool:
        """更新错误日志状态（new/resolved/ignored）"""
        with self.engine.begin() as conn:
            result = conn.execute(
                ErrorLogRow.__table__.update()
                .where(ErrorLogRow.id == error_log_id)
                .values(status=status)
            )
            return result.rowcount > 0

    def delete_error_log(self, error_log_id: int) -> bool:
        """删除单条错误日志"""
        with self.engine.begin() as conn:
            result = conn.execute(
                ErrorLogRow.__table__.delete().where(ErrorLogRow.id == error_log_id)
            )
            return result.rowcount > 0

    def batch_update_error_log_status(self, ids: list[int], status: str) -> int:
        """批量更新错误日志状态

        统一一次事务处理，避免循环单条更新产生的多次事务开销
        """
        if not ids:
            return 0
        with self.engine.begin() as conn:
            result = conn.execute(
                ErrorLogRow.__table__.update()
                .where(ErrorLogRow.id.in_(ids))
                .values(status=status)
            )
            return result.rowcount

    def batch_delete_error_logs(self, ids: list[int]) -> int:
        """批量删除错误日志"""
        if not ids:
            return 0
        with self.engine.begin() as conn:
            result = conn.execute(
                ErrorLogRow.__table__.delete().where(ErrorLogRow.id.in_(ids))
            )
            return result.rowcount

    def count_error_logs_by_status(self) -> dict[str, int]:
        """按状态统计错误日志数量"""
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(ErrorLogRow.status, func.count(ErrorLogRow.id))
                .group_by(ErrorLogRow.status)
            ).all()
            return {row[0]: row[1] for row in rows}

    def cleanup_old_error_logs(self, days: int = 30) -> int:
        """清理指定天数前的已解决/已忽略错误日志"""
        # S6903: 使用时区感知的 UTC 时间，避免 datetime.utcnow() 返回 naive datetime
        # 导致与数据库中 tz-aware 时间戳比较时出现隐式时区错位
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        with self.engine.begin() as conn:
            result = conn.execute(
                ErrorLogRow.__table__.delete().where(
                    ErrorLogRow.timestamp < cutoff,
                    ErrorLogRow.status.in_(["resolved", "ignored"]),
                )
            )
            return result.rowcount
