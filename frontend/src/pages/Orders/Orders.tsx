import { useEffect, useState, useCallback, useRef } from 'react'
import { formatDateTime, formatDuration } from '../../utils/timeFormat'
import {
  App, Card, Table, Tag, Select, Space, Spin, Statistic, Row, Col,
  message, Empty, Modal, Steps, Progress, Radio, InputNumber, Result,
  Alert, Tooltip,
} from 'antd'
import type { SortOrder } from 'antd/es/table/interface'
import { useSearchParams } from 'react-router-dom'
import {
  ReloadOutlined, ThunderboltOutlined, CheckOutlined, CloseOutlined,
  SmileOutlined, LoadingOutlined, DollarOutlined, SettingOutlined,
  DeleteOutlined, QuestionCircleOutlined,
} from '@ant-design/icons'
import { TipButton } from '@/components/TipButton'
import { orderApi, type OrderItem, type OrderStats } from '../../api'
import {
  ORDER_STATUS,
  orderStatusColor,
  orderStatusLabel,
  orderStatusOptions,
} from '../../constants/orderStatus'
import { usePersistentState } from '../../hooks/usePersistentState'
import { useColumnConfig, type ColumnConfig } from '../../hooks/useColumnConfig'
import ColumnSettingsModal from '../Evaluations/components/ColumnSettingsModal'
import { API_BASE } from '../../utils/apiBase'
import { parseOrderStatusParam } from '../../utils/alertDeepLink'
import ItemSummaryCell from './ItemSummaryCell'

// 列配置元数据：key 必须与下方 columns 定义中的 key 完全一致
const COLUMN_DEFINITIONS: ColumnConfig[] = [
  { key: 'id', label: 'ID' },
  { key: 'item_id', label: '商品ID' },
  { key: 'price', label: '金额' },
  { key: 'status', label: '状态', locked: true },
  { key: 'created_at', label: '创建时间' },
  { key: 'confirmed_at', label: '确认时间' },
  { key: 'takeover_deadline', label: '接管截止' },
  { key: 'action', label: '操作', locked: true },
]

// 状态中文标签与颜色统一来自 constants/orderStatus（与后端 OrderStatus 同源，T02716）
// 原先这里一份 STATUS_TEXT、移动端一份 STATUS_LABELS，两边都各自漏过值（桌面漏 cancelled）

// ============== 利润计算器 ==============

/** 费率选项：普通 0.6% / 鱼小铺 1.6% */
const FEE_RATES = [
  { label: '普通 0.6%', value: 0.006 },
  { label: '鱼小铺 1.6%', value: 0.016 },
]

function ProfitCalculator({ amount }: { readonly amount: number }) {
  const [feeRate, setFeeRate] = useState(0.006)
  const [buyPrice, setBuyPrice] = useState<number | null>(amount)

  // 利润 = 卖出价 - 买入价 - 手续费（手续费按卖出价计算）
  const sellPrice = amount
  const price = buyPrice ?? 0
  const fee = sellPrice * feeRate
  const profit = sellPrice - price - fee

  return (
    <div style={{ marginTop: 16, padding: 16, background: 'var(--xh-bg-spotlight)', borderRadius: 8 }}>
      <div style={{ fontWeight: 600, marginBottom: 12 }}>
        <DollarOutlined /> 利润计算器
      </div>

      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        <div>
          <span style={{ marginRight: 8 }}>费率：</span>
          <Radio.Group
            optionType="button"
            buttonStyle="solid"
            size="small"
            value={feeRate}
            onChange={(e) => setFeeRate(e.target.value)}
            options={FEE_RATES}
          />
        </div>

        <div>
          <span style={{ marginRight: 8 }}>买入价：</span>
          <InputNumber
            min={0}
            precision={2}
            value={buyPrice}
            onChange={(v) => setBuyPrice(v)}
            prefix="¥"
            style={{ width: 160 }}
          />
        </div>

        <div style={{ display: 'flex', gap: 32, fontSize: 14 }}>
          <span>手续费：<span style={{ color: '#faad14' }}>¥{fee.toFixed(2)}</span></span>
          <span>净赚：<span style={{ color: profit >= 0 ? '#52c41a' : '#ff4d4f', fontWeight: 600 }}>¥{profit.toFixed(2)}</span></span>
        </div>
      </Space>
    </div>
  )
}

// ============== 接管 Modal 阶段 ==============

type TakeoverPhase = 'confirm' | 'progress' | 'done'

