import client from './client'

// 与后端 NotificationRow 字段对齐（src/xianyu_hunter/infra/db_models.py:305）
// read_at: null = 未读，非空 = 已读时间字符串
export interface NotificationItem {
  id: number
  level: 'info' | 'warn' | 'err'
  category: 'order' | 'auth' | 'system' | 'config' | 'task'
  title: string
  message: string
  link?: string | null
  dedup_key: string
  read_at: string | null
  created_at: string
}

export interface NotificationListResponse {
  items: NotificationItem[]
  count: number
  total: number
  limit: number
  offset: number
  status: 'all' | 'unread' | 'read'
}

// 状态参数复用三个端点（list / count / clear），统一类型避免散落字符串
export type NotificationStatus = 'unread' | 'read' | undefined

export const notificationApi = {
  list: (params?: {
    status?: 'unread' | 'read'
    limit?: number
    offset?: number
  }) =>
    client
      .get<NotificationListResponse>('/api/notifications', { params })
      .then((r) => r.data),

  unreadCount: () =>
    client.get<{ unread: number }>('/api/notifications/unread_count').then((r) => r.data),

  // 标记单条已读：后端幂等，已读不报错
  markRead: (id: number) =>
    client.post<{ ok: boolean; id: number; newly_read: boolean }>(`/api/notifications/${id}/read`).then((r) => r.data),

  markAllRead: () =>
    client.post<{ ok: boolean; updated: number }>('/api/notifications/read_all').then((r) => r.data),

  delete: (id: number) =>
    client.delete<{ ok: boolean; id: number; deleted: boolean }>(`/api/notifications/${id}`).then((r) => r.data),

  // status=read 仅清已读；status 留空全清；后端拒绝其他值
  clear: (status?: 'unread' | 'read') =>
    client
      .delete<{ ok: boolean; deleted: number; status: string }>('/api/notifications', {
        params: status ? { status } : undefined,
      })
      .then((r) => r.data),
}
