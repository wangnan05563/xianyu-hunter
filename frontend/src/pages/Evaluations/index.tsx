import { useEffect, useMemo, useState } from 'react'
import {
  Card, Table, Button, Space, Spin, Input, Select, Slider, Row, Col,
  Empty, DatePicker, Alert, Progress, Checkbox, Tag, Statistic, InputNumber,
  Tooltip,
} from 'antd'
import {
  ReloadOutlined, AimOutlined, SearchOutlined, UndoOutlined,
  RetweetOutlined, SettingOutlined, LeftOutlined, RightOutlined,
  RobotOutlined, CloudDownloadOutlined, QuestionCircleOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { taskApi, type EvalItem } from '../../api'
import { usePersistentState } from '../../hooks/usePersistentState'
import { useColumnConfig, type ColumnConfig } from '../../hooks/useColumnConfig'
import EvalHeatmap from './components/EvalHeatmap'
import ResultBarChart from './components/ResultBarChart'
import PriceHistogram from './components/PriceHistogram'
import TrendSparkline from './components/TrendSparkline'
import ColumnSettingsModal from './components/ColumnSettingsModal'
import CollapsibleRail from './components/CollapsibleRail'
import { ExportButton } from '../../components/ExportButton'
import { AIEvalModal } from './components/AIEvalModal'
import { DeepAnalyzeModal } from './components/DeepAnalyzeModal'
import { CollectResultModal } from './components/CollectResultModal'

import { useEvalFilters, type ResultCategory } from './hooks/useEvalFilters'
import { useEvalList } from './hooks/useEvalList'
import { useEvalDist } from './hooks/useEvalDist'
import { useEvalAI } from './hooks/useEvalAI'
import { useEvalCollect } from './hooks/useEvalCollect'
import { useEvalBatch } from './hooks/useEvalBatch'
import { useEvalTrend } from './hooks/useEvalTrend'
import { useEvalFeedback } from './hooks/useEvalFeedback'
import { useEvalColumns } from './hooks/useEvalColumns'

import { translateDimension, translateRejectReason } from './dimensionLabels'
import type { DistResponse, SellerTrendData } from './utils'

const { RangePicker } = DatePicker

const SCROLL_X = 2170

// S3776 修复：用查表替代原 useMemo 内 switch（5 case 嵌套在 if 内贡献 ~+10 复杂度）
// 为什么用 Record：列宽/responsive 调整是静态映射，查表比 switch 更扁平
const COLLAPSED_COLUMN_OVERRIDES: Record<string, Record<string, unknown>> = {
  task_id: { responsive: undefined },
  title: { width: 280 },
  seller: { width: 220 },
  publish: { responsive: undefined },
  condition_tags: { width: 180 },
}

const COLUMN_DEFINITIONS: ColumnConfig[] = [
  { key: 'task_id', label: '任务ID' },
  { key: 'thumb', label: '图片' },
  { key: 'title', label: '标题', locked: true },
  { key: 'price', label: '价格' },
  { key: 'estimated_profit', label: '预估盈利' },
  { key: 'seller', label: '卖家' },
  { key: 'region', label: '地区' },
  { key: 'brand', label: '品牌' },
  { key: 'want', label: '想要' },
  { key: 'view', label: '浏览' },
  { key: 'publish', label: '发布时间' },
  { key: 'is_sold', label: '状态' },
  { key: 'condition', label: '成色' },
  { key: 'condition_tags', label: '成色标签' },
  { key: 'score', label: '评分', locked: true },
  { key: 'risk', label: '风险' },
  { key: 'ai', label: 'AI' },
  { key: 'collect', label: '官方采集' },
  { key: 'feedback', label: '反馈' },
]

function ExpandedDetail({ r, trendCache, trendLoading, trendError, loadSellerTrend }: {
  readonly r: EvalItem
  readonly trendCache: Record<string, SellerTrendData>
  readonly trendLoading: string
  readonly trendError: Record<string, string>
  readonly loadSellerTrend: (itemId: string) => Promise<void>
}) {
  const d = useMemo(() => {
    const p = r.payload ?? {}
    const dimScores = p.dimension_scores as Record<string, unknown> | undefined
    const ruleDims: Array<[string, number]> = []
    if (dimScores) {
      for (const [k, v] of Object.entries(dimScores)) {
        if (k === 'ai_condition_eval') continue
        if (typeof v === 'number') ruleDims.push([k, v])
      }
    }
    return {
      description: p.item_description as string | undefined,
      imageUrls: p.image_urls as string[] | undefined,
      reviews: p.reviews as string[] | undefined,
      sellerCreditScore: p.seller_credit_score as number | undefined,
      sellerOnSaleCount: p.seller_on_sale_count as number | undefined,
      sellerSoldCount: p.seller_sold_count as number | undefined,
      sellerRegisterDays: p.seller_register_days as number | undefined,
      dataSource: p.data_source as string | undefined,
      aiEval: dimScores?.ai_condition_eval as Record<string, unknown> | undefined,
      ruleDims,
      rejectReasons: p.reject_reasons as string[] | undefined,
    }
  }, [r.payload])

  const hasDetail = d.description || d.imageUrls?.length || d.reviews?.length ||
    d.sellerCreditScore != null || d.sellerOnSaleCount != null ||
    d.sellerSoldCount != null || d.sellerRegisterDays != null ||
    d.aiEval || d.ruleDims.length > 0 || d.rejectReasons?.length || d.dataSource

  return (
    <div>
      {hasDetail && (
        <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
          {(d.description || d.imageUrls?.length) && (
            <Col span={24}>
              <Card size="small" title="商品详情" style={{ marginBottom: 8 }}>
                {d.description && (
                  <div style={{ marginBottom: 8, color: 'var(--xh-text-secondary)', fontSize: 13, whiteSpace: 'pre-wrap' }}>
                    {d.description}
                  </div>
                )}
                {d.imageUrls && d.imageUrls.length > 0 && (
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {d.imageUrls.slice(0, 6).map((url, i) => (
                      // S1077：img 必须有 alt 属性，装饰性图片用空字符串
                      <img key={`${url}-${i}`} src={url} width={80} height={80} alt={`商品图片${i + 1}`} style={{ objectFit: 'cover', borderRadius: 6 }} />
                    ))}
                  </div>
                )}
              </Card>
            </Col>
          )}
          {(d.sellerCreditScore != null || d.sellerOnSaleCount != null || d.sellerSoldCount != null || d.sellerRegisterDays != null) && (
            <Col xs={24} md={12}>
              <Card size="small" title="卖家信息" style={{ marginBottom: 8 }}>
                <Row gutter={[8, 8]}>
                  {d.sellerCreditScore != null && <Col span={12}>芝麻信用：{d.sellerCreditScore}</Col>}
                  {d.sellerRegisterDays != null && <Col span={12}>注册天数：{d.sellerRegisterDays} 天</Col>}
                  {d.sellerOnSaleCount != null && <Col span={12}>在售数：{d.sellerOnSaleCount}</Col>}
                  {d.sellerSoldCount != null && <Col span={12}>已售数：{d.sellerSoldCount}</Col>}
                </Row>
              </Card>
            </Col>
          )}
          {(d.ruleDims.length > 0 || d.rejectReasons?.length) && (
            <Col xs={24} md={12}>
              <Card size="small" title="评估维度" style={{ marginBottom: 8 }}>
                {d.ruleDims.length > 0 && (
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                    {d.ruleDims.map(([k, v]) => (
                      <Tag key={k} color="blue">{translateDimension(k)}: {v}</Tag>
                    ))}
                  </div>
                )}
                {d.rejectReasons && d.rejectReasons.length > 0 && (
                  <div style={{ fontSize: 12 }}>
                    <span style={{ color: 'var(--xh-text-tertiary)' }}>拒绝原因: </span>
                    {d.rejectReasons.map((reason, i) => (
                      <Tag key={`${reason}-${i}`} color="orange" style={{ fontSize: 11, marginBottom: 2 }}>{translateRejectReason(reason)}</Tag>
                    ))}
                  </div>
                )}
              </Card>
            </Col>
          )}
          {d.reviews && d.reviews.length > 0 && (
            <Col span={24}>
              <Card size="small" title={`评价/留言 (${d.reviews.length})`} style={{ marginBottom: 8 }}>
                {d.reviews.slice(0, 5).map((review, i) => (
                  <div key={`${review}-${i}`} style={{ padding: '4px 0', borderBottom: i < 4 ? '1px solid var(--xh-border-secondary)' : 'none', fontSize: 13 }}>
                    {review}
                  </div>
                ))}
                {d.reviews.length > 5 && (
                  <div style={{ color: 'var(--xh-text-tertiary)', fontSize: 12, marginTop: 4 }}>
                    还有 {d.reviews.length - 5} 条评价
                  </div>
                )}
              </Card>
            </Col>
          )}
          {d.dataSource && (
            <Col span={24}><Tag color="blue">数据来源: {d.dataSource}</Tag></Col>
          )}
        </Row>
      )}
      <TrendSparkline
        trend={trendCache[r.item_id]}
        loading={trendLoading === r.item_id}
        error={trendError[r.item_id]}
        onLoad={() => loadSellerTrend(r.item_id)}
      />
    </div>
  )
}

function AnalysisPanel({
  panelCollapsed, onExpand, dist, distRange, distLoading, onDistRangeChange,
  passScore, autoBuyScore, thresholdTarget, onThresholdTargetChange, fetchSuggestion, suggestion,
  thresholdValue, onThresholdValueChange, thresholdPassCount, thresholdPassRate, itemsCount,
  targetPassRate, onTargetPassRateChange, autoSuggestedThreshold,
}: {
  readonly panelCollapsed: boolean
  readonly onExpand: () => void
  readonly dist: DistResponse | null
  readonly distRange: number
  readonly distLoading: boolean
  readonly onDistRangeChange: (v: number) => void
  readonly passScore: number
  readonly autoBuyScore: number
  readonly thresholdTarget: number
  readonly onThresholdTargetChange: (v: number) => void
  readonly fetchSuggestion: () => void
  readonly suggestion: { suggested_threshold: number; current_pass_rate: number } | null
  readonly thresholdValue: number
  readonly onThresholdValueChange: (v: number) => void
  readonly thresholdPassCount: number
  readonly thresholdPassRate: number
  readonly itemsCount: number
  readonly targetPassRate: number
  readonly onTargetPassRateChange: (v: number) => void
  readonly autoSuggestedThreshold: number
}) {
  if (panelCollapsed === true) {
    return <CollapsibleRail onExpand={onExpand} />
  }
  return (
    <>
      <EvalHeatmap dist={dist} distRange={distRange} distLoading={distLoading} onRangeChange={onDistRangeChange} />
      <ResultBarChart dist={dist} passScore={passScore} autoBuyScore={autoBuyScore} />
      <PriceHistogram dist={dist} />
      <Card title={<><AimOutlined style={{ marginRight: 6 }} />阈值建议</>} style={{ marginTop: 16 }}>
        <div style={{ marginBottom: 8 }}>目标通过率：{thresholdTarget}%</div>
        <Slider value={thresholdTarget} onChange={onThresholdTargetChange} min={10} max={90} step={5} />
        <Button type="primary" icon={<AimOutlined />} onClick={fetchSuggestion} style={{ marginTop: 8 }} block>
          计算建议阈值
        </Button>
        {suggestion && (
          <div style={{ marginTop: 16, padding: 12, background: 'rgba(82, 196, 26, 0.08)', borderRadius: 4 }}>
            <div>建议阈值：<b style={{ color: '#52c41a' }}>{suggestion.suggested_threshold}</b></div>
            <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)' }}>当前通过率：{(suggestion.current_pass_rate * 100).toFixed(1)}%</div>
            <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)' }}>样本数：{dist?.total ?? '—'}</div>
          </div>
        )}
      </Card>
      <Card title={<><SettingOutlined style={{ marginRight: 6 }} />阈值通过率计算器</>} style={{ marginTop: 16 }}>
        <div style={{ marginBottom: 8 }}>
          当前阈值：<b style={{ color: '#1890ff' }}>{thresholdValue}</b> 分
        </div>
        <Slider value={thresholdValue} onChange={onThresholdValueChange} min={0} max={100} step={1}
          marks={{ 0: '0', 60: '60', 80: '80', 100: '100' }} />
        <Row gutter={16} style={{ marginTop: 12 }}>
          <Col span={8}>
            <Statistic title="通过率" value={thresholdPassRate.toFixed(1)} suffix="%"
              valueStyle={{ color: thresholdPassRate >= 60 ? '#52c41a' : '#ff4d4f' }} />
          </Col>
          <Col span={8}>
            <Statistic title="通过数" value={thresholdPassCount} valueStyle={{ color: '#1890ff' }} />
          </Col>
          <Col span={8}>
            <Statistic title="总数" value={itemsCount} />
          </Col>
        </Row>
        <div style={{ marginTop: 20, paddingTop: 12, borderTop: '1px solid #f0f0f0' }}>
          <div style={{ marginBottom: 8 }}>
            目标通过率：<b style={{ color: '#faad14' }}>{targetPassRate}%</b>
          </div>
          <Slider value={targetPassRate} onChange={onTargetPassRateChange} min={10} max={100} step={5}
            marks={{ 10: '10%', 50: '50%', 70: '70%', 100: '100%' }} />
          <div style={{ marginTop: 8, padding: 12, background: 'rgba(250, 140, 22, 0.08)', borderRadius: 4 }}>
            <div>建议阈值：<b style={{ color: '#fa8c16' }}>{autoSuggestedThreshold.toFixed(1)}</b> 分</div>
            <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)' }}>
              即评分 ≥ {autoSuggestedThreshold.toFixed(1)} 时，约 {targetPassRate}% 的评估可通过
            </div>
          </div>
        </div>
      </Card>
    </>
  )
}

