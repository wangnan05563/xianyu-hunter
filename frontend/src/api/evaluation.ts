import client from './client'
import type { EvalItem } from './types'

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
  }) => client.get<{ items: EvalItem[]; count: number; total: number }>('/api/evaluations', { params }).then((r) => r.data),

  distribution: (params: { range_hours?: number; price_bin_count?: number; score_bin_count?: number }) =>
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
}
