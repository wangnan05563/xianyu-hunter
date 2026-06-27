"""SQLAlchemy 表结构定义

设计文档 §5 数据模型 DDL 的 1:1 实现。

时间字段约定：所有 datetime 列统一使用 UTC（datetime.utcnow），
SQLite 不存储时区信息，统一 UTC 避免本地时区混淆。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    text as sa_text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    """返回当前 UTC 时间（替代 datetime.now，确保时区一致）

    使用 timezone-aware 的 datetime.now(UTC) 替代已弃用的 datetime.utcnow()。
    SQLite 不存储时区信息，但 Python 侧统一 UTC 避免混淆。
    """
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类"""


# 5.1 任务表
class TaskRow(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    keyword: Mapped[str] = mapped_column(String, nullable=False)
    min_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 仅展示最近 N 天内发布的商品（None 表示不过滤）
    max_publish_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exclude_words: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    region: Mapped[str | None] = mapped_column(String, nullable=True)
    # 闲鱼筛选标签（JSON 数组，如 ["personal_idle", "free_shipping"]）
    search_filters: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    cron: Mapped[str] = mapped_column(String, nullable=False, default="*/1 * * * *")
    # 调度模式开关：True=cron 表达式，False=interval_seconds 固定间隔
    use_cron: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 固定间隔调度模式下的循环间隔（秒），仅 use_cron=0 时生效
    interval_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=60.0)
    mode: Mapped[str] = mapped_column(String, nullable=False, default="confirm")
    notifier_channels: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    ai_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    eval_threshold: Mapped[int] = mapped_column(Integer, default=60)
    status: Mapped[str] = mapped_column(String, nullable=False, default="running")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )


