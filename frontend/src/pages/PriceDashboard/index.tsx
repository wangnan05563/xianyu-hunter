import { useEffect, useState, useCallback, useMemo } from 'react'
import {
  Card, Table, Tag, Select, Button, Space, Spin, Empty, Statistic, Row, Col,
  Alert, Tooltip, Typography, theme,
} from 'antd'
import { ReloadOutlined, InfoCircleOutlined } from '@ant-design/icons'
import ReactECharts from '../../components/charts/EChart'
import { priceApi, taskApi } from '../../api'
import type {
  CategoryStat, CategoryComparisonItem, CategoryComparisonSortBy,
} from '../../api'
import type { Task } from '../../api/types'

const { Text } = Typography

// 排序字段下拉项：与后端 _ALLOWED_COMPARISON_SORT 对齐
// 标签使用业务术语而非统计学术语，降低理解门槛
const SORT_OPTIONS: Array<{ value: CategoryComparisonSortBy; label: string }> = [
  { value: 'mean', label: '均价' },
  { value: 'median', label: '中位数' },
  { value: 'min', label: '最低价' },
  { value: 'max', label: '最高价' },
  { value: 'p10', label: 'P10（低端）' },
  { value: 'p25', label: 'P25' },
  { value: 'p75', label: 'P75' },
  { value: 'p90', label: 'P90（高端）' },
  { value: 'count', label: '样本数' },
]

// 时间窗下拉项：覆盖短/中/长期视角
// 0 表示全量；7/30/90 天用于观察短期行情波动
const RANGE_OPTIONS = [
  { value: 0, label: '全部时间' },
  { value: 7, label: '近 7 天' },
  { value: 30, label: '近 30 天' },
  { value: 90, label: '近 90 天' },
]

// 价格格式化：≤1000 直接显示，>1000 用 k 简写
function formatPrice(v: number | null | undefined): string {
  if (v == null) return '—'
  if (!Number.isFinite(v)) return '—'
  if (v < 1000) return `¥${v}`
  return `¥${(v / 1000).toFixed(1)}k`
}

