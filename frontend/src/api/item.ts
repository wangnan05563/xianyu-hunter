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
  // taskId 可选：items 表无记录时回填 task_links.display 使用
  // 返回完整采集字段：实时模式下前端用此结果直接更新 liveItemsRef，避免重新搜索覆盖采集结果
  refresh: (itemId: string, taskId?: string) =>
    client.post<{
      ok: boolean
      item_id: string
      is_sold: boolean
      title: string
      price: number
      brand: string
      seller_id: string
      region: string
      want_cnt: number
      view_cnt: number
      thumb_url: string
      image_urls: string[]
      publish_time: string | null
      seller_nick: string
      seller_credit: number | null
    }>(
      `/api/items/${itemId}/refresh`,
      null,
      { params: taskId ? { task_id: taskId } : {} },
    ).then((r) => r.data),
}
