// frontend/src/mobile/pages/Orders/OrderDetail.tsx
import { Card, Descriptions, Spin, Button, Tag } from 'antd'
import { useNavigate, useParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { orderApi } from '../../../api'
import type { OrderItem } from '../../../api/types'

const STATUS_LABELS: Record<string, string> = {
  pending_pay: '待支付',
  paid: '已成功',
  cancelled: '已取消',
}

export default function MobileOrderDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [order, setOrder] = useState<OrderItem | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!id) return
    // 直连 GET /api/orders/{id}，避免 list+find 全量拉取
    orderApi.get(id)
      .then(setOrder)
      .catch(() => setOrder(null))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>
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
            <Tag>{STATUS_LABELS[order.status] || order.status}</Tag>
          </Descriptions.Item>
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
