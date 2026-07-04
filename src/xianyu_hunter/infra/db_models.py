"""SQLAlchemy 表结构定义

设计文档 §5 数据模型 DDL 的 1:1 实现。

时间字段约定：所有 datetime 列统一使用 UTC（datetime.utcnow），
SQLite 不存储时区信息，统一 UTC 避免本地时区混淆。
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

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
from sqlalchemy.pool import NullPool


def _utcnow() -> datetime:
    """返回当前 UTC 时间（替代 datetime.now，确保时区一致）

    使用 timezone-aware 的 datetime.now(UTC) 替代已弃用的 datetime.utcnow()。
    SQLite 不存储时区信息，但 Python 侧统一 UTC 避免混淆。
    """
    return datetime.now(timezone.utc)


# S1192: 提取迁移函数中重复的正则为模块级常量
# S6353: [A-Za-z0-9_] 等价于 ASCII 模式下的 \w，使用 re.ASCII 保证不匹配 Unicode 字母
_IDENT_RE = re.compile(r'^[A-Za-z_]\w*$', re.ASCII)


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
    # nullable=True：None 表示沿用全局 eval.pass_score，任务级覆盖时才写入具体值
    eval_threshold: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 任务级配置覆盖（JSON）：为空表示沿用全局配置
    # 为什么用单个 JSON 字段而非多列：任务级覆盖字段稀疏，多列会让 DB schema 臃肿且迁移繁琐；
    # JSON 存储支持灵活的字段扩展，运行时深度合并全局配置与任务级覆盖
    # search_config: 覆盖 AppConfig.search（page_size/sort_type/timeout/regions/filter_tags）
    search_config: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    # price_config: 覆盖 AppConfig.price_strategy（enabled_max/max_price/enabled_min/min_price/...）
    price_config: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    # antidetect_config: 覆盖 AppConfig.antidetect（qps/min_delay_ms/max_delay_ms/fail_pause_threshold/fail_window_sec）
    antidetect_config: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    # eval_config: 覆盖 AppConfig.eval 的部分字段（auto_collect_official/auto_collect_max_per_run 等）
    # 与 search_config/price_config/antidetect_config 保持一致的 JSON 存储模式
    eval_config: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    status: Mapped[str] = mapped_column(String, nullable=False, default="running")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )
    # 多用户：任务归属用户 ID（default 为迁移默认用户）
    # server_default 与 init_db 迁移的 ALTER TABLE ... DEFAULT 'default' 保持一致，
    # 确保全新数据库（create_all）下 raw SQL INSERT 未指定 user_id 时也能自动填充
    user_id: Mapped[str] = mapped_column(String, nullable=False, default="default", server_default="default")


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
    # 采集来源标记：search=搜索结果 / official=官方采集 / live=实时搜索/手动刷新
    # 为什么单独建列：原仅写在 events.payload JSON 中无法高效筛选，建列后支持按来源统计与过滤
    data_source: Mapped[str] = mapped_column(Text, default='search')


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
    # 全局流水号：标识触发本条事件的请求/任务链路
    # nullable=True 兼容历史数据；查询层通过 request_id 快速关联同链路所有日志
    request_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

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
    # 全局流水号：关联到触发本次异常的请求链路
    # 与 events.request_id 同名，便于聚合查询端点统一检索两表
    request_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

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


# 5.20 批量采集进度持久化表（断点续传）
# 暂停时写入待处理 item_id 列表，继续时读取并过滤已处理项。
# 为什么不用内存：进程重启会丢失进度，导致重复采集；
# 为什么单行设计：同一时刻最多只有一个批次在运行，task_id 唯一标识某次运行。
class BatchRefreshProgressRow(Base):
    __tablename__ = "batch_refresh_progress"
    __table_args__ = (
        Index("ix_batch_refresh_progress_task_id", "task_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # 待处理 item_id 列表（JSON 数组），暂停时持久化，继续时读取
    pending_item_ids: Mapped[str] = mapped_column(Text, nullable=False)
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # paused=暂停中可续传 / running=运行中 / done=已完成 / stopped=已停止
    status: Mapped[str] = mapped_column(String, nullable=False, default="paused")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )


# 5.21 批量采集任务执行历史表
# 与 batch_refresh_progress 分工：
# - progress 表：仅存当前未完成批次的断点信息，批次结束即清理
# - history 表：持久化每次执行的完整记录，用于查询历史/统计执行次数/排查问题
# task_id 全局自增（从 DB MAX(task_id)+1 初始化），跨进程重启不重置
class BatchRefreshHistoryRow(Base):
    __tablename__ = "batch_refresh_history"
    __table_args__ = (
        Index("ix_batch_refresh_history_task_id", "task_id"),
        Index("ix_batch_refresh_history_started_at", "started_at"),
        Index("ix_batch_refresh_history_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 全局自增任务 ID，跨进程重启不重置（启动时从 DB MAX 初始化）
    task_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # 触发来源：manual=用户手动触发 / scheduler=APScheduler 定时触发
    trigger_source: Mapped[str] = mapped_column(String, nullable=False, default="manual")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    # 完成时间：批次结束时填充（含 cancelled）；running 状态时为 NULL
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # completed=正常完成 / cancelled=用户停止 / failed=连续失败熔断 / running=执行中
    status: Mapped[str] = mapped_column(String, nullable=False, default="running")
    # 错误/警告消息聚合（JSON 数组字符串，每条 {item_id, error, timestamp}），上限 50 条
    error_messages: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 触发熔断时的连续失败次数（仅 failed 状态有值，用于排查浏览器异常）
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 执行耗时毫秒（completed_at - started_at），completed 时计算
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


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


# ============== 智能客服模块表（chatbot_*）==============
# 设计文档：docs/chatbot-详细设计.md §2.2
# 所有表统一 chatbot_ 前缀，与主系统表解耦，无外键关联（关系在应用层维护）

class ChatbotSessionRow(Base):
    """智能客服会话表

    一个会话对应一次连续对话，支持多轮消息交互。
    message_count 为冗余字段，由 add_message 时同步维护，避免 N+1 聚合查询。
    """
    __tablename__ = "chatbot_sessions"
    __table_args__ = (
        # 会话列表查询核心索引：WHERE user_id=? AND status=? ORDER BY created_at DESC
        Index("ix_chatbot_sessions_user_status_created", "user_id", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)  # UUID32（无连字符）
    # 单 Token 系统下固定为 'default'，预留多用户扩展
    user_id: Mapped[str] = mapped_column(String, nullable=False, default="default", index=True)
    title: Mapped[str] = mapped_column(String, nullable=False, default="新对话")
    # active=活跃 / ended=已结束 / escalated=已转人工（见 §6.1 状态机）
    status: Mapped[str] = mapped_column(String, nullable=False, default="active", index=True)
    # 冗余计数：由 ChatbotRepository.add_message 同步维护
    # 为什么冗余：会话列表展示消息数时避免 N+1 聚合查询
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 最后活跃时间：用于会话超时判定（session_timeout_min）
    last_active_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
    # 会话元数据（JSON）：intent_summary / escalation_reason 等
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # M2：收藏标记，收藏的会话在列表中置顶显示
    is_favorite: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class ChatbotMessageRow(Base):
    """智能客服消息表

    存储每个会话的完整对话历史，支持上下文构建与消息回放。
    role: user=用户消息 / assistant=AI回复 / system=系统消息
    """
    __tablename__ = "chatbot_messages"
    __table_args__ = (
        # 消息历史查询核心索引：WHERE session_id=? ORDER BY created_at
        Index("ix_chatbot_messages_session_created", "session_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)  # UUID32
    session_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String, nullable=False)  # user / assistant / system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # AI 回复的元数据（JSON）：sources / tool_calls / intent / tokens_used
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 用户反馈：positive：点赞 / negative：点踩 / null：未反馈
    feedback: Mapped[str | None] = mapped_column(String, nullable=True)
    feedback_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    # M6：1-5 星评分（存于 messages 表用于快速展示）
    feedback_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # M6：反馈分类（irrelevant/inaccurate/other）
    feedback_category: Mapped[str | None] = mapped_column(String, nullable=True)
    # token 消耗（仅 assistant 消息）：用于预算追踪
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # M4：用户消息关联的图片（JSON 数组，存 data URL），仅 user 消息有值
    images_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # M4：消息撤回标记（0=正常，1=已撤回），软删除保留审计
    is_recalled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class ChatbotFAQRow(Base):
    """FAQ 知识库

    存储高频问题与标准答案，由 FAQMatcher 进行相似度匹配。
    question_embedding 存 DB 而非 ChromaDB：FAQ 量小（<1000），
    DB 查询 + 应用层 cosine 即可，避免 ChromaDB 双集合管理复杂度。
    """
    __tablename__ = "chatbot_faqs"
    __table_args__ = (
        Index("ix_chatbot_faqs_category_active", "category", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False, default="general")
    # 问题向量（JSON 数组，1536 维）：由 EmbeddingService 生成
    question_embedding: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 1=启用 / 0=禁用（用 Integer 而非 Boolean，与主系统 is_sold 等字段保持一致）
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class ChatbotFeedbackRow(Base):
    """用户反馈独立表

    与 chatbot_messages.feedback 解耦：
    - chatbot_messages.feedback：快速标记，用于列表展示
    - chatbot_feedback：完整记录，用于趋势分析与转人工判定
    """
    __tablename__ = "chatbot_feedback"
    __table_args__ = (
        # 转人工判定核心索引：WHERE session_id=? AND created_at > ?（30 分钟窗口）
        Index("ix_chatbot_feedback_session_created", "session_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    message_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    rating: Mapped[str] = mapped_column(String, nullable=False)  # positive / negative
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    # M6：1-5 星评分（与 rating 并存：4-5→positive，1-3→negative）
    star_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # M6：反馈分类（irrelevant/inaccurate/other）
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    # 触发转人工的反馈会标记 escalate_triggered=1
    escalate_triggered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class ChatbotKBVersionRow(Base):
    """知识库版本表

    每次构建/增量更新创建一条版本记录，支持回滚到任意历史版本。
    snapshot_path 指向磁盘上的 ChromaDB 快照目录。
    """
    __tablename__ = "chatbot_kb_versions"
    __table_args__ = (
        Index("ix_chatbot_kb_versions_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)  # UUID32
    # 快照磁盘路径：data/chromadb/snapshots/{version_id}/
    snapshot_path: Mapped[str] = mapped_column(Text, nullable=False)
    # 文档内容 hash（MD5）：用于增量更新时检测是否真的变更
    doc_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # build：全量构建 / incremental：增量更新 / rollback：回滚产生
    build_type: Mapped[str] = mapped_column(String, nullable=False, default="build")
    # 构建状态：success / partial / failed / rolled_back（见 §6.2 状态机）
    status: Mapped[str] = mapped_column(String, nullable=False, default="success")
    # 构建耗时（秒）
    build_duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 错误信息（status=failed 时填充）
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class ChatbotConfigRow(Base):
    """客服模块运行时配置表（KV 模式）

    与 yaml_config.py 的 ChatbotConfig 分工：
    - yaml_config.py：启动时加载的静态配置，修改需重启
    - chatbot_config 表：运行时热更新的配置，通过 PUT /api/chatbot/config 修改
    仅支持热更新的字段存于此表（如 enabled / similarity_threshold / escalation_contact）
    """
    __tablename__ = "chatbot_config"
    __table_args__ = (
        UniqueConstraint("key", name="uq_chatbot_config_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    # 值类型：bool / int / float / string / json
    value_type: Mapped[str] = mapped_column(String, nullable=False, default="string")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class ChatbotAuditLogRow(Base):
    """客服模块审计日志表

    记录配置变更、FAQ 增删、知识库重建等敏感操作。
    不记录明文 value，仅记录 hash 以便审计追溯（敏感字段保护）。
    """
    __tablename__ = "chatbot_audit_logs"
    __table_args__ = (
        Index("ix_chatbot_audit_logs_action_created", "action", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # config_update / faq_upsert / faq_delete / kb_rebuild / kb_rollback
    action: Mapped[str] = mapped_column(String, nullable=False)
    target: Mapped[str] = mapped_column(String, nullable=False)  # 配置 key / FAQ id / 版本 id
    old_value_hash: Mapped[str | None] = mapped_column(String, nullable=True)  # SHA256
    new_value_hash: Mapped[str | None] = mapped_column(String, nullable=True)  # SHA256
    # 操作来源：web=Web界面 / api=API调用 / scheduler=调度器 / system=系统自动
    source: Mapped[str] = mapped_column(String, nullable=False, default="web")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


# ============================================================
# 多用户模块表（MU1）
# ============================================================

class UserRow(Base):
    """用户表：每个闲鱼账号对应一个用户记录

    user_id 来源：闲鱼 Cookie 的 unb 字段；default 为迁移默认用户
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    nickname: Mapped[str] = mapped_column(String, default="")
    avatar_url: Mapped[str] = mapped_column(String, default="")
    custom_alias: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    last_active_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        Index("idx_users_status", "status"),
    )


