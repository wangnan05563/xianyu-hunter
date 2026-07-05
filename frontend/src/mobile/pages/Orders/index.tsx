// frontend/src/mobile/pages/Orders/index.tsx
import { Card, Select, Tag, Spin, Empty, App } from 'antd'
import { useNavigate } from 'react-router-dom'
import { useEffect, useState, useCallback } from 'react'
import { orderApi } from '../../../api'
import type { OrderItem } from '../../../api/types'
import PullToRefresh from '../../components/PullToRefresh'

// 状态中文映射
const STATUS_LABELS: Record<string, string> = {
  pending_pay: '待支付',
  paid: '已成功',
  cancelled: '已取消',
}

const STATUS_COLORS: Record<string, string> = {
  pending_pay: 'orange',
  paid: 'green',
  cancelled: 'default',
}

export default function MobileOrders() {
  const navigate = useNavigate()
  const { message } = App.useApp()
  const [orders, setOrders] = useState<OrderItem[]>([])
  const [loading, setLoading] = useState(true)
  const [filterStatus, setFilterStatus] = useState<string | undefined>(undefined)

  const fetchOrders = useCallback(async () => {
    try {
      const data = await orderApi.list({ status: filterStatus })
      setOrders(data.items)
    } catch {
      // 弱网保留已有数据
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
    } catch {
      message.error('更新失败')
    }
  }

  if (loading) return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>

  return (
    <PullToRefresh onRefresh={fetchOrders}>
      {/* 状态筛选 */}
      <Select
        placeholder="全部状态"
        allowClear
        style={{ width: '100%', marginBottom: 12 }}
        onChange={(v) => setFilterStatus(v)}
        options={[
          { value: 'pending_pay', label: '待支付' },
          { value: 'paid', label: '已成功' },
          { value: 'cancelled', label: '已取消' },
        ]}
      />
      {orders.length === 0 ? (
        <Empty description="暂无订单" />
      ) : (
        orders.map((order) => (
          <Card
            key={order.id}
            className="m-order-card"
            size="small"
            style={{ marginBottom: 12 }}
          >
            <div onClick={() => navigate(`/m/orders/${order.id}`)}>
              <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 4 }}>
                {order.item_id || '商品'}
              </div>
              <div style={{ fontSize: 13, color: '#999', marginBottom: 8 }}>
                ¥{order.price} · {order.created_at}
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Tag color={STATUS_COLORS[order.status]}>
                {STATUS_LABELS[order.status] || order.status}
              </Tag>
              {/* 状态修改下拉：用户支付后标记为已成功 */}
              <Select
                size="small"
                value={order.status}
                style={{ width: 100 }}
                onChange={(v) => handleStatusChange(order.id, v)}
                options={[
                  { value: 'pending_pay', label: '待支付' },
                  { value: 'paid', label: '已成功' },
                  { value: 'cancelled', label: '已取消' },
                ]}
              />
            </div>
          </Card>
        ))
      )}
    </PullToRefresh>
  )
}
