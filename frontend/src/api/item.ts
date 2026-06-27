import client from './client'
import type { ItemSummary } from './types'

// 商品 API：提供商品摘要的单条与批量查询
export const itemApi = {
  summary: (itemId: string) =>
    client.get<ItemSummary>(`/api/items/${itemId}/summary`).then((r) => r.data),

  batch: (ids: string[]) =>
    client.get<Record<string, ItemSummary>>('/api/items/batch', { params: { ids: ids.join(',') } }).then((r) => r.data),

  // 刷新单个商品详情：采集详情页并更新销售状态
  // 触发场景：链接点击异步刷新、官方采集、抢单失败回退
  refresh: (itemId: string) =>
    client.post<{ ok: boolean; item_id: string; is_sold: boolean }>(
      `/api/items/${itemId}/refresh`,
    ).then((r) => r.data),
}
