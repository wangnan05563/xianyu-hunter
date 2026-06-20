import client from './client'
import type { OrderItem } from './types'

// 订单 API：管理抢单记录与接管流程
export const orderApi = {
  list: (params?: { limit?: number; status?: string; task_id?: string }) =>
    client
      .get<{ items: OrderItem[]; stats: { succeeded: number; pending: number; failed: number; takeover: number } }>(
        '/api/orders',
        { params },
      )
      .then((r) => r.data),

  takeover: (id: number) => client.post(`/api/orders/${id}/takeover`).then((r) => r.data),

  confirmTakeover: (id: number) =>
    client.post(`/api/orders/${id}/takeover/confirm`).then((r) => r.data),

  cancelTakeover: (id: number) =>
    client.post(`/api/orders/${id}/takeover/cancel`).then((r) => r.data),
}