class UserSessionRow(Base):
    """用户会话表：session_token 的 sha256 哈希存储

    原始 token 仅存 cookie，库内只存哈希（防库泄露后伪造）
    """
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    token_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    last_renewed_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    client_ip: Mapped[str] = mapped_column(String, default="")
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        Index("idx_sessions_user_active", "user_id", "is_active"),
        Index("idx_sessions_expires", "expires_at"),
    )


class UserCookieRow(Base):
    """用户级 Cookie 存储：替代全局 Cookies 表，新增 user_id 维度"""
    __tablename__ = "user_cookies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    host_key: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str] = mapped_column(String, default="/")
    expires: Mapped[int] = mapped_column(Integer, default=-1)
    is_secure: Mapped[int] = mapped_column(Integer, default=1)
    is_httponly: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        UniqueConstraint("user_id", "host_key", "name", name="uq_user_cookies"),
        Index("idx_user_cookies_user", "user_id"),
        Index("idx_user_cookies_user_host", "user_id", "host_key"),
    )


class UserMenuConfigRow(Base):
    """用户菜单配置表：可见性、排序、别名等用户级覆盖"""
    __tablename__ = "user_menu_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    menu_key: Mapped[str] = mapped_column(String, nullable=False)
    visible: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    group_name: Mapped[str] = mapped_column(String, default="")
    custom_label: Mapped[str] = mapped_column(String, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        UniqueConstraint("user_id", "menu_key", name="uq_user_menu"),
        Index("idx_menu_configs_user", "user_id"),
        Index("idx_menu_configs_user_sort", "user_id", "sort_order"),
    )


