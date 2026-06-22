import client from './client'

// ============== 类型定义 ==============

/** 策略评估结果 */
export interface StrategyEvaluation {
  ok: boolean
  recommended: string
  reason: string
  available_strategies: string[]
  details: Record<string, unknown>
}

/** 初始化响应 */
export interface InitializeResult {
  ok: boolean
  mode: 'launch' | 'cdp'
  fingerprint_profile: string | null
  user_agent: string | null
  stealth_scripts_count: number
  message?: string
  error?: string
}

/** 会话状态 */
export interface SessionStatus {
  ok: boolean
  active: boolean
  strategy: string
  fingerprint_profile: string
  token_age_sec: number | null
  token_expired: boolean | null
  health_score: number | null
  health_action: string
  waf_status: string
  cookie_layers: Record<string, boolean>
  freq_stats: Record<string, number>
  captcha_stats: Record<string, number>
  started_at: number
  uptime_sec: number
}

/** 指纹 profile 信息 */
export interface FingerprintInfo {
  ok: boolean
  mode: 'launch' | 'cdp'
  profile: {
    name: string
    ua: string
    platform: string
    vendor: string
    hardware_concurrency: number
    device_memory: number
    gpu_vendor: string
    gpu_renderer: string
    screen_width: number
    screen_height: number
    color_depth: number
    pixel_ratio: number
    languages: string[]
  } | null
  stealth_scripts_count: number
  message?: string
}

/** 频率伪装统计 */
export interface FreqStats {
  ok: boolean
  total_requests: number
  noise_requests: number
  noise_ratio: number
  mean_interval?: number
  median_interval?: number
  std_interval?: number
}

/** 请求延迟 */
export interface RequestDelay {
  ok: boolean
  action: string
  delay_sec: number
  error?: string
  valid_actions?: string[]
}

/** Cookie 层状态 */
export interface CookieLayerState {
  valid: boolean
  updated_at: number
  cookie_count: number
}

export interface CookieLayersResult {
  ok: boolean
  layers: Record<string, CookieLayerState>
}

/** 健康检查报告 */
export interface HealthReport {
  ok: boolean
  score: number
  cookie_valid: boolean
  api_reachable: boolean
  page_accessible: boolean
  waf_status: string
  action: string
  details: Record<string, unknown>
  is_healthy: boolean
  needs_attention: boolean
  error?: string
  hint?: string
}

/** 通用操作结果 */
export interface OperationResult {
  ok: boolean
  message?: string
  error?: string
  written?: number
  cascaded?: boolean
  strategy?: string
  valid_strategies?: string[]
  valid_layers?: string[]
}

// ============== API 封装 ==============

/** 反爬登录管理 API */
export const anticrawlApi = {
  // 策略评估
  getStrategy: () =>
    client.get<StrategyEvaluation>('/api/anticrawl/strategy').then((r) => r.data),

  setStrategy: (strategy: string) =>
    client.post<OperationResult>('/api/anticrawl/strategy/set', { strategy }).then((r) => r.data),

  // 协调器初始化
  initialize: (use_cdp: boolean = false) =>
    client.post<InitializeResult>('/api/anticrawl/initialize', { use_cdp }).then((r) => r.data),

  // 会话管理
  getSessionStatus: () =>
    client.get<SessionStatus>('/api/anticrawl/session/status').then((r) => r.data),

  startSession: () =>
    client.post<SessionStatus>('/api/anticrawl/session/start', {}).then((r) => r.data),

  stopSession: () =>
    client.post<OperationResult>('/api/anticrawl/session/stop', {}).then((r) => r.data),

  // 健康检查
  checkHealth: () =>
    client.get<HealthReport>('/api/anticrawl/health').then((r) => r.data),

  // 指纹信息
  getFingerprint: () =>
    client.get<FingerprintInfo>('/api/anticrawl/fingerprint').then((r) => r.data),

  // 频率伪装
  getFreqStats: () =>
    client.get<FreqStats>('/api/anticrawl/freq/stats').then((r) => r.data),

  getRequestDelay: (action: string) =>
    client
      .get<RequestDelay>('/api/anticrawl/freq/delay', { params: { action } })
      .then((r) => r.data),

  // Cookie 分层管理
  updateCookies: (cookies: Record<string, string>) =>
    client.post<OperationResult>('/api/anticrawl/cookies/update', { cookies }).then((r) => r.data),

  getCookieLayers: () =>
    client.get<CookieLayersResult>('/api/anticrawl/cookies/layers').then((r) => r.data),

  invalidateLayer: (layer: string) =>
    client.post<OperationResult>('/api/anticrawl/cookies/invalidate', { layer }).then((r) => r.data),
}
