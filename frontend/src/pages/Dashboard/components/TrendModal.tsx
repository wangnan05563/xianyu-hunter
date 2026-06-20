import { useMemo } from 'react'
import { Modal, Button, Empty } from 'antd'
import { ExpandOutlined } from '@ant-design/icons'
import ReactECharts from '../../../components/charts/EChart'
import type { TrendSeries } from '../../../api'

interface TrendModalProps {
  trendOpen: boolean
  trendMetric: string
  trendRange: number
  trendData: TrendSeries | null
  onClose: () => void
  onRangeChange: (range: number) => void
}

export default function TrendModal({
  trendOpen, trendMetric, trendRange, trendData, onClose, onRangeChange,
}: TrendModalProps) {
  // 趋势大图 ECharts 配置
  const trendOption = useMemo(() => {
    if (!trendData?.series?.length) return null
    const series = trendData.series
    const markLines: Array<{ yAxis?: number; name?: string; label: { formatter: string }; lineStyle: { color: string; type: string } }> = []
    // 参考线：评估分中位数 / 成功率 50% 告警
    if (trendMetric === 'eval_score') {
      const vals = series.map(s => s.value).filter(v => v > 0)
      if (vals.length) {
        const sorted = [...vals].sort((a, b) => a - b)
        const median = sorted[Math.floor(sorted.length / 2)]
        markLines.push({ yAxis: median, name: '中位', label: { formatter: `中位 ${median.toFixed(1)}` }, lineStyle: { color: '#1677ff', type: 'dashed' } })
      }
    }
    if (trendMetric === 'success_rate') {
      markLines.push({ yAxis: 50, name: '告警', label: { formatter: '告警 50%' }, lineStyle: { color: '#ff4d4f', type: 'dashed' } })
    }
    return {
      tooltip: {
        trigger: 'axis',
        formatter: (p: Array<{ dataIndex: number }>) => {
          const i = p[0].dataIndex
          const s = series[i]
          const v = trendMetric === 'success_rate' ? s.value.toFixed(1) + '%' : trendMetric === 'eval_score' ? s.value.toFixed(1) : Math.round(s.value).toString()
          return `${s.ts}<br/>值: <b>${v}</b>${s.count ? ' · ' + s.count + ' 条' : ''}`
        },
      },
      xAxis: {
        type: 'category',
        data: series.map(s => {
          const parts = s.ts.split('T')
          // 长周期显示月-日，短周期显示时:分
          return trendRange >= 720 ? (parts[0] || '').slice(5) : (parts[1] || '').slice(0, 5)
        }),
        axisLabel: { color: '#8c8c8c', fontSize: 10, interval: Math.max(0, Math.floor(series.length / 8) - 1) },
      },
      yAxis: {
        type: 'value',
        axisLabel: {
          color: '#8c8c8c',
          formatter: (v: number) => trendMetric === 'success_rate' ? v + '%' : v >= 1000 ? (v / 1000).toFixed(1) + 'k' : v.toString(),
        },
        splitLine: { lineStyle: { color: '#f5f5f5' } },
      },
      series: [{
        type: 'line',
        data: series.map(s => s.value),
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#FF6200', width: 2 },
        areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [{ offset: 0, color: '#FF620030' }, { offset: 1, color: '#FF620005' }] } },
        markLine: markLines.length > 0 ? { symbol: 'none', data: markLines } : undefined,
      }],
      grid: { left: 55, right: 20, bottom: 40, top: 30 },
    }
  }, [trendData, trendMetric, trendRange])

  return (
    <Modal
      title={
        <span>
          <ExpandOutlined style={{ marginRight: 8 }} />
          {trendMetric === 'events' ? '事件密度趋势' : trendMetric === 'orders' ? '订单量趋势' : trendMetric === 'eval_score' ? '评估分趋势' : '成功率趋势'}
        </span>
      }
      open={trendOpen} onCancel={onClose} footer={null} width={900}
      bodyStyle={{ padding: '12px 24px' }}>
      <div style={{ marginBottom: 12, display: 'flex', gap: 8 }}>
        {[168, 720, 2160].map(h => (
          <Button key={h} size="small" type={trendRange === h ? 'primary' : 'default'} onClick={() => onRangeChange(h)}>
            {h === 168 ? '7 天' : h === 720 ? '30 天' : '90 天'}
          </Button>
        ))}
      </div>
      {trendOption ? (
        <>
          <ReactECharts option={trendOption} style={{ height: 320 }} />
          {trendData?.summary && (
            <div style={{ display: 'flex', gap: 24, marginTop: 8, fontSize: 12, color: '#8c8c8c' }}>
              <span>最低 <b style={{ color: '#262626' }}>{trendMetric === 'success_rate' ? trendData.summary.min.toFixed(1) + '%' : Math.round(trendData.summary.min)}</b></span>
              <span>最高 <b style={{ color: '#262626' }}>{trendMetric === 'success_rate' ? trendData.summary.max.toFixed(1) + '%' : Math.round(trendData.summary.max)}</b></span>
              <span>均值 <b style={{ color: '#262626' }}>{trendMetric === 'success_rate' ? trendData.summary.avg.toFixed(1) + '%' : Math.round(trendData.summary.avg)}</b></span>
              <span>当前 <b style={{ color: '#FF6200' }}>{trendMetric === 'success_rate' ? trendData.summary.current.toFixed(1) + '%' : Math.round(trendData.summary.current)}</b></span>
            </div>
          )}
        </>
      ) : (
        <Empty description="暂无趋势数据" />
      )}
    </Modal>
  )
}
