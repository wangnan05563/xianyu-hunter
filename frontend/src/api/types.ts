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
    channels: { serverchan: boolean; pushplus: boolean; bark: boolean }
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
  }
  // 敏感字段（脱敏后为 ***）
  serverchan_send_key?: string
  pushplus_token?: string
  bark_server?: string
  bark_key?: string
}

export interface BackupItem {
  filename: string
  ts_raw: string
  mtime: number
  size: number
  ts: string
}

// ============== 任务 ==============

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
  display: {
    title: string
    price: number
    thumb_url?: string
    region?: string
    seller_id?: string
    seller_nick?: string
    want_cnt?: number
    view_cnt?: number
    publish_time?: string
    is_sold?: boolean
    url?: string
  }
}

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
  payload: {
    score: number
    risk_level: string
    item_title?: string
    item_price?: number
    seller_id?: string
    seller_nick?: string
    [k: string]: unknown
  }
}

// ============== AI ==============

export interface AIConditionResult {
  verdict: 'recommend' | 'caution'
  condition_score: number
  reason: string
  risk_signals: string[]
  detail?: string
  source: 'llm' | 'rule'
  cached?: boolean
}

export interface AIConfig {
  ai_enabled: boolean
  base_url: string
  api_key: string
  model: string
  vision_model: string
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
  [k: string]: unknown
}

// ============== 订单 ==============

export interface OrderItem {
  id: number
  item_id: string
  amount: number
  status: string
  created_at: string
  confirmed_at: string | null
  takeover_deadline?: string | null
  remaining_sec?: number | null
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

export interface HistogramData {
  bins: Array<{ min: number; max: number | null; count: number }>
  summary: {
    count: number; min: number; max: number; mean: number; median: number
    p25: number; p75: number
    compare: { yesterday: number; last7d: number; diff_pct: number }
  }
  scope: { mode: string; task_id: string | null; label: string }
  mode: string
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

// ============== 认证 ==============

export interface AuthMe {
  logged_in: boolean
  user_id?: string
  nick?: string
  avatar_url?: string
  fetched_at?: number
  detecting?: boolean
}
