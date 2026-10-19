import { useMemo } from 'react'
import { Modal, Empty, Segmented } from 'antd'
import { ExpandOutlined } from '@ant-design/icons'
import ReactECharts from '../../../components/charts/EChart'
import { TipButton } from '@/components/TipButton'
import FetchFailedHint from '@/components/FetchFailedHint'
import type { TrendSeries } from '../../../api'

interface TrendModalProps {
  // 标记 readonly 以表达「父级传入后子组件不应修改」的契约（SonarQube S6759）
  readonly trendOpen: boolean
  readonly trendMetric: string
  readonly trendRange: number
  readonly trendData: TrendSeries | null
  readonly onClose: () => void
  readonly onRangeChange: (range: number) => void
  readonly onMetricChange: (metric: string) => void
  readonly error?: boolean
  readonly onRetry?: () => void
}

// 可切换的趋势指标：与后端 /api/stats/trend 的 metric 分发一一对应
// （trend.py 的 _ORDER_STATUS_METRICS + events/orders/eval_score/success_rate）
export const TREND_METRICS: Array<{ key: string; label: string }> = [
  { key: 'events', label: '事件密度' },
  { key: 'orders', label: '订单量' },
  { key: 'orders_pending', label: '待支付订单' },
  { key: 'orders_succeeded', label: '成功订单' },
  { key: 'orders_failed', label: '失败订单' },
  { key: 'eval_score', label: '评估分' },
  { key: 'success_rate', label: '成功率' },
]

export function trendMetricLabel(metric: string): string {
  return TREND_METRICS.find(m => m.key === metric)?.label ?? metric
}

export default function TrendModal({
  trendOpen, trendMetric, trendRange, trendData, onClose, onRangeChange, onMetricChange,
  error, onRetry,
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
          const v = (() => {
            // 不同指标有不同的展示格式
            if (trendMetric === 'success_rate') return s.value.toFixed(1) + '%'
            if (trendMetric === 'eval_score') return s.value.toFixed(1)
            return Math.round(s.value).toString()
          })()
          // 计数类指标 value 就是条数，再补一句「N 条」是重复信息（后端已改为桶内求和）
          const isCountMetric = trendMetric !== 'eval_score' && trendMetric !== 'success_rate'
          return `${s.ts}<br/>值: <b>${v}</b>${isCountMetric ? '' : (s.count ? ' · ' + s.count + ' 条' : '')}`
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
          formatter: (v: number) => {
            if (trendMetric === 'success_rate') return v + '%'
            if (v >= 1000) return (v / 1000).toFixed(1) + 'k'
            return v.toString()
          },
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
          {trendMetricLabel(trendMetric)}趋势
        </span>
      }
      open={trendOpen} onCancel={onClose} footer={null} width={900}
      styles={{ body: { padding: '12px 24px' } }}>
      <div style={{ marginBottom: 12 }}>
        {/* 指标切换：原父级把 trendMetric 写死为 events，Modal 只能看一种指标；
            与下方时间范围分成两行，避免 7 个指标 + 3 个范围挤在一行折行 */}
        <Segmented
          size="small"
          options={TREND_METRICS.map(m => ({ label: m.label, value: m.key }))}
          value={trendMetric}
          onChange={(v) => onMetricChange(v as string)}
        />
      </div>
      <div style={{ marginBottom: 12, display: 'flex', gap: 8 }}>
        {[168, 720, 2160].map(h => (
          <TipButton key={h} size="small" type={trendRange === h ? 'primary' : 'default'} onClick={() => onRangeChange(h)} tip={h === 168 ? '查看近 7 天趋势' : h === 720 ? '查看近 30 天趋势' : '查看近 90 天趋势'}>
            {(() => {
              // 时间范围文案
              if (h === 168) return '7 天'
              if (h === 720) return '30 天'
              return '90 天'
            })()}
          </TipButton>
        ))}
      </div>
      {error && <FetchFailedHint source="趋势数据" onRetry={onRetry} />}
      {trendOption ? (
        <>
          <ReactECharts option={trendOption} style={{ height: 320 }} />
          {trendData?.summary && (
            <div style={{ display: 'flex', gap: 24, marginTop: 8, fontSize: 12, color: 'var(--xh-text-tertiary)' }}>
              <span>最低 <b style={{ color: 'var(--xh-text-primary)' }}>{trendMetric === 'success_rate' ? trendData.summary.min.toFixed(1) + '%' : Math.round(trendData.summary.min)}</b></span>
              <span>最高 <b style={{ color: 'var(--xh-text-primary)' }}>{trendMetric === 'success_rate' ? trendData.summary.max.toFixed(1) + '%' : Math.round(trendData.summary.max)}</b></span>
              <span>均值 <b style={{ color: 'var(--xh-text-primary)' }}>{trendMetric === 'success_rate' ? trendData.summary.avg.toFixed(1) + '%' : Math.round(trendData.summary.avg)}</b></span>
              <span>当前 <b style={{ color: '#FF6200' }}>{trendMetric === 'success_rate' ? trendData.summary.current.toFixed(1) + '%' : Math.round(trendData.summary.current)}</b></span>
            </div>
          )}
        </>
      ) : error ? null : (
        <Empty description="暂无趋势数据" />
      )}
    </Modal>
  )
}
