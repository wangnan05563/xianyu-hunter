import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { formatDateTime as formatTime, formatDuration } from '../../utils/timeFormat'
import {
  Alert,
  App,
  Button,
  Card,
  Col,
  DatePicker,
  Drawer,
  Form,
  InputNumber,
  Popconfirm,
  Progress,
  Row,
  Select,
  Space,
  Statistic,
  Switch,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
  notification,
} from 'antd'
import type { TableColumnsType, TableProps } from 'antd'
import type { Dayjs } from 'dayjs'
import {
  DeleteOutlined,
  EyeOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  SaveOutlined,
  SearchOutlined,
  StopOutlined,
} from '@ant-design/icons'
import {
  batchRefreshApi,
  type BatchRefreshChangeLogEntry,
  type BatchRefreshHistoryItem,
  type BatchRefreshHistoryQuery,
  type BatchRefreshHistoryStatus,
  type BatchRefreshStatus,
  type BatchRefreshTriggerSource,
  type BatchRefreshTriggerPreview,
} from '../../api'
import { extractApiError } from '../../utils/apiError'
import { usePersistentState } from '../../hooks/usePersistentState'
import { TipButton } from '@/components/TipButton'

const { Text, Paragraph } = Typography
const { RangePicker } = DatePicker

// 后端返回的字段名 → 中文显示
const FIELD_LABELS: Record<string, string> = {
  title: '标题',
  price: '价格',
  seller_id: '卖家',
  region: '地区',
  thumb_url: '缩略图',
  want_cnt: '想要数',
  view_cnt: '浏览数',
  is_sold: '已售状态',
}

// 调度器状态 → Tag 颜色与文案
function renderStatusTag(status: BatchRefreshStatus['status']) {
  switch (status) {
    case 'running':
      return <Tag color="processing">执行中</Tag>
    case 'paused':
      return <Tag color="warning">已暂停</Tag>
    case 'stopping':
      return <Tag color="orange">停止中</Tag>
    case 'idle':
      return <Tag color="success">空闲</Tag>
    default:
      return <Tag color="default">未启动</Tag>
  }
}

// 历史记录状态 → Tag 颜色与文案
const HISTORY_STATUS_META: Record<
  BatchRefreshHistoryStatus,
  { color: string; label: string }
> = {
  running: { color: 'processing', label: '执行中' },
  completed: { color: 'success', label: '已完成' },
  cancelled: { color: 'orange', label: '已取消' },
  failed: { color: 'error', label: '已失败' },
}

function renderHistoryStatusTag(status: BatchRefreshHistoryStatus) {
  const meta = HISTORY_STATUS_META[status] ?? { color: 'default', label: status }
  return <Tag color={meta.color}>{meta.label}</Tag>
}

// 触发来源 → Tag 文案
function renderTriggerSourceTag(source: BatchRefreshTriggerSource) {
  return source === 'scheduler' ? (
    <Tag color="blue">定时</Tag>
  ) : (
    <Tag color="purple">手动</Tag>
  )
}

// Statistic formatter 用：渲染上次执行时间，提取到顶层避免组件内嵌套子组件（SonarQube S6478）
function renderLastRunTimeText(time: string) {
  return <Text style={{ fontSize: 14 }}>{time}</Text>
}

// 毫秒 → 可读时长：单位词表与算法都交给 formatDuration，这里只做毫秒→秒的换算
function formatElapsed(ms: number | null | undefined): string {
  if (ms == null || ms < 0) return '—'
  return formatDuration(Math.floor(ms / 1000), { withSeconds: true })
}

// ===== T02578 批量采集收尾反馈：可单测的纯函数（4.4-1 / 4.4-3 / 4.4-5）=====

/** 批次运行态（会跃迁到 idle 的前置状态） */
const BATCH_ACTIVE_STATES = ['running', 'paused', 'stopping'] as const

/**
 * 「本批刚跑完」判定：上一帧是运行/暂停/停止，这一帧回到空闲。
 * 首帧（prev 为 null/undefined）一律不报——否则一进页面就把上次遗留的 last_result
 * 当成「刚完成的收尾」弹出来，是一种假回执。
 */
export function batchRunJustFinished(
  prev: string | null | undefined,
  next: string | null | undefined,
): boolean {
  const wasActive = prev != null && (BATCH_ACTIVE_STATES as readonly string[]).includes(prev)
  return wasActive && next === 'idle'
}

/** 收尾通知文案：数字一律取自后端 last_result，拿不到就明说拿不到 */
export function buildBatchFinishCopy(
  result: { success: number; failed: number; skipped: number; stopped?: boolean } | null | undefined,
  lastRunAt: string | null | undefined,
): { level: 'success' | 'warning' | 'info'; message: string; description: string } {
  const when = lastRunAt ? formatTime(lastRunAt) : '时间未回传'
  if (!result) {
    return {
      level: 'info',
      message: '批量采集已回到空闲',
      description: `本轮结束时间 ${when}，但后端未回传统计（成功/失败/跳过条数未知）。可在下方「执行历史」按状态筛选核对。`,
    }
  }
  const summary = `成功 ${result.success} · 失败 ${result.failed} · 跳过 ${result.skipped}`
  const tail = result.stopped ? '（本批次被手动停止，未处理商品已持久化，下次触发从断点续传）' : ''
  const level: 'success' | 'warning' = result.failed > 0 ? 'warning' : 'success'
  return {
    level,
    message: result.failed > 0 ? `批量采集结束：${summary}` : `批量采集完成：${summary}`,
    description: `最近一次批次记录于 ${when}${tail}。`,
  }
}

/** 清理预览状态（按 days 维度缓存，避免每次打开 Popconfirm 都重复请求） */
export type CleanupPreviewState = {
  status: 'loading' | 'ready' | 'error'
  matched?: number
}

/**
 * 清理确认框的口径说明（4.4-3）：条数必须来自 /history/cleanup-preview——
 * 它与真正 DELETE 的 WHERE 逐字同源，不能用当前筛选的 total 冒充「将被删除的条数」。
 */
export function cleanupPreviewDescription(
  state: CleanupPreviewState | undefined,
  days: number,
): string {
  if (!state || state.status === 'loading') return '正在统计将被删除的条数…'
  if (state.status === 'error' || state.matched == null) {
    return '条数统计失败：无法确认本次删除范围，请点「重试」后再确认'
  }
  const n = state.matched
  if (n === 0) {
    return days === 0 ? '当前没有可清空的执行历史（0 条）' : `当前没有 ${days} 天前的记录（0 条）`
  }
  return days === 0
    ? `将删除全部 ${n} 条执行历史（整表清空，不区分用户），操作不可恢复`
    : `将删除 ${days} 天前的 ${n} 条执行历史，操作不可恢复`
}

