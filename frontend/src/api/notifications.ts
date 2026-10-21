import client from './client'

// 与后端 NotificationRow 字段对齐（src/xianyu_hunter/infra/db_models.py:305）
// read_at: null = 未读，非空 = 已读时间字符串
export interface NotificationItem {
  id: number
  level: NotificationLevel
  category: NotificationCategory
  title: string
  message: string
  link?: string | null
  dedup_key: string
  read_at: string | null
  created_at: string
}

// 分类与等级的唯一口径在后端 domain/notification.py（T02619）。
// 盯盘降价通知一直写的是 category='price'，但这里曾漏把它列进联合类型，
// 桌面/移动两张标签表都取到 undefined，通知中心那条 Tag 直接显示空白。
export type NotificationLevel = 'info' | 'warn' | 'err'
export type NotificationCategory = 'order' | 'auth' | 'price' | 'task' | 'config' | 'system'

// 中文标签：桌面端与移动端共用这一份（此前两张表把 auth 分别写成「登录」和「认证」）
// 新增分类必须同时补这里的标签——TS 的 Record 联合类型会编译报错，不会静默漏。
export const NOTIFICATION_CATEGORY_LABEL: Record<NotificationCategory, string> = {
  order: '订单',
  auth: '登录',
  price: '盯盘',
  task: '任务',
  config: '配置',
  system: '系统',
}

// level 颜色与文案：与后端 NOTIFICATION_LEVEL_VALUES 对齐
export const NOTIFICATION_LEVEL_LABEL: Record<NotificationLevel, string> = {
  info: '信息',
  warn: '警告',
  err: '错误',
}

export const NOTIFICATION_LEVEL_COLOR: Record<NotificationLevel, string> = {
  info: 'blue',
  warn: 'orange',
  err: 'red',
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

// 全量计数：三个数字都由后端一次性算出，与列表筛选/分页无关（T02561 / 2.9-3）
export interface NotificationCounts {
  unread: number
  read: number
  total: number
}

export const notificationApi = {
  list: (params?: {
    status?: 'unread' | 'read'
    limit?: number
    offset?: number
  }) =>
    client
      .get<NotificationListResponse>('/api/notifications', { params })
      .then((r) => r.data),

  counts: () =>
    client.get<NotificationCounts>('/api/notifications/unread_count').then((r) => r.data),

  // 标记单条已读：后端幂等，已读不报错
  markRead: (id: number) =>
    client.post<{ ok: boolean; id: number; newly_read: boolean }>(`/api/notifications/${id}/read`).then((r) => r.data),

  markAllRead: () =>
    client.post<{ ok: boolean; updated: number }>('/api/notifications/read_all').then((r) => r.data),

  delete: (id: number) =>
    client.delete<{ ok: boolean; id: number; deleted: boolean }>(`/api/notifications/${id}`).then((r) => r.data),

  // 批量删除（2.9-5 勾选删除）：deleted 可能小于 requested，
  // 勾中的通知可能已在其他标签页被删；前端按 deleted 如实提示
  deleteBatch: (ids: number[]) =>
    client
      .post<{ ok: boolean; deleted: number; requested: number }>(
        '/api/notifications/batch-delete',
        { ids },
      )
      .then((r) => r.data),

  // status=read 仅清已读；status 留空全清；后端拒绝其他值
  clear: (status?: 'unread' | 'read') =>
    client
      .delete<{ ok: boolean; deleted: number; status: string }>('/api/notifications', {
        params: status ? { status } : undefined,
      })
      .then((r) => r.data),
}
