import { useState, useMemo, useCallback, useEffect } from 'react'
import dayjs from 'dayjs'
import type { Task } from '../../../api'
import { usePersistentState } from '../../../hooks/usePersistentState'

/**
 * 筛选条件 Hook
 *
 * 为什么拆出：主组件中有 ~15 个筛选相关的 state + 对应的 setter，
 * 集中管理后主组件只需消费一个对象，认知复杂度显著降低。
 *
 * 包含：
 * - 商品ID、任务ID、评分范围、时间范围
 * - 品牌、状态、价格范围
 * - 结果分类（统计卡片点击）
 * - 显示超范围商品
 */
export type ResultCategory = 'auto' | 'pass' | 'fail' | 'insufficient' | null

export interface EvalFilters {
  itemId: string
  setItemId: (v: string) => void
  taskId: string
  setTaskId: (v: string) => void
  tasks: Task[]
  setTasks: (t: Task[]) => void
  scoreRange: [number, number]
  setScoreRange: (v: [number, number]) => void
  dateRange: [dayjs.Dayjs | null, dayjs.Dayjs | null] | null
  setDateRange: (v: [string, string] | null) => void
  brandFilter: string
  setBrandFilter: (v: string) => void
  soldFilter: 'all' | 'onsale' | 'sold'
  setSoldFilter: (v: 'all' | 'onsale' | 'sold') => void
  resultCategory: ResultCategory
  setResultCategory: (v: ResultCategory) => void
  toggleResultCategory: (v: ResultCategory) => void
  priceRange: [number | null, number | null]
  setPriceRange: (v: [number | null, number | null]) => void
  includeOutOfRange: boolean
  setIncludeOutOfRange: (v: boolean) => void
  reset: () => void
}

export function useEvalFilters(): EvalFilters {
  const [itemId, setItemId] = usePersistentState<string>('xh.evals.itemId', '')
  const [taskId, setTaskId] = usePersistentState<string>('xh.evals.taskId', '')
  const [tasks, setTasks] = useState<Task[]>([])
  const [scoreRange, setScoreRange] = usePersistentState<[number, number]>(
    'xh.evals.scoreRange', [0, 100],
    {
      validator: (v): v is [number, number] =>
        Array.isArray(v) && v.length === 2 && v.every(n => typeof n === 'number' && Number.isFinite(n)),
    },
  )

  const [dateRangeIso, setDateRange] = usePersistentState<[string, string] | null>(
    'xh.evals.dateRange', null,
    {
      validator: (v): v is [string, string] | null =>
        v === null || (Array.isArray(v) && v.length === 2 && v.every(s => typeof s === 'string')),
    },
  )
  const dateRange = useMemo<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(
    () => dateRangeIso
      ? [dateRangeIso[0] ? dayjs(dateRangeIso[0]) : null, dateRangeIso[1] ? dayjs(dateRangeIso[1]) : null]
      : null,
    [dateRangeIso],
  )

  const [brandFilter, setBrandFilter] = usePersistentState<string>('xh.evals.brandFilter', '')
  const [soldFilter, setSoldFilter] = usePersistentState<'all' | 'onsale' | 'sold'>(
    'xh.evals.soldFilter', 'all',
    {
      validator: (v): v is 'all' | 'onsale' | 'sold' => v === 'all' || v === 'onsale' || v === 'sold',
    },
  )

  const [resultCategory, setResultCategory] = useState<ResultCategory>(null)
  const toggleResultCategory = useCallback((c: ResultCategory) => {
    setResultCategory(prev => prev === c ? null : c)
  }, [])

  const [priceRange, setPriceRange] = useState<[number | null, number | null]>([null, null])
  const [includeOutOfRange, setIncludeOutOfRange] = useState<boolean>(false)

  useEffect(() => {
    if (taskId === '') {
      setPriceRange([null, null])
      return
    }
    const task = tasks.find(t => t.id === taskId)
    if (task) {
      setPriceRange([
        task.min_price ?? null,
        task.max_price ?? null,
      ])
    }
  }, [taskId, tasks])

  const reset = useCallback(() => {
    setItemId('')
    setTaskId('')
    setScoreRange([0, 100])
    setDateRange(null)
    setBrandFilter('')
    setSoldFilter('all')
    setResultCategory(null)
    setPriceRange([null, null])
    setIncludeOutOfRange(false)
  }, [setItemId, setTaskId, setScoreRange, setDateRange, setBrandFilter, setSoldFilter])

  return {
    itemId, setItemId,
    taskId, setTaskId,
    tasks, setTasks,
    scoreRange, setScoreRange,
    dateRange, setDateRange,
    brandFilter, setBrandFilter,
    soldFilter, setSoldFilter,
    resultCategory, setResultCategory,
    toggleResultCategory,
    priceRange, setPriceRange,
    includeOutOfRange, setIncludeOutOfRange,
    reset,
  }
}