// T02676：接管链路失败透传后端 detail（登录态失效/风控/超时…），
// 只展示不改写、不做子串判定（后端语义不进前端逻辑，T02660 风险区）；
// 无 detail 或非字符串时给通用兜底文案
function takeoverErrMsg(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof detail === 'string' && detail ? detail : fallback
}

interface TakeoverModalProps {
  readonly open: boolean
  readonly order: OrderItem | null
  readonly onClose: () => void
  readonly onSuccess: () => void
}

function TakeoverModal({ open, order, onClose, onSuccess }: TakeoverModalProps) {
  const [phase, setPhase] = useState<TakeoverPhase>('confirm')
  const [loading, setLoading] = useState(false)
  // 倒计时相关
  const [remaining, setRemaining] = useState(0)
  const totalSec = useRef(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  // 完成阶段自动关闭
  const [autoCloseCount, setAutoCloseCount] = useState(5)
  const autoClosePaused = useRef(false)
  const autoCloseTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // 当打开/切换订单时重置状态
  useEffect(() => {
    if (open && order) {
      setPhase('confirm')
      setLoading(false)
      setAutoCloseCount(5)
      autoClosePaused.current = false
    }
  }, [open, order])

  // 清理定时器
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
      if (autoCloseTimerRef.current) clearInterval(autoCloseTimerRef.current)
    }
  }, [])

  // 阶段2：启动倒计时
  const startCountdown = useCallback((deadline: string) => {
    const endMs = new Date(deadline).getTime()
    const calcRemaining = () => Math.max(0, Math.floor((endMs - Date.now()) / 1000))
    const initRemain = calcRemaining()
    setRemaining(initRemain)
    totalSec.current = initRemain

    timerRef.current = setInterval(() => {
      const r = calcRemaining()
      setRemaining(r)
      if (r <= 0 && timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
    }, 1000)
  }, [])

  // 阶段3：启动自动关闭倒计时
  const startAutoClose = useCallback(() => {
    setAutoCloseCount(5)
    autoCloseTimerRef.current = setInterval(() => {
      if (autoClosePaused.current) return
      setAutoCloseCount((prev) => {
        if (prev <= 1) {
          if (autoCloseTimerRef.current) clearInterval(autoCloseTimerRef.current)
          onClose()
          return 0
        }
        return prev - 1
      })
    }, 1000)
  }, [onClose])

  // 确认接管
  const handleTakeover = async () => {
    if (!order) return
    setLoading(true)
    try {
      // 用后端返回的 takeover_deadline 启动倒计时
      // 为什么不用订单对象字段：点击接管时订单还是 pending，没有 deadline；
      // takeover 接口返回值包含新生成的 takeover_deadline
      const result = await orderApi.takeover(order.id)
      message.success('已接管')
      setPhase('progress')
      if (result.takeover_deadline) {
        startCountdown(result.takeover_deadline)
      }
      onSuccess()
    } catch (err) {
      message.error(takeoverErrMsg(err, '接管失败'))
    } finally {
      setLoading(false)
    }
  }

  // 确认完成
  const handleConfirm = async () => {
    if (!order) return
    setLoading(true)
    try {
      await orderApi.confirmTakeover(order.id)
      message.success('已确认完成')
      // 清理倒计时
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
      setPhase('done')
      startAutoClose()
      onSuccess()
    } catch (err) {
      message.error(takeoverErrMsg(err, '确认失败'))
    } finally {
      setLoading(false)
    }
  }

  // 取消接管
  const handleCancel = async () => {
    if (!order) return
    setLoading(true)
    try {
      await orderApi.cancelTakeover(order.id)
      message.success('已取消接管')
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
      onClose()
      onSuccess()
    } catch (err) {
      message.error(takeoverErrMsg(err, '取消失败'))
    } finally {
      setLoading(false)
    }
  }

  // 关闭时清理所有定时器
  const handleClose = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    if (autoCloseTimerRef.current) {
      clearInterval(autoCloseTimerRef.current)
      autoCloseTimerRef.current = null
    }
    onClose()
  }

  if (!order) return null

  const progressPct = totalSec.current > 0 ? Math.round(((totalSec.current - remaining) / totalSec.current) * 100) : 0
  // S3358：用 if/else 替代嵌套三元
  let phaseTitle = '接管完成'
  if (phase === 'confirm') phaseTitle = '确认接管'
  else if (phase === 'progress') phaseTitle = '接管进行中'

  return (
    <Modal
      open={open}
      title={phaseTitle}
      onCancel={handleClose}
      footer={null}
      width={520}
      destroyOnHidden
    >
      {/* 阶段1：确认接管 */}
      {phase === 'confirm' && (
        <div>
          <div style={{ marginBottom: 16 }}>
            <div style={{ marginBottom: 4, color: 'var(--xh-text-secondary)' }}>订单信息</div>
            <div>商品ID：{order.item_id}</div>
            <div>金额：<span style={{ color: '#f5222d', fontWeight: 600 }}>¥{order.price.toFixed(2)}</span></div>
            <div>创建时间：{formatDateTime(order.created_at)}</div>
          </div>

          <div style={{ marginBottom: 16, padding: 12, background: 'var(--xh-bg-info)', borderRadius: 6, border: '1px solid var(--xh-border-info)' }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>接管流程</div>
            <Steps
              size="small"
              direction="vertical"
              current={-1}
              items={[
                { title: '确认接管' },
                { title: '在闲鱼完成支付' },
                { title: '确认完成' },
              ]}
            />
          </div>

          <div style={{ textAlign: 'right' }}>
            <Space>
              <TipButton tip="关闭接管弹窗" onClick={handleClose}>取消</TipButton>
              <TipButton tip="开始接管此订单" type="primary" icon={<ThunderboltOutlined />} loading={loading} onClick={handleTakeover}>
                确认接管
              </TipButton>
            </Space>
          </div>
        </div>
      )}

      {/* 阶段2：进行中 */}
      {phase === 'progress' && (
        <div>
          <div style={{ textAlign: 'center', marginBottom: 16 }}>
            <div style={{ fontSize: 28, fontWeight: 700, color: remaining > 0 ? '#faad14' : '#ff4d4f' }}>
              {remaining > 0 ? formatDuration(remaining, { withSeconds: true }) : '已超时'}
            </div>
            <Progress
              percent={progressPct}
              status={remaining > 0 ? 'active' : 'exception'}
              style={{ maxWidth: 400, margin: '12px auto' }}
            />
          </div>

          <Steps
            size="small"
            current={1}
            style={{ marginBottom: 24 }}
            items={[
              { title: '确认接管', icon: <CheckOutlined style={{ color: '#52c41a' }} /> },
              { title: '闲鱼支付中', icon: <LoadingOutlined /> },
              { title: '确认完成', icon: <SmileOutlined /> },
            ]}
          />

          {/* T02675：倒计时归零不再只甩一个红字——说明超时后会发生什么。
              后端 confirm/cancel 只校验状态不校验 deadline（超时窗口内仍接受），
              超时清理调度器稍后会把过期单转为 failed；届时确认会收到 409，
              原因经 T02676 的透传直出。按钮保持可点，语义交给这段说明。 */}
          {remaining <= 0 && (
            <Alert
              type="warning"
              showIcon
              style={{ marginBottom: 16 }}
              message="接管已超时"
              description="支付截止时间已过，系统稍后会自动把这条订单转为失败单。若你确实已在闲鱼完成支付，仍可点「确认完成」（风险自负：商品可能已被平台自动关闭）；若未支付，建议点「取消接管」。"
            />
          )}

          <div style={{ textAlign: 'right' }}>
            <Space>
              <TipButton tip="取消接管并保留订单为待处理" danger icon={<CloseOutlined />} loading={loading} onClick={handleCancel}>
                取消接管
              </TipButton>
              <TipButton tip="确认已在闲鱼完成支付" type="primary" icon={<CheckOutlined />} loading={loading} onClick={handleConfirm}>
                确认完成
              </TipButton>
            </Space>
          </div>
        </div>
      )}

      {/* 阶段3：完成 */}
      {phase === 'done' && (
        // S6819：用 <section aria-label> 替代 div role="region"，语义化区域
        <section
          aria-label="接管完成区域"
          onMouseEnter={() => { autoClosePaused.current = true }}
          onMouseLeave={() => { autoClosePaused.current = false }}
        >
          <Result
            icon={<SmileOutlined style={{ color: '#52c41a' }} />}
            title="接管完成"
            subTitle={`${autoCloseCount} 秒后自动关闭（鼠标移入暂停）`}
          />
          <ProfitCalculator amount={order.price} />
          <div style={{ textAlign: 'right', marginTop: 16 }}>
            <TipButton tip="关闭完成提示" onClick={handleClose}>关闭</TipButton>
          </div>
        </section>
      )}
    </Modal>
  )
}

