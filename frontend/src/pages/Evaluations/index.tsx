import { useEffect, useState, useCallback, useRef } from 'react'
import {
  Card, Table, Tag, Button, Space, Spin, Input, Select, Slider, Row, Col, message,
  Empty, DatePicker, Modal, Collapse, Statistic, Image, Tooltip, Alert, Progress,
} from 'antd'
import {
  ReloadOutlined, AimOutlined, RobotOutlined, LinkOutlined,
  SearchOutlined, UndoOutlined, RetweetOutlined, EnvironmentOutlined,
  ClockCircleOutlined, UserOutlined, PictureOutlined,
  CheckCircleOutlined, CloseCircleOutlined, WarningOutlined,
  CloudDownloadOutlined, GlobalOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { evalApi, aiApi, taskApi, type EvalItem, type AIConditionResult, type Task, type OfficialCollectResult } from '../../api'
import { RISK_LEVEL_CONFIG } from '../../constants/riskLevels'
import { isDataInsufficient, getInsufficientReason, type DistResponse, type SellerTrendData } from './utils'
import { usePersistentState } from '../../hooks/usePersistentState'
import EvalHeatmap from './components/EvalHeatmap'
import ResultBarChart from './components/ResultBarChart'
import PriceHistogram from './components/PriceHistogram'
import TrendSparkline from './components/TrendSparkline'

const { RangePicker } = DatePicker

// === 响应式断点（与 Ant Design 默认一致） ===
// xs < 576, sm ≥ 576, md ≥ 768, lg ≥ 992, xl ≥ 1200, xxl ≥ 1600
// 评估明细页主要面向桌面端，移动端走横向滚动 + 列隐藏
const SCROLL_X = 1610

// 把任意时间格式化为 zh-CN 友好的本地时间；无法解析时返回 null
function formatPublishTime(raw: string | number | null | undefined): string | null {
  if (raw === null || raw === undefined || raw === '') return null
  const d = new Date(raw)
  if (isNaN(d.getTime())) return null
  return d.toLocaleString('zh-CN', { hour12: false })
}

// 缩略图兜底：URL 为空或加载失败时显示占位符
function ThumbCell({ url, title }: { url?: string | null; title?: string | null }) {
  const [errored, setErrored] = useState(false)
  if (!url || errored) {
    return (
      <div
        style={{
          width: 50, height: 50, borderRadius: 6,
          background: '#f5f5f5', color: 'var(--xh-text-quaternary)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
        title={title || '暂无图片'}
      >
        <PictureOutlined style={{ fontSize: 20 }} />
      </div>
    )
  }
  return (
    <Image
      src={url}
      referrerPolicy="no-referrer"
      width={50}
      height={50}
      style={{ objectFit: 'cover', borderRadius: 6, background: 'var(--xh-bg-code)' }}
      preview={{ mask: '预览' }}
      onError={() => setErrored(true)}
      alt={title || ''}
    />
  )
}

export default function Evaluations() {
  // === 列表数据 ===
  const [items, setItems] = useState<EvalItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)

  // === 查询条件 ===
  const [itemId, setItemId] = useState<string>('')
  const [taskId, setTaskId] = useState<string>('')
  const [tasks, setTasks] = useState<Task[]>([])
  const [scoreRange, setScoreRange] = useState<[number, number]>([0, 100])
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null)

  // === 分页 ===
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = usePersistentState<number>('xh.evals.pageSize', 20, {
    validator: (v): v is number => typeof v === 'number' && v > 0 && Number.isFinite(v),
  })

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

  // === 阈值通过率计算器 ===
  const [thresholdValue, setThresholdValue] = useState(60)
  const [targetPassRate, setTargetPassRate] = useState(70)

  // === 批量 AI 评估 ===
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [batchEvaluating, setBatchEvaluating] = useState(false)
  const [batchProgress, setBatchProgress] = useState({ done: 0, total: 0 })

  // === 官方页面采集+评估 ===
  // 单条采集 loading 状态（按 item_id 索引，支持多行独立 loading）
  const [collecting, setCollecting] = useState<Record<string, boolean>>({})
  // 采集结果弹窗
  const [collectResult, setCollectResult] = useState<OfficialCollectResult | null>(null)
  const [collectModalOpen, setCollectModalOpen] = useState(false)
  // 批量官方采集
  const [batchCollecting, setBatchCollecting] = useState(false)
  const [batchCollectProgress, setBatchCollectProgress] = useState({ done: 0, total: 0 })

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

  // === 阈值通过率计算：当前页面评分 >= 阈值的比例 ===
  const thresholdPassCount = items.filter(item => (item.payload.score ?? 0) >= thresholdValue).length
  const thresholdPassRate = items.length > 0 ? (thresholdPassCount / items.length * 100) : 0

  // 根据目标通过率自动推算建议阈值（从当前页面数据降序排列取分位点）
  const computeSuggestedThreshold = (targetRate: number): number => {
    if (items.length === 0) return 0
    const sortedScores = [...items.map(item => item.payload.score ?? 0)].sort((a, b) => b - a)
    const targetCount = Math.ceil(items.length * targetRate / 100)
    return sortedScores[Math.min(targetCount - 1, sortedScores.length - 1)] ?? 0
  }
  const autoSuggestedThreshold = computeSuggestedThreshold(targetPassRate)

  // === 批量 AI 成色评估 ===
  const onBatchAIEval = async () => {
    // 从选中行中提取 item_id
    const ids = items
      .filter(item => selectedRowKeys.includes(`${item.item_id}-${item.created_at}`))
      .map(item => item.item_id)
    if (ids.length === 0) return

    setBatchEvaluating(true)
    setBatchProgress({ done: 0, total: ids.length })

    let done = 0
    for (const id of ids) {
      try {
        await aiApi.evaluateCondition(id)
      } catch {
        // 单个失败不中断整体流程，继续评估下一项
      }
      done++
      setBatchProgress({ done, total: ids.length })
    }

    setBatchEvaluating(false)
    setSelectedRowKeys([])
    message.success(`批量评估完成，共处理 ${ids.length} 项`)
    load()
  }

  // === 官方页面采集+评估（单条）===
  // 访问闲鱼官方商品详情页+卖家主页，用完整数据重新评估
  const onCollectOfficial = async (r: EvalItem) => {
    const itemId = r.item_id
    setCollecting((prev) => ({ ...prev, [itemId]: true }))
    try {
      const result = await evalApi.collectOfficial(itemId, r.task_id)
      setCollectResult(result)
      setCollectModalOpen(true)
      message.success(`官方采集评估完成，评分：${result.evaluation.score ?? 'N/A'}`)
      load()  // 刷新列表以展示更新后的评估结果
    } catch (err: unknown) {
      const error = err as { response?: { status?: number; data?: { detail?: string } } }
      const status = error?.response?.status
      const detail = error?.response?.data?.detail
      if (status === 503) {
        message.error(detail || '官方采集需要浏览器实例，请以 XH_WITH_SCHEDULER=1 模式启动')
      } else if (status === 403) {
        // 403 表示闲鱼 Cookie 失效（非系统登录失效），不能用 401 以免触发 axios 全局登出
        message.error(detail || '闲鱼登录已过期，请重新登录闲鱼')
      } else if (status === 502) {
        message.error(detail || '浏览器连接异常，请重启服务后重试')
      } else {
        message.error(detail || '官方采集失败，请稍后重试')
      }
    } finally {
      setCollecting((prev) => ({ ...prev, [itemId]: false }))
    }
  }

  // === 批量官方采集+评估 ===
  // 逐个调用单条端点以展示实时进度，单个失败不中断
  const onBatchCollectOfficial = async () => {
    const ids = items
      .filter(item => selectedRowKeys.includes(`${item.item_id}-${item.created_at}`))
      .map(item => item.item_id)
    if (ids.length === 0) return

    setBatchCollecting(true)
    setBatchCollectProgress({ done: 0, total: ids.length })

    let done = 0
    let succeeded = 0
    let failed = 0
    for (const id of ids) {
      try {
        await evalApi.collectOfficial(id)
        succeeded++
      } catch {
        // 单个失败不中断，继续采集下一项
        failed++
      }
      done++
      setBatchCollectProgress({ done, total: ids.length })
    }

    setBatchCollecting(false)
    setSelectedRowKeys([])
    message.success(`批量官方采集完成：成功 ${succeeded}，失败 ${failed}`)
    load()
  }

  // 加载评估列表
  // 用 ref 持有筛选条件最新值，避免每次键入触发 API 请求
  const filtersRef = useRef({ itemId, taskId, scoreRange, dateRange })
  filtersRef.current = { itemId, taskId, scoreRange, dateRange }

  const load = useCallback(() => {
    setLoading(true)
    const { itemId: fItemId, taskId: fTaskId, scoreRange: fScore, dateRange: fDate } = filtersRef.current
    const params: Record<string, unknown> = {
      page_num: page,
      page_size: pageSize,
      limit: pageSize * 4,
    }
    if (fItemId) params.item_id = fItemId
    if (fTaskId) params.task_id = fTaskId
    if (fScore[0] > 0) params.min_score = fScore[0]
    if (fScore[1] < 100) params.max_score = fScore[1]
    if (fDate && fDate[0]) params.start_time = fDate[0].format('YYYY-MM-DD')
    if (fDate && fDate[1]) params.end_time = fDate[1].format('YYYY-MM-DD')

    evalApi.list(params)
      .then((res) => {
        setItems(res.items || [])
        setTotal(res.total || res.count || 0)
      })
      .catch(() => message.error('加载评估列表失败'))
      .finally(() => setLoading(false))
  }, [page, pageSize])

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
  // 加载任务列表（供下拉选择器使用）
  useEffect(() => {
    taskApi.list({ limit: 200 }).then((res) => {
      setTasks(res.items || [])
    }).catch(() => {})
  }, [])

  // 查询/重置
  // 修复：之前 setPage(1) + load() 会用旧 page 闭包加载一次，导致双重请求
  // 改为：page 变化时由 useEffect 自动触发 load；page 未变时手动调用 load
  const onSearch = () => {
    if (page !== 1) {
      setPage(1)  // useEffect 会自动触发 load（filtersRef.current 已是最新）
    } else {
      load()
    }
  }
  const onReset = () => {
    setItemId(''); setTaskId(''); setScoreRange([0, 100]); setDateRange(null)
    // 重置后需要用新条件重新加载
    filtersRef.current = { itemId: '', taskId: '', scoreRange: [0, 100] as [number, number], dateRange: null }
    if (page !== 1) {
      setPage(1)  // useEffect 会自动触发 load
    } else {
      load()
    }
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

  // P3: 评估准确率反馈——写入 events.payload.feedback，用于阈值自动优化
  // 反馈类型：accurate（准确）/ inaccurate（不准确）/ partial（部分准确）
  const [feedbackSubmitting, setFeedbackSubmitting] = useState<Record<string, boolean>>({})
  const onFeedback = async (r: EvalItem, feedback: 'accurate' | 'inaccurate' | 'partial') => {
    const itemId = r.item_id
    const taskId = r.task_id
    setFeedbackSubmitting((prev) => ({ ...prev, [itemId]: true }))
    try {
      await evalApi.submitFeedback(itemId, feedback, undefined, taskId)
      // 本地同步更新 payload.feedback，避免重新拉取列表
      setItems((prev) =>
        prev.map((it) =>
          it.item_id === itemId && it.created_at === r.created_at
            ? { ...it, payload: { ...it.payload, feedback } }
            : it,
        ),
      )
      message.success('反馈已提交，感谢您的评价')
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 404) {
        message.error('评估记录不存在，可能已被重新计算')
      } else {
        message.error('反馈提交失败')
      }
    } finally {
      setFeedbackSubmitting((prev) => ({ ...prev, [itemId]: false }))
    }
  }

  // 卖家价格趋势
  const [trendError, setTrendError] = useState<Record<string, string>>({})
  const loadSellerTrend = async (itemId: string) => {
    if (trendCache[itemId]) return
    setTrendLoading(itemId)
    setTrendError((prev) => ({ ...prev, [itemId]: '' }))
    try {
      const data: SellerTrendData = await evalApi.sellerTrend(itemId)
      setTrendCache((prev) => ({ ...prev, [itemId]: data }))
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      // 404: 商品未入库或无卖家信息
      if (msg.includes('404') || msg.includes('未找到')) {
        setTrendError((prev) => ({ ...prev, [itemId]: '该商品未入库，无法查询卖家趋势' }))
      } else {
        setTrendError((prev) => ({ ...prev, [itemId]: '加载失败：' + msg.slice(0, 50) }))
      }
    } finally {
      setTrendLoading('')
    }
  }

  // === 表格列定义（与商品列表页对齐） ===
  // 列宽考虑响应式：固定宽度列（任务ID/图片/价格/想要/评分/风险/AI）保留，
  // 自适应列（标题/卖家）通过 ellipsis 处理；窄屏下整体走横向滚动
  const columns = [
    {
      title: '任务ID', dataIndex: 'task_id', key: 'task_id', width: 120,
      ellipsis: true,
      // 任务 ID 在窄屏下隐藏，避免占用关键展示位
      responsive: ['sm'] as ('sm' | 'md')[],
      render: (v: string) => <Tooltip title={v}>{v?.slice(0, 10)}...</Tooltip>,
    },
    {
      title: '图片', key: 'thumb', width: 70,
      render: (_: unknown, r: EvalItem) => {
        const url = r.payload?.thumb_url as string | undefined
        return <ThumbCell url={url} title={r.payload?.item_title as string | undefined} />
      },
    },
    {
      title: '标题', key: 'title', ellipsis: true,
      // 标题列在极窄屏保留 ellipsis + tooltip，宽屏完整显示
      render: (_: unknown, r: EvalItem) => {
        const title = r.payload?.item_title || '—'
        const url = `https://www.goofish.com/item?id=${r.item_id}`
        return (
          <Tooltip title={title}>
            <a href={url} target="_blank" rel="noopener noreferrer">
              {title} <LinkOutlined />
            </a>
          </Tooltip>
        )
      },
    },
    {
      title: '价格', key: 'price', width: 90,
      sorter: (a: EvalItem, b: EvalItem) =>
        (a.payload?.item_price ?? 0) - (b.payload?.item_price ?? 0),
      render: (_: unknown, r: EvalItem) => r.payload?.item_price != null
        ? <span style={{ color: '#f5222d', fontWeight: 600 }}>¥{Number(r.payload.item_price).toFixed(2)}</span>
        : <span style={{ color: 'var(--xh-text-quaternary)' }}>—</span>,
    },
    {
      // 卖家列：参考闲鱼商品详情页风格，昵称+信用度合并显示
      // 视觉权重：昵称 > 信用度；缺数据时显示 ID 后备文案，避免空荡荡
      title: '卖家', key: 'seller', width: 170, ellipsis: true,
      render: (_: unknown, r: EvalItem) => {
        const nick = r.payload?.seller_nick as string | undefined
        const id = r.payload?.seller_id as string | undefined
        const credit = r.payload?.seller_credit as string | undefined
        // 真实昵称优先级：清洗后的 seller_nick > seller_id（截短）> '—'
        const hasNick = !!(nick && nick.trim())
        const displayName = hasNick
          ? nick
          : (id ? `用户 ${id.slice(0, 8)}` : '—')
        return (
          <div style={{ lineHeight: 1.3 }}>
            <div>
              <UserOutlined style={{ marginRight: 4, color: hasNick ? '#1890ff' : 'var(--xh-text-quaternary)' }} />
              <Tooltip title={hasNick ? nick : (id || '无卖家信息')}>
                <span>{displayName}</span>
              </Tooltip>
            </div>
            {credit && (
              <div style={{ fontSize: 11, color: '#52c41a', marginTop: 2 }}>
                信用 {credit}
              </div>
            )}
          </div>
        )
      },
    },
    {
      // 地区列：优先用后端清洗后的 region；空值显示"—"避免布局跳动
      title: '地区', key: 'region', width: 90,
      render: (_: unknown, r: EvalItem) => {
        const region = r.payload?.region as string | undefined
        if (!region) return <span style={{ color: 'var(--xh-text-quaternary)' }}>—</span>
        return (
          <span>
            <EnvironmentOutlined style={{ marginRight: 4, color: '#fa8c16' }} />
            {region}
          </span>
        )
      },
    },
    {
      // 想要数：仅在有数据时显示，无数据灰色"—"
      title: '想要', key: 'want', width: 60,
      render: (_: unknown, r: EvalItem) => {
        const w = r.payload?.want_cnt as number | undefined
        return w != null ? <span>{w}</span> : <span style={{ color: 'var(--xh-text-quaternary)' }}>—</span>
      },
    },
    {
      // 发布时间列：优先级 = 完整时间戳 > 历史数据中的发布时间短语 > '—'
      // 兜底显示"一周内发布"等从 seller_nick 脏数据中恢复的原文
      title: '发布时间', key: 'publish', width: 160,
      // 窄屏下隐藏发布时间（信息密度高，窄屏优先看评分/风险）
      responsive: ['md'] as ('sm' | 'md')[],
      render: (_: unknown, r: EvalItem) => {
        const formatted = formatPublishTime(r.payload?.publish_time as string | undefined)
        if (formatted) {
          return (
            <Tooltip title={formatted}>
              <span>
                <ClockCircleOutlined style={{ marginRight: 4, color: '#1890ff' }} />
                {formatted}
              </span>
            </Tooltip>
          )
        }
        // 兜底：从脏数据中恢复的发布时间短语（如"一周内发布"）
        const text = r.payload?.publish_time_text as string | undefined
        if (text) {
          return <span style={{ color: '#faad14' }}>{text}</span>
        }
        return <span style={{ color: 'var(--xh-text-quaternary)' }}>—</span>
      },
    },
    {
      title: '成色', key: 'condition', width: 110,
      filters: [
        { text: '全新', value: '全新' },
        { text: '近全新', value: '近全新' },
        { text: '正常使用', value: '正常使用' },
        { text: '明显使用', value: '明显使用' },
        { text: '有故障/维修', value: '有故障/维修' },
        { text: '未注明', value: '未注明' },
        { text: '未知', value: '未知' },
      ],
      onFilter: (val: unknown, r: EvalItem) => r.condition_label === val,
      render: (_: unknown, r: EvalItem) => {
        const label = r.condition_label || '未知'
        const score = r.condition_score || 0
        // 颜色：全新=绿、近全新=蓝、正常使用=灰、明显使用=橙、故障=红
        const colorMap: Record<string, string> = {
          '全新': 'green',
          '近全新': 'cyan',
          '正常使用': 'default',
          '明显使用': 'orange',
          '有故障/维修': 'red',
          '未注明': 'default',
          '未知': 'default',
        }
        return (
          <div>
            <Tag color={colorMap[label] || 'default'}>{label}</Tag>
            {score !== 0 && (
              <span style={{ fontSize: 11, marginLeft: 4, color: score > 0 ? '#52c41a' : '#ff4d4f' }}>
                {score > 0 ? `+${score}` : score}分
              </span>
            )}
          </div>
        )
      },
    },
    {
      title: '成色标签', key: 'condition_tags', width: 150,
      render: (_: unknown, r: EvalItem) => {
        const tags = r.condition_tags || []
        if (tags.length === 0) return '—'
        // 显示具体命中的关键词（限制最多 3 个，避免列表过长）
        return (
          <span style={{ fontSize: 11 }}>
            {tags.slice(0, 3).map((t, i) => (
              <Tag key={i} style={{ marginBottom: 2 }} color="blue">{t.label}</Tag>
            ))}
            {tags.length > 3 && <span style={{ color: 'var(--xh-text-tertiary)' }}>+{tags.length - 3}</span>}
          </span>
        )
      },
    },
    {
      title: '评分', key: 'score', width: 80,
      sorter: (a: EvalItem, b: EvalItem) => (a.payload.score ?? 0) - (b.payload.score ?? 0),
      render: (_: unknown, r: EvalItem) => {
        if (isDataInsufficient(r)) {
          // 方案C改进：显示具体原因而非笼统的"数据不足"
          return <Tag color="default">{getInsufficientReason(r)}</Tag>
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
        const cfg = RISK_LEVEL_CONFIG[level] || RISK_LEVEL_CONFIG.unknown
        return <Tag color={cfg.color}>{cfg.label}</Tag>
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
    {
      // 官方采集：访问闲鱼官方商品详情页+卖家主页，用完整数据重新评估
      // 解决本地采集数据有限的问题，获取权威数据提升评估准确性
      title: '官方采集', key: 'collect', width: 90,
      render: (_: unknown, r: EvalItem) => (
        <Tooltip title="访问闲鱼官方页面采集完整数据并重新评估">
          <Button
            size="small"
            type="default"
            icon={<CloudDownloadOutlined />}
            loading={collecting[r.item_id]}
            onClick={() => onCollectOfficial(r)}
          />
        </Tooltip>
      ),
    },
    {
      // P3: 评估准确率反馈列——三档反馈按钮，已反馈时高亮当前选项
      title: '反馈', key: 'feedback', width: 110,
      render: (_: unknown, r: EvalItem) => {
        const current = r.payload?.feedback as 'accurate' | 'inaccurate' | 'partial' | undefined
        const submitting = feedbackSubmitting[r.item_id]
        const btn = (
          type: 'accurate' | 'inaccurate' | 'partial',
          icon: React.ReactNode,
          color: string,
          title: string,
        ) => (
          <Tooltip title={title}>
            <Button
              size="small"
              type={current === type ? 'primary' : 'text'}
              ghost={current === type}
              icon={icon}
              loading={submitting}
              onClick={() => onFeedback(r, type)}
              style={current === type ? { background: color, borderColor: color } : { color }}
            />
          </Tooltip>
        )
        return (
          <Space size={2}>
            {btn('accurate', <CheckCircleOutlined />, '#52c41a', '准确')}
            {btn('partial', <WarningOutlined />, '#faad14', '部分准确')}
            {btn('inaccurate', <CloseCircleOutlined />, '#ff4d4f', '不准确')}
          </Space>
        )
      },
    },
  ]

  // 展开行：卖家价格趋势（委托给 TrendSparkline 组件）
  const expandedRowRender = (r: EvalItem) => (
    <TrendSparkline
      trend={trendCache[r.item_id]}
      loading={trendLoading === r.item_id}
      error={trendError[r.item_id]}
      onLoad={() => loadSellerTrend(r.item_id)}
    />
  )

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
          <Select
            placeholder="选择任务" allowClear showSearch
            style={{ width: 260 }}
            value={taskId || undefined}
            onChange={(v) => { setTaskId(v || ''); setPage(1); setTimeout(load, 0) }}
            onClear={() => setTaskId('')}
            filterOption={(input, option) =>
              (option?.label as string ?? '').toLowerCase().includes(input.toLowerCase())
            }
            options={tasks.map((t) => ({
              label: `${t.name}（${t.keyword}）`,
              value: t.id,
            }))}
            notFoundContent="暂无任务"
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

      {/* 方案C改进：数据不足时显示引导提示 */}
      {dist && dist.insufficient_count > 0 && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message={`有 ${dist.insufficient_count} 条评估记录因卖家信息缺失仅基于价格评估`}
          description="建议在 Dashboard 页面重新登录闲鱼后，点击上方「重新评估」按钮获取完整评估结果。"
        />
      )}

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
            <Card size="small"><Statistic title="数据不足" value={dist.insufficient_count} valueStyle={{ color: 'var(--xh-text-tertiary)' }} /></Card>
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
            {/* 批量操作工具条：选中行后显示 */}
            {selectedRowKeys.length > 0 && (
              <Alert
                type="info"
                showIcon
                style={{ marginBottom: 12 }}
                message={
                  <Space>
                    <span>已选择 <b>{selectedRowKeys.length}</b> 项</span>
                    <Button
                      type="primary"
                      size="small"
                      icon={<RobotOutlined />}
                      loading={batchEvaluating}
                      onClick={onBatchAIEval}
                    >
                      批量 AI 评估 ({selectedRowKeys.length} 项)
                    </Button>
                    <Button
                      size="small"
                      icon={<CloudDownloadOutlined />}
                      loading={batchCollecting}
                      onClick={onBatchCollectOfficial}
                    >
                      批量官方采集 ({selectedRowKeys.length} 项)
                    </Button>
                    <Button size="small" onClick={() => setSelectedRowKeys([])}>取消选择</Button>
                  </Space>
                }
                description={(batchEvaluating || batchCollecting) && (
                  <Progress
                    percent={Math.round(
                      (batchCollecting ? batchCollectProgress.done : batchProgress.done) /
                      (batchCollecting ? batchCollectProgress.total : batchProgress.total) * 100
                    )}
                    size="small"
                    format={() =>
                      `${batchCollecting ? batchCollectProgress.done : batchProgress.done}/${batchCollecting ? batchCollectProgress.total : batchProgress.total}`
                    }
                  />
                )}
              />
            )}
            <Spin spinning={loading}>
              {items.length === 0 ? (
                <Empty description="暂无评估数据" />
              ) : (
                <Table
                  columns={columns}
                  dataSource={items}
                  rowKey={(r) => `${r.item_id}-${r.created_at}`}
                  size="middle"
                  rowSelection={{
                    selectedRowKeys,
                    onChange: (keys) => setSelectedRowKeys(keys),
                  }}
                  // 横向滚动：保证窄屏（< SCROLL_X）下所有列仍可访问；
                  // 列上的 responsive 会在 >= sm/md 时自动展开
                  scroll={{ x: SCROLL_X }}
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
                    // 极窄屏隐藏快速跳转，避免按钮溢出
                    showLessItems: true,
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
          <EvalHeatmap
            dist={dist}
            distRange={distRange}
            distLoading={distLoading}
            onRangeChange={setDistRange}
          />

          <ResultBarChart dist={dist} passScore={passScore} autoBuyScore={autoBuyScore} />

          <PriceHistogram dist={dist} />

          {/* 阈值建议 */}
          <Card title="阈值建议">
            <div style={{ marginBottom: 8 }}>目标通过率：{thresholdTarget}%</div>
            <Slider value={thresholdTarget} onChange={(v) => setThresholdTarget(v)} min={10} max={90} step={5} />
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

          {/* 阈值通过率计算器：拖动阈值滑块实时查看通过率 */}
          <Card title="阈值通过率计算器" style={{ marginTop: 16 }}>
            <div style={{ marginBottom: 8 }}>
              当前阈值：<b style={{ color: '#1890ff' }}>{thresholdValue}</b> 分
            </div>
            <Slider
              value={thresholdValue}
              onChange={setThresholdValue}
              min={0} max={100} step={1}
              marks={{ 0: '0', 60: '60', 80: '80', 100: '100' }}
            />
            <Row gutter={16} style={{ marginTop: 12 }}>
              <Col span={8}>
                <Statistic
                  title="通过率"
                  value={thresholdPassRate.toFixed(1)}
                  suffix="%"
                  valueStyle={{ color: thresholdPassRate >= 60 ? '#52c41a' : '#ff4d4f' }}
                />
              </Col>
              <Col span={8}>
                <Statistic title="通过数" value={thresholdPassCount} valueStyle={{ color: '#1890ff' }} />
              </Col>
              <Col span={8}>
                <Statistic title="总数" value={items.length} />
              </Col>
            </Row>

            {/* 目标通过率：设定目标后自动推算建议阈值 */}
            <div style={{ marginTop: 20, paddingTop: 12, borderTop: '1px solid #f0f0f0' }}>
              <div style={{ marginBottom: 8 }}>
                目标通过率：<b style={{ color: '#faad14' }}>{targetPassRate}%</b>
              </div>
              <Slider
                value={targetPassRate}
                onChange={setTargetPassRate}
                min={10} max={100} step={5}
                marks={{ 10: '10%', 50: '50%', 70: '70%', 100: '100%' }}
              />
              <div style={{ marginTop: 8, padding: 12, background: 'rgba(250, 140, 22, 0.08)', borderRadius: 4 }}>
                <div>建议阈值：<b style={{ color: '#fa8c16' }}>{autoSuggestedThreshold.toFixed(1)}</b> 分</div>
                <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)' }}>
                  即评分 ≥ {autoSuggestedThreshold.toFixed(1)} 时，约 {targetPassRate}% 的评估可通过
                </div>
              </div>
            </div>
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
              {/* 同类物品价格区间（捡漏价格参考）
                  后端在 AI 评估时查询同类已售商品价格区间并注入评估逻辑，
                  此处展示价格区间供用户判断当前商品价格是否合理可拾。
                  当无数据时显示友好提示，不阻断评估流程。 */}
              {aiResult.price_range && aiResult.price_range.sample_size > 0 ? (
                <div style={{
                  marginBottom: 12, padding: 12, borderRadius: 6,
                  background: 'rgba(82, 196, 26, 0.06)', border: '1px solid #d9f7be',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <strong style={{ color: '#389e0d' }}>同类物品价格参考</strong>
                    <Tag color="green" style={{ fontSize: 11 }}>
                      {aiResult.price_range.source_label || aiResult.price_range.source}
                    </Tag>
                  </div>
                  <Row gutter={8}>
                    <Col span={8}>
                      <Statistic
                        title="捡漏价格"
                        value={aiResult.price_range.bargain_price != null ? `¥${aiResult.price_range.bargain_price}` : '—'}
                        valueStyle={{ color: '#52c41a', fontSize: 18 }}
                      />
                    </Col>
                    <Col span={8}>
                      <Statistic
                        title="价格区间"
                        value={aiResult.price_range.min_price != null && aiResult.price_range.max_price != null
                          ? `¥${aiResult.price_range.min_price}~${aiResult.price_range.max_price}`
                          : '—'}
                        valueStyle={{ fontSize: 14 }}
                      />
                    </Col>
                    <Col span={8}>
                      <Statistic
                        title="中位数"
                        value={aiResult.price_range.median_price != null ? `¥${aiResult.price_range.median_price}` : '—'}
                        valueStyle={{ fontSize: 14 }}
                      />
                    </Col>
                  </Row>
                  <div style={{ marginTop: 8, fontSize: 12, color: 'var(--xh-text-tertiary)' }}>
                    样本数：{aiResult.price_range.sample_size}
                    {aiResult.price_range.range_days ? ` · 近${aiResult.price_range.range_days}天` : ''}
                    {' · 低于捡漏价格的商品可能为真捡漏，也需警惕假货风险'}
                  </div>
                </div>
              ) : (
                <Alert
                  type="info"
                  showIcon
                  style={{ marginBottom: 12 }}
                  message="暂无同类物品价格参考"
                  description={aiResult.price_range?.message || '当前商品无关联任务或暂无已售数据，建议先执行实时搜索采集更多商品以获取价格参考。'}
                />
              )}
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
              <div style={{ marginTop: 12, fontSize: 12, color: 'var(--xh-text-tertiary)' }}>
                来源：{aiResult.source === 'llm' ? 'AI 视觉分析' : '规则模拟'}
                {aiResult.cached ? '（缓存）' : ''}
              </div>
            </div>
          ) : (
            !aiLoading && <Empty description="点击评估按钮开始 AI 分析" />
          )}
        </Spin>
      </Modal>

      {/* 官方采集结果弹窗：展示从闲鱼官方页面采集的完整数据 + 重新评估结果 */}
      <Modal
        title={
          <Space>
            <GlobalOutlined style={{ color: '#1890ff' }} />
            <span>官方采集结果 - {collectResult?.item_id}</span>
            <Tag color="blue">官方数据</Tag>
          </Space>
        }
        open={collectModalOpen}
        onCancel={() => setCollectModalOpen(false)}
        footer={<Button onClick={() => setCollectModalOpen(false)}>关闭</Button>}
        width={720}
      >
        {collectResult && (
          <div>
            {/* 评估结果摘要 */}
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col span={6}>
                <Card size="small">
                  <Statistic
                    title="评估评分"
                    value={collectResult.evaluation.score ?? 'N/A'}
                    valueStyle={{
                      color: collectResult.evaluation.score != null
                        ? (collectResult.evaluation.score >= 80 ? '#52c41a'
                          : collectResult.evaluation.score >= 60 ? '#faad14' : '#ff4d4f')
                        : '#999',
                      fontSize: 24,
                    }}
                  />
                </Card>
              </Col>
              <Col span={6}>
                <Card size="small">
                  <Statistic
                    title="风险等级"
                    value={collectResult.evaluation.risk_level}
                    valueStyle={{ fontSize: 16 }}
                  />
                </Card>
              </Col>
              <Col span={6}>
                <Card size="small">
                  <Statistic
                    title="数据质量"
                    value={collectResult.evaluation.data_quality}
                    valueStyle={{ fontSize: 16 }}
                  />
                </Card>
              </Col>
              <Col span={6}>
                <Card size="small">
                  <Statistic
                    title="是否通过"
                    value={collectResult.evaluation.is_passed ? '通过' : '未通过'}
                    valueStyle={{
                      color: collectResult.evaluation.is_passed ? '#52c41a' : '#ff4d4f',
                      fontSize: 16,
                    }}
                  />
                </Card>
              </Col>
            </Row>

            {/* 商品基本信息 */}
            <Card title="商品信息" size="small" style={{ marginBottom: 12 }}>
              <Row gutter={[8, 8]}>
                <Col span={12}><strong>标题：</strong>{collectResult.item.title || '—'}</Col>
                <Col span={6}><strong>价格：</strong><span style={{ color: '#f5222d', fontWeight: 600 }}>¥{collectResult.item.price?.toFixed(2)}</span></Col>
                <Col span={6}><strong>地区：</strong>{collectResult.item.region || '—'}</Col>
                <Col span={6}><strong>想要数：</strong>{collectResult.item.want_cnt}</Col>
                <Col span={6}><strong>浏览数：</strong>{collectResult.item.view_cnt}</Col>
                <Col span={24}>
                  <strong>描述：</strong>
                  <p style={{ marginTop: 4, maxHeight: 100, overflow: 'auto', color: 'var(--xh-text-secondary)' }}>
                    {collectResult.item.description || '暂无描述'}
                  </p>
                </Col>
                {collectResult.item.image_urls.length > 0 && (
                  <Col span={24}>
                    <strong>商品图片：</strong>
                    <div style={{ display: 'flex', gap: 8, marginTop: 4, flexWrap: 'wrap' }}>
                      {collectResult.item.image_urls.slice(0, 6).map((url, i) => (
                        <Image
                          key={i}
                          src={url}
                          referrerPolicy="no-referrer"
                          width={80}
                          height={80}
                          style={{ objectFit: 'cover', borderRadius: 4 }}
                          alt={`图片${i + 1}`}
                        />
                      ))}
                    </div>
                  </Col>
                )}
              </Row>
            </Card>

            {/* 卖家信息 */}
            <Card title="卖家信息" size="small" style={{ marginBottom: 12 }}>
              <Row gutter={[8, 8]}>
                <Col span={8}><strong>昵称：</strong>{collectResult.seller.nick || '—'}</Col>
                <Col span={8}><strong>信用分：</strong>{collectResult.seller.credit_score ?? '—'}</Col>
                <Col span={8}><strong>注册天数：</strong>{collectResult.seller.register_days}天</Col>
                <Col span={8}><strong>在售数：</strong>{collectResult.seller.on_sale_count}</Col>
                <Col span={8}><strong>已售数：</strong>{collectResult.seller.sold_count}</Col>
                <Col span={8}><strong>卖家ID：</strong>{collectResult.seller.id || '—'}</Col>
              </Row>
            </Card>

            {/* 评价信息 */}
            {collectResult.reviews.length > 0 && (
              <Card title={`评价/留言 (${collectResult.reviews.length})`} size="small" style={{ marginBottom: 12 }}>
                {collectResult.reviews.map((review, i) => (
                  <div key={i} style={{
                    padding: '6px 0', borderBottom: i < collectResult.reviews.length - 1 ? '1px solid #f0f0f0' : 'none',
                    fontSize: 13,
                  }}>
                    {review}
                  </div>
                ))}
              </Card>
            )}

            {/* 评估维度详情 */}
            <Card title="评估维度详情" size="small" style={{ marginBottom: 12 }}>
              <Row gutter={[8, 8]}>
                {Object.entries(collectResult.evaluation.dimension_scores).map(([dim, score]) => (
                  <Col key={dim} span={8}>
                    <Statistic
                      title={dim}
                      value={score}
                      valueStyle={{ fontSize: 16, color: score >= 70 ? '#52c41a' : score >= 40 ? '#faad14' : '#ff4d4f' }}
                    />
                  </Col>
                ))}
              </Row>
              {collectResult.evaluation.reject_reasons.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <strong>拒绝原因：</strong>
                  {collectResult.evaluation.reject_reasons.map((reason, i) => (
                    <Tag key={i} color="orange" style={{ marginBottom: 4 }}>{reason}</Tag>
                  ))}
                </div>
              )}
            </Card>

            <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', textAlign: 'center' }}>
              数据来源：闲鱼官方页面采集 · 采集时间：{new Date().toLocaleString('zh-CN', { hour12: false })}
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