// S3776 修复：把评估结果分类卡片提取为子组件
// 5 个 Card 共享 onClick + 条件 style 模式，用配置数组驱动消除 5 处内联 onClick + 5 处三元样式
function ResultCategoryCards({
  dist, passScore, autoBuyScore, resultCategory, onSelect,
}: {
  readonly dist: DistResponse
  readonly passScore: number
  readonly autoBuyScore: number
  readonly resultCategory: ResultCategory
  readonly onSelect: (category: ResultCategory) => void
}) {
  // 配置数组：5 个分类卡片共享同一渲染模板，只差 title/value/color
  // 为什么用数组：原 5 段几乎相同 JSX，每段含 onClick + 条件 style，配置化后子组件复杂度 ~3，主函数减 ~7
  const cards: ReadonlyArray<{
    readonly key: ResultCategory
    readonly title: string
    readonly value: number
    readonly valueStyle?: { color: string }
    readonly activeColor: string
    readonly activeBg: string
  }> = [
    { key: null, title: '评估总数', value: dist.total, activeColor: '#1890ff', activeBg: 'rgba(24,144,255,0.06)' },
    { key: 'auto', title: `可抢(≥${autoBuyScore})`, value: dist.marginals.result.auto, valueStyle: { color: '#52c41a' }, activeColor: '#52c41a', activeBg: 'rgba(82,196,26,0.06)' },
    { key: 'pass', title: `通过(${passScore}-${autoBuyScore - 1})`, value: dist.marginals.result.pass, valueStyle: { color: '#1890ff' }, activeColor: '#1890ff', activeBg: 'rgba(24,144,255,0.06)' },
    { key: 'fail', title: `驳回(<${passScore})`, value: dist.marginals.result.fail, valueStyle: { color: '#ff4d4f' }, activeColor: '#ff4d4f', activeBg: 'rgba(255,77,79,0.06)' },
    { key: 'insufficient', title: '数据不足', value: dist.insufficient_count, valueStyle: { color: 'var(--xh-text-tertiary)' }, activeColor: '#faad14', activeBg: 'rgba(250,173,20,0.06)' },
  ]
  return (
    <Row gutter={12} style={{ marginBottom: 16 }}>
      {cards.map((c) => (
        <Col span={4} key={String(c.key)}>
          <Card
            size="small" hoverable
            onClick={() => onSelect(c.key)}
            style={resultCategory === c.key ? { borderColor: c.activeColor, background: c.activeBg } : {}}
          >
            <Statistic title={c.title} value={c.value} valueStyle={c.valueStyle} />
          </Card>
        </Col>
      ))}
      <Col span={4}>
        <Card size="small" hoverable>
          <Statistic title="价格区间" value={dist.price_range[0] > 0 ? `¥${dist.price_range[0]}~${dist.price_range[1]}` : '—'} />
        </Card>
      </Col>
    </Row>
  )
}

