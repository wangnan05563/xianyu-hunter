import { useEffect, useState, useCallback } from 'react'
import {
  Card, Table, Tag, Button, Space, Spin, Input, Slider, Row, Col, message,
  Empty, Tooltip, DatePicker, Modal, Collapse, Badge, Statistic, Segmented, Image,
} from 'antd'
import {
  ReloadOutlined, AimOutlined, RobotOutlined, LinkOutlined,
  LineChartOutlined, SearchOutlined, UndoOutlined, RetweetOutlined,
} from '@ant-design/icons'
import ReactECharts from '../../components/charts/EChart'
import dayjs from 'dayjs'
import { evalApi, aiApi, type EvalItem, type AIConditionResult } from '../../api'
import { RISK_LEVEL_CONFIG } from '../../constants/riskLevels'

const { RangePicker } = DatePicker

const RANGE_OPTIONS = [
  { label: '24h', value: 24 },
  { label: '3天', value: 72 },
  { label: '7天', value: 168 },
  { label: '30天', value: 720 },
]

// 分布 API 返回的完整类型
interface DistResponse {
  buckets: Array<Array<{ count: number; pass: number; auto: number; fail: number }>>
  marginals: {
    price: number[]
    score: number[]
    result: { pass: number; auto: number; fail: number }
  }
  distribution: Array<{ range: string; count: number }>
  suggested_threshold: { score: number; pass_rate: number }
  total: number
  insufficient_count: number
  price_range: [number, number]
  // 后端返回的当前生效阈值，前端据此动态显示分类标签
  thresholds?: { pass_score: number; auto_buy_score: number }
}

// 卖家价格趋势数据
interface SellerTrendData {
  seller_id: string
  items_count: number
  price_points: Array<{ date: string; avg_price: number; min_price: number; max_price: number; count: number }>
  current_avg: number
  trend: 'up' | 'down' | 'stable'
}

// 检测数据不足（score=null / data_quality=insufficient / risk_level=unknown）
function isDataInsufficient(r: EvalItem): boolean {
  return r.payload.score == null || r.payload.risk_level === 'unknown'
}

