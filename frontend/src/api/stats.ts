import client from './client'
import type { StatsOverview, KpiCard, RecentEvent, TrendSeries, TodayAlert } from './types'

// 统计 API：聚合仪表盘所需的概览、KPI、趋势与今日告警数据
export const statsApi = {
  overview: () => client.get<StatsOverview>('/api/stats').then((r) => r.data),

  today: () => client.get<TodayAlert>('/api/stats/today').then((r) => r.data),

  businessKpi: (rangeDays = 30) =>
    client.get<{ kpis: KpiCard[]; range_days: number; generated_at: string }>('/api/stats/business-kpi', { params: { range_days: rangeDays } }).then((r) => r.data),

  // 事件流复用 /api/events 命名空间，但语义归属统计仪表盘
  recentEvents: (limit = 20) =>
    client.get<{ events: RecentEvent[] }>('/api/events/recent', { params: { limit } }).then((r) => r.data),

  trend: (params: { metric: string; range_hours?: number; task_id?: string }) =>
    client.get<TrendSeries>('/api/stats/trend', { params }).then((r) => r.data),
}
