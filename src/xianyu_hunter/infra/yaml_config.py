"""YAML 配置加载（pydantic 模型校验）"""
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator

# 路径统一入口：避免硬编码 Path("config") / Path("data/chromadb")
from xianyu_hunter.paths import get_config_dir, get_chromadb_path


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
    # 代理服务器配置：
    # - 留空（默认）：强制禁用系统代理，避免 Clash/V2Ray 等代理软件未运行时
    #   触发 ERR_PROXY_CONNECTION_FAILED（闲鱼为国内站点，无需代理）
    # - 配置示例："socks5://127.0.0.1:7890" / "http://127.0.0.1:7890"
    #   海外部署需要代理访问闲鱼时配置此项
    proxy_server: str = ""
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
    telegram: bool = False
    wecom: bool = False
    dingtalk: bool = False
    webhook: bool = False
    ntfy: bool = False


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
    credit_score_min: int = 60           # 低于一票否决
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
    # P1: 自动官方采集——对通过 pass_score 的商品自动调用官方采集做深度验证
    # 关闭时仅靠爬虫方式采集详情+卖家主页；开启后额外提取评价/留言等官方数据
    auto_collect_official: bool = False
    # 每轮 run_once 最多自动官方采集的商品数（避免拖慢+反爬）
    auto_collect_max_per_run: int = 3
    # 自动官方采集去重窗口（分钟）：同一商品在窗口内不被重复采集
    # 默认 30 分钟，避免短时间内重复采集浪费配额
    auto_collect_dedup_window_minutes: int = 30
    # 自动官方采集失败退避阈值：连续失败达到此次数后暂停本轮自动采集
    # 默认 3 次，避免连续失败浪费配额；通过 notifier 发送告警
    auto_collect_fail_pause_threshold: int = 3
    # P3: AI 多轮优化建议——累积 N 轮后调用 LLM 生成自然语言优化建议
    # 与单轮结论(_save_run_conclusion)互补：单轮给即时反馈，多轮给趋势洞察
    ai_multi_run_suggestion: bool = False
    # 每隔多少轮生成一次 AI 建议（太小浪费 token，太大反馈滞后）
    ai_suggestion_interval: int = 5

    @model_validator(mode="after")
    def _check_score_order(self) -> "EvalConfig":
        # pass_score 必须不大于 auto_buy_score，否则逻辑矛盾（通过线高于自动抢单线）
        if self.pass_score > self.auto_buy_score:
            raise ValueError(
                f"通过分数 pass_score({self.pass_score}) 不能大于 "
                f"自动抢单分数 auto_buy_score({self.auto_buy_score})"
            )
        return self

    @model_validator(mode="after")
    def _check_interval_range(self) -> "EvalConfig":
        # ai_suggestion_interval 必须 >= 1：worker.py 用 len(history) % interval 触发，
        # interval=0 会抛 ZeroDivisionError；同时 max_history = interval*2 = 0 会导致
        # self._run_history[-0:] 等价于 [0:]（不截断），内存无限增长
        if self.ai_suggestion_interval < 1:
            raise ValueError(
                f"ai_suggestion_interval 必须 >= 1，实际 {self.ai_suggestion_interval}"
            )
        # auto_collect_max_per_run 不能为负：worker.py 用 stats.official_collected < max 判断，
        # 负数会让条件永远 False，官方采集静默禁用且语义不清
        if self.auto_collect_max_per_run < 0:
            raise ValueError(
                f"auto_collect_max_per_run 不能为负，实际 {self.auto_collect_max_per_run}"
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


class BatchRefreshConfig(BaseModel):
    """批量采集调度器配置

    定时刷新在售商品详情，用于检测已售状态、补全字段。
    - interval_minutes: 定时触发间隔
    - batch_size: 每批从 DB 拉取的最大商品数（分页控制）
    - max_items_per_run: 单次运行最多采集的商品数（防止长时间占用浏览器）
    - history_retention_days: 执行历史保留天数，启动时清理超过此天数的记录
      （0 表示永不清理；默认 90 天平衡排查需求与磁盘占用）
    """
    enabled: bool = True
    interval_minutes: int = 30
    batch_size: int = 50
    max_items_per_run: int = 100
    history_retention_days: int = Field(default=90, ge=0, le=3650)


# ============== 智能客服模块配置 ==============
# 设计文档：docs/chatbot-详细设计.md §3.1
# 所有配置类用 Pydantic BaseModel（与上方现有配置类一致），不用 @dataclass

class ChatbotRAGConfig(BaseModel):
    """RAG 检索配置"""
    top_k: int = Field(5, ge=1, le=20, description="检索返回的片段数量")
    similarity_threshold: float = Field(0.65, ge=0.0, le=1.0, description="相似度阈值，低于此值的片段丢弃")
    max_context_chars: int = Field(8000, ge=500, le=32000, description="context 最大字符数，超出则整片丢弃最低相似度片段")
    # 后续问题预测：每轮回答后生成 3-5 个推荐问题，引导用户持续对话
    enable_follow_ups: bool = Field(True, description="是否在回答后生成推荐后续问题")
    follow_up_count: int = Field(3, ge=1, le=5, description="生成的后续问题数量")


class ChatbotLLMConfig(BaseModel):
    """LLM 调用配置"""
    model: str = Field("gpt-4o-mini", description="OpenAI 模型名")
    temperature: float = Field(0.3, ge=0.0, le=2.0, description="采样温度，0=确定性，2=最大随机")
    max_tokens: int = Field(2000, ge=1, le=4096, description="单次回复最大 token 数")
    http_timeout_sec: int = Field(25, ge=5, le=120, description="HTTP 总超时")
    first_token_timeout_sec: int = Field(15, ge=3, le=60, description="首 token 超时")
    vision_model: str | None = Field(
        None,
        description="多模态视觉模型名（如 gpt-4o、qwen-vl-max）；None 表示用 model 处理图片（可能不支持）",
    )


class ChatbotAgentConfig(BaseModel):
    """AGENT 工具调用配置"""
    enable_tools: bool = Field(True, description="是否启用 AGENT 工具调用")
    max_tool_rounds: int = Field(3, ge=1, le=10, description="最大工具调用轮数")
    tool_trigger_mode: str = Field("function_calling", description="工具触发模式：function_calling 优先 / fallback 兜底")
    tool_call_timeout_sec: int = Field(5, ge=1, le=30, description="单轮工具本地执行超时")
    tool_llm_timeout_sec: int = Field(15, ge=5, le=60, description="单轮 LLM 决策超时")
    tool_total_timeout_sec: int = Field(30, ge=10, le=120, description="AGENT 总超时")


class ChatbotKBConfig(BaseModel):
    """知识库构建与更新配置"""
    auto_update_enabled: bool = Field(True, description="是否启用定时自动更新")
    update_interval_hours: int = Field(6, ge=1, le=168, description="自动更新间隔（小时）")
    doc_paths: list[str] = Field(
        default_factory=lambda: ["docs/", "src/xianyu_hunter/"],
        description="文档扫描路径列表",
    )
    embedding_concurrency: int = Field(5, ge=1, le=20, description="Embedding 并发数")
    embedding_model: str = Field("text-embedding-3-small", description="OpenAI Embedding 模型名")
    embedding_dimensions: int = Field(1536, ge=256, le=3072, description="向量维度")
    chunk_size: int = Field(500, ge=100, le=2000, description="分块字符数")
    chunk_overlap: int = Field(50, ge=0, le=500, description="分块重叠字符数")
    snapshot_max_keep: int = Field(10, ge=1, le=50, description="快照保留数量上限")
    persist_path: str = Field(str(get_chromadb_path()), description="ChromaDB 持久化路径")
    collection_name: str = Field("xianyu_hunter_docs", description="ChromaDB 集合名")
    project_root: str = Field(".", description="知识库扫描项目根目录")


class ChatbotFAQConfig(BaseModel):
    """FAQ 匹配配置"""
    similarity_threshold: float = Field(0.85, ge=0.0, le=1.0, description="≥ 此值直接返回")
    confirm_threshold: float = Field(0.65, ge=0.0, le=1.0, description="此值 ~ similarity_threshold 区间需确认")


class ChatbotEscalationConfig(BaseModel):
    """转人工配置"""
    feedback_threshold: int = Field(2, ge=1, le=10, description="触发转人工的点踩次数")
    feedback_window_min: int = Field(30, ge=5, le=1440, description="点踩统计时间窗口（分钟）")
    contact: str = Field("", description="转人工联系方式（空则显示'请联系管理员'）")
    sanitize_pii: bool = Field(True, description="是否脱敏 PII")


class ChatbotConfig(BaseModel):
    """智能客服总配置（对应 yaml 中 chatbot 段）

    静态配置：启动时从 yaml 加载，修改需重启
    动态配置：存 chatbot_config 表，通过 PUT /api/chatbot/config 热更新
    """
    enabled: bool = Field(True, description="智能客服总开关（支持热更新）")
    max_history_turns: int = Field(10, ge=1, le=20, description="上下文历史最大轮数")
    session_timeout_min: int = Field(30, ge=5, le=1440, description="会话超时时间（分钟）")
    rag: ChatbotRAGConfig = Field(default_factory=ChatbotRAGConfig)
    llm: ChatbotLLMConfig = Field(default_factory=ChatbotLLMConfig)
    agent: ChatbotAgentConfig = Field(default_factory=ChatbotAgentConfig)
    kb: ChatbotKBConfig = Field(default_factory=ChatbotKBConfig)
    faq: ChatbotFAQConfig = Field(default_factory=ChatbotFAQConfig)
    escalation: ChatbotEscalationConfig = Field(default_factory=ChatbotEscalationConfig)


class TaskSchedulerConfig(BaseModel):
    """任务调度默认值与前端自动搜索配置

    - default_interval_seconds: 新建任务未指定 interval_seconds 时的默认值
      （30-3600 秒，过短易触发反爬，过长错过抢单窗口）
    - auto_search_enabled: 任务管理页前端「自动搜索」开关的初始默认值
      （用户在页面内切换后会持久化到 localStorage，覆盖此默认值）
    - auto_search_concurrency: 前端自动搜索并发上限（保留字段，当前固定 1）
      未来若需要并行搜索可放宽，需配合后端浏览器锁改造
    """
    default_interval_seconds: int = Field(60, ge=30, le=3600)
    auto_search_enabled: bool = False
    auto_search_concurrency: int = Field(1, ge=1, le=5)

    @model_validator(mode="after")
    def _warn_concurrency_gt_one(self) -> "TaskSchedulerConfig":
        # 仅警告不抛错：auto_search_concurrency 是保留字段，前端 useAutoLiveSearch
        # 当前固定串行队列（processingRef 互斥），并发 > 1 不会真正生效但语义误导
        # 未来若实现并行搜索需同步改造前端队列与后端浏览器锁
        if self.auto_search_concurrency > 1:
            warnings.warn(
                f"auto_search_concurrency={self.auto_search_concurrency} 当前未生效"
                f"（前端固定串行队列），前端实际并发仍为 1。如需并行搜索请先完成浏览器锁改造",
                stacklevel=2,
            )
        return self


# ============== Cookie 自愈体系配置 ==============
# 设计文档：docs/plans/cookie-self-healing-optimization.md
# 统一管理 Cookie 三层架构、续期、跨进程同步等关键参数，替代散落在
# cookie_rotator / cookie_store / token_renewer / login_orchestrator /
# _search / browser_import / cookie_inject 等模块的硬编码常量。
# 配置化目的：确保 75+ cookie 全程保留，避免不同模块独立定义名单导致丢失。


class CookieLayerDefinitionConfig(BaseModel):
    """单个 Cookie 层定义（对应 cookie_rotator.LAYER_DEFINITIONS）

    - cookies: 该层包含的 cookie 名集合（运行时转 set 加速查询）
    - ttl: 生命周期描述（语义化字符串，不做强制校验）
           identity=session（随浏览器会话）/ session=15-22min（MTOP token）/ tracking=dynamic
    - depends_on: 依赖的上一层名（None 表示无依赖）
    """
    cookies: list[str]
    ttl: str = "session"
    depends_on: str | None = None


class CookieManagementConfig(BaseModel):
    """Cookie 管理统一配置

    聚合 cookie_store / cookie_rotator / browser_import / cookie_inject
    四个模块的硬编码常量。配置化的核心动机：用户反馈"75 个 cookie 齐全时
    各类问题大幅度减少"，但原代码中 4 处独立定义关键 cookie 集合
    （_GOOFISH_KEY_COOKIES 6 个 / LAYER_DEFINITIONS 13 个 / _TARGET_COOKIE_NAMES
    7 个 / key_cookie_names 6 个）和 3 处独立定义域名集合，存在名单漂移风险。
    """
    # 关键 Cookie 名单：用于 JSON 持久化时的关键字段过滤
    # 与 mtop_sync.key_cookie_names 保持一致即可（避免重复定义）
    key_cookies: list[str] = Field(
        default_factory=lambda: [
            "_m_h5_tk", "_m_h5_tk_enc", "unb", "sgcookie", "cookie2", "lg2",
        ]
    )
    # CookieStore 内存缓存 TTL（秒）：30s 平衡一致性与查询性能
    cache_ttl_sec: float = 30.0
    # 测试用 Cookie 值：用于过滤无效的占位符值（避免测试数据被当作有效 cookie）
    test_cookie_values: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "unb": ["123456", "123"],
            "cookie2": ["abc"],
            "_m_h5_tk": ["abc"],
            "_m_h5_tk_enc": ["enc", "enc_123", "abc123enc456"],
            "sgcookie": ["sg", "sg_token"],
        }
    )
    # Cookie 格式正则（字符串形式，运行时由 cookie_store 编译为 re.Pattern）
    # 用于校验 cookie 值是否符合预期格式，过滤残缺数据
    cookie_format_patterns: dict[str, str] = Field(
        default_factory=lambda: {
            "_m_h5_tk": r"^[0-9a-fA-F]{32}_\d{13}$",
            "unb": r"^\d{8,}$",
            "cookie2": r"^[0-9a-fA-F]{32,}$",
            "sgcookie": r"^.{20,}$",
            "_m_h5_tk_enc": r"^.{16,}$",
        }
    )
    # 三层架构定义（identity / session / tracking）
    # 层间依赖关系决定恢复顺序：identity 失效需重登录，session 失效可续期，tracking 失效可重建
    layer_definitions: dict[str, CookieLayerDefinitionConfig] = Field(
        default_factory=lambda: {
            "identity": CookieLayerDefinitionConfig(
                cookies=["unb", "cookie2", "sgcookie", "t", "_tb_token_", "lg2"],
                ttl="session",
                depends_on=None,
            ),
            "session": CookieLayerDefinitionConfig(
                cookies=["_m_h5_tk", "_m_h5_tk_enc"],
                ttl="15-22min",
                depends_on="identity",
            ),
            "tracking": CookieLayerDefinitionConfig(
                cookies=["cna", "tfstk", "xlly_s", "ali_aplus_v3", "utdid"],
                ttl="dynamic",
                depends_on=None,
            ),
        }
    )
    # Cookie 写入的目标域名：统一 cookie_rotator.DOMAINS / cookie_inject._INJECT_DOMAINS
    # 注意：必须同时包含 .goofish.com 与 goofish.com 两种形式，浏览器 Cookie 域名匹配规则
    domains: list[str] = Field(
        default_factory=lambda: [
            ".goofish.com", "goofish.com",
            ".taobao.com", "taobao.com",
            ".alipay.com", "alipay.com",
            "login.taobao.com", ".login.taobao.com",
        ]
    )
    # browser_import 是否全量导入：true=保留所有 75+ cookie（推荐），
    # false=仅导入 key_cookies 白名单（会丢失 68 个 cookie，不推荐）
    import_full: bool = True