# 5.2 商品表
class ItemRow(Base):
    __tablename__ = "items"
    # 联合索引：按任务+首见时间排序是 Dashboard 商品列表的核心查询路径
    __table_args__ = (
        Index("ix_items_task_first_seen", "task_id", "first_seen"),
        Index("ix_items_seller", "seller_id"),
        Index("ix_items_publish_time", "publish_time"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    publish_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    region: Mapped[str | None] = mapped_column(String, nullable=True)
    seller_id: Mapped[str | None] = mapped_column(String, nullable=True)
    want_cnt: Mapped[int] = mapped_column(Integer, default=0)
    view_cnt: Mapped[int] = mapped_column(Integer, default=0)
    thumb_url: Mapped[str | None] = mapped_column(String, nullable=True)
    image_urls: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    last_seen: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )
    # 销售状态：0=在售，1=已售。由 buyer/collector 检测写入
    is_sold: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 检测到已售的时间戳，便于排查检测来源
    sold_detected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


# 5.3 卖家表
class SellerRow(Base):
    __tablename__ = "sellers"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    nick: Mapped[str | None] = mapped_column(String, nullable=True)
    credit_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    register_days: Mapped[int] = mapped_column(Integer, default=0)
    on_sale_count: Mapped[int] = mapped_column(Integer, default=0)
    sold_count: Mapped[int] = mapped_column(Integer, default=0)
    top_category: Mapped[str | None] = mapped_column(String, nullable=True)
    top_category_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    post_count_30d: Mapped[int] = mapped_column(Integer, default=0)
    bad_review_count: Mapped[int] = mapped_column(Integer, default=0)
    in_blacklist: Mapped[int] = mapped_column(Integer, default=0)
    recent_posts_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_visited: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_eval: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


# 5.4 评估结果表
class EvaluationRow(Base):
    __tablename__ = "evaluations"
    __table_args__ = (
        Index("ix_evaluations_seller", "seller_id"),
        Index("ix_evaluations_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    seller_id: Mapped[str | None] = mapped_column(String, nullable=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_level: Mapped[str] = mapped_column(String, nullable=False)
    dimension_scores: Mapped[str | None] = mapped_column(Text, nullable=True)
    reject_reasons: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


# 5.5 订单快照
class OrderRow(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_seller", "seller_id"),
        Index("ix_orders_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    item_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    seller_id: Mapped[str | None] = mapped_column(String, nullable=True)
    order_no: Mapped[str | None] = mapped_column(String, nullable=True)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String, nullable=False)
    screenshot: Mapped[str | None] = mapped_column(String, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


# 5.6 事件日志
class EventRow(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    task_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    item_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    stage: Mapped[str] = mapped_column(String, nullable=False)
    level: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)

    # 联合索引：按任务+时间范围查事件是 Dashboard 时间线的核心查询路径
    __table_args__ = (
        Index("ix_events_task_created", "task_id", "created_at"),
    )


# 5.6.1 后台错误日志（独立表：捕获未处理异常 + 请求上下文 + AI 诊断上下文）
# 与 events 表解耦：error_logs 专供技术维护人员排查问题，
# 包含完整堆栈/请求参数/服务器环境等异常专用字段
class ErrorLogRow(Base):
    __tablename__ = "error_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow, index=True)
    error_type: Mapped[str] = mapped_column(String, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    stack_trace: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 请求上下文（异常发生在 HTTP 请求中时填充）
    request_method: Mapped[str | None] = mapped_column(String, nullable=True)
    request_path: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    request_params: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: query + body（脱敏）
    request_headers: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: 脱敏后的 headers

    # 来源标识（单 token 认证体系下用请求来源代替用户身份）
    client_ip: Mapped[str | None] = mapped_column(String, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String, nullable=True)

    # 服务器环境快照
    server_env: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON

    # AI 诊断上下文（双格式：结构化 JSON + Markdown 报告）
    ai_context_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_context_md: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 状态管理：new / resolved / ignored
    status: Mapped[str] = mapped_column(String, nullable=False, default="new", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


# 5.7 任务-内容关联（支持 Items / Sellers / URL）
# 设计：link_type + link_key 联合唯一，避免重复关联。
# source 区分 auto（Worker 抓到自动写入）/ manual（用户在 Web 端手动添加）。
class TaskLinkRow(Base):
    __tablename__ = "task_links"
    __table_args__ = (
        UniqueConstraint("task_id", "link_type", "link_key", name="uq_task_link"),
        # 联合索引：按 link_type+link_key 反查任务关联是常用查询路径
        Index("ix_task_links_type_key", "link_type", "link_key"),
        # refresh_links 按 task_id + source='auto' 批量删除，复合索引避免全表扫描
        Index("ix_task_links_task_source", "task_id", "source"),
        # 商品列表查询核心索引：list_and_count_task_links 按 task_id+link_type 过滤并按 created_at 降序排序，
        # 三元组复合索引使查询走 covering index scan，避免临时 B-Tree 排序
        Index("ix_task_links_task_type_created", "task_id", "link_type", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    link_type: Mapped[str] = mapped_column(String, nullable=False)  # 'item' | 'seller'
    link_key: Mapped[str] = mapped_column(String, nullable=False, index=True)
    display: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON 冗余
    source: Mapped[str] = mapped_column(String, nullable=False, default="auto")  # 'auto' | 'manual'
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )


# 5.9 任务依赖关系（F-16）
# 语义：task_id 依赖 depends_on 成功后才启动
# 如"A 抢到镜头 → 自动启动 B 抢配套滤镜"，则 B.task_id 依赖 A.depends_on
# UniqueConstraint 防止重复声明同一对依赖
class TaskDepRow(Base):
    __tablename__ = "task_deps"
    __table_args__ = (
        UniqueConstraint("task_id", "depends_on", name="uq_task_dep"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    depends_on: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


# 5.8 业务通知（P1-4 Notification Center）
# 与 events 表分工：
# - events：技术性日志（订单状态变化、任务启停、评估命中），高频、只读追加
# - notifications：业务性提醒（订单超时待支付、登录态失效、配置回滚），低频、
#   持久化、区分已读/未读、支持点击跳转
# dedup_key：同业务事件去重（避免同一订单超时被反复告警），升级阈值时换 key
# UNIQUE(dedup_key)：同 dedup_key 只保留最新一条
class NotificationRow(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("dedup_key", name="uq_notification_dedup"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    level: Mapped[str] = mapped_column(String, nullable=False, default="info")  # info / warn / err
    category: Mapped[str] = mapped_column(String, nullable=False)  # order / auth / system / config
    title: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str | None] = mapped_column(String, nullable=True)  # 点击跳转 URL
    dedup_key: Mapped[str] = mapped_column(String, nullable=False)  # 同类去重 key
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # NULL = 未读
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


# 5.10 闲鱼账号池（P1-2 多账号轮换）
# 支持配置多个闲鱼账号，任务可绑定账号，自动轮换避免单账号高频触发风控。
# status：active=可用 / cooldown=冷却中（触发风控后自动冷却）/ disabled=禁用
# cookies：JSON 字符串，存储登录后的 Cookie 列表
# last_used_at：上次使用时间，轮换调度器据此选择最久未用的账号
# cooldown_until：冷却截止时间，超过此时间自动恢复 active
class AccountRow(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        Index("ix_accounts_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)  # 账号别名（唯一）
    nickname: Mapped[str | None] = mapped_column(String, nullable=True)  # 闲鱼昵称
    cookies: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: Cookie 列表
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")  # active/cooldown/disabled
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0)  # 累计使用次数
    fail_count: Mapped[int] = mapped_column(Integer, default=0)  # 连续失败次数
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )


# 5.11 代理 IP 池（P1-2 代理池）
# 支持配置多个代理 IP，任务执行时自动轮换，降低单 IP 触发风控概率。
# status：active=可用 / disabled=禁用
# fail_count：连续失败次数，超过阈值自动禁用
# last_check_at：上次健康检查时间
class ProxyRow(Base):
    __tablename__ = "proxies"
    __table_args__ = (
        Index("ix_proxies_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String, nullable=False, unique=True)  # http://user:pass@host:port
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")  # active/disabled
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 最近一次健康检查延迟
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


def create_sqlite_engine(db_path: str = "data/xianyu.db"):
    """创建 SQLite 引擎（启用 WAL、外键约束）"""
    from pathlib import Path

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
    )

    # 启用 WAL 模式（提升并发读写）
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    return engine


def init_db(db_path: str = "data/xianyu.db") -> None:
    """初始化数据库（创建所有表 + 增量迁移缺失列/索引）"""
    engine = create_sqlite_engine(db_path)
    Base.metadata.create_all(engine)
    # 增量迁移：为已有表添加 ORM 中新增但数据库中缺失的列
    _migrate_add_column(engine, "events", "type", "TEXT")
    _migrate_add_column(engine, "tasks", "max_publish_days", "INTEGER")
    # 调度模式字段：修复前端 cron 配置断层（之前 use_cron 始终为 False，所有任务走 60s interval）
    _migrate_add_column(engine, "tasks", "use_cron", "INTEGER")
    _migrate_add_column(engine, "tasks", "interval_seconds", "REAL")
    # 回填 NULL 行：ALTER TABLE 对已有行填 NULL，读取端 float(None) 会抛 TypeError 导致 scheduler 启动崩溃
    # 必须在迁移后立即 UPDATE，保证 DB 数据干净
    with engine.connect() as conn:
        conn.execute(sa_text("UPDATE tasks SET use_cron=0 WHERE use_cron IS NULL"))
        conn.execute(sa_text("UPDATE tasks SET interval_seconds=60.0 WHERE interval_seconds IS NULL"))
        conn.commit()
    # 增量迁移：items 表新增销售状态字段（buyer/collector 检测写入）
    _migrate_add_column(engine, "items", "is_sold", "INTEGER")
    _migrate_add_column(engine, "items", "sold_detected_at", "TEXT")
    # 增量迁移：为 task_links 添加 task_id+source 复合索引（refresh_links 批量删除用）
    _migrate_create_index(engine, "task_links", "ix_task_links_task_source", "task_id, source")

    # 性能优化：补建 items 表缺失的索引
    # 为什么需要：Base.metadata.create_all 只对新建表生效，已有数据库不会自动补建索引。
    # 实测发现 items 表只有主键索引，导致 list_items_by_seller / list_items 全表扫描。
    _migrate_create_index(engine, "items", "ix_items_task_first_seen", "task_id, first_seen")
    _migrate_create_index(engine, "items", "ix_items_seller", "seller_id")
    _migrate_create_index(engine, "items", "ix_items_publish_time", "publish_time")

    # 性能优化：补建 task_links 缺失的复合索引
    # ix_task_links_type_key：lookup_task_links 反查使用 (link_type, link_key)
    _migrate_create_index(engine, "task_links", "ix_task_links_type_key", "link_type, link_key")
    # ix_task_links_task_type_created：list_and_count_task_links 核心查询路径使用
    # 覆盖 (task_id, link_type, created_at) 三元组，避免 ORDER BY 临时 B-Tree 排序
    _migrate_create_index(engine, "task_links", "ix_task_links_task_type_created", "task_id, link_type, created_at")


def _migrate_add_column(engine: Engine, table: str, column: str, col_type: str) -> None:
    """安全地为已有表添加列（列已存在则跳过）

    table/column/col_type 仅接受内部硬编码值，通过白名单校验防止注入。
    """
    # 白名单校验：仅允许字母数字和下划线，防止SQL注入
    import re
    _IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
    if not (_IDENT_RE.match(table) and _IDENT_RE.match(column) and _IDENT_RE.match(col_type)):
        raise ValueError(f"Invalid identifier: table={table!r}, column={column!r}, col_type={col_type!r}")
    with engine.connect() as conn:
        # PRAGMA table_info 返回已有列名
        existing = {row[1] for row in conn.execute(sa_text(f"PRAGMA table_info({table})")).all()}
        if column not in existing:
            conn.execute(sa_text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
            conn.commit()


def _migrate_create_index(engine: Engine, table: str, index_name: str, columns: str) -> None:
    """安全地为已有表创建索引（索引已存在则跳过）

    columns 为逗号分隔的列名列表，如 "task_id, source"。
    """
    import re
    _IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
    if not _IDENT_RE.match(table) or not _IDENT_RE.match(index_name):
        return
    # 校验每个列名
    for col in columns.split(","):
        if not _IDENT_RE.match(col.strip()):
            return
    with engine.connect() as conn:
        existing = {row[1] for row in conn.execute(sa_text(f"PRAGMA index_list({table})")).all()}
        if index_name not in existing:
            conn.execute(sa_text(f"CREATE INDEX {index_name} ON {table} ({columns})"))
            conn.commit()
