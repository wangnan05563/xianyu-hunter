import { useEffect, useState, useCallback, useRef } from 'react'
import {
  Card, Table, Tag, Select, Button, Space, Spin, Statistic, Row, Col,
  message, Empty, Modal, Steps, Progress, Radio, InputNumber, Result,
} from 'antd'
import {
  ReloadOutlined, ThunderboltOutlined, CheckOutlined, CloseOutlined,
  SmileOutlined, LoadingOutlined, DollarOutlined,
} from '@ant-design/icons'
import { orderApi, type OrderItem } from '../../api'
import { ORDER_STATUS_CONFIG } from '../../constants/orderStatus'

// 保留组件特有的中文标签（与 Timeline 的简短标签不同，以维持原有显示效果）
const STATUS_TEXT: Record<string, string> = {
  pending: '待处理',
  succeeded: '已成功',
  failed: '已失败',
  takeover: '人工接管',
}

// ============== 利润计算器 ==============

/** 费率选项：普通 0.6% / 鱼小铺 1.6% */
const FEE_RATES = [
  { label: '普通 0.6%', value: 0.006 },
  { label: '鱼小铺 1.6%', value: 0.016 },
]

function ProfitCalculator({ amount }: { amount: number }) {
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

interface TakeoverModalProps {
  open: boolean
  order: OrderItem | null
  onClose: () => void
  onSuccess: () => void
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
      await orderApi.takeover(order.id)
      message.success('已接管')
      setPhase('progress')
      // 用 takeover_deadline 启动倒计时，若无则用 remaining_sec 估算
      if (order.takeover_deadline) {
        startCountdown(order.takeover_deadline)
      } else if (order.remaining_sec) {
        totalSec.current = order.remaining_sec
        setRemaining(order.remaining_sec)
        // remaining_sec 也需要启动定时器递减
        timerRef.current = setInterval(() => {
          setRemaining((prev) => {
            const next = Math.max(0, prev - 1)
            if (next <= 0 && timerRef.current) {
              clearInterval(timerRef.current)
              timerRef.current = null
            }
            return next
          })
        }, 1000)
      }
      onSuccess()
    } catch {
      message.error('接管失败')
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
    } catch {
      message.error('确认失败')
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
    } catch {
      message.error('取消失败')
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

  const formatTime = (sec: number) => `${Math.floor(sec / 60)}分${sec % 60}秒`
  const progressPct = totalSec.current > 0 ? Math.round(((totalSec.current - remaining) / totalSec.current) * 100) : 0

  return (
    <Modal
      open={open}
      title={phase === 'confirm' ? '确认接管' : phase === 'progress' ? '接管进行中' : '接管完成'}
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
            <div>金额：<span style={{ color: '#f5222d', fontWeight: 600 }}>¥{order.amount.toFixed(2)}</span></div>
            <div>创建时间：{new Date(order.created_at).toLocaleString('zh-CN')}</div>
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
              <Button onClick={handleClose}>取消</Button>
              <Button type="primary" icon={<ThunderboltOutlined />} loading={loading} onClick={handleTakeover}>
                确认接管
              </Button>
            </Space>
          </div>
        </div>
      )}

      {/* 阶段2：进行中 */}
      {phase === 'progress' && (
        <div>
          <div style={{ textAlign: 'center', marginBottom: 16 }}>
            <div style={{ fontSize: 28, fontWeight: 700, color: remaining > 0 ? '#faad14' : '#ff4d4f' }}>
              {remaining > 0 ? formatTime(remaining) : '已超时'}
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

          <div style={{ textAlign: 'right' }}>
            <Space>
              <Button danger icon={<CloseOutlined />} loading={loading} onClick={handleCancel}>
                取消接管
              </Button>
              <Button type="primary" icon={<CheckOutlined />} loading={loading} onClick={handleConfirm}>
                确认完成
              </Button>
            </Space>
          </div>
        </div>
      )}

      {/* 阶段3：完成 */}
      {phase === 'done' && (
        <div
          onMouseEnter={() => { autoClosePaused.current = true }}
          onMouseLeave={() => { autoClosePaused.current = false }}
        >
          <Result
            icon={<SmileOutlined style={{ color: '#52c41a' }} />}
            title="接管完成"
            subTitle={`${autoCloseCount} 秒后自动关闭（鼠标移入暂停）`}
          />
          <ProfitCalculator amount={order.amount} />
          <div style={{ textAlign: 'right', marginTop: 16 }}>
            <Button onClick={handleClose}>关闭</Button>
          </div>
        </div>
      )}
    </Modal>
  )
}

