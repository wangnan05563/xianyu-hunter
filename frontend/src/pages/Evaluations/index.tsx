import { useEffect, useState, useCallback, useRef, useMemo } from 'react'
import {
  Card, Table, Tag, Button, Space, Spin, Input, Select, Slider, Row, Col, message,
  Empty, DatePicker, Modal, Collapse, Statistic, Image, Tooltip, Alert, Progress,
  Descriptions, Tabs, InputNumber, Checkbox,
} from 'antd'
import {
  ReloadOutlined, AimOutlined, RobotOutlined, LinkOutlined,
  SearchOutlined, UndoOutlined, RetweetOutlined, EnvironmentOutlined,
  ClockCircleOutlined, UserOutlined, PictureOutlined,
  CheckCircleOutlined, CloseCircleOutlined, WarningOutlined,
  CloudDownloadOutlined, GlobalOutlined, SettingOutlined,
  ThunderboltOutlined, LeftOutlined, RightOutlined, CalculatorOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { evalApi, aiApi, taskApi, orderApi, itemApi, type EvalItem, type AIConditionResult, type DeepAnalyzeResult, type DeepCheckResult, type Task, type OfficialCollectResult } from '../../api'
import { RISK_LEVEL_CONFIG } from '../../constants/riskLevels'
import { isDataInsufficient, getInsufficientReason, type DistResponse, type SellerTrendData } from './utils'
import { translateDimension, translateRejectReason } from './dimensionLabels'
import { usePersistentState } from '../../hooks/usePersistentState'
import { useColumnConfig, type ColumnConfig } from '../../hooks/useColumnConfig'
import EvalHeatmap from './components/EvalHeatmap'
import ResultBarChart from './components/ResultBarChart'
import PriceHistogram from './components/PriceHistogram'
import TrendSparkline from './components/TrendSparkline'
import ColumnSettingsModal from './components/ColumnSettingsModal'
import CollapsibleRail from './components/CollapsibleRail'
import { ExportButton } from '../../components/ExportButton'

const { RangePicker } = DatePicker

// === 响应式断点（与 Ant Design 默认一致） ===
// xs < 576, sm ≥ 576, md ≥ 768, lg ≥ 992, xl ≥ 1200, xxl ≥ 1600
// 评估明细页主要面向桌面端，移动端走横向滚动 + 列隐藏
// SCROLL_X 调整：所有固定宽度列总和约 1790px（含标题列 width=200），
// 新增订单列(90)+操作列(80)=170px，预留 60px 缓冲，避免窄屏滚动时列被压缩至不可见
// O-13-26 AI 列从 70 增至 110（加深度鉴伪按钮），SCROLL_X 同步 +40
const SCROLL_X = 2060

// P3：官方采集重试退避工具
// 仅对临时性错误（410/441/502/超时）重试 1 次，避免偶发失败打扰用户
// 不可重试错误（403/440/503）直接抛出，需用户操作（重新登录/重启服务）
const RETRYABLE_STATUSES = new Set([410, 441, 502])
const RETRY_DELAYS: Record<string, number> = {
  '410': 1000,   // 页面未加载，快速重试
  '441': 3000,   // 反爬触发，需 3s 冷却
  '502': 1000,   // 连接异常，快速重试
  'timeout': 2000,  // 超时，2s 后重试
}

async function collectOfficialWithRetry(itemId: string, taskId?: string): Promise<OfficialCollectResult> {
  const MAX_RETRIES = 1
  let lastErr: unknown
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      return await evalApi.collectOfficial(itemId, taskId)
    } catch (err: unknown) {
      lastErr = err
      if (attempt >= MAX_RETRIES) break
      // 判断是否可重试
      const e = err as { response?: { status?: number }; code?: string; message?: string }
      const status = e?.response?.status
      const isTimeout = e?.code === 'ECONNABORTED' || /timeout/i.test(e?.message || '')
      const retryable = isTimeout || (status !== undefined && RETRYABLE_STATUSES.has(status))
      if (!retryable) break
      // 计算退避时间
      const delayKey = isTimeout ? 'timeout' : String(status)
      const delay = RETRY_DELAYS[delayKey] ?? 2000
      await new Promise(resolve => setTimeout(resolve, delay))
      // 重试时不弹消息，避免打扰用户（仅在最终失败时展示错误）
    }
  }
  throw lastErr
}

// === 列元数据定义：用于配置面板（拖拽排序与显示/隐藏） ===
// key 必须与下方 columns 中每列的 key 一致
// locked=true 的列禁止隐藏（标题、评分等核心展示列）
const COLUMN_DEFINITIONS: ColumnConfig[] = [
  { key: 'task_id', label: '任务ID' },
  { key: 'thumb', label: '图片' },
  { key: 'title', label: '标题', locked: true },
  { key: 'price', label: '价格' },
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

// 把任意时间格式化为 zh-CN 友好的本地时间；无法解析时返回 null
function formatPublishTime(raw: string | number | null | undefined): string | null {
  if (raw === null || raw === undefined || raw === '') return null
  const d = new Date(raw)
  // 用 Number.isNaN 替代全局 isNaN：全局 isNaN 会先强制转字符串，可能误判非数字值
  if (Number.isNaN(d.getTime())) return null
  return d.toLocaleString('zh-CN', { hour12: false })
}

// 缩略图兜底：URL 为空或加载失败时显示占位符
function ThumbCell({ url, title }: { readonly url?: string | null; readonly title?: string | null }) {
  const [errored, setErrored] = useState(false)
  // url 变化时重置 errored：官方采集更新图片后需重新尝试加载，
  // 否则旧失败状态残留导致 React 复用实例时永远显示占位图
  useEffect(() => { setErrored(false) }, [url])
  // 改写为肯定条件：URL 有效且未触发错误时走主流程，避免否定条件认知负担
  if (url && !errored) {
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

// O-13-26 深度分析单维度展示：score + risk_level + 信号列表 + 详情
// 后端 _normalize_deep_result 已把 signals/damages/inconsistencies 统一归并到 signals 字段，
// 所以前端只需消费 check.signals，不需要按维度区分字段名
type DeepCheckPanelProps = {
  readonly title: string
  readonly check: DeepCheckResult
  readonly signalLabel: string
}
function DeepCheckPanel({ title, check, signalLabel }: DeepCheckPanelProps) {
  const riskColor = (() => {
    if (check.risk_level === 'low') return 'success'
    if (check.risk_level === 'medium') return 'warning'
    return 'error'
  })()
  const scoreColor = (() => {
    if (check.score >= 7) return '#52c41a'
    if (check.score >= 4) return '#faad14'
    return '#ff4d4f'
  })()
  // 后端归一化保证 signals 总是数组（可能为空）；types 中 damages/inconsistencies 仅作兼容保留
  const signals = check.signals ?? []
  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 12 }}>
        <Col span={12}>
          <Statistic
            title={`${title} 评分`}
            value={`${check.score}/10`}
            valueStyle={{ color: scoreColor, fontSize: 20 }}
          />
        </Col>
        <Col span={12} style={{ display: 'flex', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginBottom: 4 }}>风险等级</div>
            <Tag color={riskColor} style={{ fontSize: 14, padding: '2px 12px' }}>
              {(() => {
                if (check.risk_level === 'low') return '低'
                if (check.risk_level === 'medium') return '中'
                return '高'
              })()}
            </Tag>
          </div>
        </Col>
      </Row>
      {signals.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginBottom: 4 }}>{signalLabel}：</div>
          <div>
            {signals.map((s, i) => (
              <Tag key={`${s}-${i}`} color="orange" style={{ marginBottom: 4 }}>{s}</Tag>
            ))}
          </div>
        </div>
      )}
      <div style={{
        padding: 10, borderRadius: 6, background: 'var(--xh-bg-code)',
        fontSize: 13, color: 'var(--xh-text-secondary)', lineHeight: 1.6,
      }}>
        {check.detail || '无详细分析'}
      </div>
    </div>
  )
}

