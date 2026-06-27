"""领域模型：任务"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class TaskMode(str, Enum):
    """任务执行模式"""
    AUTO = "auto"            # 全自动直接拍
    SEMI_AUTO = "semi_auto"  # 推送确认后拍
    CONFIRM = "confirm"      # 仅推送不拍（默认最保守）
    NOTIFY_ONLY = "notify"   # 仅推送


class TaskStatus(str, Enum):
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"
    DELETED = "deleted"  # 软删除：任务本身保留但标记为已删除，关联数据已物理删除


@dataclass
class Task:
    """监控任务"""
    id: str
    name: str
    keyword: str
    min_price: float | None = None
    max_price: float | None = None
    # 仅展示最近 N 天内发布的商品（None 表示不过滤）
    max_publish_days: int | None = None
    exclude_words: list[str] = field(default_factory=list)
    region: str | None = None
    # 闲鱼筛选标签（对应搜索页的复选框：个人闲置、验货宝、包邮等）
    # 存储为字符串列表，搜索时映射为 URL 查询参数
    search_filters: list[str] = field(default_factory=list)
    cron: str = "*/1 * * * *"
    # 调度模式开关：True 时按 cron 表达式调度，False 时按 interval_seconds 固定间隔
    # 持久化到 DB，避免之前 TaskConfig.use_cron 与 Task.cron 分裂脑导致 cron 永远不生效
    use_cron: bool = False
    # 固定间隔调度模式下的循环间隔（秒），仅 use_cron=False 时生效
    interval_seconds: float = 60.0
    mode: TaskMode = TaskMode.CONFIRM
    notifier_channels: list[str] = field(default_factory=lambda: ["serverchan"])
    ai_prompt: str | None = None
    eval_threshold: int = 60
    status: TaskStatus = TaskStatus.RUNNING
    # 统一使用 UTC，与 infra/db_models._utcnow 保持一致
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# 闲鱼筛选标签 → 搜索 URL 参数映射
# 来源：goofish.com/search 页面的筛选复选框
XIANYU_FILTER_MAP = {
    "personal_idle": "sourceType=0",       # 个人闲置
    "verified":      "yhb=1",               # 验货宝（官方验真）
    "account_guarantee": "yhzp=1",          # 验号担保
    "free_shipping": "postageType=1",        # 包邮
    "super_shop":    "superShop=1",          # 超赞鱼小铺
    "brand_new":     "itemCondition=100",    # 全新
    "strict_select": "strictSelect=1",       # 严选
    "resale":        "resaleType=1",         # 转卖
}


@dataclass
class TaskConfig:
    """任务运行时配置（不持久化到 DB，由调度层构造）

    与 Task 领域模型的差异：
    - Task 是"声明"，存 DB；TaskConfig 是"调度参数"，运行时使用
    - interval_seconds: Worker 循环间隔（默认 60s）
    - max_items_per_run: 每次循环最多处理多少件商品（防 OOM/超时）
    - stop_on_first_buy: 抢到 1 单后立即停止本轮（防刷单）
    - cooldown_after_buy: 拍下后冷却秒数，期间不再下单

    设计文档 §3.8 - 调度配置。

    P1-7：新增 use_cron 模式，启用后按 Task.cron 表达式调度，
    适用于"每天 9:00-22:00 每 10 分钟一次"等作息化场景。
    """
    interval_seconds: float = 60.0
    max_items_per_run: int = 20
    stop_on_first_buy: bool = True
    cooldown_after_buy: float = 30.0
    # P1-7：是否使用 cron 表达式调度（True 时忽略 interval_seconds）
    use_cron: bool = False
    # 搜索参数（从 AppConfig.search 注入，控制 collector.search() 行为）
    search_page_size: int = 20        # 单次搜索返回的商品条目数
    search_sort_type: str = "default"  # 排序方式：default/newest/price_asc/price_desc/want_count
    search_timeout: int = 30          # 单次搜索请求的最大等待秒数
    search_regions: str = ""         # 地区过滤（逗号分隔，空字符串表示全国）
    search_filter_tags: list = None  # 闲鱼筛选标签列表（如包邮、信用极好等）
