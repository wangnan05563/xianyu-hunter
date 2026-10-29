// 商品价格走势图（PRD FR-F1-2，REQ-007）：近 30 天快照 ECharts 折线，标注降价点
// 消费方：商品中心行展开（ItemList expandable）
import { useEffect, useState } from 'react'
import { Empty, Spin } from 'antd'
import ReactECharts from '@/components/charts/EChart'
import { itemApi, type PriceHistoryPoint } from '../api/item'
import { formatShortDateTime } from '../utils/timeFormat'

// 快照来源中文标签（与后端 price_history.source 枚举对齐）
const SOURCE_LABELS: Record<string, string> = {
  collect: '采集',
  live_search: '实时搜索',
  detail: '详情采集',
}

export default function PriceTrendChart({ itemId }: { readonly itemId: string }) {
  const [points, setPoints] = useState<PriceHistoryPoint[] | null>(null)
  const [minPrice, setMinPrice] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)

  // 展开即加载：每次展开重新拉取，保证看到最新快照
  useEffect(() => {
    if (!itemId) return
    setLoading(true)
    itemApi.priceHistory(itemId)
      .then((data: { points: PriceHistoryPoint[]; min_price: number | null }) => {
        setPoints(data.points)
        setMinPrice(data.min_price)
      })
      .catch(() => setPoints([]))
      .finally(() => setLoading(false))
  }, [itemId])

  if (loading) {
    return <div style={{ textAlign: 'center', padding: 24 }}><Spin /></div>
  }
  // 无历史：PRD 明确要求展示「暂无价格记录」而非空图
  if (!points || points.length === 0) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无价格记录" style={{ padding: 16 }} />
  }

  // 降价点标注：价格低于前一个快照的点用红色标记（FR-F1-2「标注每次降价点」）
  const dropIndices = points
    .map((p, i) => (i > 0 && p.price < points[i - 1].price ? i : -1))
    .filter((i) => i >= 0)

  return (
    <div style={{ padding: '8px 4px' }}>
      <ReactECharts
        option={{
          tooltip: {
            trigger: 'axis',
            formatter: (params: unknown) => {
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              const p = (params as any[])[0]
              const src = SOURCE_LABELS[points[p.dataIndex]?.source] || points[p.dataIndex]?.source || ''
              // S4624：内层模板先算成变量，避免模板字符串里再嵌模板字符串
              const srcSuffix = src ? `（${src}）` : ''
              return `${p.axisValue}<br/>¥${Number(p.value).toFixed(2)}${srcSuffix}`
            },
          },
          grid: { left: 60, right: 20, top: 30, bottom: 50 },
          xAxis: {
            type: 'category',
            data: points.map((p) => formatShortDateTime(p.ts, 'month-day-time')),
            axisLabel: { fontSize: 10 },
          },
          yAxis: { type: 'value', scale: true, axisLabel: { fontSize: 10 } },
          series: [{
            type: 'line',
            data: points.map((p) => p.price),
            smooth: true,
            symbol: 'circle',
            symbolSize: 6,
            lineStyle: { width: 2, color: '#2563EB' },
            itemStyle: { color: '#2563EB' },
            areaStyle: { color: 'rgba(37, 99, 235, 0.08)' },
            // 降价点：红色大标记突出显示
            markPoint: dropIndices.length > 0 ? {
              data: dropIndices.map((i) => ({
                coord: [formatShortDateTime(points[i].ts, 'month-day-time'), points[i].price],
                value: '降',
                itemStyle: { color: '#ff4d4f' },
              })),
              symbolSize: 34,
              label: { fontSize: 10 },
            } : undefined,
            // S7735：条件改成正向（minPrice 为 null 时不画最低价线）
            markLine: minPrice === null ? undefined : {
              silent: true,
              symbol: 'none',
              data: [{ yAxis: minPrice, label: { formatter: `最低 ¥${minPrice.toFixed(2)}`, fontSize: 10 } }],
              lineStyle: { color: '#faad14', type: 'dashed' },
            },
          }],
        }}
        style={{ height: 240 }}
      />
    </div>
  )
}
