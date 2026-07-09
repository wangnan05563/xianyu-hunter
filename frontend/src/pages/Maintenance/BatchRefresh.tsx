import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert,
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
  Tooltip,
  Typography,
  message,
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
} from '../../api'
import { extractApiError } from '../../utils/apiError'
import { usePersistentState } from '../../hooks/usePersistentState'

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

// ISO 时间字符串 → 本地可读时间
function formatTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return iso
  }
}

// Statistic formatter 用：渲染上次执行时间，提取到顶层避免组件内嵌套子组件（SonarQube S6478）
function renderLastRunTimeText(time: string) {
  return <Text style={{ fontSize: 14 }}>{time}</Text>
}

// 毫秒 → 可读时长（如 "1分23秒"）
function formatElapsed(ms: number | null | undefined): string {
  if (!ms || ms < 0) return '—'
  const sec = Math.floor(ms / 1000)
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return m > 0 ? `${m}分${s}秒` : `${s}秒`
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

function CurrentBatchPanel() {
  const [status, setStatus] = useState<BatchRefreshStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [triggering, setTriggering] = useState(false)
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
  const [form] = Form.useForm<{ enabled: boolean; interval_minutes: number }>()
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
  const percent = progress && progress.total > 0
    ? Math.round((progress.current / progress.total) * 100)
    : 0

  // 拆分嵌套三元为独立变量，提升可读性（SonarQube S3358）
  const stoppedSuffix = lastResult?.stopped ? ' · 已停止' : ''
  const lastResultText = lastResult
    ? `成功 ${lastResult.success} · 失败 ${lastResult.failed} · 跳过 ${lastResult.skipped}${stoppedSuffix}`
    : '暂无执行记录'
  // 触发按钮 Tooltip：用 if/else 替代嵌套三元（SonarQube S3358）
  let triggerTooltipText = ''
  if (inProgress) triggerTooltipText = '已有批次在运行，请先停止'
  else if (unavailable) triggerTooltipText = '调度器未启动'

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
          <Button icon={<ReloadOutlined />} onClick={() => loadStatus()} loading={loading}>
            刷新状态
          </Button>
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
              <Button
                type="primary"
                size="small"
                icon={<SaveOutlined />}
                loading={saving}
                disabled={unavailable}
                onClick={handleSaveConfig}
              >
                保存
              </Button>
            }
          >
            <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 16 }}>
              仅支持运行时热更新启用状态与触发间隔。如需修改 batch_size / max_items_per_run，请前往任务编辑器 Step 6 的「批量采集配置」弹窗。
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
            </Form>
          </Card>

          <Card title="任务控制">
            <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 16 }}>
              手动触发或控制当前批次。暂停/停止请求立即响应（&lt;500ms），实际生效在当前商品采集完成后。
            </Paragraph>

            {/* 触发按钮：仅空闲态可用 */}
            <Tooltip title={triggerTooltipText}>
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                loading={triggering}
                disabled={unavailable || inProgress}
                onClick={handleTrigger}
                block
                style={{ marginBottom: 12 }}
              >
                立即触发批量采集
              </Button>
            </Tooltip>

            {/* 控制按钮组：暂停/继续/停止 */}
            <Space style={{ width: '100%' }} direction="vertical">
              <Row gutter={8}>
                <Col span={12}>
                  <Button
                    block
                    icon={<PauseCircleOutlined />}
                    loading={controlling === 'pause'}
                    disabled={!running}
                    onClick={handlePause}
                  >
                    暂停
                  </Button>
                </Col>
                <Col span={12}>
                  <Button
                    block
                    type="primary"
                    icon={<PlayCircleOutlined />}
                    loading={controlling === 'resume'}
                    disabled={!paused}
                    onClick={handleResume}
                  >
                    继续
                  </Button>
                </Col>
              </Row>
              <Button
                block
                danger
                icon={<StopOutlined />}
                loading={controlling === 'stop'}
                disabled={!inProgress}
                onClick={handleStop}
              >
                停止（持久化进度，可续传）
              </Button>
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

function HistoryPanel() {
  const [loading, setLoading] = useState(false)
  const [items, setItems] = useState<BatchRefreshHistoryItem[]>([])
  const [total, setTotal] = useState(0)
  const [statusCounts, setStatusCounts] = useState<Record<string, number>>({})
  const [detail, setDetail] = useState<BatchRefreshHistoryItem | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)

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

  const handleCleanup = async (days: number) => {
    try {
      const res = await batchRefreshApi.cleanupHistory(days)
      message.success(`已清理 ${res.deleted} 条记录`)
      setPage(1)
      loadList()
    } catch (e) {
      message.error(extractApiError(e), 5)
    }
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
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleViewDetail(r)}
          >
            详情
          </Button>
          <Popconfirm
            title="确认删除此条历史记录？"
            onConfirm={() => handleDelete(r.id)}
            okText="删除"
            cancelText="取消"
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ], [])

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
      {/* 概览卡片：按状态聚合统计 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="总执行次数"
              value={total}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="已完成"
              value={statusCounts['completed'] ?? 0}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="已取消"
              value={statusCounts['cancelled'] ?? 0}
              valueStyle={{ color: '#fa8c16' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="已失败"
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
              <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>
                查询
              </Button>
              <Button onClick={handleReset}>重置</Button>
            </Space>
          </Col>
          <Col flex="auto" style={{ textAlign: 'right' }}>
            <Space>
              <Tooltip title="清理 30 天前的历史记录">
                <Popconfirm
                  title="确认清理 30 天前的历史记录？"
                  onConfirm={() => handleCleanup(30)}
                  okText="清理"
                  cancelText="取消"
                >
                  <Button icon={<DeleteOutlined />}>清理 30 天前</Button>
                </Popconfirm>
              </Tooltip>
              <Popconfirm
                title="确认清空全部历史记录？此操作不可恢复。"
                onConfirm={() => handleCleanup(0)}
                okText="清空"
                okButtonProps={{ danger: true }}
                cancelText="取消"
              >
                <Button danger icon={<DeleteOutlined />}>清空全部</Button>
              </Popconfirm>
              <Button icon={<ReloadOutlined />} onClick={loadList} loading={loading}>
                刷新
              </Button>
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
