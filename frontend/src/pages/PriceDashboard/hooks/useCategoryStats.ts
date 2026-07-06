import { useState, useCallback, useEffect } from 'react'
import { priceApi } from '../../../api'
import type { CategoryStat } from '../../../api'

// 品类统计 Hook：封装品类统计数据的状态管理与数据加载
// 为什么提取：原组件中品类统计的 3 个 state + fetch 函数 + useEffect 占据约 20 行，
// 提取后主组件只需关注业务逻辑，无需关心加载状态的细节
export function useCategoryStats() {
  const [stats, setStats] = useState<CategoryStat[]>([])
  const [statsTotal, setStatsTotal] = useState(0)
  const [statsLoading, setStatsLoading] = useState(false)

  const fetchStats = useCallback(async () => {
    setStatsLoading(true)
    try {
      const data = await priceApi.categoryStats({})
      setStats(data.categories || [])
      setStatsTotal(data.total_count || 0)
    } catch {
      setStats([])
      setStatsTotal(0)
    } finally {
      setStatsLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchStats()
  }, [fetchStats])

  return {
    stats,
    statsTotal,
    statsLoading,
    fetchStats,
  }
}
