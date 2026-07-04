import type { EvalItem } from '../../api'

// 分布 API 返回的完整类型
export interface DistResponse {
  buckets: Array<Array<{ count: number; pass: number; auto: number; fail: number }>>
  marginals: {
    price: number[]
    score: number[]
    result: { pass: number; auto: number; fail: number }
  }
  distribution: Array<{ range: string; count: number }>
  suggested_threshold: { score: number; pass_rate: number }
  total: number
  insufficient_count: number
  price_range: [number, number]
  // 后端返回的当前生效阈值，前端据此动态显示分类标签
  thresholds?: { pass_score: number; auto_buy_score: number }
}

// 卖家价格趋势数据
export interface SellerTrendData {
  seller_id: string
  items_count: number
  price_points: Array<{ date: string; avg_price: number; min_price: number; max_price: number; count: number }>
  current_avg: number
  trend: 'up' | 'down' | 'stable'
}

// 时间范围选项：与后端 range_hours 参数对齐
export const RANGE_OPTIONS = [
  { label: '24h', value: 24 },
  { label: '3天', value: 72 },
  { label: '7天', value: 168 },
  { label: '30天', value: 720 },
]

// 检测数据不足（score=null / risk_level=unknown），用于禁用 AI 评估与显示占位标签
export function isDataInsufficient(r: EvalItem): boolean {
  return r.payload.score == null || r.payload.risk_level === 'unknown'
}

// 方案C改进：获取数据不足的具体原因，用于前端展示
export function getInsufficientReason(r: EvalItem): string {
  const reasons = r.payload?.reject_reasons as string[] | undefined
  if (reasons?.includes('insufficient_seller_data')) {
    return '卖家信息采集失败，仅基于价格评估'
  }
  if (r.payload?.data_quality === 'partial') {
    return '卖家数据不完整，评估结果仅供参考'
  }
  return '数据不足，无法完整评估'
}

// 热力图辅助函数：生成价格/评分区间标签
// X 轴按价格等分，Y 轴按评分等分且从高到低排列（索引 0 = 顶部 = 最高分）
export function buildHeatmapLabels(dist: DistResponse) {
  const pBins = dist.buckets[0]?.length || 10
  const sBins = dist.buckets.length || 10
  const [pMin, pMax] = dist.price_range || [0, 5000]
  const pStep = (pMax - pMin) / pBins
  const xLabels = Array.from({ length: pBins }, (_, i) => {
    const lo = Math.round(pMin + i * pStep)
    const hi = Math.round(pMin + (i + 1) * pStep)
    return `¥${lo}~${hi}`
  })
  const sStep = 100 / sBins
  const yLabels = Array.from({ length: sBins }, (_, i) => {
    const hi = Math.round(100 - i * sStep)
    const lo = Math.round(100 - (i + 1) * sStep)
    return `${lo}-${hi}分`
  })
  return { xLabels, yLabels }
}

// 动态计算热力图最大值，避免颜色全白或全深
export function calcHeatmapMax(dist: DistResponse): number {
  let maxVal = 1
  dist.buckets.forEach((row) =>
    row.forEach((b) => { if (b.count > maxVal) maxVal = b.count })
  )
  return maxVal
}

// 操作列占位类型：表示为何不显示抢单按钮
// 抽取为纯函数便于单元测试覆盖优先级顺序（已下单 > 已售 > 未达阈值 > 可抢）
export type ActionPlaceholderType = 'ordered' | 'sold' | 'below_threshold' | null

// 判定评估记录在操作列应显示占位还是按钮
// 返回 null 表示应渲染抢单按钮，否则返回占位类型
// 优先级顺序的业务原因：
// - ordered 优先：已成功/进行中的订单不可重复下单
// - sold 次之：商品已售时即使订单失败也无法再抢，避免用户点击后才发现无法成交
// - below_threshold 最后：低分商品本就不应被抢，但若已售/已下单则状态展示优先
export function resolveActionDisplay(
  r: EvalItem,
  autoBuyScore: number,
): ActionPlaceholderType {
  const score = r.payload.score ?? 0
  const orderStatus = r.payload?.order_status
  // 已有订单（非失败/取消）时不显示抢单按钮，避免重复下单
  // null/undefined 在真值判断中均被排除，无需 as 断言
  if (orderStatus && orderStatus !== 'failed' && orderStatus !== 'cancelled') {
    return 'ordered'
  }
  // 已售商品不可抢：商品已下架/已被他人购得时下单必失败且可能产生脏数据
  if (r.payload?.is_sold) {
    return 'sold'
  }
  // 评分低于阈值时不显示，避免误操作
  if (score < autoBuyScore) {
    return 'below_threshold'
  }
  return null
}
