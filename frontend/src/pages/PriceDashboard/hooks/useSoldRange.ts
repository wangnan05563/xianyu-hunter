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
  // 为什么用 tasksLoaded：默认 soldTaskId 为 undefined 会触发"全部任务聚合视图"请求，
  // 该聚合值与 worker 实际过滤口径不一致，对用户无意义；用此标记延迟首次请求，
  // 等任务列表加载后自动选中首个任务再发起查询，避免浪费一次聚合请求
  const [tasksLoaded, setTasksLoaded] = useState(false)

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
  // 为什么自动选中首个任务：聚合视图的捡漏价是跨任务 P10，与 worker 通知/抢单过滤
  // 使用的"任务级 P10"口径不一致，默认显示首个任务更贴合用户预期
  useEffect(() => {
    taskApi.list({ limit: 200 })
      .then((r) => {
        const items = r.items || []
        setTasks(items)
        if (items.length > 0) {
          setSoldTaskId(items[0].id)
        }
      })
      .catch(() => setTasks([]))
      .finally(() => setTasksLoaded(true))
  }, [])

  // 在任务列表加载完成前不发起请求，避免默认进入"全部任务聚合视图"
  useEffect(() => {
    if (!tasksLoaded) return
    void fetchSoldRange()
  }, [fetchSoldRange, tasksLoaded])

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
