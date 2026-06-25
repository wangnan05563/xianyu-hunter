"""YAML 配置加载（pydantic 模型校验）"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator


# ============== 配置模型定义 ==============

class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000


class BrowserConfig(BaseModel):
    headless: bool = False  # 非 headless 模式避免闲鱼 RGV587_ERROR 反爬检测
    user_data_dir: str = "./browser-data"
    viewport_width: int = 1920
    viewport_height: int = 1080
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
    # Cookie 定时自动同步配置
    auto_sync: bool = False                     # 默认关闭，需显式启用
    auto_sync_interval: int = 30                # 同步间隔（分钟）
    auto_sync_expiry_threshold: int = 10        # Cookie 剩余有效期阈值（分钟）
    cdp_port: int = 9222                        # CDP 调试端口


class AntiDetectConfig(BaseModel):
    qps: int = 1                          # 全局每秒请求上限
    min_delay_ms: int = 200
    max_delay_ms: int = 1500
    fail_pause_threshold: int = 3         # 连续失败次数触发熔断
    fail_window_sec: int = 3600           # 失败计数窗口


class WAFConfig(BaseModel):
    enabled: bool = True
    login_check_interval_min: int = 30    # 登录态检查间隔


class NotifierChannelsConfig(BaseModel):
    """推送渠道配置（Key 来自 keyring 加密存储）"""
    serverchan: bool = True
    pushplus: bool = True
    bark: bool = True


class QuietHoursConfig(BaseModel):
    """P3-F-10 免打扰时段配置

    - enabled: 总开关；关闭时所有事件照常推送
    - start / end: 24h "HH:MM"；支持跨午夜（如 23:00-07:00 表示 23:00 → 次日 07:00）
    - critical_only: 免打扰时段内仅 critical 级别可推送，其他事件落本地"待发摘要"
    - weekend_only: 仅周末（周六/日）启用；工作日保持全量推送
    """
    enabled: bool = False
    start: str = "23:00"
    end: str = "07:00"
    critical_only: bool = True
    weekend_only: bool = False


class NotifierConfig(BaseModel):
    default_channels: list[str] = Field(default_factory=lambda: ["serverchan"])
    channels: NotifierChannelsConfig = NotifierChannelsConfig()
    # P3-F-10：免打扰时段
    quiet_hours: QuietHoursConfig = QuietHoursConfig()
    # 事件订阅规则：用户勾选的事件类型列表（持久化到 YAML）
    subscribed_events: list[str] = Field(
        default_factory=lambda: [
            "EVAL_PASSED", "BUY_SUCCEEDED",  # 默认只订阅重要事件
        ]
    )


class EvalWeights(BaseModel):
    """评估维度权重（和应为 100）"""
    professional: int = 30
    credit: int = 30
    dispute: int = 25
    price: int = 15

    @model_validator(mode="after")
    def _check_weight_sum(self) -> "EvalWeights":
        total = self.professional + self.credit + self.dispute + self.price
        if total != 100:
            raise ValueError(
                f"评估权重之和必须为 100，实际 {total}: "
                f"professional={self.professional}, credit={self.credit}, "
                f"dispute={self.dispute}, price={self.price}"
            )
        return self


class EvalThresholds(BaseModel):
    """评估阈值"""
    on_sale_count: int = 30              # 超过视为职业
    post_count_30d: int = 15
    top_category_ratio: float = 0.8
    credit_score_min: int = 600          # 低于一票否决
    bad_review_max: int = 3
    register_days_min: int = 30


class EvalConfig(BaseModel):
    weights: EvalWeights = EvalWeights()
    thresholds: EvalThresholds = EvalThresholds()
    professional_keywords: list[str] = Field(
        default_factory=lambda: [
            "批发", "代理", "代购", "大量", "店铺", "厂家", "直发", "一手",
        ]
    )
    pass_score: int = 60                  # 大于等于通过
    auto_buy_score: int = 80              # 大于等于全自动拍下
    ai_auto_eval: bool = False            # 调度流程中自动调用 AI 评估（消耗 token）
    ai_auto_deep_analyze: bool = False    # 调度流程中自动深度分析（消耗更多 token）

    @model_validator(mode="after")
    def _check_score_order(self) -> "EvalConfig":
        # pass_score 必须不大于 auto_buy_score，否则逻辑矛盾（通过线高于自动抢单线）
        if self.pass_score > self.auto_buy_score:
            raise ValueError(
                f"通过分数 pass_score({self.pass_score}) 不能大于 "
                f"自动抢单分数 auto_buy_score({self.auto_buy_score})"
            )
        return self


class SearchConfig(BaseModel):
    """搜索参数配置（对应前端 /app/config/search 页面）

    独立于 antidetect（通用反检测），专门控制闲鱼搜索行为：
    - page_size: 单次搜索请求返回的商品条目数
    - sort_type: 搜索结果排序方式（default/newest/price_asc/price_desc/want_count）
    - timeout: 单次搜索请求的最大等待秒数
    - regions: 地区过滤（逗号分隔，空字符串表示全国）
    - filter_tags: 闲鱼筛选标签列表（如包邮、信用极好等）
    """
    page_size: int = 20
    sort_type: str = "default"
    timeout: int = 30
    regions: str = ""
    filter_tags: list[str] = Field(default_factory=list)


class PriceStrategyConfig(BaseModel):
    """价格策略配置（对应前端 /app/config/price 页面）

    4 种策略独立开关，与 PriceConfig（运行时 dataclass）对齐：
    - enabled_max / max_price: 硬性价格上限
    - enabled_min / min_price: 硬性价格下限（防 1 元引流）
    - enabled_market_ratio / market_ratio: 低于市场参考价比例
    - enabled_top_n / top_n: 同类低价 TopN
    """
    enabled_max: bool = True
    max_price: int = 10000
    enabled_min: bool = True
    min_price: int = 100
    enabled_market_ratio: bool = False
    market_ratio: float = 0.8
    enabled_top_n: bool = False
    top_n: int = 5


class AppConfig(BaseModel):
    """根配置"""
    server: ServerConfig = ServerConfig()
    browser: BrowserConfig = BrowserConfig()
    antidetect: AntiDetectConfig = AntiDetectConfig()
    waf: WAFConfig = WAFConfig()
    notifier: NotifierConfig = NotifierConfig()
    eval: EvalConfig = EvalConfig()
    search: SearchConfig = SearchConfig()
    price_strategy: PriceStrategyConfig = PriceStrategyConfig()


# ============== 加载逻辑 ==============

def load_yaml(path: str | Path) -> dict[str, Any]:
    """读取 YAML 文件"""
    p = Path(path)
    if not p.exists():
        return {}
    with p.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


_config: AppConfig | None = None


def get_config() -> AppConfig:
    """单例获取 AppConfig，从 config/*.yaml 加载"""
    global _config
    if _config is None:
        _config = _load_all()
    return _config


def _load_all() -> AppConfig:
    """合并 config/*.yaml 全部内容

    加载顺序与合并策略：
    1. 先加载子配置（eval.yaml / notifier.yaml / browser.yaml）作为默认值基线
    2. 最后加载主配置（config.yaml），用深度合并覆盖子配置

    为什么要这样：修复"抢单策略页面保存后刷新参数被重置"问题。
    旧实现用 data.update() 浅合并且 config.yaml 先加载，导致 eval.yaml 顶层
    整体覆盖 config.yaml 的 eval 块 → 用户在 /app/config/buyer 修改的
    pass_score / auto_buy_score 保存到 config.yaml 后，下次加载被 eval.yaml
    的默认值覆盖，表现为"保存后刷新参数被重置"。

    改用深度合并后：config.yaml 与 eval.yaml 同一字段，config.yaml 优先；
    两边都有的字段（weights / thresholds）保留 config.yaml；只在 eval.yaml
    出现的字段（如历史遗留的 ai_auto_eval）仍能加载到 AppConfig。
    """
    base = Path("config")
    data: dict[str, Any] = {}

    # 1) 先加载子配置（默认值基线）
    for name in ("eval.yaml", "notifier.yaml", "browser.yaml"):
        section_data = load_yaml(base / name)
        if section_data:
            _deep_merge_yaml(data, section_data)

    # 2) 主配置最后加载（用户修改覆盖子配置）
    main_data = load_yaml(base / "config.yaml")
    if main_data:
        _deep_merge_yaml(data, main_data)

    return AppConfig.model_validate(data)


def _deep_merge_yaml(target: dict[str, Any], source: dict[str, Any]) -> None:
    """深度合并：source 的字段覆盖 target 同名字段

    与 api_config.py 中 _deep_merge 的区别：函数同名但语义一致（patch 覆盖 target），
    单独命名是为了避免 yaml_config.py 依赖 web 层的工具。
    """
    for k, v in source.items():
        if isinstance(v, dict) and isinstance(target.get(k), dict):
            _deep_merge_yaml(target[k], v)
        else:
            target[k] = v


def reload_config() -> AppConfig:
    """重新加载（用于热更新）"""
    global _config
    _config = None
    return get_config()
