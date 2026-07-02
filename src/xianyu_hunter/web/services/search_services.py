"""4 个搜索接口的 SearchService 子类实现

每个子类对应一个 GET 列表接口，复用基类的分页/埋点/响应结构。
关键约束：4 个接口均已在 SQL 层分页（比内存分页高效），因此统一重写 _paginate
直接返回 rows，跳过基类的内存切片逻辑。

对应关系：
- TaskLinkSearchService        → GET /api/tasks/links/search
- ErrorLogSearchService        → GET /api/error-logs
- DbAdminSearchService         → GET /api/db-admin/tables/{table}/rows
- ChatbotSessionSearchService  → GET /api/chatbot/sessions
"""
from __future__ import annotations

from typing import Any

from xianyu_hunter.web.services.search_base import SearchParams, SearchService


# ============== A1: 任务关联搜索 ==============

class TaskLinkSearchParams(SearchParams):
    def __init__(self, q: str, link_type: str | None = None, limit: int = 50, offset: int = 0):
        super().__init__(q=q, limit=limit, offset=offset)
        self.link_type = link_type


class TaskLinkSearchService(SearchService):
    """跨任务模糊搜索 link_key / display

    repo.search_task_links 返回 list[dict]（无 total 字段），
    这里用 len(rows) 兼容基类的 (rows, total) 契约，与原路由 count=len(rows) 行为一致。
    """

    def __init__(self, repo):
        self._repo = repo

    def _build_query(self, params: TaskLinkSearchParams) -> Any:
        # repo 直接接受 q/limit 参数构造 ORM 查询，无需在此预构造 query 对象
        return None

    def _execute(self, query: Any, params: TaskLinkSearchParams) -> tuple[list[dict], int]:
        rows = self._repo.search_task_links(
            q=params.q, link_type=params.link_type, limit=params.limit,
        )
        return rows, len(rows)

    def _extract_facets(self, rows: list[dict]) -> dict[str, list[dict]]:
        return {}

    def _paginate(self, rows: list[dict], params: TaskLinkSearchParams) -> list[dict]:
        # SQL 层已通过 LIMIT 分页，直接返回
        return rows


# ============== A6: 错误日志搜索 ==============

class ErrorLogSearchParams(SearchParams):
    def __init__(
        self,
        q: str | None = None,
        status: str | None = None,
        error_type: str | None = None,
        request_path: str | None = None,
        request_id: str | None = None,
        start_dt=None,
        end_dt=None,
        limit: int = 50,
        offset: int = 0,
    ):
        super().__init__(q=q, limit=limit, offset=offset)
        self.status = status
        self.error_type = error_type
        self.request_path = request_path
        self.request_id = request_id
        self.start_dt = start_dt
        self.end_dt = end_dt


class ErrorLogSearchService(SearchService):
    """错误日志多维度过滤

    repo.list_error_logs 返回 list[dict]（无 total），用 len(rows) 兼容契约。
    status_counts 是全局状态分布（不依赖当前过滤条件），由路由层单独调用
    repo.count_error_logs_by_status() 获取，保持 service 职责单一。
    """

    def __init__(self, repo):
        self._repo = repo

    def _build_query(self, params: ErrorLogSearchParams) -> Any:
        return None

    def _execute(self, query: Any, params: ErrorLogSearchParams) -> tuple[list[dict], int]:
        rows = self._repo.list_error_logs(
            status=params.status,
            error_type=params.error_type,
            request_path=params.request_path,
            request_id=params.request_id,
            start_dt=params.start_dt,
            end_dt=params.end_dt,
            limit=params.limit,
            offset=params.offset,
        )
        return rows, len(rows)

    def _extract_facets(self, rows: list[dict]) -> dict[str, list[dict]]:
        return {}

    def _paginate(self, rows: list[dict], params: ErrorLogSearchParams) -> list[dict]:
        # SQL 层已通过 LIMIT/OFFSET 分页
        return rows


# ============== A4: 数据库维护行查询 ==============

class DbAdminSearchParams(SearchParams):
    def __init__(
        self,
        table: str,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
        order_by: str | None = None,
    ):
        super().__init__(q=q, limit=limit, offset=offset)
        self.table = table
        self.order_by = order_by  # 形如 "-created_at" 或 "created_at"