export default function PriceDashboard() {
  const { token } = theme.useToken()

  // ============== 状态 ==============
  // 品类统计（全量，不排序）
  const [stats, setStats] = useState<CategoryStat[]>([])
  const [statsTotal, setStatsTotal] = useState(0)
  const [statsLoading, setStatsLoading] = useState(false)

  // 横向对比（按 sort_by 排序的前 N 项）
  const [comparison, setComparison] = useState<CategoryComparisonItem[]>([])
  const [overallMean, setOverallMean] = useState(0)
  const [compLoading, setCompLoading] = useState(false)
  const [sortBy, setSortBy] = useState<CategoryComparisonSortBy>('mean')
  const [order, setOrder] = useState<'asc' | 'desc'>('desc')
  const [rangeDays, setRangeDays] = useState(0)

  // 捡漏价格参考
  const [soldRange, setSoldRange] = useState<{
    min_price: number | null
    max_price: number | null
    median_price: number | null
    bargain_price: number | null
    sample_size: number
    source: string
    source_label?: string
    message?: string
  } | null>(null)
  const [soldLoading, setSoldLoading] = useState(false)
  const [soldTaskId, setSoldTaskId] = useState<string | undefined>(undefined)
  const [soldRangeDays, setSoldRangeDays] = useState(30)

  // 任务列表（用于捡漏价格参考的品类选择器）
  const [tasks, setTasks] = useState<Task[]>([])

  // ============== 数据加载 ==============
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

  const fetchSoldRange = useCallback(async () => {
    setSoldLoading(true)
    try {
      const data = await priceApi.soldRange({
        task_id: soldTaskId,
        range_days: soldRangeDays,
      })
      setSoldRange(data)
    } catch {
      setSoldRange(null)
    } finally {
      setSoldLoading(false)
    }
  }, [soldTaskId, soldRangeDays])

  // 拉取任务列表，用于捡漏价格参考的品类下拉
  useEffect(() => {
    taskApi.list({ limit: 200 }).then((r) => setTasks(r.items || [])).catch(() => setTasks([]))
  }, [])

  // 首次挂载并行拉取三类数据
  useEffect(() => {
    void fetchStats()
  }, [fetchStats])

  useEffect(() => {
    void fetchComparison()
  }, [fetchComparison])

  useEffect(() => {
    void fetchSoldRange()
  }, [fetchSoldRange])

  // ============== 横向对比图配置 ==============
  // 横向条形图：y 轴品类名，x 轴价格；用 markLine 标注全体均价基线
  const comparisonOption = useMemo(() => {
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

  // ============== 品类统计表列定义 ==============
  const statsColumns = useMemo(() => [
    {
      title: '品类',
      dataIndex: 'name',
      key: 'name',
      width: 180,
      render: (name: string, record: CategoryStat) => (
        <span>{name || record.keyword || '未分类'}</span>
      ),
    },
    { title: '样本数', dataIndex: 'count', key: 'count', width: 80, sorter: (a: CategoryStat, b: CategoryStat) => a.count - b.count, render: (v: number) => <Tag color="blue">{v}</Tag> },
    { title: '最低价', dataIndex: 'min', key: 'min', width: 90, sorter: (a: CategoryStat, b: CategoryStat) => a.min - b.min, render: (v: number) => formatPrice(v) },
    { title: '最高价', dataIndex: 'max', key: 'max', width: 90, sorter: (a: CategoryStat, b: CategoryStat) => a.max - b.max, render: (v: number) => formatPrice(v) },
    { title: '均价', dataIndex: 'mean', key: 'mean', width: 90, sorter: (a: CategoryStat, b: CategoryStat) => a.mean - b.mean, render: (v: number) => formatPrice(v) },
    { title: '中位数', dataIndex: 'median', key: 'median', width: 90, sorter: (a: CategoryStat, b: CategoryStat) => a.median - b.median, render: (v: number) => formatPrice(v) },
    { title: 'P25', dataIndex: 'p25', key: 'p25', width: 80, render: (v: number) => formatPrice(v) },
    { title: 'P75', dataIndex: 'p75', key: 'p75', width: 80, render: (v: number) => formatPrice(v) },
    { title: 'P10', dataIndex: 'p10', key: 'p10', width: 80, render: (v: number) => formatPrice(v) },
    { title: 'P90', dataIndex: 'p90', key: 'p90', width: 80, render: (v: number) => formatPrice(v) },
  ], [])

  // ============== 渲染 ==============
  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* 页面顶部说明 */}
      <Alert
        type="info"
        showIcon
        icon={<InfoCircleOutlined />}
        message="价格行情看板"
        description="按品类聚合的商品价格统计与横向对比。捡漏价格参考基于近期已售商品，低于该价格可视为捡漏机会。"
        style={{ marginBottom: 0 }}
      />

      {/* 模块 A：品类横向对比图 */}
      <Card
        title="品类横向对比"
        extra={
          <Space wrap>
            <Select
              size="small" value={sortBy} style={{ width: 140 }}
              onChange={(v) => setSortBy(v)}
              options={SORT_OPTIONS}
            />
            <Select
              size="small" value={order} style={{ width: 90 }}
              onChange={(v) => setOrder(v)}
              options={[{ value: 'desc', label: '降序' }, { value: 'asc', label: '升序' }]}
            />
            <Select
              size="small" value={rangeDays} style={{ width: 110 }}
              onChange={(v) => setRangeDays(v)}
              options={RANGE_OPTIONS}
            />
            <Tooltip title="刷新">
              <Button size="small" icon={<ReloadOutlined />} onClick={fetchComparison} loading={compLoading} />
            </Tooltip>
          </Space>
        }
      >
        {compLoading ? (
          <div style={{ textAlign: 'center', padding: 60 }}><Spin /></div>
        ) : comparisonOption ? (
          <>
            <ReactECharts option={comparisonOption} style={{ height: 420 }} notMerge={true} lazyUpdate={true} />
            <div style={{ marginTop: 8, fontSize: 12, color: token.colorTextTertiary }}>
              <span>全体均价：<b style={{ color: token.colorText }}>{formatPrice(overallMean)}</b></span>
              <span style={{ marginLeft: 16 }}>红色：高于均价 5% 以上</span>
              <span style={{ marginLeft: 12 }}>绿色：低于均价 5% 以上</span>
              <span style={{ marginLeft: 12 }}>蓝色：接近均价</span>
            </div>
          </>
        ) : (
          <Empty description="暂无对比数据" />
        )}
      </Card>

      {/* 模块 B：捡漏价格参考 */}
      <Card
        title="捡漏价格参考"
        extra={
          <Space wrap>
            <Select
              size="small" value={soldTaskId} style={{ width: 200 }}
              placeholder="选择品类"
              allowClear
              onChange={(v) => setSoldTaskId(v)}
              options={tasks.map((t) => ({ value: t.id, label: (t.name || t.keyword || t.id).slice(0, 30) }))}
            />
            <Select
              size="small" value={soldRangeDays} style={{ width: 110 }}
              onChange={(v) => setSoldRangeDays(v)}
              options={RANGE_OPTIONS.filter((o) => o.value !== 0)}
            />
            <Tooltip title="刷新">
              <Button size="small" icon={<ReloadOutlined />} onClick={fetchSoldRange} loading={soldLoading} />
            </Tooltip>
          </Space>
        }
      >
        {soldLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
        ) : soldRange && soldRange.sample_size > 0 ? (
          <>
            <Row gutter={16}>
              <Col xs={12} sm={6}>
                <Statistic
                  title="捡漏价格"
                  value={soldRange.bargain_price ?? 0}
                  precision={2}
                  prefix="¥"
                  valueStyle={{ color: token.colorSuccess }}
                />
                <Text type="secondary" style={{ fontSize: 11 }}>低于此价可捡漏</Text>
              </Col>
              <Col xs={12} sm={6}>
                <Statistic title="最低价" value={soldRange.min_price ?? 0} precision={2} prefix="¥" />
              </Col>
              <Col xs={12} sm={6}>
                <Statistic title="中位数" value={soldRange.median_price ?? 0} precision={2} prefix="¥" />
              </Col>
              <Col xs={12} sm={6}>
                <Statistic title="最高价" value={soldRange.max_price ?? 0} precision={2} prefix="¥" />
              </Col>
            </Row>
            <div style={{ marginTop: 12, display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 12 }}>
              <span><Text type="secondary">样本数：</Text><Tag color="blue">{soldRange.sample_size}</Tag></span>
              {soldRange.source_label && (
                <span><Text type="secondary">数据来源：</Text><Tag color="purple">{soldRange.source_label}</Tag></span>
              )}
            </div>
          </>
        ) : (
          <Empty description={soldRange?.message || '暂无已售价格数据，建议先执行实时搜索采集更多商品'} />
        )}
      </Card>

      {/* 模块 C：品类统计明细表 */}
      <Card
        title="品类统计明细"
        extra={
          <Space>
            <span style={{ fontSize: 12, color: token.colorTextTertiary }}>
              共 {statsTotal} 件商品 · {stats.length} 个品类
            </span>
            <Tooltip title="刷新">
              <Button size="small" icon={<ReloadOutlined />} onClick={fetchStats} loading={statsLoading} />
            </Tooltip>
          </Space>
        }
      >
        <Table<CategoryStat>
          rowKey={(r) => r.task_id || '__orphan__'}
          columns={statsColumns}
          dataSource={stats}
          loading={statsLoading}
          size="small"
          pagination={{ pageSize: 10, showSizeChanger: false, showTotal: (t) => `共 ${t} 个品类` }}
          scroll={{ x: 960 }}
          locale={{ emptyText: <Empty description="暂无统计数据" /> }}
        />
      </Card>
    </div>
  )
}
