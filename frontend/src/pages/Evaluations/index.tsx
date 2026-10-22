import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Card, Table, Space, Spin, Input, Select, Slider, Row, Col,
  Empty, DatePicker, Alert, Progress, Checkbox, Tag, Statistic, InputNumber,
  Tooltip, Popconfirm,
} from 'antd'
import {
  ReloadOutlined, AimOutlined, SearchOutlined, UndoOutlined,
  RetweetOutlined, SettingOutlined, LeftOutlined, RightOutlined,
  RobotOutlined, CloudDownloadOutlined, QuestionCircleOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { taskApi, type EvalItem } from '../../api'
import { parseEvalDeepLink, evalDeepLinkMatchesFilters } from '../../utils/alertDeepLink'
import { usePersistentState } from '../../hooks/usePersistentState'
import { useColumnConfig } from '../../hooks/useColumnConfig'
import { COLUMN_DEFINITIONS } from './columnDefinitions'
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
import { TipButton } from '@/components/TipButton'
import FetchFailedHint from '../../components/FetchFailedHint'
import { useFailedSources } from '../../hooks/useFailedSources'

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
        <TipButton type="primary" icon={<AimOutlined />} onClick={fetchSuggestion} style={{ marginTop: 8 }} block tip="根据目标通过率计算建议评分阈值">
          计算建议阈值
        </TipButton>
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
          <TipButton type="primary" size="small" icon={<RobotOutlined />} loading={batchAIEvaluating} onClick={onBatchAIEval} tip="对选中商品批量执行 AI 成色评估">
            批量 AI 评估 ({selectedCount} 项)
          </TipButton>
          <TipButton size="small" icon={<CloudDownloadOutlined />} loading={batchCollecting} onClick={onBatchCollectOfficial} tip="对选中商品批量访问官方页面采集">
            批量官方采集 ({selectedCount} 项)
          </TipButton>
          <TipButton size="small" onClick={onClearSelection} tip="取消已选中的商品">取消选择</TipButton>
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

// 本页独立请求的数据源（T02899）：任务列表喂筛选下拉，
// 原先把 reject 吞成空块后，「没有任务」与「后端挂了」是同一个画面。
type EvaluationsSource = 'tasks'

const SOURCE_LABELS: Record<EvaluationsSource, string> = {
  tasks: '任务列表',
}

export default function Evaluations() {
  // 告警深链（T02620）：抽屉的「低分评估」项跳过来带 ?item_id=<id>&score_max=<0-100>，
  // 本页必须真的读取，否则链接只是「跳过来自己找」——与 Orders.tsx 读 ?ref= 同一族。
  const [searchParams, setSearchParams] = useSearchParams()
  const deepLink = useMemo(() => parseEvalDeepLink(searchParams), [searchParams])
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

  // 深链落地即套用筛选：只做一次（用户之后手动改筛选不再被 URL 覆盖）。
  // 必须「先写筛选 state，再在下一轮渲染后 reload」两步走：useEvalList 通过
  // filtersRef 读快照，同一轮里直接 load() 会拿到旧筛选条件（测试实测过一次）。
  // reloadToken 就是「渲染已追平」的信号，清除定位与深链套用共用这条通道。
  const deepLinkApplied = useRef(false)
  const [reloadToken, setReloadToken] = useState(0)
  useEffect(() => {
    if (deepLinkApplied.current) return
    if (!deepLink.itemId && deepLink.scoreMax == null) return
    deepLinkApplied.current = true
    if (deepLink.itemId) filters.setItemId(deepLink.itemId)
    if (deepLink.scoreMax != null) filters.setScoreRange([0, deepLink.scoreMax])
    setReloadToken((t) => t + 1)
    // 依赖刻意留空：本效果只在挂载时消费一次 URL，重复执行会覆盖用户手动筛选
  }, [])
  useEffect(() => {
    if (reloadToken === 0) return
    list.setPage(1)
    list.load()
  }, [reloadToken])

  // 清除深链：去掉 URL 里的 item_id/score_max，并把筛选复位后重新加载
  const clearDeepLink = () => {
    const next = new URLSearchParams(searchParams)
    next.delete('item_id')
    next.delete('score_max')
    setSearchParams(next, { replace: true })
    filters.setItemId('')
    filters.setScoreRange([0, 100])
    deepLinkApplied.current = true
    setReloadToken((t) => t + 1)
  }

  // 深链参数是否仍然是当前筛选的真实描述（T02831），判定在 utils/alertDeepLink 里，
  // 好让「只带 score_max」「商品ID 被改掉」这些分支能被单元测试逐个钉住。
  // 首帧筛选还没套用（套用要等下一轮渲染），故 deepLinkApplied 之前不出提示条，
  // 免得把「马上要套用」闪成「已被覆盖」。
  const deepLinkVisible =
    (!!deepLink.itemId || deepLink.scoreMax != null) && deepLinkApplied.current
  const deepLinkMatchesFilters = evalDeepLinkMatchesFilters(deepLink, {
    itemId: filters.itemId,
    scoreRange: filters.scoreRange,
  })

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

  const { isFailed, track } = useFailedSources<EvaluationsSource>()

  // track 内部 mark 是稳定引用，这里不依赖 filters（它的对象每次渲染都换，进了依赖会自触发无限请求）
  const loadTasks = useCallback(() => {
    void track('tasks', taskApi.list({ limit: 200 })).then((res) => {
      if (res) filters.setTasks(res.items || [])
    })
  }, [track]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    loadTasks()
  }, [loadTasks])

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

  // 评审 2.4-2：重新评估原先静默一键触发全库重算，这里把「会重算什么范围」显式化。
  // 范围口径与后端一致（routes/evaluations_recompute.py:361）：按 user_id + 可选 task_id
  // 取 eval.* 事件重算，不受当前时间窗/价格筛选影响，故描述里不引用这两个筛选值。
  const selectedTaskName = filters.tasks.find((t) => t.id === filters.taskId)?.name
  const recomputeScope = filters.taskId
    ? `任务「${selectedTaskName || filters.taskId}」下的历史评估记录`
    : '当前账号全部历史评估记录（未选择任务）'

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
      {/* 深链落地说明（T02620）：让用户知道当前视图是「告警带来的筛选」而非全量列表，
          并提供一键回到正常筛选——与 Orders.tsx 的 ref 定位提示同构。
          T02831：这条提示描述的是「URL 参数 = 当前筛选」，用户手动改过筛选之后参数就不再是
          当前视图的真实描述，所以按是否仍一致分两种文案；不自动清参数——清掉会把用户
          点进来的那条线索直接抹掉，降级文案至少还说明差在哪。 */}
      {deepLinkVisible && (
        <Alert
          type={deepLinkMatchesFilters ? 'info' : 'warning'}
          showIcon
          style={{ marginBottom: 12 }}
          message={deepLinkMatchesFilters
            ? `已按告警定位到商品 ${deepLink.itemId ?? '—'}${deepLink.scoreMax != null ? `（评分 ≤ ${deepLink.scoreMax}）` : ''}`
            : `链接里的告警定位条件（商品 ${deepLink.itemId ?? '—'}${deepLink.scoreMax != null ? ` / 评分 ≤ ${deepLink.scoreMax}` : ''}）已被手动筛选覆盖，下方列表按当前筛选条件展示`}
          action={<TipButton size="small" onClick={clearDeepLink} tip="清除告警深链参数，回到正常筛选视图">清除定位</TipButton>}
        />
      )}
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
          <TipButton type="primary" icon={<SearchOutlined />} onClick={onSearch} tip="按当前筛选条件查询评估记录">查询</TipButton>
          <TipButton icon={<UndoOutlined />} onClick={onReset} tip="重置全部筛选条件">重置</TipButton>
          <TipButton icon={<ReloadOutlined />} onClick={list.load} loading={list.loading} tip="重新加载评估列表数据">刷新</TipButton>
          <Popconfirm
            title="确认重新评估？"
            description={(
              <div style={{ maxWidth: 340 }}>
                <div>重算范围：{recomputeScope}</div>
                <div>
                  将用当前评估规则重新打分并覆盖这些记录的评估结果，覆盖后无法恢复原分值。
                </div>
                <div>
                  重算不受上方时间窗与价格筛选限制；不调用 AI、不产生接口费用，也不发送通知。
                </div>
                <div style={{ color: 'var(--xh-text-secondary)' }}>
                  实际处理条数将在完成后提示。
                </div>
              </div>
            )}
            okText="确认重算"
            okButtonProps={{ danger: true }}
            cancelText="取消"
            placement="bottomRight"
            onConfirm={batch.onRecompute}
          >
            <TipButton
              icon={<RetweetOutlined />}
              loading={batch.recomputing}
              tip="用当前规则重新计算评估分值，点击后需二次确认"
            >
              重新评估
            </TipButton>
          </Popconfirm>
          <TipButton icon={<RetweetOutlined />} onClick={batch.onBatchEvaluateUnevaluated} loading={batch.batchEvaluating} tip="对尚未评估的商品批量评估">批量评估未评估商品</TipButton>
          <TipButton icon={<SettingOutlined />} onClick={() => setColumnConfigOpen(true)} tip="打开列显示与排序配置">列配置</TipButton>
          <ExportButton dataset="evaluations" params={{ task_id: filters.taskId || undefined }} />
        </Space>
      </Card>

      {isFailed('tasks') && (
        <FetchFailedHint
          source={SOURCE_LABELS.tasks}
          onRetry={loadTasks}
          description="任务下拉的选项取自该接口。失败时列表仍是上次取到的数据，但按任务筛选暂时用不了。"
        />
      )}
      {dist.distFailed && (
        <FetchFailedHint
          source={dist.distSourceLabel}
          onRetry={dist.loadDist}
          description="下方分布统计卡与阈值面板整块取不到数据——这是「没取到」，不是「近 7 天没有评估记录」。"
        />
      )}

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
              <TipButton
                type="text"
                size="small"
                icon={panelCollapsed ? <RightOutlined /> : <LeftOutlined />}
                onClick={() => setPanelCollapsed(!panelCollapsed)}
                tip={panelCollapsed ? '展开分析面板' : '收起分析面板'}
              />
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
