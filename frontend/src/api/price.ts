import client from './client'
import type { SoldPriceRange } from './types'

// 单品类价格统计：count/min/max/mean/median/p10/p25/p75/p90
export interface CategoryStat {
  task_id: string | null
  name: string
  keyword: string
  count: number
  min: number
  max: number
  mean: number
  median: number
  p10: number
  p25: number
  p75: number
  p90: number
}

// 多品类横向对比项：在 CategoryStat 基础上增加相对全体的偏离度
export interface CategoryComparisonItem extends CategoryStat {
  // 相对全体均价的偏离度百分比；正=高于均价，负=低于均价
  deviation_pct: number
}

// 排序字段白名单：与后端 _ALLOWED_COMPARISON_SORT 保持一致
export type CategoryComparisonSortBy =
  | 'mean' | 'median' | 'min' | 'max'
  | 'p10' | 'p25' | 'p75' | 'p90' | 'count'

// 价格 API：提供价格分布直方图、类目统计与 AI 分析
export const priceApi = {
  histogram: (params: { task_id?: string; range_hours?: number; bins?: number }) =>
    client.get('/api/prices/histogram', { params }).then((r) => r.data),

  categoryStats: (params: { task_id?: string; range_hours?: number }) =>
    client.get<{ categories: CategoryStat[]; total_count: number }>(
      '/api/prices/category-stats',
      { params },
    ).then((r) => r.data),

  // 多品类横向对比：返回前 N 个品类的统计 + 偏离度
  // range_days>0 时仅统计最近 N 天的商品，便于观察短期行情变化
  categoryComparison: (params: {
    sort_by?: CategoryComparisonSortBy
    order?: 'asc' | 'desc'
    limit?: number
    range_days?: number
  }) =>
    client.get<{
      categories: CategoryComparisonItem[]
      overall_mean: number
      sort_by: CategoryComparisonSortBy
      order: 'asc' | 'desc'
      range_days: number
      total_categories: number
    }>('/api/prices/category-comparison', { params }).then((r) => r.data),

  // AI 分析耗时较长，超时设为 60s
  analyze: (params: { task_id?: string }) =>
    client.post<{ analysis: string; source: string; scope_label?: string }>('/api/prices/analyze', null, { params, timeout: 60000 }).then((r) => r.data),

  // 同类物品已售价格区间（捡漏价格参考）
  // 返回指定品类下近期已售商品的最低价/最高价/中位数/样本数
  // 最低价作为"捡漏价格"参考指标
  soldRange: (params: { task_id?: string; range_days?: number }) =>
    client.get<SoldPriceRange>('/api/prices/sold-range', { params }).then((r) => r.data),
}
