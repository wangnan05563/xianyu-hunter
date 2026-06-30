import client from './client'
import type { SoldPriceRange } from './types'

// 价格 API：提供价格分布直方图、类目统计与 AI 分析
export const priceApi = {
  histogram: (params: { task_id?: string; range_hours?: number; bins?: number }) =>
    client.get('/api/prices/histogram', { params }).then((r) => r.data),

  categoryStats: (params: { task_id?: string; range_hours?: number }) =>
    client.get('/api/prices/category-stats', { params }).then((r) => r.data),

  // AI 分析耗时较长，超时设为 60s
  analyze: (params: { task_id?: string }) =>
    client.post<{ analysis: string; source: string; scope_label?: string }>('/api/prices/analyze', null, { params, timeout: 60000 }).then((r) => r.data),

  // 同类物品已售价格区间（捡漏价格参考）
  // 返回指定品类下近期已售商品的最低价/最高价/中位数/样本数
  // 最低价作为"捡漏价格"参考指标
  soldRange: (params: { task_id?: string; range_days?: number }) =>
    client.get<SoldPriceRange>('/api/prices/sold-range', { params }).then((r) => r.data),
}
