// frontend/src/mobile/pages/Orders/index.tsx
import { Card, Select, Tag, Spin, Empty, App } from 'antd'
import { useNavigate } from 'react-router-dom'
import { useEffect, useState, useCallback } from 'react'
import { orderApi } from '../../../api'
import type { OrderItem } from '../../../api/types'
import { extractApiError } from '../../../utils/apiError'
import { formatDateTime } from '../../../utils/timeFormat'
import PullToRefresh from '../../components/PullToRefresh'
import FetchFailedHint from '../../../components/FetchFailedHint'
import TakeoverCountdown from '../../components/TakeoverCountdown'
import {
  ORDER_STATUS,
  ORDER_STATUS_USER_CHOICES,
  orderStatusColor,
  orderStatusLabel,
  orderStatusOptions,
} from '../../../constants/orderStatus'

// 状态文案与颜色全部来自 constants/orderStatus（与后端 domain/order.py OrderStatus 同源，T02716）
// 原先这里另写一份 STATUS_LABELS/STATUS_COLORS，桌面端再写第三份：拼错或漏值不报错，只静默显示英文末段

export default function MobileOrders() {
  const navigate = useNavigate()
  const { message } = App.useApp()
  const [orders, setOrders] = useState<OrderItem[]>([])
  const [loading, setLoading] = useState(true)
  const [loadFailed, setLoadFailed] = useState(false)
  const [filterStatus, setFilterStatus] = useState<string | undefined>(undefined)

  const fetchOrders = useCallback(async () => {
    try {
      const data = await orderApi.list({ status: filterStatus })
      setOrders(data.items)
      setLoadFailed(false)
    } catch {
      // 弱网保留已有数据，但必须显式声明失败：否则列表空态会被读成「真的没有订单」
      setLoadFailed(true)
    } finally {
      setLoading(false)
    }
  }, [filterStatus])

  useEffect(() => { fetchOrders() }, [fetchOrders])

  // 订单状态修改：用户在闲鱼支付后标记为"已成功"
  const handleStatusChange = async (orderId: string, newStatus: string) => {
    try {
      await orderApi.updateStatus(orderId, newStatus)
      message.success('状态已更新')
      fetchOrders() // 刷新列表
    } catch (e) {
      message.error(extractApiError(e, '更新失败'), 3)
    }
  }

  if (loading) return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>

  // 空态：请求失败时给重试入口，成功但无数据才说「暂无」，避免 JSX 里嵌套三元
  const emptyState = loadFailed ? (
    <FetchFailedHint source="订单列表" onRetry={() => void fetchOrders()} />
  ) : (
    <Empty description="暂无订单" />
  )

  return (
    <PullToRefresh onRefresh={fetchOrders}>
      {/* 状态筛选 */}
      <Select
        placeholder="全部状态"
        allowClear
        style={{ width: '100%', marginBottom: 12 }}
        onChange={(v) => setFilterStatus(v)}
        options={orderStatusOptions(ORDER_STATUS_USER_CHOICES)}
      />
      {orders.length === 0 ? (
        emptyState
      ) : (
        <>
          {loadFailed && (
            <FetchFailedHint source="订单列表" onRetry={() => void fetchOrders()} />
          )}
          {orders.map((order) => (
          <Card
            key={order.id}
            className="m-order-card"
            size="small"
            style={{ marginBottom: 12 }}
          >
            <button
              type="button"
              onClick={() => navigate(`/m/orders/${order.id}`)}
              style={{ border: 'none', background: 'none', padding: 0, width: '100%', textAlign: 'left', cursor: 'pointer' }}
            >
              <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 4 }}>
                {order.item_id || '商品'}
              </div>
              <div style={{ fontSize: 13, color: '#999', marginBottom: 8 }}>
                ¥{order.price} · {formatDateTime(order.created_at)}
              </div>
            </button>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <Tag color={orderStatusColor(order.status)}>
                  {orderStatusLabel(order.status)}
                </Tag>
                {/* 人工接管：显示真实剩余时间（闲鱼待付款 30 分钟自动关闭） */}
                {order.status === ORDER_STATUS.TAKEOVER_PENDING && (
                  <TakeoverCountdown
                    deadline={order.takeover_deadline}
                    remainingSec={order.takeover_remaining_sec}
                  />
                )}
              </div>
              {/* 状态修改下拉：用户支付后标记为已成功 */}
              <Select
                size="small"
                value={order.status}
                style={{ width: 100 }}
                onChange={(v) => handleStatusChange(order.id, v)}
                options={orderStatusOptions(ORDER_STATUS_USER_CHOICES)}
              />
            </div>
          </Card>
          ))}
        </>
      )}
    </PullToRefresh>
  )
}