/** 触发前预估状态（T02771 / 4.4-2）：每次打开确认框都重新取，条数是活的 */
export type TriggerPreviewState = {
  status: 'loading' | 'ready' | 'error'
  data?: BatchRefreshTriggerPreview
}

/**
 * 触发确认框的口径说明（4.4-2）：条数来自 /trigger-preview，它与 `_prepare_batch_items`
 * 共用 `select_batch_items()`——不能拿商品表 count 或 history total 冒充。
 * 统计失败时绝不显示「0 个」：那会让用户以为本批没东西可跑。
 */
export function triggerPreviewDescription(state: TriggerPreviewState | undefined): string {
  if (!state || state.status === 'loading') return '正在统计本批将处理的商品数…'
  if (state.status === 'error' || !state.data) {
    return '本批范围统计失败：无法确认会跑多少商品，请点「重试」后再确认'
  }
  const { pending, limit, at_limit, resumed, resumed_processed, resumed_total } = state.data
  if (resumed) {
    return `从断点续传：原批次共 ${resumed_total} 个（已处理 ${resumed_processed} 个），本批将把剩余 ${pending} 个跑完`
  }
  if (pending === 0) return '本批无待处理商品（当前没有在售商品），确认不会启动浏览器'
  const cap = at_limit ? `（已达单次上限 ${limit}，本轮只跑这些）` : `（单次上限 ${limit}）`
  return `本批将采集 ${pending} 个在售商品${cap}`
}

/** 控制按钮的悬浮提示按当前状态生成（4.4-5：禁用态不能再写动作描述） */
export function controlButtonTips(flags: {
  running: boolean
  paused: boolean
  stopping: boolean
}): { pause: string; resume: string; stop: string } {
  const { running, paused, stopping } = flags
  const inProgress = running || paused || stopping
  let pause = '当前空闲，无可暂停批次'
  if (running) pause = '暂停当前批次，当前商品采集完成后生效'
  else if (stopping) pause = '正在停止当前批次，无需再暂停'
  else if (paused) pause = '批次已处于「已暂停」，无需再暂停'
  let resume = '仅当批次处于「已暂停」时可继续'
  if (paused) resume = '从断点继续当前批次'
  else if (running) resume = '当前正在采集，无需继续'
  const stop = inProgress
    ? '停止当前批次并持久化未处理商品，下次触发从断点续传'
    : '当前没有正在运行的批次，无需停止'
  return { pause, resume, stop }
}

export default function BatchRefresh() {
  // 当前 Tab：持久化到 localStorage，避免每次进入页面都回到默认 Tab
  const [activeTab, setActiveTab] = usePersistentState<'current' | 'history'>(
    'xh.batchRefresh.activeTab',
    'current',
    { validator: (v): v is 'current' | 'history' => v === 'current' || v === 'history' },
  )

  return (
    <div className="page-container">
      <div style={{ marginBottom: 16 }}>
        <Text type="secondary" style={{ fontSize: 13 }}>
          定时刷新在售商品详情 · 检测已售状态 · 补全字段变更 · 完整执行历史可追溯
        </Text>
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={(k) => setActiveTab(k as 'current' | 'history')}
        items={[
          { key: 'current', label: '当前执行', children: <CurrentBatchPanel /> },
          { key: 'history', label: '执行历史', children: <HistoryPanel /> },
        ]}
      />
    </div>
  )
}

// ============== Tab 1: 当前执行 ==============

// S3358：汇总 Alert 的 type 用分支函数推导，避免三元套三元
function resolveResultAlertType(lastResult: BatchRefreshStatus['last_result'] | undefined): 'warning' | 'success' | 'info' {
  if (!lastResult) return 'info'
  if (lastResult.failed > 0) return 'warning'
  return 'success'
}

// S3358：汇总文案里的「已手动停止」后缀与兜底文案拆成独立函数
function formatLastResultSummary(lastResult: BatchRefreshStatus['last_result'] | undefined): string {
  if (!lastResult) return '最近一次批次汇总：后端未回传统计'
  let stoppedSuffix = ''
  if (lastResult.stopped) stoppedSuffix = ' · 已手动停止'
  const base = `最近一次批次汇总：成功 ${lastResult.success} · 失败 ${lastResult.failed} · 跳过 ${lastResult.skipped}`
  return `${base}${stoppedSuffix}`
}

// S3776：进度百分比抽成纯函数，主组件不再保留条件表达式
function calcProgressPercent(progress: BatchRefreshStatus['progress'] | undefined): number {
  if (!progress || progress.total <= 0) return 0
  return Math.round((progress.current / progress.total) * 100)
}

