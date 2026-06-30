import { Card, Empty } from 'antd'
import ReactECharts from '../../../components/charts/EChart'
import type { DistResponse } from '../utils'

interface PriceHistogramProps {
  dist: DistResponse | null
}

// 分数分布直方图：按后端返回的 distribution 区间统计商品数量
export default function PriceHistogram({ dist }: PriceHistogramProps) {
  const option = dist ? {
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 20, bottom: 40 },
    xAxis: {
      type: 'category', data: dist.distribution?.map((d) => d.range) || [],
      axisLabel: { fontSize: 10 },
    },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{
      type: 'bar', barWidth: '60%',
      data: dist.distribution?.map((d) => d.count) || [],
      itemStyle: { color: '#1890ff', borderRadius: [4, 4, 0, 0] },
      label: { show: true, position: 'top', fontSize: 10 },
    }],
  } : null

  return (
    <Card title="分数分布" style={{ marginBottom: 16 }}>
      {option ? (
        <ReactECharts option={option} style={{ height: 180 }} />
      ) : (
        <Empty description="暂无数据" />
      )}
    </Card>
  )
}