class DbAdminSearchService(SearchService):
    """动态表名行查询（原生 SQL）

    此接口不能用 ORM：表名是运行时参数，无静态类型映射。
    service 内部复用 api_db_admin 模块的 _validate_identifier / _serialize_row
    工具函数，保持与原路由一致的标识符校验和行序列化行为。

    _validate_table 由路由层提前调用（未通过直接 400），service 不再重复校验。
    """

    def __init__(self, engine):
        self._engine = engine

    def _build_query(self, params: DbAdminSearchParams) -> Any:
        return None

    def _execute(self, query: Any, params: DbAdminSearchParams) -> tuple[list[dict], int]:
        # 延迟导入避免与路由模块产生循环依赖
        from sqlalchemy import inspect, text

        from xianyu_hunter.web.routes.api_db_admin import (
            _serialize_row,
            _validate_identifier,
        )

        # 反射列信息（与 _get_columns 输出格式兼容，但不含 label 等元数据，
        # 因为 list_rows 只需 name/type 用于 SQL 构造和行序列化）
        cols = [
            {"name": c["name"], "type": str(c["type"])}
            for c in inspect(self._engine).get_columns(params.table)
        ]
        if not cols:
            return [], 0

        # 解析排序方向：- 前缀表示倒序，与原 list_rows 路由保持一致
        desc = False
        ob = params.order_by
        if ob and ob.startswith("-"):
            desc = True
            ob = ob[1:]
        if ob:
            _validate_identifier(ob, "order_by")

        # 构造 SQL（表名已由路由层 _validate_table 白名单校验，列名走参数化绑定）
        where_clauses: list[str] = []
        sql_params: dict[str, Any] = {"limit": params.limit, "offset": params.offset}
        if params.q:
            # 文本列做 LIKE 搜索；数字/日期列跳过避免类型转换异常
            text_cols = [
                c["name"] for c in cols
                if any(t in c["type"].upper() for t in ("CHAR", "TEXT", "VARCHAR", "CLOB"))
            ]
            if text_cols:
                ors = [f"CAST({c} AS TEXT) LIKE :search" for c in text_cols]
                where_clauses.append("(" + " OR ".join(ors) + ")")
                sql_params["search"] = f"%{params.q}%"

        sql = f"SELECT * FROM {params.table}"
        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)
        if ob:
            sql += f" ORDER BY {ob} {'DESC' if desc else 'ASC'}"
        sql += " LIMIT :limit OFFSET :offset"

        count_sql = f"SELECT COUNT(*) FROM {params.table}"
        if where_clauses:
            count_sql += " WHERE " + " AND ".join(where_clauses)

        with self._engine.connect() as conn:
            total = conn.execute(text(count_sql), sql_params).scalar() or 0
            rows = conn.execute(text(sql), sql_params).mappings().all()

        items = [_serialize_row(dict(r), cols) for r in rows]
        return items, total

    def _extract_facets(self, rows: list[dict]) -> dict[str, list[dict]]:
        return {}

    def _paginate(self, rows: list[dict], params: DbAdminSearchParams) -> list[dict]:
        # SQL 层已通过 LIMIT/OFFSET 分页
        return rows


# ============== A8: 智能客服会话搜索 ==============

class ChatbotSessionSearchParams(SearchParams):
    def __init__(
        self,
        q: str | None = None,
        status: str | None = None,
        favorite_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ):
        super().__init__(q=q, limit=limit, offset=offset)
        self.status = status
        self.favorite_only = favorite_only


class ChatbotSessionSearchService(SearchService):
    """智能客服会话列表

    repo 将 list_sessions 和 count_sessions 拆为两个方法，service 内部依次调用
    拼装 (items, total)。keyword 参数对应 params.q，统一由基类 SearchParams 持有。
    """

    def __init__(self, repo):
        self._repo = repo

    def _build_query(self, params: ChatbotSessionSearchParams) -> Any:
        return None

    def _execute(self, query: Any, params: ChatbotSessionSearchParams) -> tuple[list[dict], int]:
        items = self._repo.list_sessions(
            status=params.status,
            keyword=params.q,
            favorite_only=params.favorite_only,
            limit=params.limit,
            offset=params.offset,
        )
        total = self._repo.count_sessions(
            status=params.status,
            keyword=params.q,
            favorite_only=params.favorite_only,
        )
        return items, total

    def _extract_facets(self, rows: list[dict]) -> dict[str, list[dict]]:
        return {}

    def _paginate(self, rows: list[dict], params: ChatbotSessionSearchParams) -> list[dict]:
        # SQL 层已通过 LIMIT/OFFSET 分页
        return rows
