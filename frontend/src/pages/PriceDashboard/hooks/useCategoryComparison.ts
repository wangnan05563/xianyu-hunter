import { useState, useCallback, useEffect, useMemo } from 'react'
import { theme } from 'antd'
import { priceApi } from '../../../api'
import type { CategoryComparisonItem, CategoryComparisonSortBy } from '../../../api'

// 品类横向对比 Hook：封装筛选状态、数据加载与图表配置
// 为什么提取：原组件中横向对比包含 6 个 state + 2 个 useMemo + fetch 函数 + 多个 useEffect，
// 逻辑高度内聚，提取后可独立测试和复用
export function useCategoryComparison() {
  const { token } = theme.useToken()
  const [comparison, setComparison] = useState<CategoryComparisonItem[]>([])
  const [overallMean, setOverallMean] = useState(0)
  const [compLoading, setCompLoading] = useState(false)
  const [sortBy, setSortBy] = useState<CategoryComparisonSortBy>('mean')
  const [order, setOrder] = useState<'asc' | 'desc'>('desc')
  const [rangeDays, setRangeDays] = useState(0)

  const fetchComparison = useCallback(async () => {
    setCompLoading(true)
    try {
      const data = await priceApi.categoryComparison({
        sort_by: sortBy,
        order,
        limit: 20,
        range_days: rangeDays,
      })
      setComparison(data.categories || [])
      setOverallMean(data.overall_mean || 0)
    } catch {
      setComparison([])
      setOverallMean(0)
    } finally {
      setCompLoading(false)
    }
  }, [sortBy, order, rangeDays])

  useEffect(() => {
    void fetchComparison()
  }, [fetchComparison])

  // 横向条形图配置：y 轴品类名，x 轴价格；用 markLine 标注全体均价基线
  const comparisonOption = useMemo<EChartOption | null>(() => {
    if (!comparison.length) return null
    // 倒序排列，让排序第一项显示在最上方（ECharts 横向条形图视觉惯例）
    const items = [...comparison].reverse()
    return {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: Array<{ dataIndex: number }>) => {
          const item = items[params[0]?.dataIndex]
          if (!item) return ''
          const lines = [
            `<b>${item.name || item.keyword || '未分类'}</b>`,
            `样本数: ${item.count}`,
            `均价: ¥${item.mean}`,
            `中位数: ¥${item.median}`,
            `最低/最高: ¥${item.min} / ¥${item.max}`,
            `P25~P75: ¥${item.p25} ~ ¥${item.p75}`,
            `偏离均价: ${item.deviation_pct > 0 ? '+' : ''}${item.deviation_pct}%`,
          ]
          return lines.join('<br/>')
        },
        backgroundColor: token.colorBgElevated,
        borderColor: token.colorBorderSecondary,
        textStyle: { color: token.colorText },
      },
      grid: { left: 120, right: 40, top: 30, bottom: 40 },
      xAxis: {
        type: 'value',
        name: '均价 (¥)',
        nameTextStyle: { color: token.colorTextTertiary },
        axisLabel: {
          color: token.colorTextTertiary,
          formatter: (v: number) => v < 1000 ? v : `${(v / 1000).toFixed(1)}k`,
        },
        splitLine: { lineStyle: { color: token.colorBorderSecondary } },
      },
      yAxis: {
        type: 'category',
        data: items.map((c) => (c.name || c.keyword || '未分类').slice(0, 12)),
        axisLabel: { color: token.colorTextSecondary, fontSize: 11 },
        axisTick: { show: false },
        axisLine: { show: false },
      },
      series: [{
        type: 'bar',
        data: items.map((c) => c.mean),
        // 高于均价用红色（贵），低于均价用绿色（便宜），与项目涨跌色约定一致
        itemStyle: {
          color: (p: { dataIndex: number }) => {
            const item = items[p.dataIndex]
            if (!item || item.deviation_pct > 5) return token.colorError
            if (item.deviation_pct < -5) return token.colorSuccess
            return token.colorPrimary
          },
          borderRadius: [0, 4, 4, 0],
        },
        barWidth: '60%',
        markLine: overallMean > 0 ? {
          symbol: 'none',
          data: [{ xAxis: overallMean, label: { formatter: '均价 ¥{c}', color: token.colorTextSecondary, position: 'insideEndTop', fontSize: 10 } }],
          lineStyle: { color: token.colorTextSecondary, type: 'dashed' },
          animation: false,
        } : undefined,
      }],
    }
  }, [comparison, overallMean, token])

  return {
    comparison,
    overallMean,
    compLoading,
    sortBy,
    order,
    rangeDays,
    setSortBy,
    setOrder,
    setRangeDays,
    fetchComparison,
    comparisonOption,
  }
}
