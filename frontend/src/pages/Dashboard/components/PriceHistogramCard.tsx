import { useMemo } from 'react'
import { Card, Select, Empty, Button, Tag, Spin, Alert } from 'antd'
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
  // 价格直方图（增强版：时间对比基线 + 分位数标线）
  const histogramOption = useMemo(() => {
    if (!histogram?.bins?.length) return null
    const bins = histogram.bins
    const compare = histogram.summary.compare
    // 标线标签交替使用 start/end 位置，避免数值接近时重叠
    const markLines: Array<{ xAxis?: number; name?: string; label: { formatter: string; color: string; position: string; distance: number; fontSize: number }; lineStyle: { color: string; type: string } }> = []
    // P25 标线（底部）
    if (histogram.summary.p25) markLines.push({ xAxis: histogram.summary.p25, name: 'P25', label: { formatter: 'P25 ¥{c}', color: '#faad14', position: 'start', distance: 6, fontSize: 10 }, lineStyle: { color: '#faad14', type: 'dashed' } })
    // P50 标线（顶部）
    if (histogram.summary.median) markLines.push({ xAxis: histogram.summary.median, name: 'P50', label: { formatter: 'P50 ¥{c}', color: '#1677ff', position: 'end', distance: 6, fontSize: 10 }, lineStyle: { color: '#1677ff', type: 'dashed' } })
    // P75 标线（底部）
    if (histogram.summary.p75) markLines.push({ xAxis: histogram.summary.p75, name: 'P75', label: { formatter: 'P75 ¥{c}', color: '#ff4d4f', position: 'start', distance: 20, fontSize: 10 }, lineStyle: { color: '#ff4d4f', type: 'dashed' } })
    // 时间对比基线（7日均价 - 顶部）
    if (compare.last7d > 0) markLines.push({ xAxis: compare.last7d, name: '7日均价', label: { formatter: '7日 ¥{c}', color: '#fa8c16', position: 'end', distance: 20, fontSize: 10 }, lineStyle: { color: '#fa8c16', type: 'dashed' } })
    // 今日均价（底部）
    if (compare.yesterday > 0) markLines.push({ xAxis: compare.yesterday, name: '今日均价', label: { formatter: '今日 ¥{c}', color: '#ff4d4f', position: 'start', distance: 34, fontSize: 10 }, lineStyle: { color: '#ff4d4f', type: 'solid' } })

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
            html += `<br/>vs 7日均价: <span style="color:${diff > 5 ? '#ff4d4f' : diff < -5 ? '#52c41a' : '#8c8c8c'}">${sign}${diff.toFixed(1)}%</span>`
          }
          return html
        },
        backgroundColor: 'rgba(255, 255, 255, 0.96)',
        borderColor: '#f0f0f0',
        textStyle: { color: '#262626' },
      },
      xAxis: {
        type: 'value',
        name: '价格 (¥)',
        nameTextStyle: { color: '#8c8c8c' },
        axisLabel: { color: '#8c8c8c', formatter: (v: number) => v >= 1000 ? (v / 1000).toFixed(v % 1000 === 0 ? 0 : 1) + 'k' : v },
        splitLine: { show: false },
        // 两侧留白，确保边界 markLine 标签不被截断
        boundaryGap: ['3%', '3%'],
      },
      yAxis: {
        type: 'value',
        name: '商品数',
        nameTextStyle: { color: '#8c8c8c' },
        axisLabel: { color: '#8c8c8c' },
        splitLine: { lineStyle: { color: '#f5f5f5' } },
      },
      series: [{
        type: 'bar',
        data: bins.map(b => [((b.min ?? 0) + (b.max ?? b.min ?? 0)) / 2, b.count]),
        // 高于均价柱子用主色，低于均价的用浅色
        itemStyle: {
          color: (p: { dataIndex: number }) => {
            const b = bins[p.dataIndex]
            const mid = ((b.min ?? 0) + (b.max ?? b.min ?? 0)) / 2
            return mid >= (histogram.summary.mean || 0) ? '#FF6200' : '#FFB380'
          },
          borderRadius: [4, 4, 0, 0],
        },
        barWidth: '80%',
        markLine: markLines.length > 0 ? { symbol: 'none', data: markLines, animation: false } : undefined,
      }],
      // 右侧留出足够空间显示 markLine 标签，避免被截断
      grid: { left: 50, right: 60, bottom: 45, top: 45 },
    }
  }, [histogram])

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
            <span style={{ fontSize: 11, color: '#8c8c8c' }}>
              均价 ¥{histogram.summary.mean} · 中位 ¥{histogram.summary.median} · {histogram.summary.count} 件
              {histogram.summary.compare.diff_pct !== 0 && (
                <span style={{ marginLeft: 6, color: histogram.summary.compare.diff_pct > 0 ? '#ff4d4f' : '#52c41a' }}>
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
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 12, padding: '8px 12px', background: '#fafafa', borderRadius: 6 }}>
            <span style={{ fontSize: 12, color: '#595959' }}>
              <Tag color="blue">P25</Tag> ¥{histogram.summary.p25}
            </span>
            <span style={{ fontSize: 12, color: '#595959' }}>
              <Tag color="green">中位数</Tag> ¥{histogram.summary.median}
            </span>
            <span style={{ fontSize: 12, color: '#595959' }}>
              <Tag color="orange">P75</Tag> ¥{histogram.summary.p75}
            </span>
            <span style={{ fontSize: 12, color: '#595959' }}>
              <Tag color="purple">IQR</Tag> ¥{histogram.summary.p25} ~ ¥{histogram.summary.p75}
              <span style={{ color: '#8c8c8c', marginLeft: 4 }}>
                ({histogram.summary.p75 - histogram.summary.p25 > 0
                  ? `${((histogram.summary.p75 - histogram.summary.p25) / histogram.summary.median * 100).toFixed(0)}% 离散度`
                  : '低离散'})
              </span>
            </span>
            {histogram.summary.compare.last7d > 0 && (
              <span style={{ fontSize: 12, color: '#595959' }}>
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
              <span style={{ fontSize: 11, color: '#bfbfbf' }}>基于价格分布数据，AI 生成参考建议</span>
            </div>
            {aiLoading && (
              <div style={{ padding: '12px 16px', background: '#fff7e6', borderRadius: 6, fontSize: 13, color: '#d48806' }}>
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
