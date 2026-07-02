// 共享类型定义：按业务域分组，供各 API 子模块与外部消费方复用
// 集中存放避免循环依赖，子模块仅按需导入所需类型

// ============== 配置 ==============

export interface AppConfig {
  server: { host: string; port: number }
  browser: {
    headless: boolean
    user_data_dir: string
    viewport_width: number
    viewport_height: number
    user_agent: string
  }
  antidetect: {
    qps: number
    min_delay_ms: number
    max_delay_ms: number
    fail_pause_threshold: number
    fail_window_sec: number
  }
  waf: { enabled: boolean; login_check_interval_min: number }
  notifier: {
    default_channels: string[]
    channels: {
      serverchan: boolean
      pushplus: boolean
      bark: boolean
      telegram: boolean
      wecom: boolean
      dingtalk: boolean
      webhook: boolean
    }
    quiet_hours: {
      enabled: boolean
      start: string
      end: string
      critical_only: boolean
      weekend_only: boolean
    }
    subscribed_events: string[]
  }
  eval: {
    weights: { professional: number; credit: number; dispute: number; price: number }
    thresholds: {
      on_sale_count: number
      post_count_30d: number
      top_category_ratio: number
      credit_score_min: number
      bad_review_max: number
      register_days_min: number
    }
    professional_keywords: string[]
    pass_score: number
    auto_buy_score: number
    // AI 评估配置
    ai_auto_eval: boolean
    ai_auto_deep_analyze: boolean
    // 自动官方采集配置
    auto_collect_official: boolean
    auto_collect_max_per_run: number
    /** 自动官方采集去重窗口（分钟） */
    auto_collect_dedup_window_minutes?: number
    /** 自动官方采集失败退避阈值 */
    auto_collect_fail_pause_threshold?: number
    // P3: AI 多轮优化建议配置
    ai_multi_run_suggestion: boolean
    ai_suggestion_interval: number
  }
  // 搜索参数配置（对应后端 SearchConfig 模型）
  search: {
    page_size: number
    sort_type: string
    timeout: number
    regions: string
    filter_tags: string[]
  }
  // 价格策略配置（对应后端 PriceStrategyConfig 模型）
  price_strategy: {
    enabled_max: boolean
    max_price: number
    enabled_min: boolean
    min_price: number
    enabled_market_ratio: boolean
    market_ratio: number
    enabled_top_n: boolean
    top_n: number
  }
  // 批量采集调度器配置（对应后端 BatchRefreshConfig 模型）
  batch_refresh: {
    enabled: boolean
    interval_minutes: number
    batch_size: number
    max_items_per_run: number
  }
  // 任务调度默认值（对应后端 TaskSchedulerConfig 模型）
  task_scheduler: {
    default_interval_seconds: number
    auto_search_enabled: boolean
    auto_search_concurrency: number
  }
  // 通知渠道凭据（明文存到 yaml，前端用 Input.Password 组件回显）
  serverchan_send_key: string
  pushplus_token: string
  bark_server: string
  bark_key: string
  telegram_bot_token: string
  telegram_chat_id: string
  wecom_webhook: string
  dingtalk_webhook: string
  dingtalk_secret: string
  webhook_url: string
}

export interface BackupItem {
  filename: string
  ts_raw: string
  mtime: number
  size: number
  ts: string
}

// ============== 任务 ==============

// 任务级搜索参数覆盖：null 表示沿用全局 AppConfig.search
// 与后端 SearchConfig 字段对齐，所有字段可选（仅覆盖用户指定项）
export interface TaskSearchOverride {
  page_size?: number
  sort_type?: string
  timeout?: number
  regions?: string
  filter_tags?: string[]
}

// 任务级价格策略覆盖：null 表示沿用全局 AppConfig.price_strategy
// 与后端 PriceStrategyConfig 字段对齐
export interface TaskPriceOverride {
  enabled_max?: boolean
  max_price?: number
  enabled_min?: boolean
  min_price?: number
  enabled_market_ratio?: boolean
  market_ratio?: number
  enabled_top_n?: boolean
  top_n?: number
}

