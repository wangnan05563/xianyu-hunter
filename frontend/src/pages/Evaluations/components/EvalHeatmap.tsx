import { Card, Segmented, Spin, Empty, theme } from 'antd'
import ReactECharts from '../../../components/charts/EChart'
import {
  RANGE_OPTIONS, buildHeatmapLabels, calcHeatmapMax, type DistResponse,
} from '../utils'

interface EvalHeatmapProps {
  readonly dist: DistResponse | null
  readonly distRange: number
  readonly distLoading: boolean
  readonly onRangeChange: (v: number) => void
}

export default function EvalHeatmap({
  dist, distRange, distLoading, onRangeChange,
}: EvalHeatmapProps) {
  // 在 ConfigProvider 内部读取 token，让 ECharts 跟随主题
  const { token } = theme.useToken()
  // 标签与颜色最大值依赖 dist，dist 为 null 时回退到空数组与最小值
  const { xLabels, yLabels } = dist ? buildHeatmapLabels(dist) : { xLabels: [], yLabels: [] }
  const heatmapMax = dist ? calcHeatmapMax(dist) : 1

  const heatmapOption = dist?.buckets?.length ? {
    tooltip: {
      position: 'top',
      backgroundColor: token.colorBgElevated,
      borderColor: token.colorBorderSecondary,
      textStyle: { color: token.colorText },
      formatter: (p: { dataIndex: [number, number]; value: number }) => {
        const [pi, si] = p.dataIndex
        const bucket = dist.buckets[si]?.[pi]
        if (!bucket || bucket.count === 0) return '该区间暂无商品'
        return `${xLabels[pi]} × ${yLabels[si]}<br/>` +
          `<b>商品数：${bucket.count}</b><br/>` +
          `可抢：${bucket.auto} / 通过：${bucket.pass} / 驳回：${bucket.fail}`
      },
    },
    grid: { left: 65, right: 20, top: 20, bottom: 70, containLabel: true },
    xAxis: {
      type: 'category', name: '价格区间', nameLocation: 'end', nameGap: 8,
      nameTextStyle: { fontSize: 11, color: token.colorTextTertiary },
      data: xLabels,
      splitArea: { show: true }, axisLabel: { fontSize: 9, rotate: 30, color: token.colorTextTertiary },
    },
    yAxis: {
      type: 'category', name: '评分区间',
      nameTextStyle: { fontSize: 11, color: token.colorTextTertiary },
      data: yLabels,
      splitArea: { show: true }, axisLabel: { fontSize: 9, color: token.colorTextTertiary },
    },
    visualMap: {
      min: 0, max: heatmapMax, calculable: true,
      orient: 'horizontal', left: 'center', bottom: 5,
      inRange: { color: ['#f5f5f5', '#bae7ff', '#69c0ff', '#1890ff', '#003a8c'] },
      textStyle: { fontSize: 10, color: token.colorTextTertiary },
      formatter: (v: number) => `${v}件`,
    },
    series: [{
      type: 'heatmap',
      data: (() => {
        const data: Array<[number, number, number]> = []
        dist.buckets.forEach((row, si) => row.forEach((bucket, pi) => data.push([pi, si, bucket.count])))
        return data
      })(),
      label: {
        show: true,
        formatter: (p: { value: number }) => p.value > 0 ? String(p.value) : '',
        fontSize: 9,
        color: token.colorText,
      },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0, 0, 0, 0.4)' } },
    }],
  } : null

  return (
    <Card
      title="评估分布热力图"
      extra={
        <Segmented
          size="small"
          options={RANGE_OPTIONS}
          value={distRange}
          // S4325: 用 Number() 转换替代 as 断言
          onChange={(v) => onRangeChange(Number(v))}
        />
      }
      style={{ marginBottom: 16 }}
    >
      <Spin spinning={distLoading}>
        {heatmapOption ? (
          <>
            <ReactECharts option={heatmapOption} style={{ height: 300 }} />
            <div style={{
              marginTop: 8, padding: '8px 12px', background: 'var(--xh-bg-spotlight)',
              borderRadius: 4, fontSize: 12, color: 'var(--xh-text-secondary)', lineHeight: 1.8,
            }}>
              <b>图表说明：</b>热力图展示商品在「价格区间 × 评分区间」中的分布密度。
              颜色越深表示该区间内商品越多。
              右上角（高评分 + 高价）为理想区域，左下角（低评分 + 低价）需谨慎。
              悬停单元格可查看具体数量和通过/驳回明细。
            </div>
          </>
        ) : (
          <Empty description="暂无分布数据" />
        )}
      </Spin>
    </Card>
  )
}
