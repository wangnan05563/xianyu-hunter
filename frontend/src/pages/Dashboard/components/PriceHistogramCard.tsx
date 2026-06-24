import { useMemo } from 'react'
import { Card, Select, Empty, Button, Tag, Spin, Alert, theme } from 'antd'
import { RobotOutlined } from '@ant-design/icons'
import ReactECharts from '../../../components/charts/EChart'
import type { HistogramData } from '../../../api'

interface PriceHistogramCardProps {
  histogram: HistogramData | null
  histoTaskId: string
  histoTasks: Array<{ id: string; name: string; keyword: string }>
  aiAnalysis: string | null
  aiLoading: boolean
  onHistoTaskChange: (taskId: string) => void
  onAiAnalyze: () => void
  onClearAiAnalysis: () => void
  onNavigate: (path: string) => void
}

export default function PriceHistogramCard({
  histogram, histoTaskId, histoTasks, aiAnalysis, aiLoading,
  onHistoTaskChange, onAiAnalyze, onClearAiAnalysis, onNavigate,
}: PriceHistogramCardProps) {
  // 在 ConfigProvider 内部读取 token，让 ECharts 跟随主题
  const { token } = theme.useToken()
  // 价格直方图（增强版：时间对比基线 + 分位数标线）
  const histogramOption = useMemo(() => {
    if (!histogram?.bins?.length) return null
    const bins = histogram.bins
    const compare = histogram.summary.compare
    // 标线标签交替使用 start/end 位置，避免数值接近时重叠
    const markLines: Array<{ xAxis?: number; name?: string; label: { formatter: string; color: string; position: string; distance: number; fontSize: number }; lineStyle: { color: string; type: string } }> = []
    // P25 标线（底部）— 使用 token 的 warning 色（深色主题下会自动变亮）
    if (histogram.summary.p25) markLines.push({ xAxis: histogram.summary.p25, name: 'P25', label: { formatter: 'P25 ¥{c}', color: token.colorWarning, position: 'start', distance: 6, fontSize: 10 }, lineStyle: { color: token.colorWarning, type: 'dashed' } })
    // P50 标线（顶部）— 使用 token 的 info 色
    if (histogram.summary.median) markLines.push({ xAxis: histogram.summary.median, name: 'P50', label: { formatter: 'P50 ¥{c}', color: token.colorInfo, position: 'end', distance: 6, fontSize: 10 }, lineStyle: { color: token.colorInfo, type: 'dashed' } })
    // P75 标线（底部）— 使用 token 的 error 色
    if (histogram.summary.p75) markLines.push({ xAxis: histogram.summary.p75, name: 'P75', label: { formatter: 'P75 ¥{c}', color: token.colorError, position: 'start', distance: 20, fontSize: 10 }, lineStyle: { color: token.colorError, type: 'dashed' } })
    // 时间对比基线（7日均价 - 顶部）— 使用 token 的 primary 色
    if (compare.last7d > 0) markLines.push({ xAxis: compare.last7d, name: '7日均价', label: { formatter: '7日 ¥{c}', color: token.colorPrimary, position: 'end', distance: 20, fontSize: 10 }, lineStyle: { color: token.colorPrimary, type: 'dashed' } })
    // 今日均价（底部）— 使用 token 的 error 色（实线）
    if (compare.yesterday > 0) markLines.push({ xAxis: compare.yesterday, name: '今日均价', label: { formatter: '今日 ¥{c}', color: token.colorError, position: 'start', distance: 34, fontSize: 10 }, lineStyle: { color: token.colorError, type: 'solid' } })

    return {
      tooltip: {
        trigger: 'axis',
        formatter: (p: Array<{ dataIndex: number }>) => {
          const i = p[0].dataIndex
          const b = bins[i]
          const mid = ((b.min ?? 0) + (b.max ?? b.min ?? 0)) / 2
          let html = `价格区间: ¥${(b.min ?? 0).toFixed(0)} - ¥${b.max != null ? b.max.toFixed(0) : '+'}<br/>商品数: <b>${b.count}</b>`
          if (compare.last7d > 0) {
            const diff = ((mid - compare.last7d) / compare.last7d * 100)
            const sign = diff > 0 ? '+' : ''
            // 涨跌色使用 token 的语义色，自动适配主题
            const diffColor = diff > 5 ? token.colorError : diff < -5 ? token.colorSuccess : token.colorTextTertiary
            html += `<br/>vs 7日均价: <span style="color:${diffColor}">${sign}${diff.toFixed(1)}%</span>`
          }
          return html
        },
        backgroundColor: token.colorBgElevated,
        borderColor: token.colorBorderSecondary,
        textStyle: { color: token.colorText },
      },
      xAxis: {
        type: 'value',
        name: '价格 (¥)',
        nameTextStyle: { color: token.colorTextTertiary },
        axisLabel: { color: token.colorTextTertiary, formatter: (v: number) => v >= 1000 ? (v / 1000).toFixed(v % 1000 === 0 ? 0 : 1) + 'k' : v },
        splitLine: { show: false },
        // 两侧留白，确保边界 markLine 标签不被截断
        boundaryGap: ['3%', '3%'],
      },
      yAxis: {
        type: 'value',
        name: '商品数',
        nameTextStyle: { color: token.colorTextTertiary },
        axisLabel: { color: token.colorTextTertiary },
        splitLine: { lineStyle: { color: token.colorBorderSecondary } },
      },
      series: [{
        type: 'bar',
        data: bins.map(b => [((b.min ?? 0) + (b.max ?? b.min ?? 0)) / 2, b.count]),
        // 高于均价柱子用主色，低于均价的用浅色（浅色主题下用橙色调和）
        itemStyle: {
          color: (p: { dataIndex: number }) => {
            const b = bins[p.dataIndex]
            const mid = ((b.min ?? 0) + (b.max ?? b.min ?? 0)) / 2
            return mid >= (histogram.summary.mean || 0) ? token.colorPrimary : token.colorPrimaryBg
          },
          borderRadius: [4, 4, 0, 0],
        },
        barWidth: '80%',
        markLine: markLines.length > 0 ? { symbol: 'none', data: markLines, animation: false } : undefined,
      }],
      // 右侧留出足够空间显示 markLine 标签，避免被截断
      grid: { left: 50, right: 60, bottom: 45, top: 45 },
    }
  }, [histogram, token])

  return (
    <Card style={{ marginTop: 16 }}
      title="价格分布直方图"
      extra={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Select
            size="small" value={histoTaskId} style={{ width: 200 }}
            onChange={onHistoTaskChange}
            options={[{ value: 'all', label: '全部任务' }, ...histoTasks.map(t => ({ value: t.id, label: `${t.name || t.keyword || t.id}`.slice(0, 30) }))]}
          />
          {histogram && (
            <span style={{ fontSize: 11, color: 'var(--xh-text-tertiary)' }}>
              均价 ¥{histogram.summary.mean} · 中位 ¥{histogram.summary.median} · {histogram.summary.count} 件
              {histogram.summary.compare.diff_pct !== 0 && (
                <span style={{ marginLeft: 6, color: histogram.summary.compare.diff_pct > 0 ? token.colorError : token.colorSuccess }}>
                  较7日 {histogram.summary.compare.diff_pct > 0 ? '+' : ''}{histogram.summary.compare.diff_pct}%
                </span>
              )}
            </span>
          )}
          <Button size="small" onClick={() => onNavigate('/items')}>查看商品</Button>
        </div>
      }>
      {histogramOption ? (
        <ReactECharts option={histogramOption} style={{ height: 340 }} notMerge={true} lazyUpdate={true} />
      ) : (
        <Empty description="暂无价格数据" />
      )}

      {/* 统计摘要 + AI 分析 */}
      {histogram && histogram.summary.count > 0 && (
        <div style={{ marginTop: 16 }}>
          {/* 快速统计指标 */}
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 12, padding: '8px 12px', background: 'var(--xh-bg-spotlight)', borderRadius: 6 }}>
            <span style={{ fontSize: 12, color: 'var(--xh-text-secondary)' }}>
              <Tag color="blue">P25</Tag> ¥{histogram.summary.p25}
            </span>
            <span style={{ fontSize: 12, color: 'var(--xh-text-secondary)' }}>
              <Tag color="green">中位数</Tag> ¥{histogram.summary.median}
            </span>
            <span style={{ fontSize: 12, color: 'var(--xh-text-secondary)' }}>
              <Tag color="orange">P75</Tag> ¥{histogram.summary.p75}
            </span>
            <span style={{ fontSize: 12, color: 'var(--xh-text-secondary)' }}>
              <Tag color="purple">IQR</Tag> ¥{histogram.summary.p25} ~ ¥{histogram.summary.p75}
              <span style={{ color: 'var(--xh-text-tertiary)', marginLeft: 4 }}>
                ({histogram.summary.p75 - histogram.summary.p25 > 0
                  ? `${((histogram.summary.p75 - histogram.summary.p25) / histogram.summary.median * 100).toFixed(0)}% 离散度`
                  : '低离散'})
              </span>
            </span>
            {histogram.summary.compare.last7d > 0 && (
              <span style={{ fontSize: 12, color: 'var(--xh-text-secondary)' }}>
                <Tag color={histogram.summary.compare.diff_pct > 5 ? 'red' : histogram.summary.compare.diff_pct < -5 ? 'green' : 'default'}>
                  较7日
                </Tag>
                {histogram.summary.compare.diff_pct > 0 ? '+' : ''}{histogram.summary.compare.diff_pct}%
              </span>
            )}
          </div>

          {/* AI 分析按钮 + 结果 */}
          <div style={{ borderTop: '1px solid #f0f0f0', paddingTop: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: aiAnalysis ? 12 : 0 }}>
              <Button
                type="primary"
                ghost
                icon={<RobotOutlined />}
                loading={aiLoading}
                onClick={onAiAnalyze}
                size="small"
              >
                AI 智能分析
              </Button>
              {aiAnalysis && (
                <Button type="link" size="small" onClick={onClearAiAnalysis}>清除</Button>
              )}
              <span style={{ fontSize: 11, color: 'var(--xh-text-quaternary)' }}>基于价格分布数据，AI 生成参考建议</span>
            </div>
            {aiLoading && (
              <div style={{ padding: '12px 16px', background: token.colorWarningBg, borderRadius: 6, fontSize: 13, color: token.colorWarning }}>
                <Spin size="small" /> AI 正在分析价格数据…
              </div>
            )}
            {aiAnalysis && !aiLoading && (
              <Alert
                type={aiAnalysis.includes('未配置') || aiAnalysis.includes('失败') || aiAnalysis.includes('错误') ? 'warning' : 'success'}
                message="AI 价格分析"
                showIcon
                icon={<RobotOutlined />}
                description={
                  <div style={{ whiteSpace: 'pre-wrap', fontSize: 13, lineHeight: 1.8 }}>
                    {aiAnalysis}
                  </div>
                }
              />
            )}
          </div>
        </div>
      )}
    </Card>
  )
}
