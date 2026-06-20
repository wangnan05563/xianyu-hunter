import { useEffect, useState, useRef, useCallback } from 'react'
import { Spin, Card, Col, Row } from 'antd'
import { useNavigate } from 'react-router-dom'
import {
  taskApi, configApi, statsApi, priceApi,
  type RecentEvent, type KpiCard, type TrendSeries, type TodayAlert, type StatsOverview, type HistogramData,
} from '../../api'
import { QuickEntryIcon } from '../../components/icons/GeometricIcons'
import StatCardsSection from './components/StatCardsSection'
import KpiSection from './components/KpiSection'
import AlertRadar from './components/AlertRadar'
import EventStreamSection from './components/EventStreamSection'
import PriceHistogramCard from './components/PriceHistogramCard'
import TrendModal from './components/TrendModal'

export default function Dashboard() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [overview, setOverview] = useState<StatsOverview | null>(null)
  const [kpiCards, setKpiCards] = useState<KpiCard[]>([])
  const [events, setEvents] = useState<RecentEvent[]>([])
  const [histogram, setHistogram] = useState<HistogramData | null>(null)
  const [configVersion, setConfigVersion] = useState(0)
  const [histoTasks, setHistoTasks] = useState<Array<{ id: string; name: string; keyword: string }>>([])
  const [histoTaskId, setHistoTaskId] = useState<string>('all')

  // Sparkline 数据
  const [sparklines, setSparklines] = useState<Record<string, TrendSeries | null>>({})

  // 异常雷达
  const [alertOpen, setAlertOpen] = useState(false)
  const [alertData, setAlertData] = useState<TodayAlert | null>(null)

  // 趋势大图 Modal
  const [trendOpen, setTrendOpen] = useState(false)
  const [trendMetric, setTrendMetric] = useState('events')
  const [trendRange, setTrendRange] = useState(168)
  const [trendData, setTrendData] = useState<TrendSeries | null>(null)

  // SSE 实时事件
  const esRef = useRef<EventSource | null>(null)
  const [streamStatus, setStreamStatus] = useState('连接中…')

  // AI 价格分析
  const [aiAnalysis, setAiAnalysis] = useState<string | null>(null)
  const [aiLoading, setAiLoading] = useState(false)

  // ========== 数据加载 ==========
  const loadOverview = useCallback(() => {
    Promise.all([
      statsApi.overview().catch(() => null),
      statsApi.businessKpi(30).catch(() => ({ kpis: [], range_days: 30, generated_at: '' })),
      statsApi.recentEvents(15).catch(() => ({ events: [] })),
      priceApi.histogram({ bins: 20, task_id: histoTaskId === 'all' ? undefined : histoTaskId }).catch(() => null),
      configApi.getVersion().catch(() => ({ version: 0 })),
      taskApi.list({ limit: 100 }).catch(() => ({ items: [], total: 0 })),
    ]).then(([ov, kpi, ev, hist, ver, tasks]) => {
      if (ov) setOverview(ov as StatsOverview)
      setKpiCards((kpi as { kpis: KpiCard[] })?.kpis || [])
      setEvents((ev as { events: RecentEvent[] })?.events || [])
      setHistogram(hist as HistogramData | null)
      setConfigVersion((ver as { version: number })?.version || 0)
      const items = (tasks as { items: Array<{ id: string; name: string; keyword: string; status: string }> })?.items || []
      setHistoTasks(items.filter(t => t.status !== 'deleted'))
      setLoading(false)
    })
  }, [histoTaskId])

  const loadSparklines = useCallback(() => {
    Promise.all([
      statsApi.trend({ metric: 'events', range_hours: 24 }).catch(() => null),
      statsApi.trend({ metric: 'orders', range_hours: 24 }).catch(() => null),
    ]).then(([tasks, orders]) => {
      setSparklines({ tasks: tasks as TrendSeries | null, orders: orders as TrendSeries | null })
    })
  }, [])

  const loadAlert = useCallback(async () => {
    try { setAlertData(await statsApi.today()) } catch { /* 静默 */ }
  }, [])

  const loadTrendData = useCallback(async () => {
    try {
      const d = await statsApi.trend({ metric: trendMetric, range_hours: trendRange })
      setTrendData(d)
    } catch { setTrendData(null) }
  }, [trendMetric, trendRange])

  // 初始加载
  useEffect(() => {
    loadOverview()
    loadSparklines()
    loadAlert()
  }, [loadOverview, loadSparklines, loadAlert])

  // 轮询：KPI 每 5 分钟，其他每 1 分钟
  useEffect(() => {
    const kpiTimer = setInterval(() => {
      statsApi.businessKpi(30).then(kpi => setKpiCards(kpi.kpis || [])).catch(() => {})
    }, 5 * 60 * 1000)
    const refreshTimer = setInterval(() => {
      loadOverview()
      loadSparklines()
    }, 60 * 1000)
    return () => { clearInterval(kpiTimer); clearInterval(refreshTimer) }
  }, [loadOverview, loadSparklines])

  // SSE 实时事件流
  useEffect(() => {
    const connect = () => {
      if (esRef.current) esRef.current.close()
      // 页面不可见时不建立连接，避免后台无效重连
      if (document.visibilityState !== 'visible') return
      const es = new EventSource('/api/events/stream')
      esRef.current = es
      setStreamStatus('连接中…')
      es.addEventListener('open', () => setStreamStatus('● 已连接'))
      es.addEventListener('ping', () => setStreamStatus('● 已连接'))
      es.addEventListener('app_event', (e) => {
        try {
          const ev = JSON.parse(e.data) as RecentEvent
          setEvents(prev => [ev, ...prev].slice(0, 100))
        } catch { /* 忽略解析错误 */ }
      })
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

  // ========== 渲染 ==========
  return (
    <div className="page-container">
      <Spin spinning={loading}>
        {/* 统计卡 + Sparkline */}
        <StatCardsSection overview={overview} sparklines={sparklines} onNavigate={navigate} />

        {/* 业务 KPI 卡：米其林星级 + 涨跌 */}
        <KpiSection kpiCards={kpiCards} />

        {/* 异常雷达：折叠式 */}
        <AlertRadar
          alertData={alertData}
          alertOpen={alertOpen}
          onToggle={handleToggleAlert}
          onReload={loadAlert}
        />

        {/* 事件流 + 系统状态 */}
        <EventStreamSection
          events={events}
          streamStatus={streamStatus}
          overview={overview}
          onNavigate={navigate}
        />

        {/* 价格直方图 + 任务筛选 + AI 分析 */}
        <PriceHistogramCard
          histogram={histogram}
          histoTaskId={histoTaskId}
          histoTasks={histoTasks}
          aiAnalysis={aiAnalysis}
          aiLoading={aiLoading}
          onHistoTaskChange={handleHistoTaskChange}
          onAiAnalyze={handleAiAnalyze}
          onClearAiAnalysis={handleClearAiAnalysis}
          onNavigate={navigate}
        />

        {/* 可视化配置入口 */}
        <Card style={{ marginTop: 16 }} title="可视化配置入口">
          <Row gutter={[16, 16]}>
            <Col xs={12} md={6}>
              <Card className="quick-entry-card" size="small" onClick={() => navigate('/tasks/new')}>
                <QuickEntryIcon type="task" size={48} />
                <div style={{ fontWeight: 600, marginBottom: 4 }}>任务创建</div>
                <div style={{ fontSize: 12, color: '#8c8c8c' }}>向导式配置</div>
              </Card>
            </Col>
            <Col xs={12} md={6}>
              <Card className="quick-entry-card" size="small" onClick={() => navigate('/config/price')}>
                <QuickEntryIcon type="price" size={48} />
                <div style={{ fontWeight: 600, marginBottom: 4 }}>价格策略</div>
                <div style={{ fontSize: 12, color: '#8c8c8c' }}>滑块 + 预览</div>
              </Card>
            </Col>
            <Col xs={12} md={6}>
              <Card className="quick-entry-card" size="small" onClick={() => navigate('/config/eval')}>
                <QuickEntryIcon type="eval" size={48} />
                <div style={{ fontWeight: 600, marginBottom: 4 }}>评估规则</div>
                <div style={{ fontSize: 12, color: '#8c8c8c' }}>雷达图可视化</div>
              </Card>
            </Col>
            <Col xs={12} md={6}>
              <Card className="quick-entry-card" size="small" onClick={() => navigate('/config/notifier')}>
                <QuickEntryIcon type="notifier" size={48} />
                <div style={{ fontWeight: 600, marginBottom: 4 }}>通知渠道</div>
                <div style={{ fontSize: 12, color: '#8c8c8c' }}>拖拽排序</div>
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
        onClose={() => setTrendOpen(false)}
        onRangeChange={setTrendRange}
      />
    </div>
  )
}