// ============== 主页面 ==============

export default function Orders() {
  const [items, setItems] = useState<OrderItem[]>([])
  const [stats, setStats] = useState({ succeeded: 0, pending: 0, failed: 0, takeover: 0 })
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined)
  const [loading, setLoading] = useState(false)

  // 接管 Modal 状态
  const [modalOpen, setModalOpen] = useState(false)
  const [activeOrder, setActiveOrder] = useState<OrderItem | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    orderApi.list({ limit: 100, status: statusFilter })
      .then((res) => {
        setItems(res.items || [])
        setStats(res.stats || { succeeded: 0, pending: 0, failed: 0, takeover: 0 })
      })
      .catch(() => message.error('加载订单失败'))
      .finally(() => setLoading(false))
  }, [statusFilter])

  useEffect(() => { load() }, [load])

  // 打开接管 Modal
  const openTakeoverModal = (record: OrderItem) => {
    setActiveOrder(record)
    setModalOpen(true)
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
    { title: '商品ID', dataIndex: 'item_id', key: 'item_id', width: 180, ellipsis: true },
    {
      title: '金额', dataIndex: 'amount', key: 'amount', width: 100,
      sorter: (a: OrderItem, b: OrderItem) => a.amount - b.amount,
      render: (v: number) => <span style={{ color: '#f5222d', fontWeight: 600 }}>¥{v.toFixed(2)}</span>,
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 100,
      render: (s: string) => <Tag color={ORDER_STATUS_CONFIG[s]?.color || 'default'}>{STATUS_TEXT[s] || s}</Tag>,
    },
    {
      title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170,
      render: (t: string) => new Date(t).toLocaleString('zh-CN'),
    },
    {
      title: '确认时间', dataIndex: 'confirmed_at', key: 'confirmed_at', width: 170,
      render: (t: string | null) => t ? new Date(t).toLocaleString('zh-CN') : '—',
    },
    {
      title: '接管截止', dataIndex: 'takeover_deadline', key: 'takeover_deadline', width: 170,
      render: (t: string | null, r: OrderItem) => {
        if (!t) return '—'
        const remain = r.remaining_sec
        if (remain !== null && remain !== undefined && remain > 0) {
          return <Tag color="orange">{Math.floor(remain / 60)}分{remain % 60}秒</Tag>
        }
        return new Date(t).toLocaleString('zh-CN')
      },
    },
    {
      title: '操作', key: 'action', width: 200, fixed: 'right' as const,
      render: (_: unknown, r: OrderItem) => {
        if (r.status === 'pending' || r.status === 'takeover') {
          return (
            <Button
              type="link"
              icon={<ThunderboltOutlined />}
              size="small"
              onClick={() => openTakeoverModal(r)}
            >
              {r.status === 'pending' ? '接管' : '查看'}
            </Button>
          )
        }
        return null
      },
    },
  ]

  return (
    <div className="page-container">
      <h2 style={{ marginBottom: 16 }}>抢单记录</h2>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}><Card><Statistic title="待处理" value={stats.pending} valueStyle={{ color: '#faad14' }} /></Card></Col>
        <Col span={6}><Card><Statistic title="已成功" value={stats.succeeded} valueStyle={{ color: '#52c41a' }} /></Card></Col>
        <Col span={6}><Card><Statistic title="已失败" value={stats.failed} valueStyle={{ color: '#ff4d4f' }} /></Card></Col>
        <Col span={6}><Card><Statistic title="人工接管" value={stats.takeover} valueStyle={{ color: '#1890ff' }} /></Card></Col>
      </Row>

      <Card>
        <Space style={{ marginBottom: 16 }}>
          <span>状态筛选：</span>
          <Select
            style={{ width: 150 }}
            allowClear
            placeholder="全部状态"
            value={statusFilter}
            onChange={(v) => setStatusFilter(v)}
            options={[
              { label: '待处理', value: 'pending' },
              { label: '已成功', value: 'succeeded' },
              { label: '已失败', value: 'failed' },
              { label: '人工接管', value: 'takeover' },
            ]}
          />
          <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>刷新</Button>
        </Space>

        <Spin spinning={loading}>
          {items.length === 0 ? (
            <Empty description="暂无订单记录" />
          ) : (
            <Table
              columns={columns}
              dataSource={items}
              rowKey="id"
              size="middle"
              scroll={{ x: 1200 }}
              pagination={{ pageSize: 50, showSizeChanger: false }}
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
    </div>
  )
}
