// 价格格式化：≤1000 直接显示，>1000 用 k 简写
export function formatPrice(v: number | null | undefined): string {
  if (v == null) return '—'
  if (!Number.isFinite(v)) return '—'
  if (v < 1000) return `¥${v}`
  return `¥${(v / 1000).toFixed(1)}k`
}
