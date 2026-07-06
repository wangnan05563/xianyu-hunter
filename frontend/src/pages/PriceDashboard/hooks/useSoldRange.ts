import { useState, useCallback, useEffect } from 'react'
import { priceApi, taskApi } from '../../../api'
import type { Task } from '../../../api/types'

interface SoldRangeData {
  min_price: number | null
  max_price: number | null
  median_price: number | null
  bargain_price: number | null
  p10?: number | null
  p25?: number | null
  p75?: number | null
  p90?: number | null
  sample_size: number
  filtered_count?: number
  source: string
  source_label?: string
  message?: string
  task_price_range?: { min_price: number | null; max_price: number | null }
}

// 捡漏价格参考 Hook：封装任务列表、soldRange 状态与数据加载
// 为什么提取：soldRange 相关逻辑涉及 2 个独立数据源（任务列表 + 价格区间），
// 状态间存在联动关系，提取后职责更清晰
export function useSoldRange() {
  const [soldRange, setSoldRange] = useState<SoldRangeData | null>(null)
  const [soldLoading, setSoldLoading] = useState(false)
  const [soldTaskId, setSoldTaskId] = useState<string | undefined>(undefined)
  const [soldRangeDays, setSoldRangeDays] = useState(30)
  const [tasks, setTasks] = useState<Task[]>([])

  const fetchSoldRange = useCallback(async () => {
    setSoldLoading(true)
    try {
      const data = await priceApi.soldRange({
        task_id: soldTaskId,
        range_days: soldRangeDays,
      })
      setSoldRange(data as SoldRangeData)
    } catch {
      setSoldRange(null)
    } finally {
      setSoldLoading(false)
    }
  }, [soldTaskId, soldRangeDays])

  // 拉取任务列表，用于捡漏价格参考的品类下拉
  useEffect(() => {
    taskApi.list({ limit: 200 }).then((r) => setTasks(r.items || [])).catch(() => setTasks([]))
  }, [])

  useEffect(() => {
    void fetchSoldRange()
  }, [fetchSoldRange])

  return {
    soldRange,
    soldLoading,
    soldTaskId,
    soldRangeDays,
    tasks,
    setSoldTaskId,
    setSoldRangeDays,
    fetchSoldRange,
  }
}
