import { useState, useCallback } from 'react'
import { evalApi } from '../../../api'
import type { SellerTrendData } from '../utils'

/**
 * 卖家价格趋势 Hook
 *
 * 为什么拆出：展开行中的趋势加载逻辑有独立的 state
 * （trendCache, trendLoading, trendError）和加载函数，
 * 独立后 ExpandedDetail 组件可以直接消费。
 */
export interface EvalTrendState {
  trendCache: Record<string, SellerTrendData>
  trendLoading: string
  trendError: Record<string, string>
  loadSellerTrend: (itemId: string) => Promise<void>
}

export function useEvalTrend(): EvalTrendState {
  const [trendCache, setTrendCache] = useState<Record<string, SellerTrendData>>({})
  const [trendLoading, setTrendLoading] = useState('')
  const [trendError, setTrendError] = useState<Record<string, string>>({})

  const loadSellerTrend = useCallback(async (itemId: string) => {
    if (trendCache[itemId]) return
    setTrendLoading(itemId)
    setTrendError((prev) => ({ ...prev, [itemId]: '' }))
    try {
      const data: SellerTrendData = await evalApi.sellerTrend(itemId)
      setTrendCache((prev) => ({ ...prev, [itemId]: data }))
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      if (msg.includes('404') || msg.includes('未找到')) {
        setTrendError((prev) => ({ ...prev, [itemId]: '该商品未入库，无法查询卖家趋势' }))
      } else {
        setTrendError((prev) => ({ ...prev, [itemId]: '加载失败：' + msg.slice(0, 50) }))
      }
    } finally {
      setTrendLoading('')
    }
  }, [trendCache])

  return {
    trendCache,
    trendLoading,
    trendError,
    loadSellerTrend,
  }
}
