import { Card, Empty } from 'antd'
import ReactECharts from '../../../components/charts/EChart'
import type { DistResponse } from '../utils'

interface ResultBarChartProps {
  dist: DistResponse | null
  passScore: number
  autoBuyScore: number
}

// 结果分布饼图：按当前生效阈值将评估结果分为可抢/通过/驳回三档
export default function ResultBarChart({
  dist, passScore, autoBuyScore,
}: ResultBarChartProps) {
  const option = dist ? {
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    series: [{
      type: 'pie', radius: ['40%', '70%'], center: ['50%', '45%'],
      data: [
        { value: dist.marginals.result.auto, name: `可抢(≥${autoBuyScore})`, itemStyle: { color: '#52c41a' } },
        { value: dist.marginals.result.pass, name: `通过(${passScore}-${autoBuyScore - 1})`, itemStyle: { color: '#1890ff' } },
        { value: dist.marginals.result.fail, name: `驳回(<${passScore})`, itemStyle: { color: '#ff4d4f' } },
      ],
      label: { formatter: '{b}: {c}' },
    }],
  } : null

  return (
    <Card title="结果分布" style={{ marginBottom: 16 }}>
      {option ? (
        <ReactECharts option={option} style={{ height: 200 }} />
      ) : (
        <Empty description="暂无数据" />
      )}
    </Card>
  )
}
