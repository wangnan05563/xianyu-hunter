import { useEffect, useState, useRef, useCallback } from 'react'
// 删除未使用的 theme 导入（S1128）
import { Spin, Card, Col, Row, Alert, Button, Space } from 'antd'
import { useNavigate } from 'react-router-dom'
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
  // 值从不变化，改用 const 替代 useState，避免无谓的状态管理（S6754）
  const trendMetric = 'events'
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
  const loadOverview = useCallback(() => {
    Promise.all([
      statsApi.overview().catch(() => null),
      statsApi.businessKpi(30).catch(() => ({ kpis: [], range_days: 30, generated_at: '' })),
      statsApi.recentEvents(15).catch(() => ({ events: [] })),
      priceApi.histogram({ bins: 20, task_id: histoTaskId === 'all' ? undefined : histoTaskId }).catch(() => null),
      taskApi.list({ limit: 100 }).catch(() => ({ items: [], total: 0 })),
    ]).then(([ov, kpi, ev, hist, tasks]) => {
      // 移除不必要的类型断言：API 返回类型已明确，TS 可正确推断（S4325）
      if (ov) setOverview(ov)
      setKpiCards(kpi.kpis || [])
      setEvents(ev.events || [])
      setHistogram(hist)
      const items = tasks.items || []
      setHistoTasks(items.filter(t => t.status !== 'deleted'))
      setLoading(false)
    })
  }, [histoTaskId])

  const loadSparklines = useCallback(() => {
    Promise.all([
      statsApi.trend({ metric: 'events', range_hours: 24 }).catch(() => null),
      statsApi.trend({ metric: 'orders', range_hours: 24 }).catch(() => null),
    ]).then(([tasks, orders]) => {
      // 移除不必要的类型断言：trend API 已返回 TrendSeries 类型（S4325）
      setSparklines({ tasks, orders })
    })
  }, [])

  const loadAlert = useCallback(async () => {
    try { setAlertData(await statsApi.today()) } catch { /* 静默 */ }
  }, [])

  // O-08-26 评估漏斗：独立加载，受 funnelRange 控制
  const loadFunnel = useCallback(async () => {
    setFunnelLoading(true)
    try {
      setFunnelData(await statsApi.evalFunnel(funnelRange))
    } catch {
      setFunnelData(null)
    } finally {
      setFunnelLoading(false)
    }
  }, [funnelRange])

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
    loadFunnel()
  }, [loadOverview, loadSparklines, loadAlert, loadFunnel])

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

  // SSE 实时事件流（O-14-26 断线重连回放）
  // 浏览器原生 EventSource 在自动重连时会携带 Last-Event-ID header，
  // 但本组件在 error 时手动 close + 重新 new EventSource，会丢失 lastEventId。
  // 因此用 localStorage 持久化 lastEventId，重连时作为 query 参数传递，
  // 后端 sse_stream.py 支持 ?last_event_id=xxx 补拉漏掉的事件。
  useEffect(() => {
    const LAST_EVENT_ID_KEY = 'xh.sse.lastEventId'
    const connect = () => {
      if (esRef.current) esRef.current.close()
      // 页面不可见时不建立连接，避免后台无效重连
      if (document.visibilityState !== 'visible') return
      // O-14-26：重连时从 localStorage 读取 lastEventId，附加到 URL
      // 后端会补拉 id > lastEventId 的事件，避免断网期间漏掉关键告警
      const lastId = localStorage.getItem(LAST_EVENT_ID_KEY)
      const url = lastId ? `/api/events/stream?last_event_id=${lastId}` : '/api/events/stream'
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
      es.addEventListener('app_event', (e) => {
        try {
          const ev = JSON.parse(e.data) as RecentEvent
          // O-14-26：记录 lastEventId 到 localStorage，供重连时补拉
          // MessageEvent 的 lastEventId 属性对应 SSE 帧的 id 字段
          if (e.lastEventId) {
            localStorage.setItem(LAST_EVENT_ID_KEY, e.lastEventId)
          }
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
                <Button size="small" type="primary" onClick={() => navigate('/tasks/new')}>
                  创建任务
                </Button>
                <Button size="small" onClick={() => navigate('/onboarding')}>
                  查看引导
                </Button>
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

        {/* 统计卡 + Sparkline */}
        <StatCardsSection overview={overview} sparklines={sparklines} onNavigate={navigate} />

        {/* 业务 KPI 卡：米其林星级 + 涨跌 */}
        <KpiSection kpiCards={kpiCards} />

        {/* O-08-26 评估漏斗 + 命中率/误报率 */}
        <EvalFunnelCard
          data={funnelData}
          loading={funnelLoading}
          rangeDays={funnelRange}
          onRangeChange={setFunnelRange}
        />

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
        onClose={() => setTrendOpen(false)}
        onRangeChange={setTrendRange}
      />
    </div>
  )
}
