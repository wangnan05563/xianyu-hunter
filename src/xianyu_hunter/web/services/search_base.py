"""搜索服务基类

统一封装搜索接口的分页、慢查询埋点与响应结构，让 4 个搜索接口（任务关联 /
错误日志 / 数据库维护 / 智能客服会话）共享同一套非业务逻辑。

设计要点：
- 模板方法模式：search() 编排流程，子类只填充 _build_query/_execute/_extract_facets
- 默认内存分页：子类若已在 SQL 层分页（更高效），重写 _paginate 直接返回 rows
- 慢查询埋点：>100ms 记 info，>1000ms 记 warning，便于后续性能优化定位
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")  # params 类型
R = TypeVar("R")  # row 类型


class SearchParams:
    """搜索参数基类

    汇总 4 个搜索接口最常出现的 q/limit/offset 三大字段，避免每个子类重复声明。
    子类可在 __init__ 中通过 super().__init__(...) 复用，再补充自身专属字段。
    """

    def __init__(self, q: str | None = None, limit: int = 50, offset: int = 0):
        self.q = q
        self.limit = limit
        self.offset = offset


class SearchService(ABC, Generic[T, R]):
    """搜索服务抽象基类

    search() 为统一入口，返回 dict 结构：
        {
            "items": [...],            # 当前页数据
            "total": int,              # 满足过滤条件的总行数
            "matched_facets": {...},   # 分面直方图（按需返回，可空 dict）
            "query_meta": {
                "elapsed_ms": float,   # 端到端耗时（毫秒）
                "cache_hit": bool,     # 是否命中缓存（当前实现固定 False）
            },
        }
    """

    SLOW_THRESHOLD_MS = 100.0
    VERY_SLOW_THRESHOLD_MS = 1000.0

    def search(self, params: T) -> dict[str, Any]:
        start = time.monotonic()
        query = self._build_query(params)
        rows, total = self._execute(query, params)
        facets = self._extract_facets(rows)
        items = self._paginate(rows, params)
        elapsed_ms = (time.monotonic() - start) * 1000
        self._maybe_log_slow(elapsed_ms, params)
        return {
            "items": items,
            "total": total,
            "matched_facets": facets,
            "query_meta": {"elapsed_ms": round(elapsed_ms, 2), "cache_hit": False},
        }

    def _paginate(self, rows: list[R], params: T) -> list[R]:
        """内存分页：子类若已在 SQL 层分页可重写此方法直接返回 rows"""
        offset = getattr(params, "offset", 0)
        limit = getattr(params, "limit", 50)
        return rows[offset: offset + limit]

    def _maybe_log_slow(self, elapsed_ms: float, params: T) -> None:
        """慢查询埋点

        阈值分级便于区分「需要优化」与「已经影响用户体验」两档：
        - 100ms~1000ms：info 级，记录便于后续分析
        - >1000ms：warning 级，需要立即关注
        """
        if elapsed_ms >= self.VERY_SLOW_THRESHOLD_MS:
            logger.warning(
                "slow search %s elapsed_ms=%.2f params=%s",
                self.__class__.__name__, elapsed_ms, vars(params),
            )
        elif elapsed_ms >= self.SLOW_THRESHOLD_MS:
            logger.info(
                "slow search %s elapsed_ms=%.2f params=%s",
                self.__class__.__name__, elapsed_ms, vars(params),
            )

    @abstractmethod
    def _build_query(self, params: T) -> Any:
        """构造查询对象。SQL 层已分页的接口可返回 None"""

    @abstractmethod
    def _execute(self, query: Any, params: T) -> tuple[list[R], int]:
        """执行查询，返回 (当前页 rows, 总数 total)"""

    @abstractmethod
    def _extract_facets(self, rows: list[R]) -> dict[str, list[dict]]:
        """从结果集提取分面直方图。无分面需求的接口返回空 dict"""