// 任务级反检测参数覆盖：null 表示沿用全局 AppConfig.antidetect
// 与后端 AntiDetectConfig 字段对齐
export interface TaskAntidetectOverride {
  qps?: number
  min_delay_ms?: number
  max_delay_ms?: number
  fail_pause_threshold?: number
  fail_window_sec?: number
}

// 任务级 eval 配置覆盖：null 表示沿用全局 AppConfig.eval
// 与后端 EvalConfig 字段对齐，仅暴露需要任务级覆盖的字段
export interface TaskEvalOverride {
  auto_collect_official?: boolean
  auto_collect_max_per_run?: number
}

export interface Task {
  id: string
  name: string
  keyword: string
  min_price: number | null
  max_price: number | null
  max_publish_days: number | null
  mode: string
  region: string | null
  exclude_words: string
  search_filters: string
  cron: string
  // 调度模式：DB 存 int(0/1)，前端读取后用 Boolean() 转 bool
  use_cron: number
  // 固定间隔调度模式下的循环间隔（秒），仅 use_cron=false 时生效
  interval_seconds: number
  // AI 评估任务级配置：null/undefined 表示沿用全局 eval.pass_score
  // 注意：DB 默认值 60（NOT NULL），此处类型仍允许 null 以支持"未设置"语义
  eval_threshold: number | null
  ai_prompt: string | null
  // 任务级配置覆盖（JSON 字段，后端 get_task 已解析为对象；null 表示沿用全局）
  search_config: TaskSearchOverride | null
  price_config: TaskPriceOverride | null
  antidetect_config: TaskAntidetectOverride | null
  eval_config: TaskEvalOverride | null
  status: string
  created_at: string
  updated_at: string
}

export interface TaskCreateBody {
  keyword: string
  name?: string
  min_price?: number | null
  max_price?: number | null
  max_publish_days?: number | null
  mode?: string
  region?: string | null
  exclude_words?: string[]
  search_filters?: string[]
  // 调度配置：与后端 TaskCreate 对齐
  cron?: string
  use_cron?: boolean
  interval_seconds?: number
  // AI 评估任务级配置：undefined=不更新（编辑模式），null=清除覆盖沿用全局
  eval_threshold?: number | null
  ai_prompt?: string | null
  // 任务级配置覆盖：undefined=不更新，null/{}=清除覆盖，对象=应用覆盖
  search_config?: TaskSearchOverride | null
  price_config?: TaskPriceOverride | null
  antidetect_config?: TaskAntidetectOverride | null
  eval_config?: TaskEvalOverride | null
}

export interface TaskRun {
  start: string
  end: string | null
  duration_s: number
  event_count: number
  hit_count: number
  err_count: number
  warn_count: number
}

export interface TaskDep {
  task_id: string
  depends_on: string
  depends_on_name?: string
  task_name?: string
}

export interface TaskLink {
  link_id: number
  link_key: string
  link_type: string
  source: string
  // DB 顶层字段：task_links 行的最近更新时间，DB 模式下由后端返回，live 模式无此字段
  updated_at?: string
  display: {
    title: string
    price: number
    thumb_url?: string
    image_urls?: string[]  // 详情页采集的图片列表（主图+细节图）
    brand?: string
    region?: string
    seller_id?: string
    seller_nick?: string
    seller_credit?: string  // 卖家信用度（极好/良好/优秀），用于发布时间兜底显示
    want_cnt?: number
    view_cnt?: number
    publish_time?: string
    is_sold?: boolean
    url?: string
  }
}

// 字段元数据：描述每个字段的显示方式（标签、类型、宽度）
// 前端根据此元数据动态渲染列，当接口字段变化时前端展示自动调整
export interface FieldMeta {
  label: string  // 列标题
  type: 'image' | 'link' | 'price' | 'seller' | 'tag' | 'text' | 'number' | 'datetime' | 'status'
  width?: number  // 列宽度（px），undefined 表示自适应
  color?: string  // Tag 颜色（type='tag' 时使用）
}

