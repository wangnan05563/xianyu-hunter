// frontend/src/mobile/pages/Orders/OrderDetail.tsx
import { Card, Descriptions, Spin, Button, Tag } from 'antd'
import { useNavigate, useParams } from 'react-router-dom'
import { useEffect, useState, useCallback } from 'react'
import { orderApi } from '../../../api'
import type { OrderItem } from '../../../api/types'
import FetchFailedHint from '../../../components/FetchFailedHint'
import TakeoverCountdown from '../../components/TakeoverCountdown'
import { ORDER_STATUS, orderStatusColor, orderStatusLabel } from '../../../constants/orderStatus'

// 状态文案/颜色来自 constants/orderStatus（与后端 OrderStatus 同源，T02716）
// 原先这里又写一份 STATUS_LABELS：新增状态只改常量表时，详情页会静默显示英文末段

export default function MobileOrderDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [order, setOrder] = useState<OrderItem | null>(null)
  const [loading, setLoading] = useState(true)
  // 区分「请求失败」与「订单真的不存在」：原先两者都渲染「订单不存在」（假回执）
  const [loadFailed, setLoadFailed] = useState(false)

  const reload = useCallback(() => {
    if (!id) return
    setLoading(true)
    setLoadFailed(false)
    orderApi.get(id)
      .then((o) => setOrder(o))
      .catch(() => setLoadFailed(true))
      .finally(() => setLoading(false))
  }, [id])

  useEffect(() => { reload() }, [reload])

  if (loading) return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>
  if (loadFailed) {
    return (
      <div>
        <Button onClick={() => navigate(-1)} style={{ marginBottom: 12 }}>← 返回</Button>
        <FetchFailedHint source="订单详情" onRetry={reload} />
      </div>
    )
  }
  if (!order) return <div>订单不存在</div>

  return (
    <div>
      <Button onClick={() => navigate(-1)} style={{ marginBottom: 12 }}>← 返回</Button>
      <Card title="订单详情" size="small">
        <Descriptions column={1} size="small">
          <Descriptions.Item label="商品">{order.item_id}</Descriptions.Item>
          <Descriptions.Item label="价格">¥{order.price}</Descriptions.Item>
          <Descriptions.Item label="卖家">{order.seller_id || '—'}</Descriptions.Item>
          <Descriptions.Item label="订单号">{order.order_no || '—'}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={orderStatusColor(order.status)}>{orderStatusLabel(order.status)}</Tag>
          </Descriptions.Item>
          {/* 人工接管倒计时（FR-G-2）：详情端点本次已附加 deadline/剩余秒 */}
          {order.status === ORDER_STATUS.TAKEOVER_PENDING && (
            <Descriptions.Item label="接管截止">
              <TakeoverCountdown
                deadline={order.takeover_deadline}
                remainingSec={order.takeover_remaining_sec}
              />
            </Descriptions.Item>
          )}
          <Descriptions.Item label="创建时间">{order.created_at}</Descriptions.Item>
        </Descriptions>
      </Card>
      {order.screenshot && (
        <Card title="截图" size="small" style={{ marginTop: 12 }}>
          <img
            src={order.screenshot}
            alt="订单截图"
            style={{ width: '100%', borderRadius: 6 }}
          />
        </Card>
      )}
    </div>
  )
}
