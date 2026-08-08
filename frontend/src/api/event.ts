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

  search: (params: { q?: string; level?: string; tag?: string; task_id?: string; start?: string; limit?: number; offset?: number }) =>
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
  exportUrl: (format: 'csv' | 'log') => `${API_BASE}api/logs/export?format=${format}`,
}
