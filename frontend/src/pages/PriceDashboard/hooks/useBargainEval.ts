import { useState, useCallback, useEffect } from 'react'
import { priceApi } from '../../../api'
import type { BargainEval } from '../../../api/types'

// 价格评估 Hook：封装评估输入、结果与加载状态
// 为什么提取：价格评估依赖 soldTaskId 和 soldRangeDays，且有独立的输入状态和评估逻辑，
// 提取后与 soldRange 解耦，各自职责单一
interface UseBargainEvalOptions {
  soldTaskId: string | undefined
  soldRangeDays: number
}

export function useBargainEval({ soldTaskId, soldRangeDays }: UseBargainEvalOptions) {
  const [evalCurrentPrice, setEvalCurrentPrice] = useState<number | null>(null)
  const [evalResult, setEvalResult] = useState<BargainEval | null>(null)
  const [evalLoading, setEvalLoading] = useState(false)

  // 价格评估：复用 soldRange 的时间窗与任务，确保评估口径与上方统计一致
  const fetchBargainEval = useCallback(async () => {
    if (!soldTaskId || evalCurrentPrice == null || evalCurrentPrice <= 0) {
      setEvalResult(null)
      return
    }
    setEvalLoading(true)
    try {
      const data = await priceApi.bargainEval({
        task_id: soldTaskId,
        current_price: evalCurrentPrice,
        range_days: soldRangeDays,
      })
      setEvalResult(data)
    } catch {
      setEvalResult(null)
    } finally {
      setEvalLoading(false)
    }
  }, [soldTaskId, evalCurrentPrice, soldRangeDays])

  // 切换任务或时间窗时清空评估结果，避免与新任务口径不一致的旧结论误导用户
  useEffect(() => {
    setEvalResult(null)
  }, [soldTaskId, soldRangeDays])

  return {
    evalCurrentPrice,
    evalResult,
    evalLoading,
    setEvalCurrentPrice,
    fetchBargainEval,
  }
}
