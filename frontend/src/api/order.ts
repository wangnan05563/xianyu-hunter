import client from './client'
import type { OrderItem } from './types'

// 订单列表查询参数：支持后端分页 + 过滤
export interface OrderListParams {
  page_num?: number
  page_size?: number
  limit?: number
  status?: string
  task_id?: string
  item_id?: string
}

// 订单 API：管理抢单记录与接管流程
export const orderApi = {
  // 后端 list_orders 返回 {items, count, total}，total 用于前端分页
  list: (params?: OrderListParams) =>
    client
      .get<{ items: OrderItem[]; count: number; total: number }>(
        '/api/orders',
        { params },
      )
      .then((r) => r.data),

  // id 为字符串组合键（item_id:timestamp:rand），非数字
  // 返回 takeover_deadline 供前端 modal 启动倒计时
  takeover: (id: string) =>
    client
      .post<{
        ok: boolean
        id: string
        status: string
        takeover_at: string
        takeover_deadline: string
        timeout_min: number
      }>(`/api/orders/${id}/takeover`)
      .then((r) => r.data),

  confirmTakeover: (id: string) =>
    client.post(`/api/orders/${id}/takeover/confirm`).then((r) => r.data),

  cancelTakeover: (id: string) =>
    client.post(`/api/orders/${id}/takeover/cancel`).then((r) => r.data),

  // 删除订单：用于清理失败/测试订单
  delete: (id: string) =>
    client.delete<{ ok: boolean; id: string; deleted: number }>(`/api/orders/${id}`).then((r) => r.data),

  // 手动触发抢单：突破纯自动模式，让用户在评估明细页面主动触发
  // 前置条件：服务以 XH_WITH_SCHEDULER=1 模式启动以注入浏览器实例
  // 超时 120 秒：浏览器自动化流程（导航+点击+等待）需要 60-90 秒
  manualTakeover: (itemId: string, taskId?: string) =>
    client
      .post<{
        ok: boolean
        outcome: 'success' | 'skipped_duplicate' | 'failed'
        order?: { order_no: string; price: number; status: string }
        message: string
      }>('/api/orders/manual-takeover', { item_id: itemId, task_id: taskId }, { timeout: 120000 })
      .then((r) => r.data),
}