// 字段映射表：字段名 → 字段元数据
export type FieldMap = Record<string, FieldMeta>

// ============== 商品 ==============

export interface ItemSummary {
  item_id: string
  title: string
  price: number
  seller_id?: string
  seller_nick?: string
}

// ============== 评估 ==============

export interface EvalItem {
  item_id: string
  task_id: string
  created_at: string
  // 后端 _enrich_condition_tags 添加的成色评估字段（顶级，非 payload 内）
  condition_label?: string
  condition_score?: number
  condition_tags?: Array<{ category: string; label: string }>
  is_branded_new?: boolean
  has_repair?: boolean
  payload: {
    score: number
    risk_level: string
    item_title?: string
    item_price?: number
    seller_id?: string
    seller_nick?: string
    // 后端 _enrich_eval_with_item 从 items/task_links.display 补充的品牌字段
    brand?: string
    [k: string]: unknown
  }
}

// ============== AI ==============

// 同类物品已售价格区间（捡漏价格参考）
// 后端 GET /api/prices/sold-range 返回结构
export interface SoldPriceRange {
  min_price: number | null
  max_price: number | null
  median_price: number | null
  // 捡漏价格 = 已售商品最低价，低于此价视为捡漏机会
  bargain_price: number | null
  sample_size: number
  // 数据来源：sold=已售成交价 / all_fallback=全部商品参考价 / empty=无数据
  source: 'sold' | 'all_fallback' | 'all_fallback_insufficient' | 'empty'
  source_label?: string
  task_id?: string | null
  range_days?: number
  message?: string  // 无数据时的友好提示
}

export interface AIConditionResult {
  verdict: 'recommend' | 'caution'
  condition_score: number
  reason: string
  risk_signals: string[]
  detail?: string
  source: 'llm' | 'rule'
  cached?: boolean
  // 同类物品价格区间（捡漏价格参考），仅当后端查询到数据时存在
  price_range?: SoldPriceRange
}

export interface AIConfig {
  ai_enabled: boolean
  base_url: string
  api_key: string
  model: string
  vision_model: string
  // Embedding 配置（独立于 LLM，DeepSeek 等厂商不支持 /embeddings 时需单独配置）
  // 留空时后端 fallback 到 LLM 配置（向后兼容）
  embedding_base_url?: string
  embedding_api_key?: string
  embedding_model?: string
  // 0 表示由模型决定（Ollama 等本地模型不接受 dimensions 参数）
  embedding_dimensions?: number
  embedding_has_key?: boolean
}

export interface AIUsage {
  today: {
    total_calls: number
    total_tokens: number
    total_cost_usd: number
    total_cost_cny: number
    by_endpoint: Record<string, number>
    by_model: Record<string, number>
  }
  budget: {
    daily_token_limit: number
    daily_cost_limit_usd: number
    rate_limit_per_min: number
    token_usage_pct: number
    cost_usage_pct: number
  }
  history: Array<{
    date: string
    total_calls: number
    total_input_tokens: number
    total_output_tokens: number
    total_cost_cny: number
  }>
}

export interface AITestConnectionResult {
  ok: boolean
  model?: string
  detail?: string
}

// Embedding 连接测试结果：额外返回 dimensions 便于前端展示模型实际维度
export interface AITestEmbeddingResult {
  ok: boolean
  model?: string
  dimensions?: number
  detail?: string
}

export interface AIBudgetBody {
  daily_token_limit: number
  daily_cost_limit_usd: number
  rate_limit_per_min: number
}

export interface AIParseTaskResult {
  keyword: string
  name: string
  min_price: number | null
  max_price: number | null
  mode: string
  exclude_words?: string[]
  notes?: string
  reason?: string
  source?: 'llm' | 'rule'
  [k: string]: unknown
}

// ============== AI 深度分析（O-13-26 接入 api_ai_deep）==============

// 单个维度的检查结果（stolen_image / damage / consistency / template）
export interface DeepCheckResult {
  score: number              // 1-10，10=最好
  risk_level: 'low' | 'medium' | 'high'
  signals?: string[]         // 检测到的风险信号
  damages?: string[]         // damage 维度：损坏类型
  inconsistencies?: string[] // consistency 维度：不一致项
  detail: string
}

