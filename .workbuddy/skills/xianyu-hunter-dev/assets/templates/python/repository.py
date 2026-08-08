"""Repository Mixin 模板

复制后替换以下占位符：
- {XxxMixin}：Mixin 类名（如 ItemsMixin）
- {XxxRow}：ORM 模型类名（如 ItemRow）
- {xxx}：方法名前缀（如 items）

设计要点：
- Mixin 不持有独立状态，通过 self.engine 访问 RepositoryBase 的引擎
- 写操作用 engine.begin()，读操作用 engine.connect()
- 返回 dict 而非 ORM 对象，通过 _row_to_dict 自动解析 JSON 字段
- LIKE 查询必须用 _escape_like() 转义
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import and_, case, delete, func, insert, select, update

from xianyu_hunter.infra.db_models import {XxxRow}
from xianyu_hunter.infra.repository_base import _escape_like


class {XxxMixin}:
    """{XxxRow} 表的数据访问 Mixin
    
    提供基本的 CRUD + 分页查询 + 关键词搜索能力。
    复杂业务查询请按需扩展，保持方法单一职责。
    """

    def list_{xxx}(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        task_id: str | None = None,
    ) -> dict:
        """分页查询 {XxxRow.__tablename__}
        
        Args:
            page: 页码，从 1 开始
            page_size: 每页数量，1-100
            keyword: 关键词搜索（name 字段，LIKE 模糊匹配）
            task_id: 按任务过滤
        
        Returns:
            {"items": [...], "total": int, "page": int, "page_size": int}
        """
        with self.engine.connect() as conn:
            stmt = select({XxxRow})
            
            # 条件过滤
            conditions = []
            if keyword:
                # 为什么用 _escape_like：防止 % 和 _ 通配符注入
                escaped = _escape_like(keyword)
                conditions.append(
                    {XxxRow}.name.like(f"%{escaped}%", escape="/")
                )
            if task_id:
                conditions.append({XxxRow}.task_id == task_id)
            
            if conditions:
                stmt = stmt.where(and_(*conditions))
            
            # 排序 + 分页
            stmt = (
                stmt.order_by({XxxRow}.created_at.desc())
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
            items = [self._row_to_dict(r) for r in conn.execute(stmt).all()]
            
            # 总数查询
            count_stmt = select(func.count()).select_from({XxxRow})
            if conditions:
                count_stmt = count_stmt.where(and_(*conditions))
            total = int(conn.execute(count_stmt).scalar() or 0)
        
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_{xxx}(self, item_id: str) -> dict | None:
        """按 ID 查询单条记录
        
        Returns:
            dict 或 None（不存在时）
        """
        with self.engine.connect() as conn:
            stmt = select({XxxRow}).where({XxxRow}.id == item_id)
            row = conn.execute(stmt).first()
            return self._row_to_dict(row) if row else None

    def create_{xxx}(self, data: dict) -> dict:
        """插入新记录
        
        Args:
            data: 字段字典，必须包含 id
        
        Returns:
            插入后的完整记录
        """
        with self.engine.begin() as conn:
            conn.execute(insert({XxxRow}).values(**data))
        
        # 返回完整记录（重新查询确保字段完整）
        return self.get_{xxx}(data["id"])

    def update_{xxx}(self, item_id: str, update_data: dict) -> dict | None:
        """更新记录（部分更新）
        
        Args:
            item_id: 记录 ID
            update_data: 待更新字段字典
        
        Returns:
            更新后的完整记录
        """
        with self.engine.begin() as conn:
            conn.execute(
                update({XxxRow})
                .where({XxxRow}.id == item_id)
                .values(**update_data)
            )
        
        return self.get_{xxx}(item_id)

    def delete_{xxx}(self, item_id: str) -> bool:
        """删除记录
        
        Returns:
            True 表示删除成功，False 表示记录不存在
        """
        with self.engine.begin() as conn:
            result = conn.execute(
                delete({XxxRow}).where({XxxRow}.id == item_id)
            )
            return result.rowcount > 0

    def batch_create_{xxx}(self, items: list[dict]) -> int:
        """批量插入
        
        为什么用批量 insert：减少事务次数，提升写入性能
        
        Returns:
            插入条数
        """
        if not items:
            return 0
        
        with self.engine.begin() as conn:
            conn.execute(insert({XxxRow}), items)
        return len(items)

    def count_{xxx}_by_predicate(
        self,
        start: datetime,
        end: datetime,
        *,
        extra_conditions: list | None = None,
    ) -> tuple[int, int]:
        """时间窗内二元计数（满足条件数 / 总数）
        
        为什么用 CASE WHEN 聚合：合并多次 COUNT 为单次查询，性能更优
        """
        return self.db_count_by_predicate(
            {XxxRow},
            start,
            end,
            time_col="created_at",
            extra_where=extra_conditions,
        )