// ============== 主页面 ==============

// 状态卡口径（评审 2.5-1）：数字来自后端全量 GROUP BY，与分页、状态筛选无关。
// 用问号 Tooltip 显式说明，避免用户把四卡读成「当前页统计」。
const STATS_SCOPE = '统计口径：当前账号全部抢单记录，不随分页与上方状态筛选变化'

// 跨页定位（T02641）：200 是后端 page_size 上限，25 页即前 5000 条；
// 上限只防「深链指向历史深处」时无限翻页，超出后把选择权交回用户（筛选/清除定位）
const REF_SCAN_PAGE_SIZE = 200
const REF_SCAN_MAX_PAGES = 25
const REF_SCAN_MAX_ROWS = REF_SCAN_PAGE_SIZE * REF_SCAN_MAX_PAGES

// 深链定位的提示文案：'' 表示还在自动翻页查找（原来的「不在当前页」提示保持不变）
function refAlertText(refId: string, reason: '' | 'missing' | 'filtered' | 'unreachable') {
  if (reason === 'missing') {
    return {
      type: 'error' as const,
      message: `订单 #${refId} 不存在或无权查看`,
      description: '链接里的订单可能已被删除，或不属于当前账号。',
    }
  }
  if (reason === 'filtered') {
    return {
      type: 'warning' as const,
      message: `订单 #${refId} 被当前筛选条件挡住`,
      description: '该订单存在，但不符合当前的状态/类型筛选，不会出现在结果里。清除筛选后会继续定位到它所在的页。',
    }
  }
  if (reason === 'unreachable') {
    return {
      type: 'warning' as const,
      message: `未能自动定位到订单 #${refId}`,
      description: `已按当前排序自动翻页查找前 ${REF_SCAN_MAX_ROWS} 条：目标不在其中，或列表在定位期间发生变化。可用状态筛选缩小范围，或清除定位。`,
    }
  }
  return {
    type: 'info' as const,
    message: `要定位的订单 #${refId} 不在当前页`,
    description: '正在按当前筛选与排序自动翻页查找；也可用上方状态筛选缩小范围，或清除定位回到正常列表。',
  }
}

