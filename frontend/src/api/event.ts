import client from './client'
import { API_BASE } from '../utils/apiBase'
import type { TimelineEntry, LogEntry } from './types'

// 时间线 API：聚合订单与事件为统一时间线视图
export const timelineApi = {
  list: (params: { types?: string; task_id?: string; limit?: number }) =>
    client
      .get<{ items: TimelineEntry[]; count: number }>('/api/timeline', { params })
      .then((r) => r.data),
}

// 日志 API：提供日志流读取、检索与导出 URL 构造
export const logApi = {
  list: (params?: { limit?: number; source?: string }) =>
    client.get<{ items: Array<{ source: string; level: string; lines: string[] }> }>('/api/logs', { params }).then(
      (r) => r.data,
    ),

  search: (params: { q?: string; level?: string; tag?: string; task_id?: string; start?: string; end?: string; limit?: number; offset?: number }) =>
    client
      .get<{
        items: LogEntry[]
        count: number
        matched_levels: Record<string, number>
        matched_tags: Record<string, number>
        total_estimate: number
      }>('/api/logs/search', { params })
      .then((r) => r.data),

  // 导出 URL 直接交给浏览器下载，无需经过 axios
  // 必须带部署子路径前缀（API_BASE），否则域名模式 /xianyu 下落到根路径被代理拦截
  // filters 只作用于 format=csv：后端 format=log 走的是原始文件拼接，不吃任何筛选参数，
  // 所以 LOG 按钮不拼参数、文案也要说清是「全部原始日志文件」
  exportUrl: (
    format: 'csv' | 'log',
    filters?: { q?: string; level?: string; task_id?: string; start?: string; end?: string },
  ) => {
    const params = new URLSearchParams({ format })
    if (filters?.q) params.set('q', filters.q)
    if (filters?.level) params.set('level', filters.level)
    if (filters?.task_id) params.set('task_id', filters.task_id)
    if (filters?.start) params.set('start', filters.start)
    if (filters?.end) params.set('end', filters.end)
    return `${API_BASE}api/logs/export?${params.toString()}`
  },
}
