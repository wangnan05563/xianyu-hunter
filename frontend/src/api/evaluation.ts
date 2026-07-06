import client from './client'
import type { EvalItem } from './types'

// 官方采集返回的采集数据维度
export interface OfficialCollectResult {
  ok: boolean
  item_id: string
  collected: boolean
  item: {
    title: string
    price: number
    description: string
    image_urls: string[]
    thumb_url: string
    region: string
    seller_id: string
    want_cnt: number
    view_cnt: number
  }
  seller: {
    id: string
    nick: string
    credit_score: number | null
    register_days: number
    on_sale_count: number
    sold_count: number
  }
  reviews: string[]
  evaluation: {
    score: number | null
    risk_level: string
    dimension_scores: Record<string, number>
    reject_reasons: string[]
    is_passed: boolean
    data_quality: string
    data_source: string
  }
}

export interface BatchCollectResult {
  ok: boolean
  total: number
  succeeded: number
  failed: number
  results: Array<OfficialCollectResult | { ok: false; item_id: string; error: string }>
  message: string
}

// 评估 API：查询商品评估记录、分布与阈值建议
export const evalApi = {
  list: (params?: {
    limit?: number
    item_id?: string
    task_id?: string
    min_score?: number
    max_score?: number
    start_time?: string
    end_time?: string
    page_num?: number
    page_size?: number
    brand?: string
    sold_filter?: 'all' | 'onsale' | 'sold'
    // 结果分类过滤：点击统计卡片时使用，按配置阈值精确分类
    // auto=可抢 / pass=通过 / fail=驳回 / insufficient=数据不足
    result_category?: 'auto' | 'pass' | 'fail' | 'insufficient'
    // 价格范围过滤：未传但传了 task_id 时后端自动从任务配置读取
    min_price?: number
    max_price?: number
    // 显示超出任务价格范围的历史商品（审计用，默认 false）
    include_out_of_range?: boolean
  }) => client.get<{ items: EvalItem[]; count: number; total: number }>('/api/evaluations', { params }).then((r) => r.data),

  distribution: (params: {
    range_hours?: number
    price_bin_count?: number
    score_bin_count?: number
    task_id?: string
    min_price?: number
    max_price?: number
    include_out_of_range?: boolean
  }) =>
    client.get('/api/evaluations/distribution', { params }).then((r) => r.data),

  thresholdSuggestion: (targetPassRate: number) =>
    client
      .get<{ suggested_threshold: number; current_pass_rate: number; target_pass_rate: number; distribution: Record<string, number>; analysis: string }>(
        '/api/evaluations/threshold-suggestion',
        { params: { target_pass_rate: targetPassRate } },
      )
      .then((r) => r.data),

  sellerTrend: (itemId: string) =>
    client.get(`/api/evaluations/${itemId}/seller-trend`).then((r) => r.data),

  // 用当前配置的评估规则重新计算历史评估数据
  recompute: (taskId?: string) =>
    client
      .post<{ ok: boolean; recomputed: number; skipped: number; errors: number; total: number; message: string }>(
        '/api/evaluations/recompute',
        null,
        { params: taskId ? { task_id: taskId } : {} },
      )
      .then((r) => r.data),

  // 批量评估 items 表中未被评估的商品
  batchEvaluateUnevaluated: (taskId?: string, limit?: number) =>
    client
      .post<{ ok: boolean; evaluated: number; skipped: number; errors: number; total: number; message: string }>(
        '/api/evaluations/batch-evaluate-unevaluated',
        null,
        { params: { ...(taskId ? { task_id: taskId } : {}), ...(limit ? { limit } : {}) } },
      )
      .then((r) => r.data),

  // P3: 提交评估准确率反馈
  submitFeedback: (itemId: string, feedback: 'accurate' | 'inaccurate' | 'partial', note?: string, taskId?: string) =>
    client
      .post<{ ok: boolean; item_id: string; feedback: string }>(
        `/api/evaluations/${itemId}/feedback`,
        null,
        { params: { feedback, note: note || undefined, task_id: taskId } },
      )
      .then((r) => r.data),

  // P3: 获取评估反馈统计
  feedbackStats: () =>
    client
      .get<{ stats: Record<string, number>; total_feedback: number; accuracy_rate: number }>(
        '/api/evaluations/feedback/stats',
      )
      .then((r) => r.data),

  // 自动官方采集统计（最近 N 小时的成功/失败聚合）
  // 用于 EvalRules 页面展示采集健康度，60s 自动刷新
  autoCollectStats: (rangeHours: number = 24) =>
    client
      .get<{
        range_hours: number
        total: number
        success: number
        failed: number
        success_rate: number
        is_paused: boolean
        fail_pause_threshold: number
        top_failures: Array<{ reason: string; count: number }>
      }>('/api/evaluations/auto-collect-stats', { params: { range_hours: rangeHours } })
      .then((r) => r.data),

  // 官方页面采集+评估：访问闲鱼商品详情页和卖家主页，获取完整数据后重新评估
  // 超时设为 90s：后端最坏路径含两次 page.goto(30s) + 多个 wait_for_selector，
  // 默认 30s 会被前端 axios 提前超时，触发兜底文案「官方采集失败，请稍后重试」
  collectOfficial: (itemId: string, taskId?: string) =>
    client
      .post<OfficialCollectResult>(
        `/api/evaluations/${itemId}/collect-official`,
        null,
        { params: taskId ? { task_id: taskId } : {}, timeout: 90000 },
      )
      .then((r) => r.data),

  // 批量官方采集+评估：串行采集多个商品，单个失败不中断
  // 单条最坏 90s × 50 条 = 4500s，取整 5400s（90min）作为上限
  batchCollectOfficial: (itemIds: string[]) =>
    client
      .post<BatchCollectResult>('/api/evaluations/batch-collect-official', { item_ids: itemIds }, { timeout: 5400000 })
      .then((r) => r.data),
}