// S3776 修复：批量选择 Alert 提取为子组件
// 原 JSX 含 5 处三元（batchCollecting ? collectProgress : batchProgress）+ 1 处 && 条件渲染
// 提取后用单个 progress 变量替代 3 处三元，主函数减少 1 处 && 条件渲染
function BatchSelectionAlert({
  selectedCount, batchAIEvaluating, batchCollecting,
  batchProgress, batchCollectProgress,
  onBatchAIEval, onBatchCollectOfficial, onClearSelection,
}: {
  readonly selectedCount: number
  readonly batchAIEvaluating: boolean
  readonly batchCollecting: boolean
  readonly batchProgress: { done: number; total: number }
  readonly batchCollectProgress: { done: number; total: number }
  readonly onBatchAIEval: () => void
  readonly onBatchCollectOfficial: () => void
  readonly onClearSelection: () => void
}) {
  if (selectedCount === 0) return null
  // 进度数据选择：批量采集进行中显示采集进度，否则显示 AI 评估进度
  const progress = batchCollecting ? batchCollectProgress : batchProgress
  const showProgress = batchAIEvaluating || batchCollecting
  return (
    <Alert
      type="info"
      showIcon
      style={{ marginBottom: 12 }}
      message={
        <Space>
          <span>已选择 <b>{selectedCount}</b> 项</span>
          <Button type="primary" size="small" icon={<RobotOutlined />} loading={batchAIEvaluating} onClick={onBatchAIEval}>
            批量 AI 评估 ({selectedCount} 项)
          </Button>
          <Button size="small" icon={<CloudDownloadOutlined />} loading={batchCollecting} onClick={onBatchCollectOfficial}>
            批量官方采集 ({selectedCount} 项)
          </Button>
          <Button size="small" onClick={onClearSelection}>取消选择</Button>
        </Space>
      }
      description={showProgress && (
        <Progress
          percent={Math.round((progress.done / progress.total) * 100)}
          size="small"
          format={() => `${progress.done}/${progress.total}`}
        />
      )}
    />
  )
}