// POST /api/ai/deep-analyze 响应
export interface DeepAnalyzeResult {
  item_id: string
  checks_performed: string[]
  source: 'llm' | 'rule'
  // 4 个维度的检查结果（按 checks_performed 过滤）
  stolen_image?: DeepCheckResult
  damage?: DeepCheckResult
  consistency?: DeepCheckResult
  template?: DeepCheckResult
  // 全局字段
  overall_verdict: 'recommend' | 'caution' | 'reject'
  overall_score: number      // 1-10
  summary: string            // 一句话总结
  image_hashes?: Array<{ url: string; hash: string }>
}

// POST /api/ai/seller-template-check 响应
export interface SellerTemplateCheckResult {
  seller_id: string
  sample_count: number
  template_score: number     // 1-10，10=个性化文案
  is_dealer: boolean
  risk_level: 'low' | 'medium' | 'high'
  signals: string[]
  keyword_freq?: Record<string, number>
  shared_sentences_count?: number
  desc_length_variance?: number
  detail: string
}

// ============== 订单 ==============

// 字段与后端 OrderRow 模型 + api_orders.list_orders 返回对齐
// id 为字符串组合键（item_id:timestamp:rand），不是自增数字
export interface OrderItem {
  id: string
  task_id?: string | null
  item_id: string
  seller_id?: string | null
  order_no?: string | null
  price: number
  status: string
  screenshot?: string | null
  error?: string | null
  created_at: string
  confirmed_at: string | null
  paid_at?: string | null
  // 仅 takeover_pending 订单由 list_orders 端点附加（后端按需注入，非数据库列）
  takeover_deadline?: string | null
  takeover_remaining_sec?: number | null
}

// ============== 统计 ==============

export interface StatsOverview {
  tasks: { running: number; total: number; paused: number; stopped: number }
  orders: { pending: number; succeeded: number; failed: number; total: number }
  events: { total: number }
  evaluation_count: number
  db_size: string
  browser_dir: string
  scheduler_running: boolean
  ts: string
}

export interface KpiCard {
  id: string
  title: string
  value: number
  delta_pct: number | null
  sample_size: number
  hint: string
  is_pct: boolean
  unit: string
  range_days: number
  generated_at: string
}

export interface RecentEvent {
  type: string
  created_at: string
  message: string
  payload?: Record<string, unknown>
  score?: number
}

export interface TrendSeries {
  metric: string
  range_hours: number
  series: Array<{ ts: string; value: number; count: number }>
  summary: { min: number; max: number; avg: number; current: number }
}

export interface TodayAlert {
  today: { orders: number; events: number; succeeded: number; failed: number }
  alerts: {
    failed_orders: Array<{ id: number; title: string; amount: number; created_at: string }>
    timeout_pending: Array<{ id: number; title: string; amount: number; created_at: string; age_sec: number }>
    low_evaluations: Array<{ id: number; message: string; type: string; created_at: string; score: number }>
    counts: { failed: number; timeout: number; low_eval: number }
  }
  ts: string
}

// O-08-26 评估漏斗
export interface EvalFunnelStage {
  key: string
  label: string
  count: number
  // 相对第一阶段（采集商品数）的占比，用于展示整体转化
  pct_of_first: number
  // 相对上一阶段的占比，用于展示阶段间流失
  pct_of_prev: number
}

export interface EvalFunnelMetrics {
  // 命中率：评估通过率 = eval_pass / evaluated
  hit_rate: number
  // 误报率：抢单失败数 / 抢单触发数
  false_positive_rate: number
  // 转化率：抢单成功率 = order_succeeded / order_triggered
  conversion_rate: number
  // 端到端成功率 = order_succeeded / discovered
  overall_rate: number
}

export interface EvalFunnelData {
  range_days: number
  generated_at: string
  stages: EvalFunnelStage[]
  metrics: EvalFunnelMetrics
}

