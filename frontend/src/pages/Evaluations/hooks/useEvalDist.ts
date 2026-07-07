import { useState, useCallback, useRef, useEffect } from 'react'
import { message } from 'antd'
import { evalApi } from '../../../api'
import type { DistResponse } from '../utils'

/**
 * 分布图数据 Hook
 *
 * 为什么拆出：分布图有独立的 state（dist, distRange, distLoading）
 * 和加载逻辑，独立后主组件只需透传数据给 AnalysisPanel。
 */
export interface EvalDistState {
  dist: DistResponse | null
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
  targetPassRate: number
  setTargetPassRate: (v: number) => void
  thresholdPassCount: number
  thresholdPassRate: number
  autoSuggestedThreshold: number
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

  const passScore = dist?.thresholds?.pass_score ?? 60
  const autoBuyScore = dist?.thresholds?.auto_buy_score ?? 80

  const [thresholdTarget, setThresholdTarget] = useState(70)
  const [suggestion, setSuggestion] = useState<{ suggested_threshold: number; current_pass_rate: number } | null>(null)

  const [thresholdValue, setThresholdValue] = useState(60)
  const [targetPassRate, setTargetPassRate] = useState(70)

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
    evalApi.distribution(params)
      .then((res) => setDist(res as DistResponse))
      .catch(() => {})
      .finally(() => setDistLoading(false))
  }, [distRange])

  useEffect(() => { loadDist() }, [loadDist])

  const fetchSuggestion = useCallback(() => {
    evalApi.thresholdSuggestion(thresholdTarget / 100)
      .then((res) => { setSuggestion(res); message.success(`建议阈值: ${res.suggested_threshold}`) })
      .catch(() => message.error('获取阈值建议失败'))
  }, [thresholdTarget])

  const thresholdPassCount = items.filter(item => (item.payload.score ?? 0) >= thresholdValue).length
  const thresholdPassRate = items.length > 0 ? (thresholdPassCount / items.length * 100) : 0

  const computeSuggestedThreshold = (targetRate: number): number => {
    if (items.length === 0) return 0
    const sortedScores = items.map(item => item.payload.score ?? 0).sort((a, b) => b - a)
    const targetCount = Math.ceil(items.length * targetRate / 100)
    return sortedScores[Math.min(targetCount - 1, sortedScores.length - 1)] ?? 0
  }
  const autoSuggestedThreshold = computeSuggestedThreshold(targetPassRate)

  return {
    dist,
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
    targetPassRate,
    setTargetPassRate,
    thresholdPassCount,
    thresholdPassRate,
    autoSuggestedThreshold,
  }
}
