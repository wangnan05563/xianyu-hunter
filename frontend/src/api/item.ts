import client from './client'
import type { ItemSummary } from './types'

// 商品 API：提供商品摘要的单条与批量查询
export const itemApi = {
  summary: (itemId: string) =>
    client.get<ItemSummary>(`/api/items/${itemId}/summary`).then((r) => r.data),

  batch: (ids: string[]) =>
    client.get<Record<string, ItemSummary>>('/api/items/batch', { params: { ids: ids.join(',') } }).then((r) => r.data),
}