export default function Evaluations() {
  // === 列表数据 ===
  const [items, setItems] = useState<EvalItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)

  // === 查询条件 ===
  const [itemId, setItemId] = useState<string>('')
  const [taskId, setTaskId] = useState<string>('')
  const [scoreRange, setScoreRange] = useState<[number, number]>([0, 100])
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null)

  // === 分页 ===
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  // === 分布图 ===
  const [dist, setDist] = useState<DistResponse | null>(null)
  const [distRange, setDistRange] = useState(168)
  const [distLoading, setDistLoading] = useState(false)

  // 从分布数据中获取当前生效阈值（后端返回），回退到默认 60/80
  const passScore = dist?.thresholds?.pass_score ?? 60
  const autoBuyScore = dist?.thresholds?.auto_buy_score ?? 80

  // === 阈值建议 ===
  const [thresholdTarget, setThresholdTarget] = useState(70)
  const [suggestion, setSuggestion] = useState<{ suggested_threshold: number; current_pass_rate: number } | null>(null)

  // === AI 评估 ===
  const [aiModalOpen, setAiModalOpen] = useState(false)
  const [aiLoading, setAiLoading] = useState(false)
  const [aiResult, setAiResult] = useState<AIConditionResult | null>(null)
  const [aiItemId, setAiItemId] = useState('')

  // === 卖家趋势（展开行） ===
  const [trendCache, setTrendCache] = useState<Record<string, SellerTrendData>>({})
  const [trendLoading, setTrendLoading] = useState('')

  // === 重新评估 ===
  const [recomputing, setRecomputing] = useState(false)

  // 用当前配置重新计算历史评估
  const onRecompute = async () => {
    setRecomputing(true)
    try {
      const res = await evalApi.recompute(taskId || undefined)
      message.success(res.message)
      // 重新加载数据
      load()
      loadDist()
    } catch {
      message.error('重新评估失败')
    } finally {
      setRecomputing(false)
    }
  }

  // 加载评估列表
  const load = useCallback(() => {
    setLoading(true)
    const params: Record<string, unknown> = {
      page_num: page,
      page_size: pageSize,
      limit: pageSize * 4,
    }
    if (itemId) params.item_id = itemId
    if (taskId) params.task_id = taskId
    if (scoreRange[0] > 0) params.min_score = scoreRange[0]
    if (scoreRange[1] < 100) params.max_score = scoreRange[1]
    if (dateRange && dateRange[0]) params.start_time = dateRange[0].format('YYYY-MM-DD')
    if (dateRange && dateRange[1]) params.end_time = dateRange[1].format('YYYY-MM-DD')

    evalApi.list(params)
      .then((res) => {
        setItems(res.items || [])
        setTotal(res.total || res.count || 0)
      })
      .catch(() => message.error('加载评估列表失败'))
      .finally(() => setLoading(false))
  }, [page, pageSize, itemId, taskId, scoreRange, dateRange])

  // 加载分布数据
  const loadDist = useCallback(() => {
    setDistLoading(true)
    evalApi.distribution({ range_hours: distRange, price_bin_count: 10, score_bin_count: 10 })
      .then((res) => setDist(res as DistResponse))
      .catch(() => {})
      .finally(() => setDistLoading(false))
  }, [distRange])

  useEffect(() => { load() }, [load])
  useEffect(() => { loadDist() }, [loadDist])

  // 查询/重置
  const onSearch = () => { setPage(1); load() }
  const onReset = () => {
    setItemId(''); setTaskId(''); setScoreRange([0, 100]); setDateRange(null); setPage(1)
  }

  // 阈值建议
  const fetchSuggestion = () => {
    evalApi.thresholdSuggestion(thresholdTarget / 100)
      .then((res) => { setSuggestion(res); message.success(`建议阈值: ${res.suggested_threshold}`) })
      .catch(() => message.error('获取阈值建议失败'))
  }

  // AI 成色评估
  const onAIEval = async (itemId: string) => {
    if (!itemId) {
      message.error('商品 ID 为空，无法评估')
      return
    }
    setAiItemId(itemId)
    setAiModalOpen(true)
    setAiLoading(true)
    setAiResult(null)
    try {
      const result = await aiApi.evaluateCondition(itemId)
      setAiResult(result)
    } catch (err: unknown) {
      const error = err as { response?: { status?: number; data?: { detail?: string } } }
      const status = error?.response?.status
      const detail = error?.response?.data?.detail
      if (status === 403) {
        message.error('AI 功能未开启，请在配置页面开启')
      } else if (status === 404) {
        message.error('商品不存在于数据库中')
      } else if (status === 422) {
        message.error('请求参数错误：商品 ID 为空')
      } else {
        message.error(detail || 'AI 评估失败，请检查 AI 配置')
      }
      setAiModalOpen(false)
    } finally {
      setAiLoading(false)
    }
  }

  // 卖家价格趋势
  const loadSellerTrend = async (itemId: string) => {
    if (trendCache[itemId]) return
    setTrendLoading(itemId)
    try {
      const data: SellerTrendData = await evalApi.sellerTrend(itemId)
      setTrendCache((prev) => ({ ...prev, [itemId]: data }))
    } catch {
      message.error('加载卖家趋势失败')
    } finally {
      setTrendLoading('')
    }
  }

  // === 热力图辅助函数：生成价格/评分区间标签 ===
  const buildHeatmapLabels = () => {
    if (!dist) return { xLabels: [], yLabels: [] }
    const pBins = dist.buckets[0]?.length || 10
    const sBins = dist.buckets.length || 10
    const [pMin, pMax] = dist.price_range || [0, 5000]
    const pStep = (pMax - pMin) / pBins
    // X轴：价格等分区间
    const xLabels = Array.from({ length: pBins }, (_, i) => {
      const lo = Math.round(pMin + i * pStep)
      const hi = Math.round(pMin + (i + 1) * pStep)
      return `¥${lo}~${hi}`
    })
    // Y轴：评分区间，从高到低（索引0=顶部=最高分）
    const sStep = 100 / sBins
    const yLabels = Array.from({ length: sBins }, (_, i) => {
      const hi = Math.round(100 - i * sStep)
      const lo = Math.round(100 - (i + 1) * sStep)
      return `${lo}-${hi}分`
    })
    return { xLabels, yLabels }
  }

  // 动态计算热力图最大值，避免颜色全白或全深
  const heatmapMax = (() => {
    if (!dist) return 1
    let maxVal = 1
    dist.buckets.forEach((row) =>
      row.forEach((b) => { if (b.count > maxVal) maxVal = b.count })
    )
    return maxVal
  })()

  const { xLabels, yLabels } = buildHeatmapLabels()

  // === 分布热力图 ===
  const heatmapOption = dist && dist.buckets?.length ? {
    tooltip: {
      position: 'top',
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
      nameTextStyle: { fontSize: 11, color: '#8c8c8c' },
      data: xLabels,
      splitArea: { show: true }, axisLabel: { fontSize: 9, rotate: 30 },
    },
    yAxis: {
      type: 'category', name: '评分区间',
      nameTextStyle: { fontSize: 11, color: '#8c8c8c' },
      data: yLabels,
      splitArea: { show: true }, axisLabel: { fontSize: 9 },
    },
    visualMap: {
      min: 0, max: heatmapMax, calculable: true,
      orient: 'horizontal', left: 'center', bottom: 5,
      inRange: { color: ['#f5f5f5', '#bae7ff', '#69c0ff', '#1890ff', '#003a8c'] },
      textStyle: { fontSize: 10 },
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
      },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0, 0, 0, 0.4)' } },
    }],
  } : null

  // === 结果分布柱状图 ===
  const resultBarOption = dist ? {
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

  // === 5档分数分布直方图 ===
  const histogramOption = dist ? {
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

  // === 卖家趋势 sparkline ===
  const trendSparkline = (data: SellerTrendData) => {
    const points = data.price_points
    if (!points.length) return null
    const prices = points.map((p) => p.avg_price)
    return {
      tooltip: { trigger: 'axis', formatter: (params: Array<{ dataIndex: number; data: number }>) => {
        const p = params[0]
        if (!p) return ''
        const point = points[p.dataIndex]
        return point ? `${point.date}<br/>均价: ¥${point.avg_price}<br/>范围: ¥${point.min_price}~¥${point.max_price}<br/>商品数: ${point.count}` : ''
      }},
      grid: { left: 40, right: 10, top: 10, bottom: 25 },
      xAxis: { type: 'category', data: points.map((p) => p.date), axisLabel: { fontSize: 9 } },
      yAxis: { type: 'value', axisLabel: { fontSize: 9 } },
      series: [{
        type: 'line', data: prices, smooth: true,
        lineStyle: { width: 2, color: '#1890ff' },
        areaStyle: { color: 'rgba(24,144,255,0.15)' },
        symbol: 'circle', symbolSize: 4,
      }],
    }
  }

  // === 表格列定义（与商品列表页对齐） ===
  const columns = [
    {
      title: '图片', key: 'thumb', width: 70,
      render: (_: unknown, r: EvalItem) => {
        const url = r.payload?.thumb_url as string | undefined
        return url ? (
          <Image src={url} referrerPolicy="no-referrer" width={50} height={50}
            style={{ objectFit: 'cover', borderRadius: 6 }} preview={false} />
        ) : '—'
      },
    },
    {
      title: '标题', key: 'title', ellipsis: true,
      render: (_: unknown, r: EvalItem) => {
        const title = r.payload?.item_title || '—'
        const url = `https://www.goofish.com/item?id=${r.item_id}`
        return <a href={url} target="_blank" rel="noopener noreferrer">{title} <LinkOutlined /></a>
      },
    },
    {
      title: '价格', key: 'price', width: 90,
      sorter: (a: EvalItem, b: EvalItem) =>
        (a.payload?.item_price ?? 0) - (b.payload?.item_price ?? 0),
      render: (_: unknown, r: EvalItem) => r.payload?.item_price != null
        ? <span style={{ color: '#f5222d', fontWeight: 600 }}>¥{Number(r.payload.item_price).toFixed(2)}</span>
        : '—',
    },
    {
      title: '卖家', key: 'seller', width: 110, ellipsis: true,
      render: (_: unknown, r: EvalItem) => r.payload?.seller_nick || r.payload?.seller_id || '—',
    },
    {
      title: '地区', key: 'region', width: 80,
      render: (_: unknown, r: EvalItem) => (r.payload?.region as string) || '—',
    },
    {
      title: '想要', key: 'want', width: 60,
      render: (_: unknown, r: EvalItem) => (r.payload?.want_cnt as number) ?? '—',
    },
    {
      title: '发布时间', key: 'publish', width: 150,
      render: (_: unknown, r: EvalItem) => {
        const t = r.payload?.publish_time as string | undefined
        return t ? new Date(t).toLocaleString('zh-CN') : '—'
      },
    },
    {
      title: '评分', key: 'score', width: 80,
      sorter: (a: EvalItem, b: EvalItem) => (a.payload.score ?? 0) - (b.payload.score ?? 0),
      render: (_: unknown, r: EvalItem) => {
        if (isDataInsufficient(r)) {
          return <Tag color="default">数据不足</Tag>
        }
        const s = r.payload.score
        const color = s >= autoBuyScore ? '#52c41a' : s >= passScore ? '#faad14' : '#ff4d4f'
        return <span style={{ color, fontWeight: 600, fontSize: 15 }}>{s.toFixed(1)}</span>
      },
    },
    {
      title: '风险', key: 'risk', width: 70,
      render: (_: unknown, r: EvalItem) => {
        const level = r.payload?.risk_level || 'unknown'
        return <Tag color={RISK_LEVEL_CONFIG[level]?.color || 'default'}>{level}</Tag>
      },
    },
    {
      title: 'AI', key: 'ai', width: 70,
      render: (_: unknown, r: EvalItem) => (
        <Button
          size="small"
          icon={<RobotOutlined />}
          onClick={() => onAIEval(r.item_id)}
          disabled={isDataInsufficient(r) && (r.payload.score ?? 0) < 60}
        />
      ),
    },
  ]

  // 展开行：卖家价格趋势
  const expandedRowRender = (r: EvalItem) => {
    const trend = trendCache[r.item_id]
    const isLoading = trendLoading === r.item_id

    return (
      <div style={{ padding: '8px 0' }}>
        {!trend && !isLoading && (
          <Button size="small" icon={<LineChartOutlined />} onClick={() => loadSellerTrend(r.item_id)}>
            加载卖家价格趋势
          </Button>
        )}
        {isLoading && <Spin size="small" />}
        {trend && (
          <Row gutter={16} align="middle">
            <Col span={6}>
              <Statistic title="卖家" value={trend.seller_id} valueStyle={{ fontSize: 14 }} />
              <div style={{ marginTop: 4 }}>
                <Badge status={
                  trend.trend === 'up' ? 'error' : trend.trend === 'down' ? 'success' : 'default'
                } text={
                  trend.trend === 'up' ? '涨价 ↑' : trend.trend === 'down' ? '降价 ↓' : '稳定 →'
                } />
                <span style={{ marginLeft: 12, fontSize: 12, color: '#999' }}>
                  {trend.items_count} 件商品 / 均价 ¥{trend.current_avg}
                </span>
              </div>
            </Col>
            <Col span={18}>
              {trend.price_points.length > 0 ? (
                <ReactECharts option={trendSparkline(trend)} style={{ height: 120 }} />
              ) : (
                <Empty description="暂无价格趋势数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              )}
            </Col>
          </Row>
        )}
      </div>
    )
  }

  return (
    <div className="page-container">
      <h2 style={{ marginBottom: 16 }}>评估明细</h2>

      {/* 查询条件 */}
      <Card style={{ marginBottom: 16 }}>
        <Space wrap size="middle">
          <span>商品ID：</span>
          <Input
            placeholder="模糊匹配" allowClear style={{ width: 160 }}
            value={itemId} onChange={(e) => setItemId(e.target.value)}
            onPressEnter={onSearch}
          />
          <span>任务ID：</span>
          <Input
            placeholder="模糊匹配" allowClear style={{ width: 160 }}
            value={taskId} onChange={(e) => setTaskId(e.target.value)}
            onPressEnter={onSearch}
          />
          <span>评分范围：</span>
          <Slider
            range style={{ width: 200 }}
            value={scoreRange}
            onChange={(v) => setScoreRange(v as [number, number])}
          />
          <span>时间范围：</span>
          <RangePicker
            value={dateRange as [dayjs.Dayjs, dayjs.Dayjs] | null}
            onChange={(v) => setDateRange(v as [dayjs.Dayjs | null, dayjs.Dayjs | null] | null)}
          />
          <Button type="primary" icon={<SearchOutlined />} onClick={onSearch}>查询</Button>
          <Button icon={<UndoOutlined />} onClick={onReset}>重置</Button>
          <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>刷新</Button>
          <Button icon={<RetweetOutlined />} onClick={onRecompute} loading={recomputing}>重新评估</Button>
        </Space>
      </Card>

      {/* 统计卡片 */}
      {dist && (
        <Row gutter={12} style={{ marginBottom: 16 }}>
          <Col span={4}>
            <Card size="small"><Statistic title="评估总数" value={dist.total} /></Card>
          </Col>
          <Col span={4}>
            <Card size="small"><Statistic title={`可抢(≥${autoBuyScore})`} value={dist.marginals.result.auto} valueStyle={{ color: '#52c41a' }} /></Card>
          </Col>
          <Col span={4}>
            <Card size="small"><Statistic title={`通过(${passScore}-${autoBuyScore - 1})`} value={dist.marginals.result.pass} valueStyle={{ color: '#1890ff' }} /></Card>
          </Col>
          <Col span={4}>
            <Card size="small"><Statistic title={`驳回(<${passScore})`} value={dist.marginals.result.fail} valueStyle={{ color: '#ff4d4f' }} /></Card>
          </Col>
          <Col span={4}>
            <Card size="small"><Statistic title="数据不足" value={dist.insufficient_count} valueStyle={{ color: '#999' }} /></Card>
          </Col>
          <Col span={4}>
            <Card size="small">
              <Statistic title="价格区间" value={dist.price_range[0] > 0 ? `¥${dist.price_range[0]}~${dist.price_range[1]}` : '—'} />
            </Card>
          </Col>
        </Row>
      )}

      <Row gutter={16}>
        {/* 左侧：列表 */}
        <Col span={16}>
          <Card>
            <Spin spinning={loading}>
              {items.length === 0 ? (
                <Empty description="暂无评估数据" />
              ) : (
                <Table
                  columns={columns}
                  dataSource={items}
                  rowKey={(r) => `${r.item_id}-${r.created_at}`}
                  size="middle"
                  scroll={{ x: 1200 }}
                  expandable={{
                    expandedRowRender,
                    rowExpandable: () => true,
                  }}
                  pagination={{
                    current: page,
                    pageSize,
                    total,
                    showSizeChanger: true,
                    showQuickJumper: true,
                    pageSizeOptions: ['10', '20', '50', '100'],
                    onChange: (p, ps) => { setPage(p); setPageSize(ps) },
                    showTotal: (t) => `共 ${t} 条`,
                  }}
                />
              )}
            </Spin>
          </Card>
        </Col>

        {/* 右侧：图表 */}
        <Col span={8}>
          {/* 热力图 */}
          <Card
            title="评估分布热力图"
            extra={
              <Segmented
                size="small"
                options={RANGE_OPTIONS}
                value={distRange}
                onChange={(v) => setDistRange(v as number)}
              />
            }
            style={{ marginBottom: 16 }}
          >
            <Spin spinning={distLoading}>
              {heatmapOption ? (
                <>
                  <ReactECharts option={heatmapOption} style={{ height: 300 }} />
                  <div style={{
                    marginTop: 8, padding: '8px 12px', background: '#fafafa',
                    borderRadius: 4, fontSize: 12, color: '#666', lineHeight: 1.8,
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

          {/* 结果分布 */}
          <Card title="结果分布" style={{ marginBottom: 16 }}>
            {resultBarOption ? (
              <ReactECharts option={resultBarOption} style={{ height: 200 }} />
            ) : (
              <Empty description="暂无数据" />
            )}
          </Card>

          {/* 5档分数分布 */}
          <Card title="分数分布" style={{ marginBottom: 16 }}>
            {histogramOption ? (
              <ReactECharts option={histogramOption} style={{ height: 180 }} />
            ) : (
              <Empty description="暂无数据" />
            )}
          </Card>

          {/* 阈值建议 */}
          <Card title="阈值建议">
            <div style={{ marginBottom: 8 }}>目标通过率：{thresholdTarget}%</div>
            <Slider value={thresholdTarget} onChange={(v) => setThresholdTarget(v)} min={10} max={90} step={5} />
            <Button type="primary" icon={<AimOutlined />} onClick={fetchSuggestion} style={{ marginTop: 8 }} block>
              计算建议阈值
            </Button>
            {suggestion && (
              <div style={{ marginTop: 16, padding: 12, background: '#f6ffed', borderRadius: 4 }}>
                <div>建议阈值：<b style={{ color: '#52c41a' }}>{suggestion.suggested_threshold}</b></div>
                <div style={{ fontSize: 12, color: '#999' }}>当前通过率：{(suggestion.current_pass_rate * 100).toFixed(1)}%</div>
                <div style={{ fontSize: 12, color: '#999' }}>样本数：{dist?.total ?? '—'}</div>
              </div>
            )}
          </Card>
        </Col>
      </Row>

      {/* AI 评估结果弹窗 */}
      <Modal
        title={`AI 成色评估 - ${aiItemId}`}
        open={aiModalOpen}
        onCancel={() => setAiModalOpen(false)}
        footer={<Button onClick={() => setAiModalOpen(false)}>关闭</Button>}
        width={560}
      >
        <Spin spinning={aiLoading}>
          {aiResult ? (
            <div>
              <Row gutter={16} style={{ marginBottom: 16 }}>
                <Col span={12}>
                  <Statistic
                    title="评估结论"
                    value={aiResult.verdict === 'recommend' ? '推荐' : '谨慎'}
                    valueStyle={{ color: aiResult.verdict === 'recommend' ? '#52c41a' : '#faad14' }}
                  />
                </Col>
                <Col span={12}>
                  <Statistic
                    title="成色评分"
                    value={`${aiResult.condition_score}/10`}
                    valueStyle={{ color: aiResult.condition_score >= 7 ? '#52c41a' : '#faad14' }}
                  />
                </Col>
              </Row>
              <div style={{ marginBottom: 12 }}>
                <strong>评估理由：</strong>
                <p style={{ marginTop: 4 }}>{aiResult.reason}</p>
              </div>
              {aiResult.risk_signals?.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <strong>风险信号：</strong>
                  <div style={{ marginTop: 4 }}>
                    {aiResult.risk_signals.map((sig, i) => (
                      <Tag key={i} color="orange" style={{ marginBottom: 4 }}>{sig}</Tag>
                    ))}
                  </div>
                </div>
              )}
              {aiResult.detail && (
                <Collapse
                  items={[{ key: 'detail', label: '详细分析', children: <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>{aiResult.detail}</pre> }]}
                  size="small"
                />
              )}
              <div style={{ marginTop: 12, fontSize: 12, color: '#999' }}>
                来源：{aiResult.source === 'llm' ? 'AI 视觉分析' : '规则模拟'}
                {aiResult.cached ? '（缓存）' : ''}
              </div>
            </div>
          ) : (
            !aiLoading && <Empty description="点击评估按钮开始 AI 分析" />
          )}
        </Spin>
      </Modal>
    </div>
  )
}