export interface HistogramData {
  bins: Array<{ min: number; max: number | null; count: number }>
  summary: {
    count: number; min: number; max: number; mean: number; median: number
    p25: number; p75: number
    // O-09-26 扩展：新增 last30d 字段用于 30 日均价基线
    compare: { yesterday: number; last7d: number; last30d: number; diff_pct: number }
    // P-09-30 新增：任务定价范围，用于在直方图上显示定价上下限标线
    // mode=all 时两个字段均为 null；mode=task 且任务未设置定价范围时也为 null
    task_price_range: { min_price: number | null; max_price: number | null }
  }
  scope: { mode: string; task_id: string | null; label: string }
  mode: string
}

// O-09-26 价格趋势对比基线
export interface PriceTrendData {
  task_id: string | null
  generated_at: string
  today_avg: number
  d7_avg: number
  d30_avg: number
  // 今日相对 7 日均价的涨跌幅（短期趋势）
  delta_pct_7d: number
  // 今日相对 30 日均价的涨跌幅（中长期趋势）
  delta_pct_30d: number
  sample_size: { today: number; d7: number; d30: number }
}

// ============== 时间线 / 日志 ==============

export interface TimelineEntry {
  _kind: 'order' | 'event'
  _ts: string
  title?: string
  item_title?: string
  amount?: number
  score?: number
  status?: string
  task_id?: string
  type?: string
  level?: string
  id?: string | number
  payload?: { message?: string; [k: string]: unknown }
  [k: string]: unknown
}

export interface LogEntry {
  id?: string
  created_at: string
  level: string
  stage?: string
  task_id?: string
  message: string
  payload?: Record<string, unknown>
}

export interface ErrorLog {
  id: number
  timestamp: string
  error_type: string
  error_message: string
  stack_trace?: string
  request_method?: string
  request_path?: string
  request_params?: Record<string, unknown>
  request_headers?: Record<string, string>
  client_ip?: string
  user_agent?: string
  server_env?: Record<string, string>
  ai_context_json?: string
  ai_context_md?: string
  status: 'new' | 'resolved' | 'ignored'
  created_at: string
}

// ============== 系统维护 ==============

export interface StorageStatus {
  db: {
    db_size_mb: number
    tasks: number
    items: number
    events: number
  }
  logs: {
    total_size_mb: number
    file_count: number
    oldest?: string
  }
  cache: {
    browser_data_mb: number
    pycache_mb: number
    pycache_count: number
  }
}

export interface CleanupResult {
  cleaned?: string[]
  errors?: string[]
  count?: number
  total_deleted?: number
  total_freed_mb?: number
}

export interface CleanupBody {
  target: string
  days?: number
  dry_run: boolean
}

// ============== 数据库维护（系统维护 → 数据库维护）==============

// 表结构中的单列描述
export interface DbColumn {
  name: string
  type: string
  nullable: boolean
  default: string | null
  primary_key: boolean
  label: string  // 中文语义标注（业务含义+数据类型+使用场景+约束条件）
}

export interface DbSchema {
  table: string
  columns: DbColumn[]
}

export interface DbTableInfo {
  name: string
  rows: number
}

export interface DbTablesResponse {
  tables: DbTableInfo[]
}

export interface DbRowListResponse {
  table: string
  total: number
  limit: number
  offset: number
  rows: Record<string, unknown>[]
}

export interface DbAuditLogItem {
  id: number
  type: string
  level: string
  message: string
  payload: string | null
  created_at: string
}

export interface DbAuditLogResponse {
  items: DbAuditLogItem[]
}

// 级联影响预览
export interface CascadeRelation {
  table: string
  fk: string
  action: 'cascade' | 'set_null'
  count: number
  description: string
}

export interface CascadePreviewResponse {
  table: string
  relations: CascadeRelation[]
  total_affected: number
}

// ============== 认证 ==============

export interface AuthMe {
  logged_in: boolean
  user_id?: string
  nick?: string
  avatar_url?: string
  fetched_at?: number
  detecting?: boolean
}
