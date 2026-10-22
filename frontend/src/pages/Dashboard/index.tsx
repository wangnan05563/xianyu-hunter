import { useEffect, useState, useRef, useCallback, type Dispatch, type SetStateAction } from 'react'
// 删除未使用的 theme 导入（S1128）
import { Spin, Card, Col, Row, Alert, Space } from 'antd'
import { useNavigate } from 'react-router-dom'
import { LineChartOutlined } from '@ant-design/icons'
import {
  taskApi, statsApi, priceApi,
  type RecentEvent, type KpiCard, type TrendSeries, type TodayAlert, type StatsOverview, type HistogramData, type EvalFunnelData,
} from '../../api'
import { QuickEntryIcon } from '../../components/icons/GeometricIcons'
import StatCardsSection from './components/StatCardsSection'
import KpiSection from './components/KpiSection'
import AlertRadar from './components/AlertRadar'
import EventStreamSection from './components/EventStreamSection'
import PriceHistogramCard from './components/PriceHistogramCard'
import EvalFunnelCard from './components/EvalFunnelCard'
import TrendModal from './components/TrendModal'
import { API_BASE } from '../../utils/apiBase'
import { TipButton } from '@/components/TipButton'
import { useFailedSources } from '../../hooks/useFailedSources'
import { TASK_STATUS } from '../../constants/taskStatus'

// SSE lastEventId 持久化 key：提取到模块级，供 handleSseAppEvent 与 connect 共享（S2004 提取避免嵌套过深）
const SSE_LAST_EVENT_ID_KEY = 'xh.sse.lastEventId'

// 各数据源的失败记账 key（T02586 假回执清零）：
// 每个区块按自己的 key 记录「这次请求有没有成功」，失败既不写空数据也不静默。
type DataSourceKey =
  | 'overview' | 'kpi' | 'events' | 'histogram' | 'tasks' | 'alert' | 'funnel' | 'trend'
  | 'spark:events' | 'spark:orders_pending' | 'spark:orders_succeeded' | 'spark:orders_failed'

const SOURCE_LABELS: Record<DataSourceKey, string> = {
  overview: '统计卡',
  kpi: '业务 KPI',
  events: '事件流',
  histogram: '价格分布',
  tasks: '任务列表（价格分布筛选）',
  alert: '异常雷达',
  funnel: '评估漏斗',
  trend: '趋势大图',
  'spark:events': '事件曲线',
  'spark:orders_pending': '待支付曲线',
  'spark:orders_succeeded': '成功曲线',
  'spark:orders_failed': '失败曲线',
}

// sparkline 指标名与 StatCardsSection 取用的 key 一一对应：
// 三张订单卡各自取按状态的趋势，不再共用 orders 同一条线（评审 2.1-2）
const SPARK_METRICS = ['events', 'orders_pending', 'orders_succeeded', 'orders_failed'] as const