class UserPreferenceRow(Base):
    """用户偏好配置表：替代 localStorage，按 user_id 隔离"""
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    pref_key: Mapped[str] = mapped_column(String, nullable=False)
    pref_value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        UniqueConstraint("user_id", "pref_key", name="uq_user_prefs"),
        Index("idx_prefs_user", "user_id"),
    )


class UserSessionEventRow(Base):
    """会话事件日志表：登录/切换/退出/Cookie过期等事件"""
    __tablename__ = "user_session_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    __table_args__ = (
        Index("idx_session_events_user", "user_id", "created_at"),
        Index("idx_session_events_type", "event_type"),
        Index("idx_session_events_created", "created_at"),
    )


def create_sqlite_engine(db_path: str = "data/xianyu.db"):
    """创建 SQLite 引擎（启用 WAL、外键约束、busy_timeout、NullPool）

    为什么用 NullPool 而非 StaticPool：
    StaticPool 全进程共享单连接，配合 check_same_thread=False 让多线程复用
    同一 sqlite3.Connection。但 sqlite3.Connection 不是线程安全对象，
    cursor.execute 与后续 fetchone 在多线程并发时会互相重置 cursor 状态，
    触发 InterfaceError("bad parameter or other API misuse")。

    NullPool 每次 engine.connect() 创建独立连接、关闭时销毁，
    每个线程持有自己的 Connection，从根本上避免跨线程 cursor 竞争。
    WAL 模式 + busy_timeout 负责处理多连接的并发读写。

    为什么必须设置 busy_timeout：
    SQLite 默认 busy_timeout=0，遇到锁立即抛 "database is locked"。
    设为 10000ms 让并发写入请求排队等待，WAL 模式下读操作不受影响。
    这是 worker/batch_refresh/cookie_sync/API 路由四路并发写入的基础保障。

    为什么增大 cache_size：
    SQLite 默认 cache_size 约 2MB，对中等规模查询偏小。
    设为 -20000（约 20MB）提升列表查询和聚合性能，内存开销可控。
    """
    from pathlib import Path

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        future=True,
        # NullPool：每次 connect() 创建独立 sqlite3.Connection，避免跨线程共享
        # check_same_thread=False：保留以兼容 anyio worker thread 复用场景
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )

    # 每个 DBAPI 连接建立时设置 PRAGMA（NullPool 下每次 connect 都执行）
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA synchronous=NORMAL")
        # busy_timeout=10000ms：并发写入时排队等待而非立即报错
        cursor.execute("PRAGMA busy_timeout=10000")
        # cache_size=-20000：约 20MB 页缓存，提升查询性能
        cursor.execute("PRAGMA cache_size=-20000")
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
    # 任务级配置覆盖字段（JSON）：为空表示沿用全局配置
    _migrate_add_column(engine, "tasks", "search_config", "TEXT")
    _migrate_add_column(engine, "tasks", "price_config", "TEXT")
    _migrate_add_column(engine, "tasks", "antidetect_config", "TEXT")
    # eval_config: 任务级覆盖 AppConfig.eval（auto_collect_official/auto_collect_max_per_run 等）
    _migrate_add_column(engine, "tasks", "eval_config", "TEXT")
    # 增量迁移：items 表新增销售状态字段（buyer/collector 检测写入）
    _migrate_add_column(engine, "items", "is_sold", "INTEGER")
    _migrate_add_column(engine, "items", "sold_detected_at", "TEXT")
    # 幂等迁移：items 表新增 data_source 列（采集来源标记）
    # 取值：search（搜索结果）/ official（官方采集）/ live（实时搜索/手动刷新）
    _migrate_add_column(engine, "items", "data_source", "TEXT")
    # 回填 NULL 行：ALTER TABLE 对已有行填 NULL，需回填默认值 'search' 保证数据干净
    with engine.connect() as conn:
        conn.execute(sa_text("UPDATE items SET data_source='search' WHERE data_source IS NULL"))
        conn.commit()
    # 增量迁移：为 task_links 添加 task_id+source 复合索引（refresh_links 批量删除用）
    _migrate_create_index(engine, "task_links", "ix_task_links_task_source", "task_id, source")

    # 性能优化：补建 items 表缺失的索引
    # 为什么需要：Base.metadata.create_all 只对新建表生效，已有数据库不会自动补建索引。
    # 实测发现 items 表只有主键索引，导致 list_items_by_seller / list_items 全表扫描。
    _migrate_create_index(engine, "items", "ix_items_task_first_seen", "task_id, first_seen")
    _migrate_create_index(engine, "items", "ix_items_seller", "seller_id")
    _migrate_create_index(engine, "items", "ix_items_publish_time", "publish_time")
    # 批量采集调度器查询 is_sold=0 的在售商品，单列索引避免全表扫描
    _migrate_create_index(engine, "items", "ix_items_is_sold", "is_sold")

    # 性能优化：补建 task_links 缺失的复合索引
    # ix_task_links_type_key：lookup_task_links 反查使用 (link_type, link_key)
    _migrate_create_index(engine, "task_links", "ix_task_links_type_key", "link_type, link_key")
    # ix_task_links_task_type_created：list_and_count_task_links 核心查询路径使用
    # 覆盖 (task_id, link_type, created_at) 三元组，避免 ORDER BY 临时 B-Tree 排序
    _migrate_create_index(engine, "task_links", "ix_task_links_task_type_created", "task_id, link_type, created_at")

    # schema 修复：将 tasks.eval_threshold 从旧版 NOT NULL 迁移为 nullable
    # 为什么需要：模型已改为 nullable=True（None 表示沿用全局 eval.pass_score），
    # 但旧版数据库创建时为 NOT NULL，create_all 不会修改已有表的列约束，
    # 导致插入 eval_threshold=None 的任务时触发 IntegrityError。
    # 放在末尾执行：先让其他迁移补齐缺失列，再统一重建表，避免列差异影响数据复制。
    _migrate_make_column_nullable(engine, "tasks", "eval_threshold")

    # MU1：tasks 表新增 user_id 字段 + 索引
    _migrate_add_column(engine, "tasks", "user_id", "TEXT DEFAULT 'default'")
    with engine.connect() as conn:
        conn.execute(sa_text("UPDATE tasks SET user_id='default' WHERE user_id IS NULL OR user_id=''"))
        conn.commit()
    _migrate_create_index(engine, "tasks", "idx_tasks_user", "user_id")
    _migrate_create_index(engine, "tasks", "idx_tasks_user_created", "user_id, created_at")
    _migrate_create_index(engine, "tasks", "idx_tasks_user_status", "user_id, status")

    # M2：chatbot_sessions 加 is_favorite 字段（收藏置顶）
    _migrate_add_column(engine, "chatbot_sessions", "is_favorite", "INTEGER")
    with engine.connect() as conn:
        conn.execute(sa_text("UPDATE chatbot_sessions SET is_favorite=0 WHERE is_favorite IS NULL"))
        conn.commit()

    # M4：chatbot_messages 加 images_json 和 is_recalled 字段
    _migrate_add_column(engine, "chatbot_messages", "images_json", "TEXT")
    _migrate_add_column(engine, "chatbot_messages", "is_recalled", "INTEGER")
    with engine.connect() as conn:
        conn.execute(sa_text("UPDATE chatbot_messages SET is_recalled=0 WHERE is_recalled IS NULL"))
        conn.commit()

    # M6：chatbot_messages 加 feedback_rating 和 feedback_category 字段
    _migrate_add_column(engine, "chatbot_messages", "feedback_rating", "INTEGER")
    _migrate_add_column(engine, "chatbot_messages", "feedback_category", "TEXT")
    # M6：chatbot_feedback 加 star_rating 和 category 字段
    _migrate_add_column(engine, "chatbot_feedback", "star_rating", "INTEGER")
    _migrate_add_column(engine, "chatbot_feedback", "category", "TEXT")

    # 全局流水号：events 和 error_logs 表新增 request_id 列 + 单列索引
    # 为什么建索引：聚合查询端点 /api/logs/request/{request_id} 按此列等值过滤，
    # 无索引会全表扫描，影响日志检索性能
    _migrate_add_column(engine, "events", "request_id", "TEXT")
    _migrate_add_column(engine, "error_logs", "request_id", "TEXT")
    _migrate_create_index(engine, "events", "ix_events_request_id", "request_id")
    _migrate_create_index(engine, "error_logs", "ix_error_logs_request_id", "request_id")


