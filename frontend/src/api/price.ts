import client from './client'

// 价格 API：提供价格分布直方图、类目统计与 AI 分析
export const priceApi = {
  histogram: (params: { task_id?: string; range_hours?: number; bins?: number }) =>
    client.get('/api/prices/histogram', { params }).then((r) => r.data),

  categoryStats: (params: { task_id?: string; range_hours?: number }) =>
    client.get('/api/prices/category-stats', { params }).then((r) => r.data),

  // AI 分析耗时较长，超时设为 60s
  analyze: (params: { task_id?: string }) =>
    client.post<{ analysis: string; source: string; scope_label?: string }>('/api/prices/analyze', null, { params, timeout: 60000 }).then((r) => r.data),
}
