"""Repository 基础设施 - 通用工具方法 + 引擎初始化

提供：
- _row_to_dict(): SQLAlchemy Row → dict 自动解析 JSON 字段
- _escape_like(): SQL LIKE 通配符转义
- db_count_by_predicate(): 时间窗二元计数
- db_distinct_items_in_window(): 时间窗去重查询
- Repository 基类：引擎初始化 + 单例管理
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

from xianyu_hunter.infra.db_models import create_sqlite_engine, init_db
# 延迟导入 Mixin 避免循环依赖（Mixin 文件反向导入 RepositoryBase）
import importlib
_mixin_modules = [
    'xianyu_hunter.infra.repo_tasks',
    'xianyu_hunter.infra.repo_items',
    'xianyu_hunter.infra.repo_events',
    'xianyu_hunter.infra.repo_error_logs',
    'xianyu_hunter.infra.repo_deps',
    'xianyu_hunter.infra.repo_links',
    'xianyu_hunter.infra.repo_evaluations',
    'xianyu_hunter.infra.repo_orders',
    'xianyu_hunter.infra.repo_notifications',
    'xianyu_hunter.infra.repo_sellers',
]


def _get_repository_class():
    """延迟构建 Repository 类，避免模块级循环导入"""
    mixin_classes = []
    for mod_name, cls_name in zip(_mixin_modules, [
        'TasksMixin', 'ItemsMixin', 'EventsMixin', 'ErrorLogsMixin',
        'TaskDepsMixin', 'TaskLinksMixin', 'EvaluationsMixin', 'OrdersMixin',
        'NotificationsMixin', 'SellersMixin',
    ]):
        mod = importlib.import_module(mod_name)
        mixin_classes.append(getattr(mod, cls_name))
    mixin_classes.append(RepositoryBase)
    return type('Repository', tuple(mixin_classes), {
        '__doc__': '组合所有 Mixin 的具体 Repository 实现',
    })


# 延迟实例化：首次调用 get_repository() 时才构建类
_repository_class = None


def _get_class():
    global _repository_class
    if _repository_class is None:
        _repository_class = _get_repository_class()
    return _repository_class


class RepositoryBase:
    """Repository 基类：提供通用工具方法和引擎管理"""

    def __init__(self, db_path: str = "data/xianyu.db"):
        self.db_path = db_path
        self.engine: Engine = create_sqlite_engine(db_path)
        init_db(db_path)

    @staticmethod
    def _row_to_dict(row: Any) -> dict:
        """SQLAlchemy Row → dict，自动解析 JSON 字段"""
        if row is None:
            return {}
        result = {}
        for col in row._mapping.keys():
            val = row._mapping[col]
            if isinstance(val, str) and col in (
                "exclude_words", "notifier_channels", "image_urls",
                "raw_json", "recent_posts_json", "dimension_scores",
                "reject_reasons", "payload", "display", "search_filters",
            ):
                try:
                    val = json.loads(val) if val else None
                except (json.JSONDecodeError, TypeError):
                    pass
            result[col] = val
        return result

    def db_count_by_predicate(
        self,
        row_cls: type,
        start: datetime,
        end: datetime,
        *,
        time_col: str = "created_at",
        extra_where: Sequence[Any] | None = None,
    ) -> tuple[int, int]:
        """在 [start, end] 时间窗内，对 row_cls 表执行"满足 extra_where / 总行数"二元计数"""
        col: Any = getattr(row_cls, time_col)
        with self.engine.connect() as conn:
            matched_stmt = (
                select(func.count())
                .select_from(row_cls)
                .where(col >= start)
                .where(col <= end)
            )
            total_stmt = (
                select(func.count())
                .select_from(row_cls)
                .where(col >= start)
                .where(col <= end)
            )
            if extra_where:
                for w in extra_where:
                    matched_stmt = matched_stmt.where(w)
            return (
                int(conn.execute(matched_stmt).scalar() or 0),
                int(conn.execute(total_stmt).scalar() or 0),
            )

    def db_distinct_items_in_window(
        self,
        row_cls: type,
        time_col: str,
        start: datetime,
        end: datetime,
        item_col: str = "item_id",
    ) -> list[str]:
        """返回时间窗内 [start, end] 的 row_cls.item_col 去重列表"""
        col_t: Any = getattr(row_cls, time_col)
        col_i: Any = getattr(row_cls, item_col)
        with self.engine.connect() as conn:
            stmt = (
                select(col_i)
                .where(col_t >= start)
                .where(col_t <= end)
                .distinct()
            )
            return [r[0] for r in conn.execute(stmt).all() if r[0] is not None]


def _escape_like(s: str) -> str:
    """转义 SQL LIKE 通配符（% 和 _），防止 LIKE 注入"""
    return s.replace("/", "//").replace("%", "/%").replace("_", "/_")


# 全局单例
_default_repo: RepositoryBase | None = None


def get_repository() -> RepositoryBase:
    """获取默认 Repository 单例（延迟构建类以避免循环导入）"""
    global _default_repo
    if _default_repo is None:
        _default_repo = _get_class()()
    return _default_repo
