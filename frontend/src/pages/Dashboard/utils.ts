import { EVENT_TYPE_LABEL } from '../../constants/eventTypes'
import type { KpiCard, RecentEvent } from '../../api'

// ========== 常量：米其林星级阈值 ==========
// 反向指标（如 notify_failure_rate）使用递减阈值，正向指标使用递增阈值
export const STAR_THRESHOLDS: Record<string, number[]> = {
  eval_pass_rate:     [0, 50, 70, 85, 95],
  order_success_rate: [0, 40, 60, 75, 85],
  items_discovered:   [0, 200, 500, 800, 1500],
  notify_failure_rate: [50, 20, 10, 5, 2],
}

// ========== 工具函数 ==========

// 计算 KPI 米其林星级（1-5），反向指标使用 <= 比较
export function kpiStar(k: KpiCard): number {
  // S6582：用可选链替代手动 null 检查
  if (k?.value == null) return 0
  const v = Number(k.value)
  if (!Number.isFinite(v)) return 0
  const th = STAR_THRESHOLDS[k.id] || []
  if (!th.length) return 0
  const inverted = k.id === 'notify_failure_rate'
  let stars = 0
  for (let i = 0; i < 5; i++) {
    if (inverted ? v <= th[i] : v >= th[i]) stars = 5 - i
  }
  return stars
}

// 星级文字提示，用于 Tooltip
export function kpiStarTip(k: KpiCard): string {
  const s = kpiStar(k)
  const tipMap: Record<number, string> = { 5: '卓越', 4: '优秀', 3: '良好', 2: '需改进', 1: '待优化', 0: '暂无评级' }
  return `${s}/5 星 · ${tipMap[s] || '暂无评级'}`
}

// 格式化 KPI 数值：百分比保留 1 位小数（边界值 0/100 取整），其他取整
export function fmtKpiValue(k: KpiCard): string {
  if (k == null) return '—'
  const v = Number(k.value)
  if (!Number.isFinite(v)) return '—'
  if (k.is_pct) return v === 0 || v === 100 ? v.toFixed(0) : v.toFixed(1)
  return Math.round(v).toString()
}

// 涨跌样式类名：反向指标方向取反
export function deltaCls(k: KpiCard): string {
  if (k?.delta_pct == null) return 'na'
  if (k.delta_pct === 0) return 'flat'
  const inverted = k.id === 'notify_failure_rate'
  // 反向指标下降为 up，正向指标上升为 up
  const isUp = inverted ? k.delta_pct < 0 : k.delta_pct > 0
  return isUp ? 'up' : 'down'
}

// 涨跌文本：0 显示"持平"，其他显示带符号百分比
export function deltaText(k: KpiCard): string {
  if (k?.delta_pct == null) return ''
  if (k.delta_pct === 0) return '持平'
  return `${k.delta_pct > 0 ? '+' : ''}${k.delta_pct.toFixed(1)}%`
}

// 事件类型标签：先精确匹配，再前缀匹配，最后取点分末段
export function evTypeLabel(type: string): string {
  if (!type) return '事件'
  if (EVENT_TYPE_LABEL[type]) return EVENT_TYPE_LABEL[type]
  for (const [key, label] of Object.entries(EVENT_TYPE_LABEL)) {
    if (type.startsWith(key)) return label
  }
  return type.split('.').pop() || type
}

// 事件消息：优先用 message，其次从 payload 拼接关键字段
export function evMsg(ev: RecentEvent): string {
  if (ev?.message) return ev.message
  const p = ev?.payload
  if (!p) return ''
  if (typeof p === 'string') return p
  // S6551：payload 为 Record<string, unknown>，值可能是对象
  // 用 typeof 收窄类型，对象用 JSON.stringify 避免 [object Object]
  const toStr = (v: unknown): string =>
    typeof v === 'object' ? JSON.stringify(v) : String(v) // NOSONAR
  const parts: string[] = []
  if (p.keyword) parts.push('关键词: ' + toStr(p.keyword))
  if (p.title) parts.push(toStr(p.title))
  if (p.price != null) parts.push('¥' + toStr(p.price))
  if (p.count != null) parts.push(toStr(p.count) + ' 件')
  if (p.error) parts.push(toStr(p.error))
  return parts.join(' · ') || JSON.stringify(p).slice(0, 100)
}
