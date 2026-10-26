import { useState, useCallback, useRef, useEffect } from 'react'
import { message } from 'antd'
import { evalApi } from '../../../api'
import { useFailedSources } from '../../../hooks/useFailedSources'
import type { DistResponse } from '../utils'

// 分布图这一路请求的数据源声明（T02899）。
// 原先把 reject 吞成空块：失败后 dist 恒为 null，主页面的统计卡与热力图整块不渲染，
// 用户看不出「没取到」和「近 7 天没有评估记录」的区别。
type EvalDistSource = 'dist'

const SOURCE_LABELS: Record<EvalDistSource, string> = {
  dist: '评估分布',
}

/**
 * 分布图数据 Hook
 *
 * 为什么拆出：分布图有独立的 state（dist, distRange, distLoading）
 * 和加载逻辑，独立后主组件只需透传数据给 AnalysisPanel。
 */
export interface EvalDistState {
  dist: DistResponse | null
  distFailed: boolean
  distSourceLabel: string
  distRange: number
  distLoading: boolean
  passScore: number
  autoBuyScore: number
  setDistRange: (v: number) => void
  loadDist: () => void
  thresholdTarget: number
  setThresholdTarget: (v: number) => void
  suggestion: { suggested_threshold: number; current_pass_rate: number } | null
  fetchSuggestion: () => void
  thresholdValue: number
  setThresholdValue: (v: number) => void
  thresholdPassCount: number
  thresholdPassRate: number
}

interface DistFilterSnapshot {
  taskId: string
  priceRange: [number | null, number | null]
  includeOutOfRange: boolean
}

export function useEvalDist(
  items: { payload: { score?: number | null } }[],
  filters: DistFilterSnapshot,
): EvalDistState {
  const [dist, setDist] = useState<DistResponse | null>(null)
  const [distRange, setDistRange] = useState(168)
  const [distLoading, setDistLoading] = useState(false)
  const { isFailed, track } = useFailedSources<EvalDistSource>()

  const passScore = dist?.thresholds?.pass_score ?? 60
  const autoBuyScore = dist?.thresholds?.auto_buy_score ?? 80

  const [thresholdTarget, setThresholdTarget] = useState(70)
  const [suggestion, setSuggestion] = useState<{ suggested_threshold: number; current_pass_rate: number } | null>(null)

  const [thresholdValue, setThresholdValue] = useState(60)

  // 解构出原始值字段，便于在 useEffect 依赖数组中精确订阅筛选变化
  // 若直接将 filters 整体放入依赖数组会因对象引用每次渲染都变化导致无限刷新
  const { taskId, priceRange, includeOutOfRange } = filters
  const minPrice = priceRange[0]
  const maxPrice = priceRange[1]

  const filtersRef = useRef(filters)
  filtersRef.current = filters

  const loadDist = useCallback(() => {
    setDistLoading(true)
    const f = filtersRef.current
    const params: {
      range_hours: number
      price_bin_count: number
      score_bin_count: number
      task_id?: string
      min_price?: number
      max_price?: number
      include_out_of_range?: boolean
    } = { range_hours: distRange, price_bin_count: 10, score_bin_count: 10 }
    if (f.taskId) params.task_id = f.taskId
    if (f.priceRange[0] != null) params.min_price = f.priceRange[0]
    if (f.priceRange[1] != null) params.max_price = f.priceRange[1]
    if (f.includeOutOfRange) params.include_out_of_range = true
    void track('dist', evalApi.distribution(params))
      .then((res) => { if (res) setDist(res as DistResponse) })
      .finally(() => setDistLoading(false))
  }, [distRange, track])

  // loadDist 内部用 filtersRef.current 读取最新筛选，但函数引用仅依赖 distRange
  // 因此显式订阅 taskId/价格范围/超范围切换，确保任务切换时统计栏同步刷新
  useEffect(() => {
    loadDist()
  }, [loadDist, taskId, minPrice, maxPrice, includeOutOfRange])

  const fetchSuggestion = useCallback(() => {
    evalApi.thresholdSuggestion(thresholdTarget / 100)
      .then((res) => { setSuggestion(res); message.success(`建议阈值: ${res.suggested_threshold}`) })
      .catch(() => message.error('获取阈值建议失败'))
  }, [thresholdTarget])

  const thresholdPassCount = items.filter(item => (item.payload.score ?? 0) >= thresholdValue).length
  const thresholdPassRate = items.length > 0 ? (thresholdPassCount / items.length * 100) : 0

  return {
    dist,
    distFailed: isFailed('dist'),
    distSourceLabel: SOURCE_LABELS.dist,
    distRange,
    distLoading,
    passScore,
    autoBuyScore,
    setDistRange,
    loadDist,
    thresholdTarget,
    setThresholdTarget,
    suggestion,
    fetchSuggestion,
    thresholdValue,
    setThresholdValue,
    thresholdPassCount,
    thresholdPassRate,
  }
}
