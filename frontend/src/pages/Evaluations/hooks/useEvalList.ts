import { useState, useCallback, useRef, useEffect } from 'react'
import { message } from 'antd'
import dayjs from 'dayjs'
import { evalApi, type EvalItem } from '../../../api'
import type { ResultCategory } from './useEvalFilters'
import { usePersistentState } from '../../../hooks/usePersistentState'

/**
 * 列表数据 Hook
 *
 * 为什么拆出：列表加载是核心业务逻辑，包含分页、筛选参数组装、
 * 数据清洗等，独立后便于测试和复用。
 */
export interface EvalListState {
  items: EvalItem[]
  total: number
  loading: boolean
  page: number
  pageSize: number
  setPage: (v: number) => void
  setPageSize: (v: number) => void
  load: () => void
  setItems: React.Dispatch<React.SetStateAction<EvalItem[]>>
}

interface FilterSnapshot {
  itemId: string
  taskId: string
  scoreRange: [number, number]
  dateRange: [dayjs.Dayjs | null, dayjs.Dayjs | null] | null
  brandFilter: string
  soldFilter: 'all' | 'onsale' | 'sold'
  resultCategory: ResultCategory
  priceRange: [number | null, number | null]
  includeOutOfRange: boolean
}

export function useEvalList(
  filters: FilterSnapshot,
): EvalListState {
  const [items, setItems] = useState<EvalItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)

  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = usePersistentState<number>('xh.evals.pageSize', 20, {
    validator: (v): v is number => typeof v === 'number' && v > 0 && Number.isFinite(v),
  })

  const filtersRef = useRef(filters)
  filtersRef.current = filters

  const load = useCallback(() => {
    setLoading(true)
    const f = filtersRef.current
    const params: Record<string, unknown> = {
      page_num: page,
      page_size: pageSize,
      limit: pageSize * 4,
    }
    if (f.itemId) params.item_id = f.itemId
    if (f.taskId) params.task_id = f.taskId
    if (f.scoreRange[0] > 0) params.min_score = f.scoreRange[0]
    if (f.scoreRange[1] < 100) params.max_score = f.scoreRange[1]
    if (f.dateRange?.[0]) params.start_time = f.dateRange[0].format('YYYY-MM-DD')
    if (f.dateRange?.[1]) params.end_time = f.dateRange[1].format('YYYY-MM-DD')
    if (f.brandFilter) params.brand = f.brandFilter
    if (f.soldFilter !== 'all') params.sold_filter = f.soldFilter
    if (f.resultCategory) params.result_category = f.resultCategory
    if (f.priceRange[0] != null) params.min_price = f.priceRange[0]
    if (f.priceRange[1] != null) params.max_price = f.priceRange[1]
    if (f.includeOutOfRange) params.include_out_of_range = true

    evalApi.list(params)
      .then((res) => {
        const items = (res.items || []).map(it => ({
          ...it,
          payload: it.payload ?? ({ score: 0 } as EvalItem['payload']),
        }))
        setItems(items)
        setTotal(res.total || res.count || 0)
      })
      .catch(() => message.error('加载评估列表失败'))
      .finally(() => setLoading(false))
  }, [page, pageSize])

  useEffect(() => { load() }, [load])

  return {
    items,
    total,
    loading,
    page,
    pageSize,
    setPage,
    setPageSize,
    load,
    setItems,
  }
}