export default function Evaluations() {
  const filters = useEvalFilters()
  const list = useEvalList({
    itemId: filters.itemId,
    taskId: filters.taskId,
    scoreRange: filters.scoreRange,
    dateRange: filters.dateRange,
    brandFilter: filters.brandFilter,
    soldFilter: filters.soldFilter,
    resultCategory: filters.resultCategory,
    priceRange: filters.priceRange,
    includeOutOfRange: filters.includeOutOfRange,
  })
  const dist = useEvalDist(list.items, {
    taskId: filters.taskId,
    priceRange: filters.priceRange,
    includeOutOfRange: filters.includeOutOfRange,
  })
  const ai = useEvalAI()
  const collect = useEvalCollect(list.load)
  const batch = useEvalBatch(list.items, filters.taskId, list.load, dist.loadDist)
  const trend = useEvalTrend()
  const feedback = useEvalFeedback(list.setItems)

  const columns = useEvalColumns({
    autoBuyScore: dist.autoBuyScore,
    passScore: dist.passScore,
    collecting: collect.collecting,
    feedbackSubmitting: feedback.feedbackSubmitting,
    manualTaking: batch.manualTaking,
    onAIEval: ai.onAIEval,
    onDeepAnalyze: ai.onDeepAnalyze,
    onCollectOfficial: collect.onCollectOfficial,
    onFeedback: feedback.onFeedback,
    onManualTakeover: batch.onManualTakeover,
    onTitleClick: batch.onTitleClick,
  })

  const [columnConfigOpen, setColumnConfigOpen] = useState(false)
  const {
    order: columnOrder,
    hidden: hiddenColumns,
    toggleHidden: toggleColumnHidden,
    moveColumn: moveColumnOrder,
    reset: resetColumnConfig,
    applyConfig: applyColumnConfig,
  } = useColumnConfig('xh.evals.columns', COLUMN_DEFINITIONS)

  const [panelCollapsed, setPanelCollapsed] = usePersistentState<boolean>(
    'xh.evals.panelCollapsed', false,
    { validator: (v): v is boolean => typeof v === 'boolean' },
  )

  useEffect(() => {
    taskApi.list({ limit: 200 }).then((res) => {
      filters.setTasks(res.items || [])
    }).catch(() => {})
  }, [])

  const onSearch = () => {
    if (list.page === 1) {
      list.load()
    } else {
      list.setPage(1)
    }
  }

  const onReset = () => {
    filters.reset()
    if (list.page === 1) {
      list.load()
    } else {
      list.setPage(1)
    }
  }

  const adaptedColumns = useMemo(() => {
    if (!panelCollapsed) return columns
    return columns.map((col) => {
      const override = COLLAPSED_COLUMN_OVERRIDES[String(col.key ?? '')]
      return override ? { ...col, ...override } : col
    })
  }, [columns, panelCollapsed])

  const visibleColumns = applyColumnConfig(adaptedColumns)
  const scrollX = panelCollapsed ? 2180 : SCROLL_X

  const brandOptions = [...new Set(
    list.items.map((i) => i.payload?.brand).filter(Boolean)
  )].sort((a, b) => String(a).localeCompare(String(b)))

  const renderExpandedRow = (r: EvalItem) => (
    <ExpandedDetail
      r={r}
      trendCache={trend.trendCache}
      trendLoading={trend.trendLoading}
      trendError={trend.trendError}
      loadSellerTrend={trend.loadSellerTrend}
    />
  )

  return (
    <div className="page-container">
      <Card style={{ marginBottom: 16 }}>
        <Space wrap size="middle">
          <span>商品ID：</span>
          <Input
            placeholder="模糊匹配" allowClear style={{ width: 160 }}
            value={filters.itemId} onChange={(e) => filters.setItemId(e.target.value)}
            onPressEnter={onSearch}
          />
          <span>任务ID：</span>
          <Select
            placeholder="选择任务" allowClear showSearch
            style={{ width: 260 }}
            value={filters.taskId || undefined}
            onChange={(v) => { filters.setTaskId(v || ''); list.setPage(1); setTimeout(list.load, 0) }}
            onClear={() => filters.setTaskId('')}
            filterOption={(input, option) =>
              (option?.label as string ?? '').toLowerCase().includes(input.toLowerCase())
            }
            options={filters.tasks.map((t) => ({
              label: `${t.name}（${t.keyword}）`,
              value: t.id,
            }))}
            notFoundContent="暂无任务"
          />
          <span>评分范围：</span>
          <Slider
            range style={{ width: 200 }}
            value={filters.scoreRange}
            onChange={(v) => filters.setScoreRange(v as [number, number])}
          />
          <span>时间范围：</span>
          <RangePicker
            value={filters.dateRange as [dayjs.Dayjs, dayjs.Dayjs] | null}
            onChange={(v) => filters.setDateRange(v ? [v[0]?.toISOString() ?? '', v[1]?.toISOString() ?? ''] : null)}
          />
          <span>品牌：</span>
          <Select
            placeholder="选择品牌"
            allowClear
            showSearch
            style={{ width: 160 }}
            value={filters.brandFilter}
            onChange={(v) => { filters.setBrandFilter(v || ''); list.setPage(1); setTimeout(list.load, 0) }}
            onClear={() => filters.setBrandFilter('')}
            filterOption={(input, option) =>
              (option?.label as string ?? '').toLowerCase().includes(input.toLowerCase())
            }
            options={brandOptions.map((b) => ({ label: b, value: b }))}
            notFoundContent="暂无品牌"
          />
          <span>状态：</span>
          <Select
            placeholder="状态筛选"
            style={{ width: 100 }}
            allowClear
            value={filters.soldFilter}
            onChange={(v) => { filters.setSoldFilter(v || 'all'); list.setPage(1); setTimeout(list.load, 0) }}
            options={[
              { label: '全部', value: 'all' },
              { label: '在售', value: 'onsale' },
              { label: '已售', value: 'sold' },
            ]}
          />
          <Tooltip
            title={
              <div style={{ lineHeight: 1.6 }}>
                <div><b>查询规则：</b></div>
                <div>1. 价格区间：商品价格需在 [最低, 最高] 范围内</div>
                <div>2. 低于市场参考价：选中任务后，按任务 market_ratio 配置过滤掉价格高于「同任务商品中位数 × market_ratio」的商品（样本数 ≥ 3 才生效）</div>
                <div style={{ marginTop: 4, color: '#aaa' }}>提示：勾选「显示超范围」可跳过市场参考价过滤，用于审计历史商品</div>
              </div>
            }
          >
            <span style={{ cursor: 'help', borderBottom: '1px dashed currentColor' }}>
              价格范围：
              <QuestionCircleOutlined style={{ marginLeft: 2, fontSize: 12, color: '#999' }} />
            </span>
          </Tooltip>
          <InputNumber
            placeholder="最低"
            min={0}
            style={{ width: 90 }}
            value={filters.priceRange[0]}
            onChange={(v) => filters.setPriceRange([v ?? null, filters.priceRange[1]])}
          />
          <span>-</span>
          <InputNumber
            placeholder="最高"
            min={0}
            style={{ width: 90 }}
            value={filters.priceRange[1]}
            onChange={(v) => filters.setPriceRange([filters.priceRange[0], v ?? null])}
          />
          <Tooltip title="开启后显示超出任务价格范围的历史商品（审计用）">
            <Checkbox
              checked={filters.includeOutOfRange}
              onChange={(e) => { filters.setIncludeOutOfRange(e.target.checked); list.setPage(1); setTimeout(list.load, 0) }}
            >
              显示超范围
            </Checkbox>
          </Tooltip>
          <Button type="primary" icon={<SearchOutlined />} onClick={onSearch}>查询</Button>
          <Button icon={<UndoOutlined />} onClick={onReset}>重置</Button>
          <Button icon={<ReloadOutlined />} onClick={list.load} loading={list.loading}>刷新</Button>
          <Button icon={<RetweetOutlined />} onClick={batch.onRecompute} loading={batch.recomputing}>重新评估</Button>
          <Button icon={<RetweetOutlined />} onClick={batch.onBatchEvaluateUnevaluated} loading={batch.batchEvaluating}>批量评估未评估商品</Button>
          <Button icon={<SettingOutlined />} onClick={() => setColumnConfigOpen(true)}>列配置</Button>
          <ExportButton dataset="evaluations" params={{ task_id: filters.taskId || undefined }} />
        </Space>
      </Card>

      {dist.dist && dist.dist.insufficient_count > 0 && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message={`有 ${dist.dist.insufficient_count} 条评估记录因卖家信息缺失仅基于价格评估`}
          description="建议在 Dashboard 页面重新登录闲鱼后，点击上方「重新评估」按钮获取完整评估结果。"
        />
      )}

      {dist.dist && (
        <ResultCategoryCards
          dist={dist.dist}
          passScore={dist.passScore}
          autoBuyScore={dist.autoBuyScore}
          resultCategory={filters.resultCategory}
          onSelect={(cat) => { filters.toggleResultCategory(cat); list.setPage(1); setTimeout(list.load, 0) }}
        />
      )}

      <Row gutter={16}>
        <Col span={panelCollapsed ? 23 : 16}>
          <Card style={{ transition: 'all 0.2s ease' }}
            extra={
              <Tooltip title={panelCollapsed ? '展开分析面板' : '收起分析面板'}>
                <Button
                  type="text"
                  size="small"
                  icon={panelCollapsed ? <RightOutlined /> : <LeftOutlined />}
                  onClick={() => setPanelCollapsed(!panelCollapsed)}
                />
              </Tooltip>
            }
          >
            <BatchSelectionAlert
              selectedCount={batch.selectedRowKeys.length}
              batchAIEvaluating={batch.batchAIEvaluating}
              batchCollecting={batch.batchCollecting}
              batchProgress={batch.batchProgress}
              batchCollectProgress={batch.batchCollectProgress}
              onBatchAIEval={batch.onBatchAIEval}
              onBatchCollectOfficial={batch.onBatchCollectOfficial}
              onClearSelection={() => batch.setSelectedRowKeys([])}
            />
            <Spin spinning={list.loading}>
              {list.items.length === 0 ? (
                <Empty description={filters.resultCategory ? '当前过滤条件下无匹配记录' : '暂无评估数据'} />
              ) : (
                <Table
                  columns={visibleColumns}
                  dataSource={list.items}
                  rowKey={(r) => `${r.item_id}-${r.created_at}`}
                  size="middle"
                  rowSelection={{
                    selectedRowKeys: batch.selectedRowKeys,
                    onChange: (keys) => batch.setSelectedRowKeys(keys),
                  }}
                  scroll={{ x: scrollX }}
                  expandable={{
                    expandedRowRender: renderExpandedRow,
                    rowExpandable: () => true,
                  }}
                  pagination={{
                    current: list.page,
                    pageSize: list.pageSize,
                    total: list.total,
                    showSizeChanger: true,
                    showQuickJumper: true,
                    pageSizeOptions: ['10', '20', '50', '100'],
                    showLessItems: true,
                    onChange: (p, ps) => { list.setPage(p); list.setPageSize(ps) },
                    showTotal: (t) => filters.resultCategory ? `过滤后 ${t} 条` : `共 ${t} 条`,
                  }}
                />
              )}
            </Spin>
          </Card>
        </Col>

        <Col span={panelCollapsed ? 1 : 8}>
          <AnalysisPanel
            panelCollapsed={panelCollapsed}
            onExpand={() => setPanelCollapsed(false)}
            dist={dist.dist}
            distRange={dist.distRange}
            distLoading={dist.distLoading}
            onDistRangeChange={dist.setDistRange}
            passScore={dist.passScore}
            autoBuyScore={dist.autoBuyScore}
            thresholdTarget={dist.thresholdTarget}
            onThresholdTargetChange={dist.setThresholdTarget}
            fetchSuggestion={dist.fetchSuggestion}
            suggestion={dist.suggestion}
            thresholdValue={dist.thresholdValue}
            onThresholdValueChange={dist.setThresholdValue}
            thresholdPassCount={dist.thresholdPassCount}
            thresholdPassRate={dist.thresholdPassRate}
            itemsCount={list.items.length}
            targetPassRate={dist.targetPassRate}
            onTargetPassRateChange={dist.setTargetPassRate}
            autoSuggestedThreshold={dist.autoSuggestedThreshold}
          />
        </Col>
      </Row>

      <AIEvalModal
        open={ai.aiModalOpen}
        loading={ai.aiLoading}
        result={ai.aiResult}
        itemId={ai.aiItemId}
        onCancel={() => ai.setAiModalOpen(false)}
      />

      <DeepAnalyzeModal
        open={ai.deepModalOpen}
        loading={ai.deepLoading}
        result={ai.deepResult}
        itemId={ai.deepItemId}
        onCancel={() => ai.setDeepModalOpen(false)}
      />

      <CollectResultModal
        open={collect.collectModalOpen}
        result={collect.collectResult}
        onCancel={() => collect.setCollectModalOpen(false)}
      />

      <ColumnSettingsModal
        open={columnConfigOpen}
        onClose={() => setColumnConfigOpen(false)}
        definitions={COLUMN_DEFINITIONS}
        order={columnOrder}
        hidden={hiddenColumns}
        onToggleHidden={toggleColumnHidden}
        onMove={moveColumnOrder}
        onReset={resetColumnConfig}
      />
    </div>
  )
}