class TokenRenewerConfig(BaseModel):
    """Token 续期器配置（对应 token_renewer.RenewerConfig）

    _m_h5_tk 是 MTOP 接口的会话 token，TTL 约 15-22 分钟，需主动续期。
    原硬编码值保留为默认值，配置化后可在不重启代码的情况下调整。
    """
    renew_before_expiry_sec: int = 600    # 提前多少秒续期（避免临到期才触发失败）
    check_interval_sec: int = 120         # 检查间隔（秒）
    token_ttl_sec: int = 1200             # Token 预估 TTL（秒，用于计算续期时机）
    max_renew_attempts: int = 3           # 最大续期尝试次数（超过触发重登录）
    retry_interval_sec: int = 30          # 续期失败后的重试间隔
    # 续期调用的 MTOP API 名：getTimestamp 接口轻量且无需业务参数，适合做 token 刷新
    timestamp_api: str = "mtop.taobao.mtop.common.getTimestamp"


class LoginOrchestratorConfig(BaseModel):
    """登录协调器配置（对应 login_orchestrator 中的硬编码阈值）"""
    # 续期失败达到此次数后触发自动重登录（避免无限重试浪费资源）
    renew_fail_threshold: int = 2
    # 自动重登录冷却（秒）：防止短时间内反复弹登录框骚扰用户
    auto_relogin_cooldown_sec: int = 600


