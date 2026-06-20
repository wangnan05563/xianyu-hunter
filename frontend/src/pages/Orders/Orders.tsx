import { useEffect, useState, useCallback } from 'react'
import { Card, Table, Tag, Select, Button, Space, Spin, Statistic, Row, Col, Popconfirm, message, Empty } from 'antd'
import { ReloadOutlined, ThunderboltOutlined, CheckOutlined, CloseOutlined } from '@ant-design/icons'
import { orderApi, type OrderItem } from '../../api'
import { ORDER_STATUS_CONFIG } from '../../constants/orderStatus'

// 保留组件特有的中文标签（与 Timeline 的简短标签不同，以维持原有显示效果）
const STATUS_TEXT: Record<string, string> = {
  pending: '待处理',
  succeeded: '已成功',
  failed: '已失败',
  takeover: '人工接管',
}

export default function Orders() {
  const [items, setItems] = useState<OrderItem[]>([])
  const [stats, setStats] = useState({ succeeded: 0, pending: 0, failed: 0, takeover: 0 })
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined)
  const [loading, setLoading] = useState(false)

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

  const handleTakeover = (id: number) => {
    orderApi.takeover(id).then(() => { message.success('已接管'); load() }).catch(() => message.error('接管失败'))
  }
  const handleConfirm = (id: number) => {
    orderApi.confirmTakeover(id).then(() => { message.success('已确认'); load() }).catch(() => message.error('确认失败'))
  }
  const handleCancel = (id: number) => {
    orderApi.cancelTakeover(id).then(() => { message.success('已取消接管'); load() }).catch(() => message.error('取消失败'))
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
        if (r.status === 'pending') {
          return (
            <Popconfirm title="确认人工接管此订单？" onConfirm={() => handleTakeover(r.id)}>
              <Button type="link" icon={<ThunderboltOutlined />} size="small">接管</Button>
            </Popconfirm>
          )
        }
        if (r.status === 'takeover') {
          return (
            <Space size="small">
              <Button type="link" icon={<CheckOutlined />} size="small" onClick={() => handleConfirm(r.id)}>确认</Button>
              <Button type="link" danger icon={<CloseOutlined />} size="small" onClick={() => handleCancel(r.id)}>取消</Button>
            </Space>
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
    </div>
  )
}