function CurrentBatchPanel() {
  const [status, setStatus] = useState<BatchRefreshStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [triggering, setTriggering] = useState(false)
  // 触发前预估：每次打开确认框重新取（4.4-2，条数是活的，不能缓存）
  const [triggerPreview, setTriggerPreview] = useState<TriggerPreviewState | undefined>()
  const [controlling, setControlling] = useState<'pause' | 'resume' | 'stop' | null>(null)
  const [saving, setSaving] = useState(false)
  // 自动刷新开关：开启后根据状态动态调整轮询间隔
  // 持久化到 localStorage：避免用户每次进入页面都需重新开启，符合 UI 偏好跨会话保留的设计
  const [autoRefresh, setAutoRefresh] = usePersistentState<boolean>(
    'xh.batchRefresh.autoRefresh',
    false,
    { validator: (v): v is boolean => typeof v === 'boolean' },
  )
  // 触发/控制操作后强制高频轮询，直到 status 真正变化或超时
  // 为什么需要：trigger 后端是异步启动批次，status 不会立即变为 running，
  // 默认 10s 间隔会让用户感觉"页面未更新"
  const [forceFastPoll, setForceFastPoll] = useState(false)
  const [form] = Form.useForm<{
    enabled: boolean
    interval_minutes: number
    batch_size: number
    max_items_per_run: number
    history_retention_days: number
  }>()
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  // 标记表单是否已被用户修改，避免轮询拉取的状态覆盖用户正在编辑的未保存值
  const formDirtyRef = useRef(false)
  // forceFastPoll 安全兜底：避免因后端异常导致永远高频轮询
  const forceFastPollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const loadStatus = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const data = await batchRefreshApi.getStatus()
      setStatus(data)
      // 仅在表单未被用户修改时同步后端值，避免覆盖正在编辑的配置
      if (!formDirtyRef.current) {
        form.setFieldsValue({
          enabled: data.enabled,
          interval_minutes: data.interval_minutes,
          batch_size: data.batch_size,
          max_items_per_run: data.max_items_per_run,
          history_retention_days: data.history_retention_days,
        })
      }
    } catch (e) {
      if (!silent) message.error(extractApiError(e), 5)
    } finally {
      if (!silent) setLoading(false)
    }
  }, [form])

  useEffect(() => {
    loadStatus()
  }, [loadStatus])

  // 自动刷新轮询：根据状态动态调整间隔
  // running/paused/stopping 时 3s 高频轮询，便于观察进度
  // 其他状态 10s 低频轮询，减少不必要的网络请求
  // forceFastPoll（trigger/控制操作后）强制 3s 高频，避免等待 status 变化
  useEffect(() => {
    if (!autoRefresh) {
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
      return
    }
    const fast = forceFastPoll
      || (status != null && ['running', 'paused', 'stopping'].includes(status.status))
    const interval = fast ? 3000 : 10000
    timerRef.current = setInterval(() => loadStatus(true), interval)
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
    }
  }, [autoRefresh, status?.status, forceFastPoll, loadStatus])

  // 当 status 真正进入运行/暂停/停止态后，解除 forceFastPoll
  // 让正常的间隔逻辑接管，避免长期高频请求
  useEffect(() => {
    if (!forceFastPoll) return
    if (status && ['running', 'paused', 'stopping'].includes(status.status)) {
      setForceFastPoll(false)
      if (forceFastPollTimerRef.current) {
        clearTimeout(forceFastPollTimerRef.current)
        forceFastPollTimerRef.current = null
      }
    }
  }, [status?.status, forceFastPoll])

  // 4.4-1 收尾反馈：记录上一帧状态，运行/暂停/停止 → 空闲 时弹汇总通知
  // 只在跃迁那一刻弹一次（轮询本身每 3s 一次，不加闸门会变成刷屏假回执）
  const prevStatusRef = useRef<string | null>(null)
  useEffect(() => {
    const current = status?.status ?? null
    if (batchRunJustFinished(prevStatusRef.current, current)) {
      const copy = buildBatchFinishCopy(status?.last_result, status?.last_run_at)
      notification[copy.level]({
        message: copy.message,
        description: copy.description,
        duration: 6,
        placement: 'bottomRight',
      })
    }
    prevStatusRef.current = current
  }, [status])

  // 组件卸载时清理 forceFastPoll 兜底定时器
  useEffect(() => {
    return () => {
      if (forceFastPollTimerRef.current) {
        clearTimeout(forceFastPollTimerRef.current)
        forceFastPollTimerRef.current = null
      }
    }
  }, [])

  // 触发/控制操作后开启短期高频轮询（最多 30s 兜底）
  // 30s 兜底理由：单个商品采集 + asyncio.sleep(0.3) 一般 < 30s 能切到 running，
  // 超时仍未变化则认为后端启动失败，自动恢复低频轮询避免持续无意义请求。
  const startForceFastPoll = useCallback(() => {
    setForceFastPoll(true)
    if (forceFastPollTimerRef.current) {
      clearTimeout(forceFastPollTimerRef.current)
    }
    forceFastPollTimerRef.current = setTimeout(() => {
      setForceFastPoll(false)
      forceFastPollTimerRef.current = null
    }, 30000)
  }, [])

  const loadTriggerPreview = async () => {
    setTriggerPreview({ status: 'loading' })
    try {
      const data = await batchRefreshApi.triggerPreview()
      setTriggerPreview({ status: 'ready', data })
    } catch {
      // 不降级成 0：统计失败必须让用户重试，而不是让他以为本批没东西可跑
      setTriggerPreview({ status: 'error' })
    }
  }

  const previewReady = triggerPreview?.status === 'ready' && triggerPreview.data != null
  const previewEmpty = previewReady && (triggerPreview?.data?.pending ?? 0) === 0
  const canConfirmTrigger = previewReady && !previewEmpty

  const handleTrigger = async () => {
    setTriggering(true)
    try {
      const result = await batchRefreshApi.trigger()
      message.success(`已触发批量采集（任务 ID: ${result.task_id}）`)
      // 立即开启高频轮询，不等 status 变化
      setAutoRefresh(true)
      startForceFastPoll()
      await loadStatus(true)
    } catch (e) {
      message.error(extractApiError(e), 5)
    } finally {
      setTriggering(false)
    }
  }

  const handlePause = async () => {
    setControlling('pause')
    try {
      await batchRefreshApi.pause()
      message.success('暂停请求已发送，将在当前商品采集完成后生效')
      startForceFastPoll()
      await loadStatus(true)
    } catch (e) {
      message.error(extractApiError(e), 5)
    } finally {
      setControlling(null)
    }
  }

  const handleResume = async () => {
    setControlling('resume')
    try {
      await batchRefreshApi.resume()
      message.success('已继续执行批量采集')
      startForceFastPoll()
      await loadStatus(true)
    } catch (e) {
      message.error(extractApiError(e), 5)
    } finally {
      setControlling(null)
    }
  }

  const handleStop = async () => {
    setControlling('stop')
    try {
      await batchRefreshApi.stop()
      message.success('停止请求已发送，未处理的商品已持久化，下次触发将从断点续传')
      startForceFastPoll()
      await loadStatus(true)
    } catch (e) {
      message.error(extractApiError(e), 5)
    } finally {
      setControlling(null)
    }
  }

  const handleSaveConfig = async () => {
    try {
      const values = await form.validateFields()
      setSaving(true)
      await batchRefreshApi.patchConfig({
        enabled: values.enabled,
        interval_minutes: values.interval_minutes,
        batch_size: values.batch_size,
        max_items_per_run: values.max_items_per_run,
        history_retention_days: values.history_retention_days,
      })
      message.success('配置已热更新')
      // 保存成功后清除 dirty 标记，让后续轮询可以同步后端值
      formDirtyRef.current = false
      await loadStatus(true)
    } catch (e) {
      if ((e as { errorFields?: unknown }).errorFields) return
      message.error(extractApiError(e), 5)
    } finally {
      setSaving(false)
    }
  }

  const unavailable = status?.status === 'unavailable'
  const running = status?.status === 'running'
  const paused = status?.status === 'paused'
  const stopping = status?.status === 'stopping'
  const inProgress = running || paused || stopping
  const lastResult = status?.last_result
  const progress = status?.progress
  const percent = calcProgressPercent(progress)

  // 拆分嵌套三元为独立变量，提升可读性（SonarQube S3358）
  const stoppedSuffix = lastResult?.stopped ? ' · 已停止' : ''
  const lastResultText = lastResult
    ? `成功 ${lastResult.success} · 失败 ${lastResult.failed} · 跳过 ${lastResult.skipped}${stoppedSuffix}`
    : '暂无执行记录'
  // 触发按钮 Tooltip：用 if/else 替代嵌套三元（SonarQube S3358）
  let triggerTooltipText = '立即触发一次批量采集'
  if (inProgress) triggerTooltipText = '已有批次在运行，请先停止'
  else if (unavailable) triggerTooltipText = '调度器未启动'
  // 4.4-5：暂停/继续/停止的提示按当前状态生成，禁用态不再写「能做的动作」
  const tips = controlButtonTips({ running, paused, stopping })

  return (
    <>
      {/* 页面标题与刷新按钮 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Text type="secondary">实时查看当前批次的执行进度与状态</Text>
        <Space>
          <Space size="small">
            <Text type="secondary" style={{ fontSize: 12 }}>自动刷新</Text>
            <Switch size="small" checked={autoRefresh} onChange={setAutoRefresh} />
          </Space>
          <TipButton tip="刷新当前批次执行状态" icon={<ReloadOutlined />} onClick={() => loadStatus()} loading={loading}>
            刷新状态
          </TipButton>
        </Space>
      </div>

      {/* 状态提示 Alert */}
      {unavailable && (
        <Alert
          type="warning"
          showIcon
          message="批量采集调度器未启动"
          description="需同时满足：① 启动参数 XH_WITH_SCHEDULER=1；② 配置文件 batch_refresh.enabled=true。修改后需重启后端服务。"
          style={{ marginBottom: 16 }}
        />
      )}
      {running && (
        <Alert
          type="info"
          showIcon
          message="批量采集任务执行中"
          description="任务正在主事件循环中执行，每个商品采集后让出 0.3s 给主业务请求。可点击下方暂停按钮等待当前商品完成后暂停。"
          style={{ marginBottom: 16 }}
        />
      )}
      {paused && (
        <Alert
          type="warning"
          showIcon
          message="批量采集已暂停"
          description="当前批次已暂停，进度已保留。点击继续从断点处恢复执行，或点击停止持久化未处理商品。"
          style={{ marginBottom: 16 }}
        />
      )}
      {stopping && (
        <Alert
          type="warning"
          showIcon
          message="正在停止当前批次"
          description="停止请求已发送，等待当前商品采集完成后停止。未处理的商品将持久化，下次触发时从断点续传。"
          style={{ marginBottom: 16 }}
        />
      )}

      {/* 4.4-1 结果汇总面板：空闲态常驻，错过收尾通知也能看到同一份真实计数 */}
      {!inProgress && status != null && (
        <Alert
          type={resolveResultAlertType(lastResult)}
          showIcon
          message={formatLastResultSummary(lastResult)}
          description={
            <span style={{ fontSize: 12 }}>
              统计时间 {formatTime(status.last_run_at ?? null)}；这是后端记录的最近一次批次结果，
              不一定是刚刚结束的一轮。失败明细可在下方「执行历史」里按状态=已失败筛选查看。
            </span>
          }
          style={{ marginBottom: 16 }}
        />
      )}

      {/* 进度条卡片：仅在运行中/暂停中/停止中显示 */}
      {inProgress && progress && (
        <Card style={{ marginBottom: 16 }}>
          <Row gutter={16} align="middle">
            <Col flex="auto">
              <Progress
                percent={percent}
                status={(() => {
                  // 暂停用 normal 停动画，停止中用 exception，运行中用 active
                  if (paused) return 'normal'
                  if (stopping) return 'exception'
                  return 'active'
                })()}
                format={(p) => `${p}% (${progress.current}/${progress.total})`}
              />
              <div style={{ marginTop: 8, fontSize: 12, color: 'var(--xh-text-tertiary)' }}>
                {progress.current_item_id ? (
                  <span>正在采集: <Text code style={{ fontSize: 12 }}>{progress.current_item_id}</Text></span>
                ) : (
                  <span>等待下一个商品…</span>
                )}
                <span style={{ marginLeft: 16 }}>已耗时: {formatElapsed(progress.elapsed_ms ?? 0)}</span>
              </div>
            </Col>
          </Row>
        </Card>
      )}

      {/* 状态概览：4 列 Statistic */}
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={24}>
          <Col span={6}>
            <Statistic
              title="调度器状态"
              formatter={() => renderStatusTag(status?.status ?? 'unavailable')}
            />
            <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginTop: 4 }}>
              {status?.enabled ? '配置已启用' : '配置已禁用'}
            </div>
          </Col>
          <Col span={6}>
            <Statistic
              title="触发间隔"
              value={status?.interval_minutes ?? 0}
              suffix="分钟"
            />
            <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginTop: 4 }}>
              由 APScheduler 按 interval 触发
            </div>
          </Col>
          <Col span={6}>
            <Statistic
              title="上次执行时间"
              // 调用顶层函数避免在 formatter 内联 JSX 子组件（SonarQube S6478）
              formatter={() => renderLastRunTimeText(formatTime(status?.last_run_at ?? null))}
            />
            <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginTop: 4 }}>
              {lastResultText}
            </div>
          </Col>
          <Col span={6}>
            <Statistic
              title="变更日志条数"
              value={status?.change_log?.length ?? 0}
              suffix="/ 50"
            />
            <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginTop: 4 }}>
              仅展示最近 50 条（内存上限 1000）
            </div>
          </Col>
        </Row>
      </Card>

      <Row gutter={16}>
        {/* 左侧：配置热更新 + 任务控制 */}
        <Col span={10}>
          <Card
            title="配置热更新"
            style={{ marginBottom: 16 }}
            extra={
              <TipButton
                tip="保存并热更新配置"
                type="primary"
                size="small"
                icon={<SaveOutlined />}
                loading={saving}
                disabled={unavailable}
                onClick={handleSaveConfig}
              >
                保存
              </TipButton>
            }
          >
            <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 16 }}>
              启用状态与触发间隔修改后立即生效；批次大小、单次上限与历史保留天数保存后写入配置文件，下次批次运行时生效。
            </Paragraph>
            <Form
              form={form}
              layout="vertical"
              disabled={unavailable}
              onValuesChange={() => {
                // 用户开始编辑后标记 dirty，避免后续轮询覆盖未保存的值
                formDirtyRef.current = true
              }}
            >
              <Form.Item
                label="启用批量采集"
                name="enabled"
                valuePropName="checked"
                tooltip="关闭后调度器不会定时触发采集（不影响已注册 job 的下次启动）"
              >
                <Switch checkedChildren="开" unCheckedChildren="关" />
              </Form.Item>
              <Form.Item
                label="触发间隔"
                tooltip="修改后立即 reschedule 定时任务，单位：分钟"
              >
                <Space.Compact style={{ width: 200 }}>
                  <Form.Item
                    name="interval_minutes"
                    rules={[
                      { required: true, message: '请输入触发间隔' },
                      { type: 'number', min: 1, max: 1440, message: '范围 1-1440 分钟' },
                    ]}
                    noStyle
                  >
                    <InputNumber min={1} max={1440} style={{ width: '100%' }} />
                  </Form.Item>
                  <div className="ant-input-number-group-addon" style={{ display: 'flex', alignItems: 'center', padding: '0 11px', background: 'var(--xh-bg-spotlight, rgba(0,0,0,0.06))', border: '1px solid var(--xh-border-color, #d9d9d9)', borderLeft: 'none', borderRadius: '0 6px 6px 0' }}>
                    分钟
                  </div>
                </Space.Compact>
              </Form.Item>
              <Form.Item
                label="批次大小"
                name="batch_size"
                tooltip="每批从数据库拉取的最大商品数（分页控制），范围 1-500"
              >
                <InputNumber min={1} max={500} style={{ width: 200 }} />
              </Form.Item>
              <Form.Item
                label="单次运行上限"
                name="max_items_per_run"
                tooltip="单次批量采集最多处理的商品数，防止长时间占用浏览器，范围 1-10000"
              >
                <InputNumber min={1} max={10000} style={{ width: 200 }} />
              </Form.Item>
              <Form.Item
                label="历史保留天数"
                name="history_retention_days"
                tooltip="执行历史保留天数，超过此天数启动时自动清理；0=永不清理，范围 0-3650"
              >
                <InputNumber min={0} max={3650} style={{ width: 200 }} />
              </Form.Item>
            </Form>
          </Card>

          <Card title="任务控制">
            <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 16 }}>
              手动触发或控制当前批次。暂停/停止请求立即响应（&lt;500ms），实际生效在当前商品采集完成后。
            </Paragraph>

            {/* 触发按钮：仅空闲态可用；确认框先展示本批范围（4.4-2） */}
            <Popconfirm
              title="触发批量采集"
              description={
                <>
                  <div>{triggerPreviewDescription(triggerPreview)}</div>
                  {triggerPreview?.status === 'error' && (
                    <Button type="link" size="small" style={{ padding: 0 }} onClick={() => void loadTriggerPreview()}>
                      重试
                    </Button>
                  )}
                </>
              }
              onOpenChange={(open) => {
                if (open) void loadTriggerPreview()
              }}
              onConfirm={handleTrigger}
              okText={previewEmpty ? '本批无待处理商品' : '开始采集'}
              cancelText="取消"
              okButtonProps={{ disabled: !canConfirmTrigger, loading: triggering }}
            >
              <TipButton
                tip={triggerTooltipText}
                type="primary"
                icon={<PlayCircleOutlined />}
                loading={triggering}
                disabled={unavailable || inProgress}
                block
                style={{ marginBottom: 12 }}
              >
                立即触发批量采集
              </TipButton>
            </Popconfirm>

            {/* 控制按钮组：暂停/继续/停止 */}
            <Space style={{ width: '100%' }} direction="vertical">
              <Row gutter={8}>
                <Col span={12}>
                  <TipButton
                    tip={tips.pause}
                    block
                    icon={<PauseCircleOutlined />}
                    loading={controlling === 'pause'}
                    disabled={!running}
                    onClick={handlePause}
                  >
                    暂停
                  </TipButton>
                </Col>
                <Col span={12}>
                  <TipButton
                    tip={tips.resume}
                    block
                    type="primary"
                    icon={<PlayCircleOutlined />}
                    loading={controlling === 'resume'}
                    disabled={!paused}
                    onClick={handleResume}
                  >
                    继续
                  </TipButton>
                </Col>
              </Row>
              <TipButton
                tip={tips.stop}
                block
                danger
                icon={<StopOutlined />}
                loading={controlling === 'stop'}
                disabled={!inProgress}
                onClick={handleStop}
              >
                停止（持久化进度，可续传）
              </TipButton>
            </Space>
          </Card>
        </Col>

        {/* 右侧：变更日志 */}
        <Col span={14}>
          <Card
            title="变更日志"
            extra={<Text type="secondary" style={{ fontSize: 12 }}>最近 50 条</Text>}
          >
            <Table<BatchRefreshChangeLogEntry>
              size="small"
              rowKey={(r) => `${r.item_id}_${r.timestamp}`}
              dataSource={status?.change_log ?? []}
              pagination={{ pageSize: 10, size: 'small' }}
              locale={{ emptyText: '暂无变更记录' }}
              scroll={{ x: 480 }}
              columns={[
                {
                  title: '商品 ID',
                  dataIndex: 'item_id',
                  key: 'item_id',
                  width: 160,
                  ellipsis: true,
                },
                {
                  title: '变更字段',
                  dataIndex: 'changed_fields',
                  key: 'changed_fields',
                  render: (fields: string[]) => (
                    <Space size={[4, 4]} wrap>
                      {fields.map((f) => (
                        <Tag key={f} color="orange">{FIELD_LABELS[f] ?? f}</Tag>
                      ))}
                    </Space>
                  ),
                },
                {
                  title: '时间',
                  dataIndex: 'timestamp',
                  key: 'timestamp',
                  width: 180,
                  render: (ts: string) => <Text style={{ fontSize: 12 }}>{formatTime(ts)}</Text>,
                },
              ]}
            />
          </Card>
        </Col>
      </Row>
    </>
  )
}