class MtopSyncConfig(BaseModel):
    """MTOP 响应 Set-Cookie 回写同步配置（对应 _search.py）

    高频搜索时每个 MTOP 响应都含 Set-Cookie，若每次都触发
    sync_cookie_layers_from_json 会造成不必要的 CPU/IO 开销。
    节流策略：仅当 _m_h5_tk 实际值变化时才触发 sync。
    """
    # 触发 JSON 回写的关键 cookie 名单（默认与 cookie_management.key_cookies 一致）
    key_cookie_names: list[str] = Field(
        default_factory=lambda: [
            "_m_h5_tk", "_m_h5_tk_enc", "unb", "sgcookie", "cookie2", "lg2",
        ]
    )
    # 是否启用节流（推荐 true：高频搜索时大幅减少 sync 调用次数）
    throttle_enabled: bool = True
    # 节流间隔（秒）：同一 cookie 名在间隔内只触发一次 sync
    # 5 秒平衡时效性与性能：搜索通常每 5-10 秒一次，太短失去节流意义
    throttle_interval_sec: float = 5.0


class SubprocessSyncConfig(BaseModel):
    """子进程 Cookie 同步配置

    子进程（scripts/auth_helper.py / scripts/browser_login.py）通过
    Playwright 启动独立浏览器进程登录，无法访问主进程的 CookieRotator 单例。
    采用"文件信号 + 主进程轮询"方案：子进程写 JSON 后创建 pending 标记文件，
    主进程 CookieSyncScheduler 启动时 + 定时轮询检查标记，存在则调用
    sync_cookie_layers_from_json 并删除标记。
    """
    # pending 标记文件路径（子进程写入，主进程读取后删除）
    # 放在 data/ 目录与 CookieStore JSON 同级，便于清理
    pending_file_path: str = "data/.cookie_sync_pending"
    # 主进程轮询间隔（秒）：30s 与 browser.auto_sync_interval 对齐
    poll_interval_sec: int = 30
    # 启动时是否立即检查 pending 标记（推荐 true：处理上次未消费的信号）
    startup_check_enabled: bool = True


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
    batch_refresh: BatchRefreshConfig = BatchRefreshConfig()
    chatbot: ChatbotConfig = ChatbotConfig()
    task_scheduler: TaskSchedulerConfig = TaskSchedulerConfig()
    # Cookie 自愈体系（统一管理 75+ cookie 的保留与恢复）
    cookie_management: CookieManagementConfig = CookieManagementConfig()
    token_renewer: TokenRenewerConfig = TokenRenewerConfig()
    login_orchestrator: LoginOrchestratorConfig = LoginOrchestratorConfig()
    mtop_sync: MtopSyncConfig = MtopSyncConfig()
    subprocess_sync: SubprocessSyncConfig = SubprocessSyncConfig()
    # 通知渠道凭据（明文存到 yaml，前端用 Input.Password 组件隐藏）
    # keyring 是设计首选，但前端需要回显已配置值，暂存 yaml
    serverchan_send_key: str = ""
    pushplus_token: str = ""
    bark_server: str = ""
    bark_key: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    wecom_webhook: str = ""
    dingtalk_webhook: str = ""
    dingtalk_secret: str = ""
    webhook_url: str = ""


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
    base = get_config_dir()
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
