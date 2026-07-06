import type { CategoryComparisonSortBy } from '../../api'

// 排序字段下拉项：与后端 _ALLOWED_COMPARISON_SORT 对齐
// 标签使用业务术语而非统计学术语，降低理解门槛
export const SORT_OPTIONS: Array<{ value: CategoryComparisonSortBy; label: string }> = [
  { value: 'mean', label: '均价' },
  { value: 'median', label: '中位数' },
  { value: 'min', label: '最低价' },
  { value: 'max', label: '最高价' },
  { value: 'p10', label: 'P10（低端）' },
  { value: 'p25', label: 'P25' },
  { value: 'p75', label: 'P75' },
  { value: 'p90', label: 'P90（高端）' },
  { value: 'count', label: '样本数' },
]

// 时间窗下拉项：覆盖短/中/长期视角
// 0 表示全量；7/30/90 天用于观察短期行情波动
export const RANGE_OPTIONS = [
  { value: 0, label: '全部时间' },
  { value: 7, label: '近 7 天' },
  { value: 30, label: '近 30 天' },
  { value: 90, label: '近 90 天' },
]

// 捡漏评估等级 → Tag 颜色 + 中文标签映射
// 与后端 _compute_bargain_level 的 excellent/good/fair/poor/unknown/out_of_range 一一对应
// out_of_range：当前价格超出任务配置的 min_price/max_price，优先级最高（避免与分位数等级语义冲突）
export const BARGAIN_LEVEL_CONFIG: Record<string, { color: string; label: string }> = {
  excellent: { color: 'green', label: '极好捡漏' },
  good: { color: 'blue', label: '价格划算' },
  fair: { color: 'orange', label: '价格适中' },
  poor: { color: 'red', label: '价格偏高' },
  unknown: { color: 'default', label: '无法评估' },
  out_of_range: { color: 'magenta', label: '超出监控范围' },
}