// ============== Tab 2: 执行历史 ==============

// S2004：删除确认弹层提到模块级，避免 render→onClick→onOk 三层闭包嵌套
function confirmDeleteHistory(
  modal: ReturnType<typeof App.useApp>['modal'],
  record: BatchRefreshHistoryItem,
  onDelete: (id: number) => void | Promise<void>,
) {
  modal.confirm({
    title: '确认删除此条历史记录？',
    okText: '删除',
    cancelText: '取消',
    onOk: () => onDelete(record.id),
  })
}

function HistoryPanel() {
  // 删除确认走 App 上下文的 modal（T02975）：操作列 fixed:'right' 是 sticky 单元格，
  // Popconfirm 的 trigger 在横向滚动时反复重算位置（同 T02671 的因果链）
  const { modal } = App.useApp()
  const [loading, setLoading] = useState(false)
  const [items, setItems] = useState<BatchRefreshHistoryItem[]>([])
  const [total, setTotal] = useState(0)
  const [statusCounts, setStatusCounts] = useState<Record<string, number>>({})
  const [detail, setDetail] = useState<BatchRefreshHistoryItem | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)
  // 清理预览：按 days 缓存，Popconfirm 打开时拉取（4.4-3 分母同源）
  const [cleanupPreview, setCleanupPreview] = useState<
    Record<number, CleanupPreviewState>
  >({})
  const [cleaning, setCleaning] = useState<number | null>(null)

  // 筛选条件（持久化：刷新后保持上次筛选状态，与 ErrorLogs 页面风格一致）
  const [filterStatus, setFilterStatus] = usePersistentState<string | undefined>(
    'xh.batchRefresh.history.filterStatus',
    undefined,
    { validator: (v): v is string | undefined => v === undefined || typeof v === 'string' },
  )
  const [filterSource, setFilterSource] = usePersistentState<string | undefined>(
    'xh.batchRefresh.history.filterSource',
    undefined,
    { validator: (v): v is string | undefined => v === undefined || typeof v === 'string' },
  )
  const [filterTaskId, setFilterTaskId] = useState<string>('')
  const [filterDateRange, setFilterDateRange] = useState<[Dayjs | null, Dayjs | null] | null>(null)

  // 分页与排序
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [orderBy, setOrderBy] = useState<BatchRefreshHistoryQuery['order_by']>('started_at')
  const [orderDir, setOrderDir] = useState<BatchRefreshHistoryQuery['order_dir']>('desc')

  const buildQuery = useCallback((): BatchRefreshHistoryQuery => {
    const q: BatchRefreshHistoryQuery = {
      order_by: orderBy,
      order_dir: orderDir,
      limit: pageSize,
      offset: (page - 1) * pageSize,
    }
    if (filterStatus) q.status = filterStatus as BatchRefreshHistoryStatus
    if (filterSource) q.trigger_source = filterSource as BatchRefreshTriggerSource
    // task_id 输入框：空字符串不传，避免 0 被当作筛选条件
    if (filterTaskId.trim()) {
      const tid = Number(filterTaskId.trim())
      if (!Number.isNaN(tid)) q.task_id = tid
    }
    // 用可选链替代显式 null 检查，更简洁（SonarQube S6582）
    if (filterDateRange?.[0] && filterDateRange?.[1]) {
      q.start = filterDateRange[0].startOf('day').toISOString()
      q.end = filterDateRange[1].endOf('day').toISOString()
    }
    return q
  }, [orderBy, orderDir, pageSize, page, filterStatus, filterSource, filterTaskId, filterDateRange])

  // 4.4-4：是否有筛选条件生效——决定第一张卡的口径文案与顶部提示条是否出现
  const filtersActive =
    !!filterStatus || !!filterSource || !!filterTaskId.trim() || !!(filterDateRange?.[0] && filterDateRange?.[1])

  const loadList = useCallback(() => {
    setLoading(true)
    batchRefreshApi
      .listHistory(buildQuery())
      .then((res) => {
        setItems(res.items)
        setTotal(res.total)
        setStatusCounts(res.status_counts || {})
      })
      .catch(() => message.error('加载执行历史失败'))
      .finally(() => setLoading(false))
  }, [buildQuery])

  useEffect(() => {
    loadList()
  }, [loadList])

  const handleSearch = () => {
    setPage(1)
    loadList()
  }

  const handleReset = () => {
    setFilterStatus(undefined)
    setFilterSource(undefined)
    setFilterTaskId('')
    setFilterDateRange(null)
    setPage(1)
    // 状态更新是异步的，下一帧再加载确保使用新筛选值
    setTimeout(loadList, 0)
  }

  const handleViewDetail = (record: BatchRefreshHistoryItem) => {
    setDetailOpen(true)
    setDetailLoading(true)
    setDetail(null)
    // 列表项已含 error_messages，但调用详情接口可保证字段完整（避免列表接口未来裁剪字段）
    batchRefreshApi
      .getHistoryDetail(record.id)
      .then((data) => setDetail(data))
      .catch(() => message.error('加载详情失败'))
      .finally(() => setDetailLoading(false))
  }

  const handleDelete = async (id: number) => {
    try {
      await batchRefreshApi.deleteHistory(id)
      message.success('已删除')
      loadList()
    } catch (e) {
      message.error(extractApiError(e), 5)
    }
  }

  /**
   * 拉取「将被删除的条数」预览。
   * 走 /history/cleanup-preview：它与真正 DELETE 的 WHERE 同源（同一 user_id 过滤 +
   * started_at < cutoff），因此不能用当前筛选的 total 代替——那是「筛出来的条数」，
   * 与「会删掉的条数」不是一回事。
   */
  const loadCleanupPreview = async (days: number) => {
    setCleanupPreview((prev) => ({ ...prev, [days]: { status: 'loading' } }))
    try {
      const res = await batchRefreshApi.cleanupHistoryPreview(days)
      setCleanupPreview((prev) => ({ ...prev, [days]: { status: 'ready', matched: res.matched } }))
    } catch {
      setCleanupPreview((prev) => ({ ...prev, [days]: { status: 'error' } }))
    }
  }

  const handleCleanup = async (days: number) => {
    setCleaning(days)
    try {
      const res = await batchRefreshApi.cleanupHistory(days)
      message.success(`已清理 ${res.deleted} 条记录`)
      setPage(1)
      // 删除后计数已变，缓存必须作废，否则下次打开确认框还显示旧的「共 N 条」
      setCleanupPreview((prev) => ({ ...prev, [days]: { status: 'loading' } }))
      loadList()
      loadCleanupPreview(days)
    } catch (e) {
      message.error(extractApiError(e), 5)
    } finally {
      setCleaning(null)
    }
  }

  /**
   * 清理类确认框统一渲染（4.4-3）：
   * 打开即取预览条数 → description 如实告知范围与不可恢复 → 统计中/统计失败/0 条时禁用确认。
   */
  const renderCleanupPopconfirm = (
    days: number,
    title: string,
    okText: string,
    danger: boolean,
    trigger: ReactNode,
  ) => {
    const state = cleanupPreview[days]
    const canConfirm = state?.status === 'ready' && (state.matched ?? 0) > 0
    return (
      <Popconfirm
        title={title}
        description={
          <>
            <div>{cleanupPreviewDescription(state, days)}</div>
            {state?.status === 'error' && (
              <Button type="link" size="small" style={{ padding: 0 }} onClick={() => loadCleanupPreview(days)}>
                重试
              </Button>
            )}
          </>
        }
        onOpenChange={(open) => {
          if (open && cleanupPreview[days]?.status !== 'ready') loadCleanupPreview(days)
        }}
        onConfirm={() => handleCleanup(days)}
        okText={okText}
        cancelText="取消"
        okButtonProps={{ danger, disabled: !canConfirm, loading: cleaning === days }}
      >
        {trigger}
      </Popconfirm>
    )
  }

  // 表格列定义
  const columns: TableColumnsType<BatchRefreshHistoryItem> = useMemo(() => [
    {
      title: 'Task ID',
      dataIndex: 'task_id',
      key: 'task_id',
      width: 90,
      sorter: true,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      sorter: true,
      render: (s: BatchRefreshHistoryStatus) => renderHistoryStatusTag(s),
    },
    {
      title: '来源',
      dataIndex: 'trigger_source',
      key: 'trigger_source',
      width: 80,
      render: (s: BatchRefreshTriggerSource) => renderTriggerSourceTag(s),
    },
    {
      title: '开始时间',
      dataIndex: 'started_at',
      key: 'started_at',
      width: 170,
      sorter: true,
      render: (t: string) => <Text style={{ fontSize: 12 }}>{formatTime(t)}</Text>,
    },
    {
      title: '完成时间',
      dataIndex: 'completed_at',
      key: 'completed_at',
      width: 170,
      render: (t: string | null) => <Text style={{ fontSize: 12 }}>{formatTime(t)}</Text>,
    },
    {
      title: '耗时',
      dataIndex: 'duration_ms',
      key: 'duration_ms',
      width: 90,
      sorter: true,
      render: (ms: number | null) => formatElapsed(ms),
    },
    {
      title: '总数',
      dataIndex: 'total',
      key: 'total',
      width: 70,
    },
    {
      title: '成功/失败/跳过',
      key: 'counts',
      width: 160,
      render: (_: unknown, r: BatchRefreshHistoryItem) => (
        <Space size={4}>
          <Tag color="green">{r.success}</Tag>
          <Tag color="red">{r.failed}</Tag>
          <Tag color="default">{r.skipped}</Tag>
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 140,
      fixed: 'right',
      render: (_: unknown, r: BatchRefreshHistoryItem) => (
        <Space size={4}>
          <TipButton
            tip="查看该条执行历史详情"
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleViewDetail(r)}
          >
            详情
          </TipButton>
          <TipButton
            tip="删除该条历史记录，操作不可恢复"
            type="link"
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => confirmDeleteHistory(modal, r, handleDelete)}
          >
            删除
          </TipButton>
        </Space>
      ),
    },
  ], [modal])

  // antd Table 排序变化 → 同步到 state 并重新加载
  const handleTableChange: TableProps<BatchRefreshHistoryItem>['onChange'] = (
    pagination,
    _filters,
    sorter,
  ) => {
    if (pagination.current) setPage(pagination.current)
    if (pagination.pageSize) setPageSize(pagination.pageSize)
    // 单字段排序
    const s = Array.isArray(sorter) ? sorter[0] : sorter
    // 用可选链替代显式 null 检查，更简洁（SonarQube S6582）
    if (s?.field && s?.order) {
      // s.field 是 dataIndex（字符串）
      const fieldMap: Record<string, BatchRefreshHistoryQuery['order_by']> = {
        task_id: 'task_id',
        status: 'status',
        started_at: 'started_at',
        duration_ms: 'duration_ms',
      }
      const nextOrderBy = fieldMap[s.field as string]
      if (nextOrderBy) {
        setOrderBy(nextOrderBy)
        setOrderDir(s.order === 'ascend' ? 'asc' : 'desc')
      }
    }
  }

  // Drawer 内容：用 if/else 替代嵌套三元（SonarQube S3358）
  let drawerContent: React.ReactNode
  if (detailLoading) {
    drawerContent = (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Text type="secondary">加载中…</Text>
      </div>
    )
  } else if (detail) {
    drawerContent = <DetailContent detail={detail} />
  } else {
    drawerContent = (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Text type="secondary">暂无数据</Text>
      </div>
    )
  }

  return (
    <>
      {/* 4.4-4 统计口径：筛选生效时顶部说明「第一张卡是筛选命中数，后三张是全表累计」 */}
      {filtersActive && (
        <Alert
          type="info"
          showIcon
          closable
          message={<span style={{ fontSize: 12 }}>当前有筛选条件生效：「当前筛选结果数」按筛选统计，状态三张卡（已完成/已取消/已失败）始终是<b>全表累计</b>，两者口径不同不可直接相加。</span>}
          style={{ marginBottom: 12 }}
        />
      )}
      {/* 概览卡片：按状态聚合统计 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title={filtersActive ? '当前筛选结果数' : '执行记录总数'}
              value={total}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="已完成（全表累计）"
              value={statusCounts['completed'] ?? 0}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="已取消（全表累计）"
              value={statusCounts['cancelled'] ?? 0}
              valueStyle={{ color: '#fa8c16' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="已失败（全表累计）"
              value={statusCounts['failed'] ?? 0}
              valueStyle={{ color: '#ff4d4f' }}
            />
          </Card>
        </Col>
      </Row>

      {/* 筛选与操作栏 */}
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={[12, 12]} align="middle">
          <Col>
            <InputNumber
              placeholder="Task ID"
              style={{ width: 120 }}
              value={filterTaskId || undefined}
              onChange={(v) => setFilterTaskId(v == null ? '' : String(v))}
              onPressEnter={handleSearch}
            />
          </Col>
          <Col>
            <Select
              placeholder="状态"
              allowClear
              style={{ width: 130 }}
              value={filterStatus}
              onChange={(v) => setFilterStatus(v)}
              options={[
                { label: '执行中', value: 'running' },
                { label: '已完成', value: 'completed' },
                { label: '已取消', value: 'cancelled' },
                { label: '已失败', value: 'failed' },
              ]}
            />
          </Col>
          <Col>
            <Select
              placeholder="来源"
              allowClear
              style={{ width: 110 }}
              value={filterSource}
              onChange={(v) => setFilterSource(v)}
              options={[
                { label: '手动触发', value: 'manual' },
                { label: '定时触发', value: 'scheduler' },
              ]}
            />
          </Col>
          <Col>
            <RangePicker
              showTime={false}
              // filterDateRange 已是 [Dayjs | null, Dayjs | null] | null 类型，as 断言冗余（SonarQube S4325）
              value={filterDateRange}
              onChange={(range) => setFilterDateRange(range as [Dayjs | null, Dayjs | null] | null)}
            />
          </Col>
          <Col>
            <Space>
              <TipButton tip="按筛选条件查询执行历史" type="primary" icon={<SearchOutlined />} onClick={handleSearch}>
                查询
              </TipButton>
              <TipButton tip="重置所有筛选条件" onClick={handleReset}>重置</TipButton>
            </Space>
          </Col>
          <Col flex="auto" style={{ textAlign: 'right' }}>
            <Space>
              {renderCleanupPopconfirm(
                30,
                '确认清理 30 天前的执行历史？',
                '清理',
                true,
                <TipButton tip="清理 30 天前的执行历史" icon={<DeleteOutlined />}>清理 30 天前</TipButton>,
              )}
              {renderCleanupPopconfirm(
                0,
                '确认清空全部执行历史？此操作不可恢复。',
                '清空',
                true,
                <TipButton tip="清空全部执行历史，不可恢复" danger icon={<DeleteOutlined />}>清空全部</TipButton>,
              )}
              <TipButton tip="重新加载执行历史列表" icon={<ReloadOutlined />} onClick={loadList} loading={loading}>
                刷新
              </TipButton>
            </Space>
          </Col>
        </Row>
      </Card>

      {/* 历史记录表格 */}
      <Card>
        <Table<BatchRefreshHistoryItem>
          rowKey="id"
          loading={loading}
          dataSource={items}
          columns={columns}
          onChange={handleTableChange}
          scroll={{ x: 1200 }}
          size="small"
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (t) => `共 ${t} 条`,
            pageSizeOptions: [10, 20, 50, 100],
            onChange: (p, ps) => {
              setPage(p)
              setPageSize(ps)
            },
          }}
          locale={{ emptyText: '暂无执行历史记录' }}
        />
      </Card>

      {/* 详情抽屉 */}
      <Drawer
        title="执行历史详情"
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        width={640}
        destroyOnHidden
      >
        {drawerContent}
      </Drawer>
    </>
  )
}