def _migrate_add_column(engine: Engine, table: str, column: str, col_type: str) -> None:
    """安全地为已有表添加列（列已存在则跳过）

    table/column/col_type 仅接受内部硬编码值，通过白名单校验防止注入。
    """
    # col_type 允许类型名 + DEFAULT + 数字 + 空格 + 单引号字符串字面量
    # （如 "INTEGER DEFAULT 0" / "TEXT DEFAULT 'default'"）
    # 为什么允许单引号：DEFAULT 子句的字符串字面量需单引号包裹（SQL 语法要求）
    # 仍禁止分号/双引号等危险字符防止注入；调用方仅限内部硬编码值
    _COL_TYPE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_ ']*$", re.ASCII)
    if not (_IDENT_RE.match(table) and _IDENT_RE.match(column) and _COL_TYPE_RE.match(col_type)):
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


def _migrate_make_column_nullable(engine: Engine, table: str, column: str) -> None:
    """SQLite 不支持 ALTER COLUMN，通过表重建将 NOT NULL 列改为 nullable

    仅在检测到列为 NOT NULL 时执行。使用 ORM 的 Table 定义重建表，
    保证 schema 与模型一致，避免 drift。数据通过列名交集复制，防止列差异。

    事务安全：整个重建过程包裹在单一事务中（engine.begin），任一步骤失败自动回滚。
    残留清理：迁移前先 DROP TABLE IF EXISTS {table}_old，避免上次失败残留导致永久阻塞。
    """
    from loguru import logger
    if not (_IDENT_RE.match(table) and _IDENT_RE.match(column)):
        return

    # 先检测是否需要迁移（单独连接，不持锁）
    with engine.connect() as conn:
        cols_info = conn.execute(sa_text(f"PRAGMA table_info({table})")).all()
        col_info = next((c for c in cols_info if c[1] == column), None)
        if not col_info:
            return  # 列不存在，create_all 会处理
        if col_info[3] == 0:
            return  # 已是 nullable，无需迁移

    logger.warning(
        f"检测到 {table}.{column} 为 NOT NULL（旧 schema），将重建表以改为 nullable"
    )

    orm_table = Base.metadata.tables.get(table)
    if orm_table is None:
        logger.error(f"ORM 中未找到 {table} 表定义，跳过迁移")
        return

    # 用单一事务包裹整个重建过程，失败时自动回滚
    from sqlalchemy.exc import SQLAlchemyError
    try:
        with engine.begin() as conn:
            # 0. 清理上次迁移失败的残留表（避免 RENAME 目标已存在报错）
            conn.execute(sa_text(f"DROP TABLE IF EXISTS {table}_old"))
            # 1. 重命名旧表
            conn.execute(sa_text(f"ALTER TABLE {table} RENAME TO {table}_old"))
            # 2. 使用当前连接创建新表（纳入事务，而非创建独立连接）
            orm_table.create(conn, checkfirst=True)
            # 3. 复制数据（取两表列名交集，防止列差异导致 INSERT 失败）
            old_cols = {c[1] for c in conn.execute(sa_text(f"PRAGMA table_info({table}_old)")).all()}
            common_cols = [c for c in orm_table.columns if c.name in old_cols]
            col_list = ", ".join(f'"{c.name}"' for c in common_cols)
            conn.execute(sa_text(
                f"INSERT INTO {table} ({col_list}) SELECT {col_list} FROM {table}_old"
            ))
            # 4. 删除旧表
            conn.execute(sa_text(f"DROP TABLE {table}_old"))
            # 退出 with 块时自动 commit
        logger.info(f"{table}.{column} 已迁移为 nullable（表重建完成）")
    except SQLAlchemyError as e:
        # engine.begin() 已自动回滚，但 SQLite 的 DDL 在某些情况下可能不完全回滚
        # 检查 {table} 是否存在，不存在则从 {table}_old 恢复
        logger.error(f"{table}.{column} 迁移失败: {e}")
        try:
            with engine.connect() as conn:
                tables = conn.execute(sa_text(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
                )).all()
                if not tables:
                    conn.execute(sa_text(f"ALTER TABLE {table}_old RENAME TO {table}"))
                    conn.commit()
                    logger.warning(f"{table} 表已从 {table}_old 恢复")
        except Exception as recover_err:
            # 恢复失败意味着 {table} 可能既不存在于新表也不存在于 _old，
            # 后续所有任务读写都会失败。必须抛异常阻止服务带病启动，
            # 否则启动日志显示"成功"但实际所有调度失败，问题难以定位
            logger.error(f"{table} 表恢复失败，请手动检查: {recover_err}")
            raise RuntimeError(
                f"数据库迁移失败且无法恢复：{table} 表可能丢失。"
                f"迁移错误: {e}; 恢复错误: {recover_err}"
            ) from recover_err