// 处理 app_event 事件：解析 SSE 数据并 prepend 到事件列表前 100 条
// 为什么提取到模块级：原 useEffect → connect → addEventListener → setEvents(prev =>) 嵌套达 5 层，违反 S2004
function handleSseAppEvent(
  e: MessageEvent,
  setEvents: Dispatch<SetStateAction<RecentEvent[]>>,
) {
  try {
    const ev = JSON.parse(e.data) as RecentEvent
    // O-14-26：记录 lastEventId 到 localStorage，供重连时补拉
    // MessageEvent 的 lastEventId 属性对应 SSE 帧的 id 字段
    if (e.lastEventId) {
      localStorage.setItem(SSE_LAST_EVENT_ID_KEY, e.lastEventId)
    }
    setEvents(prev => [ev, ...prev].slice(0, 100))
  } catch { /* 忽略解析错误 */ }
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [overview, setOverview] = useState<StatsOverview | null>(null)
  const [kpiCards, setKpiCards] = useState<KpiCard[]>([])
  const [events, setEvents] = useState<RecentEvent[]>([])
  const [histogram, setHistogram] = useState<HistogramData | null>(null)
  const [histoTasks, setHistoTasks] = useState<Array<{ id: string; name: string; keyword: string }>>([])
  const [histoTaskId, setHistoTaskId] = useState<string>('all')

  // Sparkline 数据
  const [sparklines, setSparklines] = useState<Record<string, TrendSeries | null>>({})

  // 异常雷达
  const [alertOpen, setAlertOpen] = useState(false)
  const [alertData, setAlertData] = useState<TodayAlert | null>(null)

  // 趋势大图 Modal
  const [trendOpen, setTrendOpen] = useState(false)
  // 指标可切换（评审 2.1-1：Modal 此前无任何入口，且指标被写死为 events）
  const [trendMetric, setTrendMetric] = useState('events')
  const [trendRange, setTrendRange] = useState(168)
  const [trendData, setTrendData] = useState<TrendSeries | null>(null)

  // SSE 实时事件
  const esRef = useRef<EventSource | null>(null)
  const [streamStatus, setStreamStatus] = useState('连接中…')

  // AI 价格分析
  const [aiAnalysis, setAiAnalysis] = useState<string | null>(null)
  const [aiLoading, setAiLoading] = useState(false)

  // O-08-26 评估漏斗
  const [funnelData, setFunnelData] = useState<EvalFunnelData | null>(null)
  const [funnelLoading, setFunnelLoading] = useState(false)
  const [funnelRange, setFunnelRange] = useState(30)

  // ========== 数据加载 ==========
  // 每个数据源单独记失败账（T02586 假回执清零）：原先所有请求 .catch(()=>null/[])
  // 会把后端故障渲染成「全 0 / 暂无数据」的正常态，且覆盖掉上一次取到的好数据。
  // 账本实现与移动端共用 useFailedSources（T02700 抽取，避免两套逻辑各自漂移）。
  const { failed: failedSources, mark: markSource, settle } = useFailedSources<DataSourceKey>()

  const loadOverview = useCallback(() => {
    Promise.allSettled([
      statsApi.overview(),
      statsApi.businessKpi(30),
      statsApi.recentEvents(15),
      priceApi.histogram({ bins: 20, task_id: histoTaskId === 'all' ? undefined : histoTaskId }),
      taskApi.list({ limit: 100 }),
    ]).then(([ov, kpi, ev, hist, tasks]) => {
      const o = settle(ov, 'overview')
      if (o) setOverview(o)
      const k = settle(kpi, 'kpi')
      if (k) setKpiCards(k.kpis || [])
      const e = settle(ev, 'events')
      if (e) setEvents(e.events || [])
      const h = settle(hist, 'histogram')
      if (h) setHistogram(h)
      const t = settle(tasks, 'tasks')
      if (t) setHistoTasks((t.items || []).filter(item => item.status !== TASK_STATUS.DELETED))
      setLoading(false)
    })
  }, [histoTaskId, settle])

  const loadSparklines = useCallback(() => {
    Promise.allSettled(
      SPARK_METRICS.map((metric) => statsApi.trend({ metric, range_hours: 24 })),
    ).then((results) => {
      const updates: Record<string, TrendSeries> = {}
      SPARK_METRICS.forEach((metric, i) => {
        const ok = results[i].status === 'fulfilled'
        markSource(`spark:${metric}` as DataSourceKey, ok)
        if (ok) updates[metric] = (results[i] as PromiseFulfilledResult<TrendSeries>).value
      })
      // 只覆盖成功的那几条，失败保留上一次曲线（配合曲线区的失败提示，不假装"没趋势"）
      setSparklines(prev => ({ ...prev, ...updates }))
    })
  }, [markSource])

  const loadAlert = useCallback(async () => {
    try {
      setAlertData(await statsApi.today())
      markSource('alert', true)
    } catch {
      markSource('alert', false)
    }
  }, [markSource])

  // O-08-26 评估漏斗：独立加载，受 funnelRange 控制
  const loadFunnel = useCallback(async () => {
    setFunnelLoading(true)
    try {
      setFunnelData(await statsApi.evalFunnel(funnelRange))
      markSource('funnel', true)
    } catch {
      markSource('funnel', false)
    } finally {
      setFunnelLoading(false)
    }
  }, [funnelRange, markSource])

  const loadTrendData = useCallback(async () => {
    try {
      setTrendData(await statsApi.trend({ metric: trendMetric, range_hours: trendRange }))
      markSource('trend', true)
    } catch {
      markSource('trend', false)
    }
  }, [trendMetric, trendRange, markSource])

  // 初始加载
  useEffect(() => {
    loadOverview()
    loadSparklines()
    loadAlert()
    loadFunnel()
  }, [loadOverview, loadSparklines, loadAlert, loadFunnel])

  // 轮询：KPI 每 5 分钟，其他每 1 分钟
  useEffect(() => {
    const kpiTimer = setInterval(() => {
      // 轮询失败同样记账：后台刷新失败要让顶栏错误态亮起来，而不是继续显示旧数字当现状
      statsApi.businessKpi(30)
        .then(kpi => { setKpiCards(kpi.kpis || []); markSource('kpi', true) })
        .catch(() => markSource('kpi', false))
    }, 5 * 60 * 1000)
    const refreshTimer = setInterval(() => {
      loadOverview()
      loadSparklines()
    }, 60 * 1000)
    return () => { clearInterval(kpiTimer); clearInterval(refreshTimer) }
  }, [loadOverview, loadSparklines])

  // SSE 实时事件流（O-14-26 断线重连回放）
  // 浏览器原生 EventSource 在自动重连时会携带 Last-Event-ID header，
  // 但本组件在 error 时手动 close + 重新 new EventSource，会丢失 lastEventId。
  // 因此用 localStorage 持久化 lastEventId，重连时作为 query 参数传递，
  // 后端 sse_stream.py 支持 ?last_event_id=xxx 补拉漏掉的事件。
  useEffect(() => {
    const connect = () => {
      if (esRef.current) esRef.current.close()
      // 页面不可见时不建立连接，避免后台无效重连
      if (document.visibilityState !== 'visible') return
      // O-14-26：重连时从 localStorage 读取 lastEventId，附加到 URL
      // 后端会补拉 id > lastEventId 的事件，避免断网期间漏掉关键告警
      const lastId = localStorage.getItem(SSE_LAST_EVENT_ID_KEY)
      const url = lastId ? `${API_BASE}api/events/stream?last_event_id=${lastId}` : `${API_BASE}api/events/stream`
      const es = new EventSource(url)
      esRef.current = es
      setStreamStatus('连接中…')
      es.addEventListener('open', () => setStreamStatus('● 已连接'))
      es.addEventListener('ping', () => setStreamStatus('● 已连接'))
      // O-14-26：处理 hello 事件，展示补拉数量
      es.addEventListener('hello', (e) => {
        try {
          const info = JSON.parse(e.data) as { replayed?: number; latest_id?: number }
          if (info.replayed && info.replayed > 0) {
            setStreamStatus(`● 已连接（补拉 ${info.replayed} 条）`)
          } else {
            setStreamStatus('● 已连接')
          }
        } catch { /* ignore */ }
      })
      // app_event 处理已提取为模块级 handleSseAppEvent，避免嵌套过深（S2004）
      es.addEventListener('app_event', (e) => handleSseAppEvent(e, setEvents))
      es.addEventListener('error', () => {
        setStreamStatus('× 断线，重连中…')
        try { es.close() } catch { /* */ }
        esRef.current = null
        if (document.visibilityState === 'visible') setTimeout(connect, 3000)
      })
    }
    connect()
    const onVisibility = () => { if (document.visibilityState === 'visible') connect() }
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      document.removeEventListener('visibilitychange', onVisibility)
      esRef.current?.close()
    }
  }, [])

  // 趋势大图打开时加载数据
  useEffect(() => {
    if (trendOpen) loadTrendData()
  }, [trendOpen, loadTrendData])

  // ========== 回调函数 ==========
  // 切换直方图任务时重置加载态与 AI 分析结果，避免显示旧任务的过期分析
  const handleHistoTaskChange = useCallback((taskId: string) => {
    setHistoTaskId(taskId)
    setLoading(true)
    setAiAnalysis(null)
  }, [])

  const handleAiAnalyze = useCallback(() => {
    setAiLoading(true)
    setAiAnalysis(null)
    priceApi.analyze({ task_id: histoTaskId === 'all' ? undefined : histoTaskId })
      .then((res) => setAiAnalysis(res.analysis))
      .catch(() => setAiAnalysis('分析请求失败，请检查 AI 服务配置后重试。'))
      .finally(() => setAiLoading(false))
  }, [histoTaskId])

  const handleClearAiAnalysis = useCallback(() => setAiAnalysis(null), [])

  const handleToggleAlert = useCallback(() => setAlertOpen(o => !o), [])

  // 失败账上的数据源（按声明顺序展示在顶栏错误态里）
  const failedKeys = (Object.keys(SOURCE_LABELS) as DataSourceKey[]).filter(k => failedSources[k])

  const retrySource = useCallback((key: DataSourceKey) => {
    // 每个区块的重试只打自己那一路请求，避免一次点击全页重刷
    if (key === 'kpi' || key === 'overview' || key === 'events' || key === 'histogram' || key === 'tasks') loadOverview()
    else if (key.startsWith('spark:')) loadSparklines()
    else if (key === 'alert') loadAlert()
    else if (key === 'funnel') loadFunnel()
    else if (key === 'trend') loadTrendData()
  }, [loadOverview, loadSparklines, loadAlert, loadFunnel, loadTrendData])

  // ========== 渲染 ==========
  return (
    <div className="page-container">
      <Spin spinning={loading}>
        {/* 后端故障必须先于任何数字表态（T02586 假回执清零）：
            原先四处 .catch(()=>null) 把故障渲染成「全 0 正常态」，用户无从判断是没事发生还是没取到数据 */}
        {failedKeys.length > 0 && (
          <Alert
            type="error"
            message={`${failedKeys.length} 个数据源加载失败：${failedKeys.map(k => SOURCE_LABELS[k]).join('、')}`}
            description="下列相关区块的数字与曲线不代表真实状态，请按各区块内的失败提示重试。"
            showIcon
            action={
              <TipButton
                size="small"
                onClick={() => { loadOverview(); loadSparklines(); loadAlert(); loadFunnel(); if (trendOpen) loadTrendData() }}
                tip="重新拉取全部数据源">
                全部重试
              </TipButton>
            }
            style={{ marginBottom: 16 }}
          />
        )}

        {/* 引导 Banner：无任务时显示欢迎引导 */}
        {overview?.tasks?.total === 0 && overview?.tasks?.running === 0 && (
          <Alert
            type="info"
            message="欢迎使用闲鱼猎人！"
            description="还没有任务，创建第一个任务开始监控吧"
            showIcon
            style={{ marginBottom: 16 }}
            action={
              <Space direction="vertical">
                <TipButton size="small" type="primary" onClick={() => navigate('/tasks/new')} tip="创建新的监控任务">
                  创建任务
                </TipButton>
                <TipButton size="small" onClick={() => navigate('/onboarding')} tip="查看新手引导说明">
                  查看引导
                </TipButton>
              </Space>
            }
          />
        )}

        {/* 调度器未运行警告 */}
        {overview && !overview.scheduler_running && (
          <Alert
            type="warning"
            message="调度器未运行"
            description="调度器未运行，任务不会自动执行。请启动调度器。"
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}

        {/* 趋势大图入口（评审 2.1-1：setTrendOpen 全仓无调用点，168h 趋势整体形同虚设） */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
          <TipButton size="small" icon={<LineChartOutlined />} onClick={() => setTrendOpen(true)} tip="打开趋势大图，可切换指标与 7 / 30 / 90 天范围">
            趋势大图
          </TipButton>
        </div>

        {/* 统计卡 + Sparkline */}
        <StatCardsSection overview={overview} sparklines={sparklines} failed={failedSources} onNavigate={navigate} />

        {/* 业务 KPI 卡：米其林星级 + 涨跌 */}
        <KpiSection kpiCards={kpiCards} error={!!failedSources.kpi} onRetry={() => retrySource('kpi')} />

        {/* O-08-26 评估漏斗 + 命中率/误报率 */}
        <EvalFunnelCard
          data={funnelData}
          loading={funnelLoading}
          error={!!failedSources.funnel}
          rangeDays={funnelRange}
          onRangeChange={setFunnelRange}
          onRetry={() => retrySource('funnel')}
        />

        {/* 异常雷达：折叠式 */}
        <AlertRadar
          alertData={alertData}
          alertOpen={alertOpen}
          loadError={!!failedSources.alert}
          onToggle={handleToggleAlert}
          onReload={loadAlert}
        />

        {/* 事件流 + 系统状态 */}
        <EventStreamSection
          events={events}
          streamStatus={streamStatus}
          overview={overview}
          error={!!failedSources.events}
          overviewFailed={!!failedSources.overview}
          onRetry={() => retrySource('events')}
          onNavigate={navigate}
        />

        {/* 价格直方图 + 任务筛选 + AI 分析 */}
        <PriceHistogramCard
          histogram={histogram}
          histoTaskId={histoTaskId}
          histoTasks={histoTasks}
          aiAnalysis={aiAnalysis}
          aiLoading={aiLoading}
          error={!!failedSources.histogram}
          tasksError={!!failedSources.tasks}
          onHistoTaskChange={handleHistoTaskChange}
          onAiAnalyze={handleAiAnalyze}
          onClearAiAnalysis={handleClearAiAnalysis}
          onRetry={() => retrySource('histogram')}
          onNavigate={navigate}
        />

        {/* 快捷入口（评审 2.1-3：原名「可视化配置入口」，但 11 项里含系统清理/反爬等非配置页，名实不符） */}
        <Card style={{ marginTop: 16 }} title="快捷入口">
          <Row gutter={[16, 16]}>
            <Col xs={12} md={6}>
              <Card className="quick-entry-card" size="small" onClick={() => navigate('/tasks/new')}>
                <QuickEntryIcon type="task" size={48} />
                <div style={{ fontWeight: 600, marginBottom: 4 }}>任务创建</div>
                <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)' }}>向导式配置</div>
              </Card>
            </Col>
            <Col xs={12} md={6}>
              <Card className="quick-entry-card" size="small" onClick={() => navigate('/config/price')}>
                <QuickEntryIcon type="price" size={48} />
                <div style={{ fontWeight: 600, marginBottom: 4 }}>价格策略</div>
                <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)' }}>滑块 + 预览</div>
              </Card>
            </Col>
            <Col xs={12} md={6}>
              <Card className="quick-entry-card" size="small" onClick={() => navigate('/config/eval')}>
                <QuickEntryIcon type="eval" size={48} />
                <div style={{ fontWeight: 600, marginBottom: 4 }}>评估规则</div>
                <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)' }}>雷达图可视化</div>
              </Card>
            </Col>
            <Col xs={12} md={6}>
              <Card className="quick-entry-card" size="small" onClick={() => navigate('/config/notifier')}>
                <QuickEntryIcon type="notifier" size={48} />
                <div style={{ fontWeight: 600, marginBottom: 4 }}>通知渠道</div>
                <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)' }}>拖拽排序</div>
              </Card>
            </Col>
            <Col xs={12} md={6}>
              <Card className="quick-entry-card" size="small" onClick={() => navigate('/config/ai')}>
                <QuickEntryIcon type="ai" size={48} />
                <div style={{ fontWeight: 600, marginBottom: 4 }}>AI 服务</div>
                <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)' }}>模型与深度分析</div>
              </Card>
            </Col>
            <Col xs={12} md={6}>
              <Card className="quick-entry-card" size="small" onClick={() => navigate('/config/buyer')}>
                <QuickEntryIcon type="buyer" size={48} />
                <div style={{ fontWeight: 600, marginBottom: 4 }}>抢单策略</div>
                <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)' }}>极速抢占配置</div>
              </Card>
            </Col>
            <Col xs={12} md={6}>
              <Card className="quick-entry-card" size="small" onClick={() => navigate('/config/search')}>
                <QuickEntryIcon type="search" size={48} />
                <div style={{ fontWeight: 600, marginBottom: 4 }}>搜索参数</div>
                <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)' }}>筛选与过滤</div>
              </Card>
            </Col>
            <Col xs={12} md={6}>
              <Card className="quick-entry-card" size="small" onClick={() => navigate('/config/version')}>
                <QuickEntryIcon type="version" size={48} />
                <div style={{ fontWeight: 600, marginBottom: 4 }}>配置版本</div>
                <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)' }}>版本回滚管理</div>
              </Card>
            </Col>
            <Col xs={12} md={6}>
              <Card className="quick-entry-card" size="small" onClick={() => navigate('/maintenance')}>
                <QuickEntryIcon type="cleanup" size={48} />
                <div style={{ fontWeight: 600, marginBottom: 4 }}>系统清理</div>
                <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)' }}>缓存与日志维护</div>
              </Card>
            </Col>
            <Col xs={12} md={6}>
              <Card className="quick-entry-card" size="small" onClick={() => navigate('/maintenance/db')}>
                <QuickEntryIcon type="dbAdmin" size={48} />
                <div style={{ fontWeight: 600, marginBottom: 4 }}>数据库维护</div>
                <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)' }}>业务表在线管理</div>
              </Card>
            </Col>
            <Col xs={12} md={6}>
              <Card className="quick-entry-card" size="small" onClick={() => navigate('/anticrawl')}>
                <QuickEntryIcon type="antiCrawl" size={48} />
                <div style={{ fontWeight: 600, marginBottom: 4 }}>反爬登录管理</div>
                <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)' }}>策略与会话监控</div>
              </Card>
            </Col>
          </Row>
        </Card>
      </Spin>

      {/* 趋势大图 Modal */}
      <TrendModal
        trendOpen={trendOpen}
        trendMetric={trendMetric}
        trendRange={trendRange}
        trendData={trendData}
        error={!!failedSources.trend}
        onClose={() => setTrendOpen(false)}
        onRangeChange={setTrendRange}
        onMetricChange={setTrendMetric}
        onRetry={() => retrySource('trend')}
      />
    </div>
  )
}