// ============== 详情抽屉内容 ==============

function DetailContent({ detail }: { readonly detail: BatchRefreshHistoryItem }) {
  return (
    <div>
      <Row gutter={[16, 16]}>
        <Col span={12}>
          <Card size="small" title="基本信息">
            <p><Text type="secondary">历史 ID：</Text>{detail.id}</p>
            <p><Text type="secondary">Task ID：</Text>{detail.task_id}</p>
            <p>
              <Text type="secondary">状态：</Text>
              {renderHistoryStatusTag(detail.status)}
            </p>
            <p>
              <Text type="secondary">触发来源：</Text>
              {renderTriggerSourceTag(detail.trigger_source)}
            </p>
            <p><Text type="secondary">开始时间：</Text>{formatTime(detail.started_at)}</p>
            <p><Text type="secondary">完成时间：</Text>{formatTime(detail.completed_at)}</p>
            <p><Text type="secondary">执行耗时：</Text>{formatElapsed(detail.duration_ms)}</p>
            {detail.consecutive_failures > 0 && (
              <p>
                <Text type="secondary">连续失败次数：</Text>
                <Tag color="red">{detail.consecutive_failures}</Tag>
              </p>
            )}
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small" title="采集统计">
            <Statistic title="总数" value={detail.total} />
            <Row gutter={8} style={{ marginTop: 12 }}>
              <Col span={8}>
                <Statistic
                  title="成功"
                  value={detail.success}
                  valueStyle={{ color: '#52c41a', fontSize: 18 }}
                />
              </Col>
              <Col span={8}>
                <Statistic
                  title="失败"
                  value={detail.failed}
                  valueStyle={{ color: '#ff4d4f', fontSize: 18 }}
                />
              </Col>
              <Col span={8}>
                <Statistic
                  title="跳过"
                  value={detail.skipped}
                  valueStyle={{ color: '#8c8c8c', fontSize: 18 }}
                />
              </Col>
            </Row>
            {detail.total > 0 && (
              <div style={{ marginTop: 12 }}>
                <Progress
                  percent={Math.round(((detail.success + detail.failed) / detail.total) * 100)}
                  format={() => `${detail.success + detail.failed}/${detail.total}`}
                />
              </div>
            )}
          </Card>
        </Col>
      </Row>

      <Card
        size="small"
        title={`错误/警告消息 (${detail.error_messages.length})`}
        style={{ marginTop: 16 }}
      >
        {detail.error_messages.length === 0 ? (
          <Text type="secondary">本次执行未记录错误消息</Text>
        ) : (
          <div style={{ maxHeight: 360, overflowY: 'auto' }}>
            {detail.error_messages.map((err, idx) => (
              <div
                key={`${err.item_id}_${idx}`}
                style={{
                  padding: '8px 12px',
                  marginBottom: 8,
                  background: 'var(--xh-bg-secondary, #fafafa)',
                  borderRadius: 6,
                  borderLeft: '3px solid #ff4d4f',
                }}
              >
                <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginBottom: 4 }}>
                  <Text code style={{ fontSize: 11 }}>{err.item_id}</Text>
                  <span style={{ marginLeft: 8 }}>{formatTime(err.timestamp)}</span>
                </div>
                <div style={{ fontSize: 13, wordBreak: 'break-word', whiteSpace: 'pre-wrap' }}>
                  {err.error}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