function StatTitle({ label }: { label: string }) {
  return (
    <Space size={4}>
      {label}
      <Tooltip title={STATS_SCOPE}>
        <QuestionCircleOutlined style={{ color: 'var(--xh-text-secondary)' }} />
      </Tooltip>
    </Space>
  )
}

export default function Orders() {
  // 删除确认走 App 上下文的 modal（T02975）：操作列 fixed:'right' 是 sticky 单元格，
  // Popconfirm 的 trigger 会在横向滚动时反复重算位置，确认框跟着闪（同 T02671 因果链）
  const { modal } = App.useApp()
  const [items, setItems] = useState<OrderItem[]>([])
  const [stats, setStats] = useState<OrderStats>({
    pending: 0, succeeded: 0, failed: 0, cancelled: 0, takeover: 0, total: 0,
  })
  // URL 深链（T02620）：本页既读 ?ref=（行定位）也读 ?status=（状态筛选）。
  // useSearchParams 必须早于 statusFilter 的初值使用，故 searchParams 上移。
  const [searchParams, setSearchParams] = useSearchParams()
  // 告警抽屉/雷达带 ?status=<OrderStatus> 过来时，落地即是筛好的异常子集；
  // 非法值按「不筛选」降级（口径见 utils/alertDeepLink.parseOrderStatusParam）
  const urlStatus = parseOrderStatusParam(searchParams.get('status'))
  const [statusFilter, setStatusFilter] = useState<string | undefined>(urlStatus)
  // T02673：「演练单」选项不是订单状态，走独立的 type 参数（real|dry_run），
  // 不挤占 ?status= 白名单——否则深链白名单会拒绝 dry_run、刷新即丢筛选。
  // 初值由下方 urlType effect 在挂载时从 URL 同步
  const [typeFilter, setTypeFilter] = useState<'dry_run' | undefined>(undefined)
  const [loading, setLoading] = useState(false)

  // 告警定位（评审 2.1-4）：异常雷达改为 SPA 跳转并带 ?ref=<订单 id>，
  // 本页必须真的读取它，否则链接只是「跳过去自己找」。
  const rawRef = searchParams.get('ref') ?? ''
  // ref 来自 URL：订单 id 是字符串（OrderItem.id: string），放行字母数字与 _-: 这类安全字符，
  // 排除引号/反斜杠/尖括号，既满足 data-row-key 选择器插值，也让脏链接静默降级为普通列表
  const refId = /^[A-Za-z0-9_:.-]{1,64}$/.test(rawRef) ? rawRef : ''
  // null=未定位 / true=在当前页找到 / false=当前页没有
  const [refLocated, setRefLocated] = useState<boolean | null>(null)
  // 跨页定位的结论：''=尚在查找 / missing=订单不存在或越权 / filtered=被筛选挡住 /
  // unreachable=扫描范围内没找到（或排序结果不稳定）
  const [refUnreachable, setRefUnreachable] = useState<'' | 'missing' | 'filtered' | 'unreachable'>('')
  const locateScanKey = useRef('')

  // 同一 sheet 内换了深链（例如又点了另一条告警）时，以 URL 为准重打筛选。
  // 手动改下拉现在也回写 URL（T02831），于是本效果收到的是同一个值：
  // setStatusFilter 幂等、setPage(1) 与 onStatusChange 里的复位一致，不会来回打架。
  useEffect(() => {
    setStatusFilter(urlStatus)
    setPage(1)
  }, [urlStatus])

  // 同一 sheet 内换了深链（?type=dry_run）时以 URL 为准；与 onStatusChange 写回的值
  // 幂等，不会来回打架（同 urlStatus 的处理）
  const urlType = searchParams.get('type') === 'dry_run' ? 'dry_run' : undefined
  useEffect(() => {
    setTypeFilter(urlType)
    setPage(1)
  }, [urlType])

  // 后端分页状态：page/pageSize 持久化，跨会话保留用户偏好
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = usePersistentState<number>('xh.orders.pageSize', 20, {
    validator: (v): v is number => typeof v === 'number' && v > 0 && Number.isFinite(v),
  })
  const [total, setTotal] = useState(0)

  // T02677：服务端排序。默认 created_at desc 与后端原固定行为一致；
  // 金额列原先只有「当前页内排序」的本地 sorter，翻页后顺序就乱，一并并入服务端排序
  const [sortBy, setSortBy] = useState<'created_at' | 'confirmed_at' | 'price'>('created_at')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  // 列配置
  const [columnConfigOpen, setColumnConfigOpen] = useState(false)
  const {
    order: columnOrder,
    hidden: hiddenColumns,
    toggleHidden: toggleColumnHidden,
    moveColumn: moveColumnOrder,
    reset: resetColumnConfig,
    applyConfig: applyColumnConfig,
  } = useColumnConfig('xh.orders.columns', COLUMN_DEFINITIONS)

  // 接管 Modal 状态
  const [modalOpen, setModalOpen] = useState(false)
  const [activeOrder, setActiveOrder] = useState<OrderItem | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    orderApi.list({ page_num: page, page_size: pageSize, status: statusFilter, type: typeFilter, sort_by: sortBy, sort_dir: sortDir })
      .then((res) => {
        const list = res.items || []
        setItems(list)
        setTotal(res.total || res.count || 0)
        setRefLocated(refId ? list.some(o => String(o.id) === refId) : null)
        // 评审 2.5-1 / REQ-036：四张状态卡改用后端 GROUP BY 全量计数。
        // 原先按「当前页 items」filter，翻到第 2 页数字全变；且 pending 桶漏掉了
        // 实际写入值 pending_pay，导致「待处理」常显示 0。
        setStats(res.stats)
      })
      .catch(() => message.error('加载订单失败'))
      .finally(() => setLoading(false))
  }, [page, pageSize, statusFilter, typeFilter, refId, sortBy, sortDir])

  useEffect(() => { load() }, [load])

  // 新深链落地时清掉上一条 ref 的定位结论；同一 ref 换筛选由扫描键另行触发
  useEffect(() => {
    setRefUnreachable('')
    locateScanKey.current = ''
  }, [refId])

  // T02641：命中判定原先只在当前页做过——目标订单在第 2 页之后时，用户落地看到的
  // 仍是「不在当前页」。未命中时补一次跨页定位：
  // 1) 按 id 单查，确认订单存在（404=已删除/越权），并识别是否被状态/类型筛选挡住；
  // 2) 用与当前列表完全相同的筛选与排序，按 200 条/页扫描，把扫描下标换算成用户
  //    当前 pageSize 下的页码；
  // 3) setPage 后由既有 load → refLocated=true → 高亮 + scrollIntoView 完成落地。
  useEffect(() => {
    // loading 期间不扫：换 ref/换筛选时 refLocated 还是上一条的结果，等新列表落地再判断
    if (!refId || refLocated !== false || loading) return
    // 同一次「订单 + 筛选 + 排序 + 每页条数」只扫一遍：跳页后 refLocated 会重新变 false，
    // 不拦会让 setPage 触发的 load 反过来再扫一轮
    const key = [refId, statusFilter, typeFilter, sortBy, sortDir, pageSize].join('|')
    if (locateScanKey.current === key) return
    locateScanKey.current = key
    let alive = true
    setRefUnreachable('')

    const locate = async () => {
      let target: OrderItem
      try {
        target = await orderApi.get(refId)
      } catch {
        if (alive) setRefUnreachable('missing')
        return
      }
      if (!alive) return
      // status/type 是列表仅有的两组筛选：订单本身不满足时，扫多少页都不会出现，
      // 直接说明原因并给「清除筛选」，不让用户盲目翻页
      if ((statusFilter && target.status !== statusFilter) ||
          (typeFilter && (target.type ?? 'real') !== typeFilter)) {
        setRefUnreachable('filtered')
        return
      }

      let scanned = 0
      for (let p = 1; p <= REF_SCAN_MAX_PAGES; p++) {
        const res = await orderApi.list({
          page_num: p, page_size: REF_SCAN_PAGE_SIZE,
          status: statusFilter, type: typeFilter,
          sort_by: sortBy, sort_dir: sortDir,
        })
        if (!alive) return
        const list = res.items || []
        const idx = list.findIndex((o) => String(o.id) === refId)
        if (idx >= 0) {
          const targetPage = Math.floor(((p - 1) * REF_SCAN_PAGE_SIZE + idx) / pageSize) + 1
          // 页码与当前页相同说明列表在扫描期间变过（新单插入/删除），不跳以免原地循环
          if (targetPage === page) setRefUnreachable('unreachable')
          else setPage(targetPage)
          return
        }
        scanned += list.length
        if (!list.length || list.length < REF_SCAN_PAGE_SIZE ||
            scanned >= (res.total ?? res.count ?? 0)) break
      }
      setRefUnreachable('unreachable')
    }

    locate().catch(() => { if (alive) setRefUnreachable('unreachable') })
    return () => { alive = false }
  }, [refId, refLocated, loading, statusFilter, typeFilter, sortBy, sortDir, pageSize, page])

  // 定位命中后把该行滚到视野内：只滚动画像内的 tr，找不到就什么都不做
  useEffect(() => {
    if (refLocated !== true) return
    const row = document.querySelector(`tr[data-row-key="${refId}"]`)
    row?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [refLocated, refId])

  // 清除定位：去掉 ref 参数，交回正常分页视图
  const clearRef = () => {
    const next = new URLSearchParams(searchParams)
    next.delete('ref')
    setSearchParams(next, { replace: true })
    setRefLocated(null)
  }

  // 只清筛选、保留 ref：urlStatus/urlType 的 effect 会把状态同步回去并触发重新定位
  const clearFiltersForRef = () => {
    const next = new URLSearchParams(searchParams)
    next.delete('status')
    next.delete('type')
    setSearchParams(next, { replace: true })
  }

  // 筛选条件变化时回到第一页，避免空页；并把筛选态回写 URL（T02831）。
  // 不回写的后果：从告警带 ?status=failed 进来后手动改成「全部」，页面上是全部、
  // URL 还是 failed，刷新就被打回「已失败」——可见筛选态与链接各说各话。
  const onStatusChange = (v: string | undefined) => {
    setPage(1)
    const next = new URLSearchParams(searchParams)
    if (v === 'dry_run') {
      // 演练单选项：两个筛选态互斥（一个下拉同时表达），URL 写 type 参数
      setTypeFilter('dry_run')
      setStatusFilter(undefined)
      next.delete('status')
      next.set('type', 'dry_run')
    } else {
      setTypeFilter(undefined)
      setStatusFilter(v)
      next.delete('type')
      if (v) next.set('status', v)
      else next.delete('status')
    }
    setSearchParams(next, { replace: true })
  }

  // 删除订单
  const handleDelete = async (id: string) => {
    try {
      await orderApi.delete(id)
      message.success('删除成功')
      // 删除后如果当前页只剩 1 条且不是第一页，回退一页
      if (items.length <= 1 && page > 1) {
        setPage(page - 1)
      } else {
        load()
      }
    } catch {
      message.error('删除失败')
    }
  }

  // SSE 订阅：监听 BUY_SUCCEEDED / BUY_FAILED 事件，自动刷新订单列表
  // 为什么需要：抢单是后端异步操作，用户在评估明细页面触发后需要看到实时更新
  // 断线 3 秒自动重连，页面不可见时不建立连接（节省资源）
  const loadRef = useRef(load)
  loadRef.current = load
  useEffect(() => {
    const MAX_RECONNECT = 10
    let reconnectAttempts = 0
    let lastEventId = 0
    let es: EventSource | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null

    const connect = () => {
      if (es) es.close()
      if (document.visibilityState !== 'visible') return
      if (reconnectAttempts >= MAX_RECONNECT) return

      const url = lastEventId > 0
        ? `${API_BASE}api/events/stream?last_event_id=${lastEventId}`
        : `${API_BASE}api/events/stream`
      es = new EventSource(url)
      es.addEventListener('app_event', (e: MessageEvent) => {
        try {
          // S7773：用 Number.parseInt 替代全局 parseInt
          lastEventId = Number.parseInt(e.lastEventId) || lastEventId
          const ev = JSON.parse(e.data)
          // 监听抢单成功/失败事件，触发列表刷新
          if (ev.type === 'buy.succeeded' || ev.type === 'buy.failed') {
            loadRef.current()
          }
        } catch { /* 忽略解析错误 */ }
      })
      es.addEventListener('error', () => {
        try { es?.close() } catch { /* */ }
        es = null
        reconnectAttempts++
        if (reconnectAttempts < MAX_RECONNECT && document.visibilityState === 'visible') {
          reconnectTimer = setTimeout(connect, 3000)
        }
      })
    }

    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible' && !es) {
        reconnectAttempts = 0
        connect()
      }
    }
    document.addEventListener('visibilitychange', onVisibilityChange)

    connect()
    return () => {
      document.removeEventListener('visibilitychange', onVisibilityChange)
      if (reconnectTimer) clearTimeout(reconnectTimer)
      if (es) {
        es.close()
        es = null
      }
    }
  }, [])

  // 打开接管 Modal
  const openTakeoverModal = (record: OrderItem) => {
    setActiveOrder(record)
    setModalOpen(true)
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
    // T02674：点 ID 弹商品快照（Popover，见 ItemSummaryCell），不再是纯文本
    { title: '商品ID', dataIndex: 'item_id', key: 'item_id', width: 180, ellipsis: true, render: (v: string) => <ItemSummaryCell itemId={v} /> },
    {
      // T02677：sorter 交服务端（sort_by=price），不再是仅当前页的本地排序
      title: '金额', dataIndex: 'price', key: 'price', width: 100,
      sorter: true,
      render: (v: number) => <span style={{ color: '#f5222d', fontWeight: 600 }}>¥{v.toFixed(2)}</span>,
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 100,
      render: (s: string) => <Tag color={orderStatusColor(s)}>{orderStatusLabel(s)}</Tag>,
    },
    {
      // T02677：创建/确认时间列补排序（服务端全量排序），接管场景找最新待接管单不再翻页人肉找
      title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170,
      sorter: true, sortDirections: ['ascend', 'descend'] as SortOrder[],
      render: (t: string) => formatDateTime(t),
    },
    {
      title: '确认时间', dataIndex: 'confirmed_at', key: 'confirmed_at', width: 170,
      sorter: true, sortDirections: ['ascend', 'descend'] as SortOrder[],
      render: (t: string | null) => formatDateTime(t),
    },
    {
      title: '接管截止', dataIndex: 'takeover_deadline', key: 'takeover_deadline', width: 170,
      render: (t: string | null, r: OrderItem) => {
        if (!t) return '—'
        const remain = r.takeover_remaining_sec
        if (remain !== null && remain !== undefined && remain > 0) {
          return <Tag color="orange">{formatDuration(remain, { withSeconds: true })}</Tag>
        }
        return formatDateTime(t)
      },
    },
    {
      title: '操作', key: 'action', width: 200, fixed: 'right' as const,
      render: (_: unknown, r: OrderItem) => (
        <Space size="small">
          {(r.status === ORDER_STATUS.PENDING_PAY || r.status === ORDER_STATUS.TAKEOVER_PENDING) && (
            <TipButton
              tip={r.status === ORDER_STATUS.PENDING_PAY ? '接管此待支付订单' : '查看接管进度'}
              type="link"
              icon={<ThunderboltOutlined />}
              size="small"
              onClick={() => openTakeoverModal(r)}
            >
              {r.status === ORDER_STATUS.PENDING_PAY ? '接管' : '查看'}
            </TipButton>
          )}
          <TipButton
            tip="删除此订单（不可恢复）"
            type="link"
            danger
            icon={<DeleteOutlined />}
            size="small"
            onClick={() => modal.confirm({
              title: '确认删除此订单？',
              content: '删除后不可恢复',
              okText: '删除',
              cancelText: '取消',
              okButtonProps: { danger: true },
              onOk: () => handleDelete(r.id),
            })}
          >
            删除
          </TipButton>
        </Space>
      ),
    },
  ]

  // 应用列配置：按用户自定义顺序重排 + 过滤隐藏列
  const visibleColumns = applyColumnConfig(columns)

  const refAlert = refId && refLocated === false ? refAlertText(refId, refUnreachable) : null

  return (
    <div className="page-container">
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}><Card><Statistic title={<StatTitle label="待处理" />} value={stats.pending} valueStyle={{ color: '#faad14' }} /></Card></Col>
        <Col span={6}><Card><Statistic title={<StatTitle label="已成功" />} value={stats.succeeded} valueStyle={{ color: '#52c41a' }} /></Card></Col>
        <Col span={6}><Card><Statistic title={<StatTitle label="已失败" />} value={stats.failed} valueStyle={{ color: '#ff4d4f' }} /></Card></Col>
        <Col span={6}><Card><Statistic title={<StatTitle label="人工接管" />} value={stats.takeover} valueStyle={{ color: '#1890ff' }} suffix={<span style={{ fontSize: 12, color: 'var(--xh-text-secondary)' }}>&nbsp;/ 共 {stats.total}</span>} /></Card></Col>
      </Row>

      <Card>
        <Space style={{ marginBottom: 16 }}>
          <span>状态筛选：</span>
          <Select
            style={{ width: 150 }}
            allowClear
            placeholder="全部状态"
            value={statusFilter ?? typeFilter}
            onChange={onStatusChange}
            options={[
              ...orderStatusOptions([
                ORDER_STATUS.PENDING_PAY,
                ORDER_STATUS.SUCCEEDED,
                ORDER_STATUS.FAILED,
                ORDER_STATUS.TAKEOVER_PENDING,
              ]),
              // T02673：演练记录与真实记录混排，高频用户无法只看/排除演练单；
              // 该项走 type=dry_run 参数，不是订单状态
              { label: '演练单', value: 'dry_run' },
            ]}
          />
          <TipButton tip="重新加载订单列表" icon={<ReloadOutlined />} onClick={load} loading={loading}>刷新</TipButton>
          <TipButton tip="自定义表格显示列与顺序" icon={<SettingOutlined />} onClick={() => setColumnConfigOpen(true)}>列配置</TipButton>
        </Space>

        <Spin spinning={loading}>
          {refAlert && (
            <Alert type={refAlert.type} showIcon style={{ marginBottom: 12 }}
              message={refAlert.message}
              description={refAlert.description}
              action={
                <Space size="small">
                  {refUnreachable === 'filtered' && (
                    <TipButton size="small" onClick={clearFiltersForRef} tip="去掉 status/type 筛选参数，保留 ref 继续定位">清除筛选</TipButton>
                  )}
                  <TipButton size="small" onClick={clearRef} tip="清除 URL 中的 ref 定位参数，回到正常分页列表">清除定位</TipButton>
                </Space>
              }
            />
          )}
          {items.length === 0 ? (
            <Empty description="暂无抢单记录" />
          ) : (
            <Table
              columns={visibleColumns}
              dataSource={items}
              rowKey="id"
              rowClassName={(r) => (refId && String(r.id) === refId ? 'xh-row-highlight' : '')}
              size="middle"
              scroll={{ x: 1200 }}
              pagination={{
                current: page,
                pageSize,
                total,
                showSizeChanger: true,
                showQuickJumper: true,
                pageSizeOptions: ['10', '20', '50', '100'],
                showLessItems: true,
                showTotal: (t) => `共 ${t} 条`,
              }}
              onChange={(p, _filters, sorter) => {
                // T02677：排序变更走服务端重查，且回到第 1 页（与筛选变更同一习惯，
                // 否则排完序还停在原页码，看到的是新顺序里的「中间段」）。
                // 非受控 sorter 在纯翻页/改 pageSize 时也会把当前排序一并上报，
                // 所以只在「排序真的变了」时才走排序分支，否则改 pageSize 会莫名跳回第 1 页
                const s = Array.isArray(sorter) ? sorter[0] : sorter
                const f = s && s.field ? String(s.field) : null
                const d = s?.order === 'ascend' ? 'asc' : s?.order === 'descend' ? 'desc' : null
                if (f && d && (f !== sortBy || d !== sortDir) &&
                    (f === 'created_at' || f === 'confirmed_at' || f === 'price')) {
                  setSortBy(f)
                  setSortDir(d)
                  setPage(1)
                  return
                }
                setPage(p.current ?? 1)
                setPageSize(p.pageSize ?? 20)
              }}
            />
          )}
        </Spin>
      </Card>

      <TakeoverModal
        open={modalOpen}
        order={activeOrder}
        onClose={() => setModalOpen(false)}
        onSuccess={load}
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