// O-13-26 综合结论 Tag：从父组件 IIFE 抽到模块顶层，
// 避免每次父组件 render 都新建组件实例导致 reconciliation 失败
type VerdictTagProps = {
  readonly verdict: 'recommend' | 'caution' | 'reject'
}
function VerdictTag({ verdict }: VerdictTagProps) {
  const tagColor = verdict === 'recommend' ? 'success' : verdict === 'caution' ? 'warning' : 'error'
  const label = verdict === 'recommend' ? '推荐' : verdict === 'caution' ? '谨慎' : '拒绝'
  return <Tag color={tagColor}>{label}</Tag>
}

export default function Evaluations() {
  // === 列表数据 ===
  const [items, setItems] = useState<EvalItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)

  // === 查询条件 ===
  // 筛选条件持久化：刷新或切换页面后恢复上次筛选，减少重复输入
  const [itemId, setItemId] = usePersistentState<string>('xh.evals.itemId', '')
  const [taskId, setTaskId] = usePersistentState<string>('xh.evals.taskId', '')
  const [tasks, setTasks] = useState<Task[]>([])
  const [scoreRange, setScoreRange] = usePersistentState<[number, number]>(
    'xh.evals.scoreRange', [0, 100],
    {
      validator: (v): v is [number, number] =>
        Array.isArray(v) && v.length === 2 && v.every(n => typeof n === 'number' && Number.isFinite(n)),
    },
  )
  // dayjs 对象无法直接 JSON 序列化（反序列化后丢失 dayjs 方法），
  // 持久化 ISO 字符串数组，使用时转回 dayjs 对象供 RangePicker 使用
  const [dateRangeIso, setDateRange] = usePersistentState<[string, string] | null>(
    'xh.evals.dateRange', null,
    {
      validator: (v): v is [string, string] | null =>
        v === null || (Array.isArray(v) && v.length === 2 && v.every(s => typeof s === 'string')),
    },
  )
  const dateRange = useMemo<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(
    () => dateRangeIso
      ? [dateRangeIso[0] ? dayjs(dateRangeIso[0]) : null, dateRangeIso[1] ? dayjs(dateRangeIso[1]) : null]
      : null,
    [dateRangeIso],
  )
  // 品牌筛选：与商品列表对齐，从当前页 items 提取选项
  const [brandFilter, setBrandFilter] = usePersistentState<string>('xh.evals.brandFilter', '')
  // 状态筛选：评估页默认看全部（含已售），与商品列表默认 onsale 区分；
  // 持久化保留用户偏好，validator 防止脏数据导致 UI 异常
  const [soldFilter, setSoldFilter] = usePersistentState<'all' | 'onsale' | 'sold'>(
    'xh.evals.soldFilter', 'all',
    {
      validator: (v): v is 'all' | 'onsale' | 'sold' => v === 'all' || v === 'onsale' || v === 'sold',
    },
  )

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

  // === O-13-26 AI 深度多模态分析 ===
  // 与 AI 成色评估（evaluateCondition）区别：深度分析做 4 维 Vision 鉴伪（盗图/损坏/一致性/模板）
  const [deepModalOpen, setDeepModalOpen] = useState(false)
  const [deepLoading, setDeepLoading] = useState(false)
  const [deepResult, setDeepResult] = useState<DeepAnalyzeResult | null>(null)
  const [deepItemId, setDeepItemId] = useState('')

  // === 卖家趋势（展开行） ===
  const [trendCache, setTrendCache] = useState<Record<string, SellerTrendData>>({})
  const [trendLoading, setTrendLoading] = useState('')

  // === 重新评估 ===
  const [recomputing, setRecomputing] = useState(false)
  // === 批量评估未评估商品 ===
  const [batchEvaluating, setBatchEvaluating] = useState(false)

  // === 阈值通过率计算器 ===
  const [thresholdValue, setThresholdValue] = useState(60)
  const [targetPassRate, setTargetPassRate] = useState(70)

  // === 批量 AI 评估 ===
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [batchAIEvaluating, setBatchAIEvaluating] = useState(false)
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

  // === 手动抢单 ===
  // 按 item_id 索引 loading 状态，支持多行独立 loading
  const [manualTaking, setManualTaking] = useState<Record<string, boolean>>({})

  // === 列配置（拖拽排序 + 显示/隐藏，持久化到 localStorage） ===
  const [columnConfigOpen, setColumnConfigOpen] = useState(false)
  const {
    order: columnOrder,
    hidden: hiddenColumns,
    toggleHidden: toggleColumnHidden,
    moveColumn: moveColumnOrder,
    reset: resetColumnConfig,
    applyConfig: applyColumnConfig,
  } = useColumnConfig('xh.evals.columns', COLUMN_DEFINITIONS)

  // === 右侧分析面板折叠状态 ===
  // 持久化用户偏好：专注列表浏览时折叠，分析时展开
  // 默认展开保持与历史行为一致，避免老用户升级后面板"消失"的困惑
  const [panelCollapsed, setPanelCollapsed] = usePersistentState<boolean>(
    'xh.evals.panelCollapsed', false,
    { validator: (v): v is boolean => typeof v === 'boolean' },
  )

  // === 统计卡片过滤 ===
  // 点击统计卡片触发后端按 result_category 过滤，返回全量匹配记录并支持分页
  // 为什么不持久化：过滤是临时浏览操作，刷新或切换任务后应回到全量视图
  // 为什么改用后端过滤：之前在前端过滤当前页 items，当当前页无匹配记录时显示空，
  // 与统计卡片显示的全量数量矛盾，用户误以为"查不到记录"
  type ResultCategory = 'auto' | 'pass' | 'fail' | 'insufficient' | null
  const [resultCategory, setResultCategory] = useState<ResultCategory>(null)
  const toggleResultCategory = useCallback((c: ResultCategory) => {
    setResultCategory(prev => prev === c ? null : c)
  }, [])

  // 价格范围筛选：null 表示不限制，由后端从任务配置自动读取
  // 为什么用 null 而非 undefined：usePersistentState 需要可序列化的默认值
  // 为什么不持久化：价格范围是临时筛选，刷新后应回到任务默认值
  const [priceRange, setPriceRange] = useState<[number | null, number | null]>([null, null])
  // 显示超出任务价格范围的历史商品（审计用，默认关闭）
  const [includeOutOfRange, setIncludeOutOfRange] = useState<boolean>(false)
  // 选中任务时自动填入任务的 min_price/max_price 作为默认值
  // 为什么用 useEffect 而非 onChange：任务列表加载完成后也需要回填
  useEffect(() => {
    if (!taskId) {
      setPriceRange([null, null])
      return
    }
    const task = tasks.find(t => t.id === taskId)
    if (task) {
      setPriceRange([
        task.min_price != null ? task.min_price : null,
        task.max_price != null ? task.max_price : null,
      ])
    }
  }, [taskId, tasks])

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

  // 批量评估 items 表中未被评估的商品
  const onBatchEvaluateUnevaluated = async () => {
    setBatchEvaluating(true)
    try {
      const res = await evalApi.batchEvaluateUnevaluated(taskId || undefined)
      message.success(res.message)
      load()
      loadDist()
    } catch {
      message.error('批量评估失败')
    } finally {
      setBatchEvaluating(false)
    }
  }

  // === 阈值通过率计算：当前页面评分 >= 阈值的比例 ===
  const thresholdPassCount = items.filter(item => (item.payload.score ?? 0) >= thresholdValue).length
  const thresholdPassRate = items.length > 0 ? (thresholdPassCount / items.length * 100) : 0

  // 根据目标通过率自动推算建议阈值（从当前页面数据降序排列取分位点）
  const computeSuggestedThreshold = (targetRate: number): number => {
    if (items.length === 0) return 0
    // map 已返回新数组，再 [...arr] 包一层属于多余克隆
    const sortedScores = items.map(item => item.payload.score ?? 0).sort((a, b) => b - a)
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

    setBatchAIEvaluating(true)
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

    setBatchAIEvaluating(false)
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
      // P3：对临时性错误（410/441/502/超时）自动退避重试 1 次
      // 避免页面偶发未加载/反爬瞬时触发打扰用户
      const result = await collectOfficialWithRetry(itemId, r.task_id)
      setCollectResult(result)
      setCollectModalOpen(true)
      message.success(`官方采集评估完成，评分：${result.evaluation.score ?? 'N/A'}`)
      load()  // 刷新列表以展示更新后的评估结果
    } catch (err: unknown) {
      const error = err as { response?: { status?: number; data?: { detail?: string } }; code?: string; message?: string }
      const status = error?.response?.status
      const detail = error?.response?.data?.detail
      // axios 超时无 response.status，需通过 code 识别，避免误报为「官方采集失败」
      if (error?.code === 'ECONNABORTED' || /timeout/i.test(error?.message || '')) {
        message.error('官方采集超时（详情页+卖家主页加载缓慢），请稍后重试或检查网络')
      } else if (status === 503) {
        message.error(detail || '官方采集需要浏览器实例，请以 XH_WITH_SCHEDULER=1 模式启动')
      } else if (status === 403 || status === 440) {
        // 403=cookie缺失、440=cookie失效被重定向，均不能使用 401 以免触发 axios 全局登出
        message.error(detail || '闲鱼登录已过期，请重新登录闲鱼')
      } else if (status === 441) {
        // 441=反爬触发（验证码/RGV587）
        message.error(detail || '触发闲鱼反爬限制，请稍后重试或手动完成验证')
      } else if (status === 410) {
        // 410=商品下架/详情页未正常加载，提示用户重试或检查商品
        message.error(detail || '商品详情页加载失败或已下架，请稍后重试')
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

  // === 手动抢单 ===
  // 让用户在评估明细页面主动触发抢单，突破纯自动模式限制
  // 前置条件：服务以 XH_WITH_SCHEDULER=1 模式启动以注入浏览器实例
  const onManualTakeover = async (r: EvalItem) => {
    const itemId = r.item_id
    setManualTaking((prev) => ({ ...prev, [itemId]: true }))
    try {
      const result = await orderApi.manualTakeover(itemId, r.task_id)
      if (result.outcome === 'success') {
        message.success(result.message || '抢单成功')
      } else if (result.outcome === 'skipped_duplicate') {
        message.info(result.message || '商品已下过单，幂等跳过')
      }
      // 刷新列表以展示最新订单状态
      load()
    } catch (err: unknown) {
      const error = err as { response?: { status?: number; data?: { detail?: string } }; code?: string; message?: string }
      const status = error?.response?.status
      const detail = error?.response?.data?.detail
      // 超时错误（ECONNABORTED）：axios 超时后 response 为 undefined
      if (error?.code === 'ECONNABORTED' || (error?.message || '').includes('timeout')) {
        message.error('抢单超时：浏览器自动化流程耗时过长，请检查网络后重试')
      } else if (status === 503) {
        message.error(detail || '抢单功能未启用：需要以 XH_WITH_SCHEDULER=1 模式启动服务')
      } else if (status === 403) {
        // 403 表示闲鱼 Cookie 失效（非系统登录失效），不能用 401 以免触发 axios 全局登出
        message.error(detail || '闲鱼登录已过期，请先在「Cookie 注入」页面重新登录闲鱼')
      } else if (status === 404) {
        message.error(detail || '商品不存在于数据库中')
      } else if (status === 502) {
        message.error(detail || '抢单失败：未找到提交订单按钮，可能商品已下架或页面结构变化')
      } else {
        message.error(detail || '抢单失败，请稍后重试')
      }
    } finally {
      setManualTaking((prev) => ({ ...prev, [itemId]: false }))
    }
  }

  // === 标题点击异步采集 + 打开新标签页 ===
  // 复用 ItemList 页面的 handleItemClick 模式：preventDefault 阻止默认跳转，
  // 异步调用 /api/items/{id}/refresh 触发后端采集（更新 brand 等字段到 task_links.display），
  // 同时 window.open 打开新标签页，让用户既能看商品页又能后台采集数据。
  // 采集完成后刷新列表，让 brand 等字段在前端展示。
  const onTitleClick = (e: React.MouseEvent, r: EvalItem, url: string) => {
    e.preventDefault()
    const itemId = r.item_id
    if (!itemId) return
    // loading 提示让用户感知后台正在采集，避免「点击后无反馈」的体验
    // 失败时显示错误：detail 卡住/超时是浏览器实例异常的常见症状，需要告知用户
    const hide = message.loading(`正在采集 ${itemId.slice(0, 8)}...`, 0)
    // 传 task_id：items 表无记录时后端用它回填 task_links.display
    itemApi.refresh(itemId, r.task_id || undefined).then(() => {
      hide()
      message.success(`已更新商品信息：${itemId.slice(0, 8)}...`)
      load()  // 刷新列表以展示更新后的 brand 等字段
    }).catch((err: unknown) => {
      hide()
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      message.error(detail || `采集失败：${itemId.slice(0, 8)}...，请稍后重试`)
    })
    globalThis.open(url, '_blank', 'noopener,noreferrer')
  }

  // 加载评估列表
  // 用 ref 持有筛选条件最新值，避免每次键入触发 API 请求
  const filtersRef = useRef({ itemId, taskId, scoreRange, dateRange, brandFilter, soldFilter, resultCategory, priceRange, includeOutOfRange })
  filtersRef.current = { itemId, taskId, scoreRange, dateRange, brandFilter, soldFilter, resultCategory, priceRange, includeOutOfRange }

  const load = useCallback(() => {
    setLoading(true)
    const { itemId: fItemId, taskId: fTaskId, scoreRange: fScore, dateRange: fDate, brandFilter: fBrand, soldFilter: fSold, resultCategory: fResultCategory, priceRange: fPriceRange, includeOutOfRange: fIncludeOutOfRange } = filtersRef.current
    const params: Record<string, unknown> = {
      page_num: page,
      page_size: pageSize,
      limit: pageSize * 4,
    }
    if (fItemId) params.item_id = fItemId
    if (fTaskId) params.task_id = fTaskId
    if (fScore[0] > 0) params.min_score = fScore[0]
    if (fScore[1] < 100) params.max_score = fScore[1]
    if (fDate?.[0]) params.start_time = fDate[0].format('YYYY-MM-DD')
    if (fDate?.[1]) params.end_time = fDate[1].format('YYYY-MM-DD')
    if (fBrand) params.brand = fBrand
    // 'all' 时不传给后端，等价于不过滤，减少参数传输
    if (fSold !== 'all') params.sold_filter = fSold
    // result_category 由统计卡片点击触发，后端按配置阈值精确分类过滤
    if (fResultCategory) params.result_category = fResultCategory
    // 价格范围：用户显式输入优先；未输入但传了 task_id 时后端自动从任务配置读取
    if (fPriceRange[0] != null) params.min_price = fPriceRange[0]
    if (fPriceRange[1] != null) params.max_price = fPriceRange[1]
    // include_out_of_range=true 时后端跳过价格过滤，用于审计历史超范围商品
    if (fIncludeOutOfRange) params.include_out_of_range = true

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
    // 改用肯定条件：page 已是 1 时直接 load，否则切到 1 由 useEffect 触发
    if (page === 1) {
      load()
    } else {
      setPage(1)  // useEffect 会自动触发 load（filtersRef.current 已是最新）
    }
  }
  const onReset = () => {
    setItemId(''); setTaskId(''); setScoreRange([0, 100]); setDateRange(null); setBrandFilter(''); setSoldFilter('all'); setResultCategory(null)
    setPriceRange([null, null]); setIncludeOutOfRange(false)
    // 重置后需要用新条件重新加载
    filtersRef.current = { itemId: '', taskId: '', scoreRange: [0, 100] as [number, number], dateRange: null, brandFilter: '', soldFilter: 'all', resultCategory: null, priceRange: [null, null] as [number | null, number | null], includeOutOfRange: false }
    if (page === 1) {
      load()
    } else {
      setPage(1)  // useEffect 会自动触发 load
    }
  }

  // 阈值建议
  const fetchSuggestion = () => {
    evalApi.thresholdSuggestion(thresholdTarget / 100)
      .then((res) => { setSuggestion(res); message.success(`建议阈值: ${res.suggested_threshold}`) })
      .catch(() => message.error('获取阈值建议失败'))
  }

  // AI 成色评估 race condition 防护：单维评估 60s，期间用户可能切换商品
  // aiItemIdRef 跟踪最新请求，旧请求结果/错误/loading 全部丢弃避免污染新商品展示
  const aiItemIdRef = useRef('')
  // AI 错误统一处理：onAIEval/onDeepAnalyze 共用，避免 403/404/422 三段 if-else 重复
  const handleAiError = (err: unknown, fallbackMsg: string, closeModal: () => void) => {
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
      message.error(detail || fallbackMsg)
    }
    closeModal()
  }

  // AI 成色评估
  const onAIEval = async (itemId: string) => {
    if (!itemId) {
      message.error('商品 ID 为空，无法评估')
      return
    }
    aiItemIdRef.current = itemId
    setAiItemId(itemId)
    setAiModalOpen(true)
    setAiLoading(true)
    setAiResult(null)
    try {
      const result = await aiApi.evaluateCondition(itemId)
      // 校验：若用户已切换到其他商品，丢弃本次过期结果
      if (aiItemIdRef.current !== itemId) return
      setAiResult(result)
    } catch (err: unknown) {
      // 旧请求的错误不处理，避免覆盖新请求的 UI 状态
      if (aiItemIdRef.current !== itemId) return
      handleAiError(err, 'AI 评估失败，请检查 AI 配置', () => setAiModalOpen(false))
    } finally {
      // 仅当本次请求仍是最新时才结束 loading，避免提前关闭新请求的 loading
      if (aiItemIdRef.current === itemId) {
        setAiLoading(false)
      }
    }
  }

  // O-13-26 AI 深度多模态分析：盗图/损坏/一致性/模板四维鉴伪
  // 与 onAIEval 区别：onAIEval 单维成色评估，deepAnalyze 多维鉴伪更耗时
  // 用 ref 跟踪最新请求 itemId：Vision 推理 90s，期间用户可能切换商品，
  // 旧请求的结果/错误/loading 状态若不校验会污染新商品的展示
  const deepItemIdRef = useRef('')
  const onDeepAnalyze = async (itemId: string) => {
    if (!itemId) {
      message.error('商品 ID 为空，无法分析')
      return
    }
    deepItemIdRef.current = itemId
    setDeepItemId(itemId)
    setDeepModalOpen(true)
    setDeepLoading(true)
    setDeepResult(null)
    try {
      const result = await aiApi.deepAnalyze(itemId)
      // 校验：若用户已切换到其他商品，丢弃本次过期结果
      if (deepItemIdRef.current !== itemId) return
      setDeepResult(result)
    } catch (err: unknown) {
      // 旧请求的错误不处理，避免覆盖新请求的 UI 状态
      if (deepItemIdRef.current !== itemId) return
      handleAiError(err, '深度分析失败，请稍后重试', () => setDeepModalOpen(false))
    } finally {
      // 仅当本次请求仍是最新时才结束 loading，避免提前关闭新请求的 loading
      if (deepItemIdRef.current === itemId) {
        setDeepLoading(false)
      }
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
        return <ThumbCell url={url} title={r.payload?.item_title} />
      },
    },
    {
      title: '标题', key: 'title', width: 200, ellipsis: true,
      // 标题列在极窄屏保留 ellipsis + tooltip，宽屏完整显示
      // 必须设 width：原代码无 width 导致与其他固定宽度列总和过近，
      // 标题列剩余空间被压缩为 0 实际不可见
      // 点击行为：异步触发后端采集（更新 brand 等字段到 task_links.display），
      // 同时打开新标签页让用户浏览商品页，采集完成后刷新列表
      render: (_: unknown, r: EvalItem) => {
        const title = r.payload?.item_title || '—'
        const url = `https://www.goofish.com/item?id=${r.item_id}`
        return (
          <Tooltip title={`${title}（点击采集更新品牌等字段）`}>
            <a
              href={url}
              onClick={(e) => onTitleClick(e, r, url)}
              style={{ cursor: 'pointer' }}
            >
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
        const nick = r.payload?.seller_nick
        const id = r.payload?.seller_id
        const credit = r.payload?.seller_credit as string | undefined
        // 真实昵称优先级：清洗后的 seller_nick > seller_id（截短）> '—'
        const hasNick = !!nick?.trim()
        const displayName = (() => {
          if (hasNick) return nick
          if (id) return `用户 ${id.slice(0, 8)}`
          return '—'
        })()
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
        // 改写为肯定条件：有 region 时走主流程，避免否定条件认知负担
        if (region) {
          return (
            <span>
              <EnvironmentOutlined style={{ marginRight: 4, color: '#fa8c16' }} />
              {region}
            </span>
          )
        }
        return <span style={{ color: 'var(--xh-text-quaternary)' }}>—</span>
      },
    },
    {
      // 品牌列：由后端 _enrich_eval_with_item 从 task_links.display 补充
      // 空值显示"—"，与商品列表页对齐
      title: '品牌', key: 'brand', width: 90, ellipsis: true,
      render: (_: unknown, r: EvalItem) => {
        const brand = r.payload?.brand
        // 改写为肯定条件：有 brand 时走主流程
        if (brand) {
          return <Tooltip title={brand}>{brand}</Tooltip>
        }
        return <span style={{ color: 'var(--xh-text-quaternary)' }}>—</span>
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
      // 浏览数：展示商品曝光度，辅助判断热度
      title: '浏览', key: 'view', width: 60,
      render: (_: unknown, r: EvalItem) => {
        const v = r.payload?.view_cnt as number | undefined
        return v != null ? <span>{v}</span> : <span style={{ color: 'var(--xh-text-quaternary)' }}>—</span>
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
      // 状态列：与商品列表对齐，已售红色、在售绿色
      // 数据来源：后端 _enrich_eval_with_item 注入到 payload.is_sold
      title: '状态', key: 'is_sold', width: 80,
      render: (_: unknown, r: EvalItem) => {
        const isSold = r.payload?.is_sold
        return isSold ? <Tag color="red">已售</Tag> : <Tag color="green">在售</Tag>
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
            {/* 维修历史/全新标识：帮助用户快速判断商品成色风险 */}
            {r.is_branded_new && (
              <Tag color="green" style={{ fontSize: 10, lineHeight: '16px', padding: '0 4px', margin: '2px 0 0 0' }}>全新</Tag>
            )}
            {r.has_repair && (
              <Tag color="red" style={{ fontSize: 10, lineHeight: '16px', padding: '0 4px', margin: '2px 0 0 4px' }}>有维修</Tag>
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
              <Tag key={`${t.label}-${i}`} style={{ marginBottom: 2 }} color="blue">{t.label}</Tag>
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
        const color = (() => {
          if (s >= autoBuyScore) return '#52c41a'
          if (s >= passScore) return '#faad14'
          return '#ff4d4f'
        })()
        // 数据质量标识：让用户了解评分的可靠性（full=完整数据/partial=部分数据/insufficient=数据不足）
        const dq = r.payload?.data_quality as string | undefined
        const dqColorMap: Record<string, string> = { full: 'green', partial: 'orange', insufficient: 'red' }
        const dqLabelMap: Record<string, string> = { full: '完整', partial: '部分', insufficient: '不足' }
        return (
          <div>
            <span style={{ color, fontWeight: 600, fontSize: 15 }}>{s.toFixed(1)}</span>
            {dq && dqLabelMap[dq] && (
              <div>
                <Tag color={dqColorMap[dq]} style={{ fontSize: 10, lineHeight: '14px', padding: '0 4px', margin: 0 }}>
                  {dqLabelMap[dq]}
                </Tag>
              </div>
            )}
          </div>
        )
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
      title: 'AI', key: 'ai', width: 110,
      render: (_: unknown, r: EvalItem) => (
        <Space size={4}>
          <Tooltip title="AI 成色评估">
            <Button
              size="small"
              icon={<RobotOutlined />}
              onClick={() => onAIEval(r.item_id)}
              disabled={isDataInsufficient(r) && (r.payload.score ?? 0) < 60}
            />
          </Tooltip>
          {/* O-13-26 深度多模态鉴伪：盗图/损坏/一致性/模板，与单维成色评估区分 */}
          <Tooltip title="深度鉴伪（盗图/损坏/一致性/模板）">
            <Button
              size="small"
              icon={<ThunderboltOutlined />}
              onClick={() => onDeepAnalyze(r.item_id)}
              disabled={isDataInsufficient(r) && (r.payload.score ?? 0) < 60}
            />
          </Tooltip>
        </Space>
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
    {
      // 订单状态列：显示商品是否已被抢单，让用户无需切换到 Orders 页面即可看到结果
      // 数据来源：后端 _enrich_eval_with_item 实时关联 orders 表注入的 order_status 字段
      title: '订单', key: 'order_status', width: 90,
      render: (_: unknown, r: EvalItem) => {
        const status = r.payload?.order_status as string | undefined
        // 改写为肯定条件：有 status 时走映射主流程
        if (status) {
          // 订单状态映射：颜色与文案与 Orders 页面保持一致
          const statusMap: Record<string, { color: string; label: string }> = {
            pending_pay: { color: 'orange', label: '待支付' },
            paid: { color: 'blue', label: '已支付' },
            succeeded: { color: 'green', label: '已成功' },
            takeover_pending: { color: 'gold', label: '接管中' },
            cancelled: { color: 'default', label: '已取消' },
            failed: { color: 'red', label: '失败' },
          }
          const cfg = statusMap[status] || { color: 'default', label: status }
          return <Tag color={cfg.color}>{cfg.label}</Tag>
        }
        return <span style={{ color: 'var(--xh-text-quaternary)' }}>—</span>
      },
    },
    {
      // 手动抢单操作列：仅在评分≥auto_buy_score（默认80）且无订单时显示
      // 突破纯自动模式限制，让用户保留抢单决策权
      title: '操作', key: 'action', width: 80, fixed: 'right' as const,
      render: (_: unknown, r: EvalItem) => {
        const score = r.payload.score ?? 0
        const orderStatus = r.payload?.order_status as string | undefined
        // 已有订单时不显示抢单按钮（避免重复下单）
        if (orderStatus && orderStatus !== 'failed' && orderStatus !== 'cancelled') {
          return <span style={{ color: 'var(--xh-text-quaternary)', fontSize: 11 }}>已下单</span>
        }
        // 评分低于阈值时不显示（避免误操作）
        if (score < autoBuyScore) {
          return <span style={{ color: 'var(--xh-text-quaternary)', fontSize: 11 }}>未达阈值</span>
        }
        return (
          <Tooltip title={`手动抢单（评分 ${score.toFixed(0)} ≥ ${autoBuyScore}）`}>
            <Button
              size="small"
              type="primary"
              ghost
              icon={<ThunderboltOutlined />}
              loading={manualTaking[r.item_id]}
              onClick={() => onManualTakeover(r)}
            />
          </Tooltip>
        )
      },
    },
  ]

  // 列宽自适应：折叠右侧面板时，列表获得更多空间，
  // 移除 task_id/publish 的 responsive 限制强制显示，并加宽 title/seller/condition_tags
  // 为什么用 useMemo 派生而非修改 useColumnConfig：折叠列宽是系统行为，
  // 与用户手动配置的显隐/排序正交，保持 hook 通用性
  const adaptedColumns = useMemo(() => {
    // 改写为肯定条件：折叠时走列宽自适应主流程
    if (panelCollapsed) {
      return columns.map((col) => {
        switch (col.key) {
          case 'task_id': return { ...col, responsive: undefined }
          case 'title': return { ...col, width: 280 }
          case 'seller': return { ...col, width: 220 }
          case 'publish': return { ...col, responsive: undefined }
          case 'condition_tags': return { ...col, width: 180 }
          default: return col
        }
      })
    }
    return columns
  }, [columns, panelCollapsed])

  // 应用列配置：根据用户拖拽顺序重排 + 跳过已隐藏的列
  // 为什么在 columns 之后派生：columns 中所有列都有 key，applyConfig 依赖 key 重排
  const visibleColumns = applyColumnConfig(adaptedColumns)

  // 折叠态下列宽总和增加（title+80, seller+50, condition_tags+30 = 160），
  // 同步扩展横向滚动宽度避免列被压缩
  const scrollX = panelCollapsed ? 2180 : SCROLL_X

  // 品牌选项：从当前已加载的评估列表中提取（payload.brand 由后端 enrich 补充）
  // 分页场景下选项可能不完整，用户可清空筛选后重新选择，与商品列表页策略一致
  const brandOptions = [...new Set(
    items.map((i) => i.payload?.brand).filter(Boolean)
  )].sort((a, b) => String(a).localeCompare(String(b)))

  // 展开行：详细信息 + 卖家价格趋势
  // 展示接口返回但主表格未显示的完整字段，帮助用户做购买决策
  const expandedRowRender = (r: EvalItem) => {
    // 从 payload 提取详细信息字段（collect-official 流程会写入这些字段）
    const description = r.payload?.item_description as string | undefined
    const imageUrls = r.payload?.image_urls as string[] | undefined
    const reviews = r.payload?.reviews as string[] | undefined
    const sellerCreditScore = r.payload?.seller_credit_score as number | undefined
    const sellerOnSaleCount = r.payload?.seller_on_sale_count as number | undefined
    const sellerSoldCount = r.payload?.seller_sold_count as number | undefined
    const sellerRegisterDays = r.payload?.seller_register_days as number | undefined
    const dataSource = r.payload?.data_source as string | undefined

    // 从 dimension_scores 提取 AI 成色评估详情
    const dimScores = r.payload?.dimension_scores as Record<string, unknown> | undefined
    const aiEval = dimScores?.ai_condition_eval as Record<string, unknown> | undefined

    // 从 dimension_scores 提取规则评估维度分数
    const ruleDims: Array<[string, number]> = []
    if (dimScores) {
      for (const [k, v] of Object.entries(dimScores)) {
        if (k === 'ai_condition_eval') continue
        if (typeof v === 'number') ruleDims.push([k, v])
      }
    }

    // 从 reject_reasons 提取拒绝原因
    const rejectReasons = r.payload?.reject_reasons as string[] | undefined

    // 判断是否有任何详细信息可显示
    const hasDetail = description || imageUrls?.length || reviews?.length ||
      sellerCreditScore != null || sellerOnSaleCount != null ||
      sellerSoldCount != null || sellerRegisterDays != null ||
      aiEval || ruleDims.length > 0 || rejectReasons?.length

    return (
      <div>
        {/* 详细信息区域：仅在有任何可展示数据时渲染 */}
        {hasDetail && (
          <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
            {/* 商品详情卡片 */}
            {(description || imageUrls?.length) && (
              <Col span={24}>
                <Card size="small" title="商品详情" style={{ marginBottom: 8 }}>
                  {description && (
                    <div style={{ marginBottom: 8, color: 'var(--xh-text-secondary)', fontSize: 13, whiteSpace: 'pre-wrap' }}>
                      {description}
                    </div>
                  )}
                  {imageUrls && imageUrls.length > 0 && (
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      {imageUrls.slice(0, 6).map((url, i) => (
                        <Image
                          key={`${url}-${i}`}
                          src={url}
                          width={80}
                          height={80}
                          style={{ objectFit: 'cover', borderRadius: 6 }}
                          referrerPolicy="no-referrer"
                        />
                      ))}
                    </div>
                  )}
                </Card>
              </Col>
            )}

            {/* 卖家信息卡片 */}
            {(sellerCreditScore != null || sellerOnSaleCount != null || sellerSoldCount != null || sellerRegisterDays != null) && (
              <Col xs={24} md={12}>
                <Card size="small" title="卖家信息" style={{ marginBottom: 8 }}>
                  <Descriptions column={2} size="small" labelStyle={{ fontSize: 12, color: 'var(--xh-text-tertiary)' }}>
                    {sellerCreditScore != null && (
                      <Descriptions.Item label="芝麻信用">{sellerCreditScore}</Descriptions.Item>
                    )}
                    {sellerRegisterDays != null && (
                      <Descriptions.Item label="注册天数">{sellerRegisterDays} 天</Descriptions.Item>
                    )}
                    {sellerOnSaleCount != null && (
                      <Descriptions.Item label="在售数">{sellerOnSaleCount}</Descriptions.Item>
                    )}
                    {sellerSoldCount != null && (
                      <Descriptions.Item label="已售数">{sellerSoldCount}</Descriptions.Item>
                    )}
                  </Descriptions>
                </Card>
              </Col>
            )}

            {/* 评估维度卡片 */}
            {(ruleDims.length > 0 || rejectReasons?.length) && (
              <Col xs={24} md={12}>
                <Card size="small" title="评估维度" style={{ marginBottom: 8 }}>
                  {ruleDims.length > 0 && (
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                      {ruleDims.map(([k, v]) => (
                        <Tag key={k} color="blue">
                          {translateDimension(k)}: {v}
                        </Tag>
                      ))}
                    </div>
                  )}
                  {rejectReasons && rejectReasons.length > 0 && (
                    <div style={{ fontSize: 12 }}>
                      <span style={{ color: 'var(--xh-text-tertiary)' }}>拒绝原因: </span>
                      {rejectReasons.map((reason, i) => (
                        <Tag key={`${reason}-${i}`} color="orange" style={{ fontSize: 11, marginBottom: 2 }}>{translateRejectReason(reason)}</Tag>
                      ))}
                    </div>
                  )}
                </Card>
              </Col>
            )}

            {/* AI 成色评估卡片 */}
            {aiEval && (
              <Col span={24}>
                <Card size="small" title="AI 成色评估" style={{ marginBottom: 8 }}>
                  <Row gutter={[16, 8]}>
                    {typeof aiEval.verdict === 'string' && aiEval.verdict.length > 0 && (
                      <Col span={6}>
                        <Statistic
                          title="结论"
                          value={aiEval.verdict === 'recommend' ? '推荐' : '谨慎'}
                          valueStyle={{ color: aiEval.verdict === 'recommend' ? '#52c41a' : '#faad14', fontSize: 16 }}
                        />
                      </Col>
                    )}
                    {typeof aiEval.condition_score === 'number' && (
                      <Col span={6}>
                        <Statistic title="成色评分" value={`${aiEval.condition_score}/10`} valueStyle={{ fontSize: 16 }} />
                      </Col>
                    )}
                    {typeof aiEval.appearance_score === 'number' && (
                      <Col span={6}>
                        <Statistic title="外观成色" value={`${aiEval.appearance_score}/10`} valueStyle={{ fontSize: 16 }} />
                      </Col>
                    )}
                    {typeof aiEval.consistency_score === 'number' && (
                      <Col span={6}>
                        <Statistic title="描述一致性" value={`${aiEval.consistency_score}/10`} valueStyle={{ fontSize: 16 }} />
                      </Col>
                    )}
                    {typeof aiEval.price_reasonability === 'number' && (
                      <Col span={6}>
                        <Statistic title="价格合理性" value={`${aiEval.price_reasonability}/10`} valueStyle={{ fontSize: 16 }} />
                      </Col>
                    )}
                  </Row>
                  {typeof aiEval.reason === 'string' && aiEval.reason.length > 0 && (
                    <div style={{ marginTop: 8, color: 'var(--xh-text-secondary)', fontSize: 13 }}>
                      {aiEval.reason}
                    </div>
                  )}
                  {Array.isArray(aiEval.risk_signals) && aiEval.risk_signals.length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      {aiEval.risk_signals.map((sig, i) => (
                        <Tag key={`${sig}-${i}`} color="orange" style={{ marginBottom: 2 }}>{String(sig)}</Tag>
                      ))}
                    </div>
                  )}
                  {typeof aiEval.detail === 'string' && aiEval.detail.length > 0 && (
                    <Collapse
                      ghost
                      size="small"
                      style={{ marginTop: 8 }}
                      items={[{ key: 'detail', label: '详细分析', children: <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>{aiEval.detail}</pre> }]}
                    />
                  )}
                </Card>
              </Col>
            )}

            {/* 评价列表 */}
            {reviews && reviews.length > 0 && (
              <Col span={24}>
                <Card size="small" title={`评价/留言 (${reviews.length})`} style={{ marginBottom: 8 }}>
                  {reviews.slice(0, 5).map((review, i) => (
                    <div key={`${review}-${i}`} style={{ padding: '4px 0', borderBottom: i < Math.min(reviews.length, 5) - 1 ? '1px solid var(--xh-border-secondary)' : 'none', fontSize: 13 }}>
                      {review}
                    </div>
                  ))}
                  {reviews.length > 5 && (
                    <div style={{ color: 'var(--xh-text-tertiary)', fontSize: 12, marginTop: 4 }}>
                      还有 {reviews.length - 5} 条评价
                    </div>
                  )}
                </Card>
              </Col>
            )}

            {/* 数据来源 */}
            {dataSource && (
              <Col span={24}>
                <Tag color="blue">数据来源: {dataSource}</Tag>
              </Col>
            )}
          </Row>
        )}

        {/* 卖家价格趋势（原有功能） */}
        <TrendSparkline
          trend={trendCache[r.item_id]}
          loading={trendLoading === r.item_id}
          error={trendError[r.item_id]}
          onLoad={() => loadSellerTrend(r.item_id)}
        />
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
            onChange={(v) => setDateRange(v ? [v[0]?.toISOString() ?? '', v[1]?.toISOString() ?? ''] : null)}
          />
          <span>品牌：</span>
          <Select
            placeholder="选择品牌"
            allowClear
            showSearch
            style={{ width: 160 }}
            value={brandFilter}
            onChange={(v) => { setBrandFilter(v || ''); setPage(1); setTimeout(load, 0) }}
            onClear={() => setBrandFilter('')}
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
            value={soldFilter}
            onChange={(v) => { setSoldFilter(v || 'all'); setPage(1); setTimeout(load, 0) }}
            options={[
              { label: '全部', value: 'all' },
              { label: '在售', value: 'onsale' },
              { label: '已售', value: 'sold' },
            ]}
          />
          <span>价格范围：</span>
          {/* 价格范围筛选：选中任务时自动填入任务配置作为默认值，用户可手动调整 */}
          <InputNumber
            placeholder="最低"
            min={0}
            style={{ width: 90 }}
            value={priceRange[0]}
            onChange={(v) => setPriceRange([v == null ? null : v, priceRange[1]])}
          />
          <span>-</span>
          <InputNumber
            placeholder="最高"
            min={0}
            style={{ width: 90 }}
            value={priceRange[1]}
            onChange={(v) => setPriceRange([priceRange[0], v == null ? null : v])}
          />
          {/* 显示超范围商品开关：审计历史已写入的超范围商品用 */}
          <Tooltip title="开启后显示超出任务价格范围的历史商品（审计用）">
            <Checkbox
              checked={includeOutOfRange}
              onChange={(e) => { setIncludeOutOfRange(e.target.checked); setPage(1); setTimeout(load, 0) }}
            >
              显示超范围
            </Checkbox>
          </Tooltip>
          <Button type="primary" icon={<SearchOutlined />} onClick={onSearch}>查询</Button>
          <Button icon={<UndoOutlined />} onClick={onReset}>重置</Button>
          <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>刷新</Button>
          <Button icon={<RetweetOutlined />} onClick={onRecompute} loading={recomputing}>重新评估</Button>
          <Button icon={<RetweetOutlined />} onClick={onBatchEvaluateUnevaluated} loading={batchEvaluating}>批量评估未评估商品</Button>
          {/* 列配置：拖拽调整列顺序 + 显示/隐藏字段，配置持久化到 localStorage */}
          <Button icon={<SettingOutlined />} onClick={() => setColumnConfigOpen(true)}>列配置</Button>
          {/* O-05-26 数据导出：按当前任务过滤导出评估记录 CSV */}
          <ExportButton dataset="evaluations" params={{ task_id: taskId || undefined }} />
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

      {/* 统计卡片 —— 前5个可点击触发后端过滤，选中态高亮 */}
      {dist && (
        <Row gutter={12} style={{ marginBottom: 16 }}>
          <Col span={4}>
            <Card
              size="small" hoverable
              onClick={() => { toggleResultCategory(null); setPage(1); setTimeout(load, 0) }}
              style={resultCategory === null ? { borderColor: '#1890ff', background: 'rgba(24,144,255,0.06)' } : {}}
            >
              <Statistic title="评估总数" value={dist.total} />
            </Card>
          </Col>
          <Col span={4}>
            <Card
              size="small" hoverable
              onClick={() => { toggleResultCategory('auto'); setPage(1); setTimeout(load, 0) }}
              style={resultCategory === 'auto' ? { borderColor: '#52c41a', background: 'rgba(82,196,26,0.06)' } : {}}
            >
              <Statistic title={`可抢(≥${autoBuyScore})`} value={dist.marginals.result.auto} valueStyle={{ color: '#52c41a' }} />
            </Card>
          </Col>
          <Col span={4}>
            <Card
              size="small" hoverable
              onClick={() => { toggleResultCategory('pass'); setPage(1); setTimeout(load, 0) }}
              style={resultCategory === 'pass' ? { borderColor: '#1890ff', background: 'rgba(24,144,255,0.06)' } : {}}
            >
              <Statistic title={`通过(${passScore}-${autoBuyScore - 1})`} value={dist.marginals.result.pass} valueStyle={{ color: '#1890ff' }} />
            </Card>
          </Col>
          <Col span={4}>
            <Card
              size="small" hoverable
              onClick={() => { toggleResultCategory('fail'); setPage(1); setTimeout(load, 0) }}
              style={resultCategory === 'fail' ? { borderColor: '#ff4d4f', background: 'rgba(255,77,79,0.06)' } : {}}
            >
              <Statistic title={`驳回(<${passScore})`} value={dist.marginals.result.fail} valueStyle={{ color: '#ff4d4f' }} />
            </Card>
          </Col>
          <Col span={4}>
            <Card
              size="small" hoverable
              onClick={() => { toggleResultCategory('insufficient'); setPage(1); setTimeout(load, 0) }}
              style={resultCategory === 'insufficient' ? { borderColor: '#faad14', background: 'rgba(250,173,20,0.06)' } : {}}
            >
              <Statistic title="数据不足" value={dist.insufficient_count} valueStyle={{ color: 'var(--xh-text-tertiary)' }} />
            </Card>
          </Col>
          <Col span={4}>
            <Card size="small" hoverable>
              <Statistic title="价格区间" value={dist.price_range[0] > 0 ? `¥${dist.price_range[0]}~${dist.price_range[1]}` : '—'} />
            </Card>
          </Col>
        </Row>
      )}

      <Row gutter={16}>
        {/* 左侧：列表 —— 折叠右侧面板时自动扩展到 23/24 宽度 */}
        <Col span={panelCollapsed ? 23 : 16}>
          <Card
            // 折叠/展开时 Col span 离散跳变，给 Card 加过渡柔化宽度突变
            style={{ transition: 'all 0.2s ease' }}
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
                      loading={batchAIEvaluating}
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
                description={(batchAIEvaluating || batchCollecting) && (
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
                <Empty description={resultCategory ? '当前过滤条件下无匹配记录' : '暂无评估数据'} />
              ) : (
                <Table
                  columns={visibleColumns}
                  dataSource={items}
                  rowKey={(r) => `${r.item_id}-${r.created_at}`}
                  size="middle"
                  rowSelection={{
                    selectedRowKeys,
                    onChange: (keys) => setSelectedRowKeys(keys),
                  }}
                  // 横向滚动：保证窄屏下所有列仍可访问；
                  // 折叠右侧面板时列宽总和增加，scrollX 同步扩展
                  scroll={{ x: scrollX }}
                  expandable={{
                    expandedRowRender,
                    rowExpandable: () => true,
                  }}
                  pagination={{
                    // 后端按 result_category 过滤后已分页返回，前端直接消费 page/total
                    current: page,
                    pageSize: pageSize,
                    total: total,
                    showSizeChanger: true,
                    showQuickJumper: true,
                    pageSizeOptions: ['10', '20', '50', '100'],
                    // 极窄屏隐藏快速跳转，避免按钮溢出
                    showLessItems: true,
                    onChange: (p, ps) => { setPage(p); setPageSize(ps) },
                    showTotal: (t) => resultCategory ? `过滤后 ${t} 条` : `共 ${t} 条`,
                  }}
                />
              )}
            </Spin>
          </Card>
        </Col>

        {/* 右侧：分析面板 —— 折叠时变为窄竖条，展开时显示完整图表列 */}
        <Col span={panelCollapsed ? 1 : 8}>
          {panelCollapsed ? (
            <CollapsibleRail onExpand={() => setPanelCollapsed(false)} />
          ) : (
            <>
              <EvalHeatmap
                dist={dist}
                distRange={distRange}
                distLoading={distLoading}
                onRangeChange={setDistRange}
              />

              <ResultBarChart dist={dist} passScore={passScore} autoBuyScore={autoBuyScore} />

              <PriceHistogram dist={dist} />

              {/* 阈值建议 */}
              <Card title={<><AimOutlined style={{ marginRight: 6 }} />阈值建议</>} style={{ marginTop: 16 }}>
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
              <Card title={<><CalculatorOutlined style={{ marginRight: 6 }} />阈值通过率计算器</>} style={{ marginTop: 16 }}>
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
            </>
          )}
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
                      <Tag key={`${sig}-${i}`} color="orange" style={{ marginBottom: 4 }}>{sig}</Tag>
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

      {/* O-13-26 AI 深度多模态分析弹窗：4 维鉴伪 */}
      <Modal
        title={`AI 深度鉴伪 - ${deepItemId}`}
        open={deepModalOpen}
        onCancel={() => setDeepModalOpen(false)}
        footer={<Button onClick={() => setDeepModalOpen(false)}>关闭</Button>}
        width={720}
      >
        <Spin spinning={deepLoading} tip="多模态分析中，最多 90s...">
          {deepResult ? (
            <div>
              {/* 顶部：综合结论 */}
              <Descriptions
                size="small"
                column={3}
                bordered
                style={{ marginBottom: 12 }}
                items={[
                  {
                    key: 'verdict',
                    label: '综合结论',
                    children: <VerdictTag verdict={deepResult.overall_verdict} />,
                  },
                  {
                    key: 'score',
                    label: '综合评分',
                    children: (
                      <span style={{ fontWeight: 600 }}>
                        {deepResult.overall_score}/10
                      </span>
                    ),
                  },
                  {
                    key: 'source',
                    label: '数据来源',
                    children: deepResult.source === 'llm' ? 'AI Vision' : '规则模拟',
                  },
                ]}
              />
              <Alert
                type={(() => {
                  const verdict = deepResult.overall_verdict
                  if (verdict === 'recommend') return 'success'
                  if (verdict === 'caution') return 'warning'
                  return 'error'
                })()}
                showIcon
                message={deepResult.summary}
                style={{ marginBottom: 12 }}
              />
              {/* 四维分析 Tab：仅展示 checks_performed 中实际执行的维度 */}
              <Tabs
                items={[
                  ...(deepResult.stolen_image ? [{
                    key: 'stolen_image',
                    label: '盗图检测',
                    children: (
                      <DeepCheckPanel
                        title="盗图检测"
                        check={deepResult.stolen_image}
                        signalLabel="风险信号"
                      />
                    ),
                  }] : []),
                  ...(deepResult.damage ? [{
                    key: 'damage',
                    label: '物理损坏',
                    children: (
                      <DeepCheckPanel
                        title="物理损坏识别"
                        check={deepResult.damage}
                        signalLabel="损坏类型"
                      />
                    ),
                  }] : []),
                  ...(deepResult.consistency ? [{
                    key: 'consistency',
                    label: '一致性',
                    children: (
                      <DeepCheckPanel
                        title="描述与图片一致性"
                        check={deepResult.consistency}
                        signalLabel="不一致项"
                      />
                    ),
                  }] : []),
                  ...(deepResult.template ? [{
                    key: 'template',
                    label: '文案模板化',
                    children: (
                      <DeepCheckPanel
                        title="文案模板化检测"
                        check={deepResult.template}
                        signalLabel="风险信号"
                      />
                    ),
                  }] : []),
                ]}
              />
              {/* 图片哈希列表（调试/取证用，折叠隐藏） */}
              {deepResult.image_hashes && deepResult.image_hashes.length > 0 && (
                <Collapse
                  size="small"
                  style={{ marginTop: 8 }}
                  items={[{
                    key: 'hashes',
                    label: `图片哈希（${deepResult.image_hashes.length}）`,
                    children: (
                      <pre style={{ fontSize: 11, whiteSpace: 'pre-wrap', margin: 0 }}>
                        {deepResult.image_hashes.map(h => `${h.url}\n  → ${h.hash}`).join('\n')}
                      </pre>
                    ),
                  }]}
                />
              )}
            </div>
          ) : (
            !deepLoading && <Empty description="点击闪电按钮开始 AI 深度鉴伪" />
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
                      color: (() => {
                        const score = collectResult.evaluation.score
                        if (score == null) return '#999'
                        if (score >= 80) return '#52c41a'
                        if (score >= 60) return '#faad14'
                        return '#ff4d4f'
                      })(),
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
                          key={`${url}-${i}`}
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
                  <div key={`${review}-${i}`} style={{
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
                      // 翻译维度 key 为中文，保留原 key 在后缀括号内供调试定位
                      title={`${translateDimension(dim)} (${dim})`}
                      value={score}
                      valueStyle={{ fontSize: 16, color: (() => {
                        const num = Number(score)
                        if (num >= 70) return '#52c41a'
                        if (num >= 40) return '#faad14'
                        return '#ff4d4f'
                      })() }}
                    />
                  </Col>
                ))}
              </Row>
              {collectResult.evaluation.reject_reasons.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <strong>拒绝原因：</strong>
                  {collectResult.evaluation.reject_reasons.map((reason, i) => (
                    <Tag key={`${reason}-${i}`} color="orange" style={{ marginBottom: 4 }} title={reason}>
                      {translateRejectReason(reason)}
                    </Tag>
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

      {/* 列配置弹窗：拖拽调整列顺序 + 显示/隐藏字段 */}
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
