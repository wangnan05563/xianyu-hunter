import { useEffect, useState, useCallback, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Card, Button, Space, Tag, Empty, Spin, message, Row, Col, Statistic,
  List, Popconfirm, Tooltip,
} from 'antd'
import {
  ReloadOutlined, CheckOutlined, CheckSquareOutlined, DeleteOutlined, ClearOutlined,
} from '@ant-design/icons'
import { notificationApi, type NotificationItem } from '../../api'

// level 颜色与文案：与后端 _ALLOWED_LEVELS 对齐
const LEVEL_COLOR: Record<NotificationItem['level'], string> = {
  info: 'blue',
  warn: 'orange',
  err: 'red',
}
const LEVEL_LABEL: Record<NotificationItem['level'], string> = {
  info: '信息',
  warn: '警告',
  err: '错误',
}

// category 文案：与后端 _ALLOWED_CATEGORIES 对齐
const CATEGORY_LABEL: Record<NotificationItem['category'], string> = {
  order: '订单',
  auth: '登录',
  system: '系统',
  config: '配置',
  task: '任务',
}

type FilterStatus = 'all' | 'unread' | 'read'

// URL 查询参数 ↔ FilterStatus 映射：刷新页面可恢复筛选状态
function parseStatus(value: string | null): FilterStatus {
  if (value === 'unread' || value === 'read') return value
  return 'all'
}

export default function Notifications() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [filter, setFilter] = useState<FilterStatus>(parseStatus(searchParams.get('status')))

  const [items, setItems] = useState<NotificationItem[]>([])
  const [total, setTotal] = useState(0)
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)

  // 筛选条件变更同步到 URL，便于刷新/分享恢复
  useEffect(() => {
    const params = new URLSearchParams()
    if (filter !== 'all') params.set('status', filter)
    setSearchParams(params, { replace: true })
  }, [filter, setSearchParams])

  const loadList = useCallback(() => {
    setLoading(true)
    notificationApi
      .list({ status: filter === 'all' ? undefined : filter, limit: 100 })
      .then((res) => {
        setItems(res.items)
        setTotal(res.total)
      })
      .catch(() => message.error('加载通知失败'))
      .finally(() => setLoading(false))
  }, [filter])

  const loadUnread = useCallback(() => {
    notificationApi
      .unreadCount()
      .then((res) => setUnreadCount(res.unread))
      .catch(() => { /* 静默：未读数加载失败不阻塞列表 */ })
  }, [])

  useEffect(() => { loadList() }, [loadList])
  useEffect(() => { loadUnread() }, [loadUnread])

  // 单条标记已读：乐观更新，失败回滚
  const handleMarkRead = async (item: NotificationItem) => {
    if (item.read_at) return
    setItems((prev) => prev.map((it) => (it.id === item.id ? { ...it, read_at: new Date().toISOString() } : it)))
    setUnreadCount((c) => Math.max(0, c - 1))
    try {
      await notificationApi.markRead(item.id)
    } catch {
      message.error('标记已读失败')
      setItems((prev) => prev.map((it) => (it.id === item.id ? { ...it, read_at: null } : it)))
      setUnreadCount((c) => c + 1)
    }
  }

  // 全部已读：仅对当前未读生效，避免重复请求
  const handleMarkAllRead = async () => {
    if (unreadCount === 0) {
      message.info('没有未读通知')
      return
    }
    setActionLoading(true)
    try {
      const res = await notificationApi.markAllRead()
      message.success(`已标记 ${res.updated} 条为已读`)
      setItems((prev) => prev.map((it) => (it.read_at ? it : { ...it, read_at: new Date().toISOString() })))
      setUnreadCount(0)
    } catch {
      message.error('全部标记已读失败')
    } finally {
      setActionLoading(false)
    }
  }

  // 删除单条：乐观更新
  const handleDelete = async (id: number) => {
    const prev = items
    const target = prev.find((it) => it.id === id)
    setItems((p) => p.filter((it) => it.id !== id))
    setTotal((t) => Math.max(0, t - 1))
    if (target && !target.read_at) setUnreadCount((c) => Math.max(0, c - 1))
    try {
      await notificationApi.delete(id)
    } catch {
      message.error('删除失败')
      setItems(prev)
      setTotal((t) => t + 1)
      if (target && !target.read_at) setUnreadCount((c) => c + 1)
    }
  }

  // 清空已读：默认仅清已读，避免误删未读
  const handleClearRead = async () => {
    setActionLoading(true)
    try {
      const res = await notificationApi.clear('read')
      message.success(`已清空 ${res.deleted} 条已读通知`)
      loadList()
    } catch {
      message.error('清空失败')
    } finally {
      setActionLoading(false)
    }
  }

  const readCount = total - unreadCount

  return (
    <div className="page-container">
      <h2 style={{ marginBottom: 16 }}>通知中心</h2>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Card>
            <Statistic title="未读" value={unreadCount} valueStyle={unreadCount > 0 ? { color: '#ff4d4f' } : undefined} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="已读" value={readCount} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Button
                type="primary"
                icon={<CheckSquareOutlined />}
                onClick={handleMarkAllRead}
                loading={actionLoading}
                disabled={unreadCount === 0}
                block
              >
                全部标记已读
              </Button>
              <Popconfirm
                title="确认清空所有已读通知？"
                description="此操作不可恢复，未读通知将保留。"
                onConfirm={handleClearRead}
                okText="清空"
                cancelText="取消"
                okButtonProps={{ danger: true }}
              >
                <Button icon={<ClearOutlined />} danger disabled={readCount === 0} block>
                  清空已读
                </Button>
              </Popconfirm>
            </Space>
          </Card>
        </Col>
      </Row>

      <Card
        title={
          <Space>
            <span>通知列表</span>
            <Tooltip title="刷新">
              <Button icon={<ReloadOutlined />} onClick={() => { loadList(); loadUnread() }} size="small" />
            </Tooltip>
          </Space>
        }
        extra={
          // 内联 Tabs 替代方案：用按钮组切换筛选，避免 Tabs 与 URL 同步的额外复杂度
          <Space>
            {(['all', 'unread', 'read'] as FilterStatus[]).map((s) => {
              // S3358：嵌套三元拆为独立 if/else，便于阅读
              let label = '已读'
              if (s === 'all') label = '全部'
              else if (s === 'unread') label = '未读'
              return (
                <Button
                  key={s}
                  size="small"
                  type={filter === s ? 'primary' : 'default'}
                  onClick={() => setFilter(s)}
                >
                  {label}
                </Button>
              )
            })}
          </Space>
        }
      >
        <Spin spinning={loading}>
          {items.length === 0 ? (
            <Empty description={filter === 'unread' ? '没有未读通知' : '暂无通知'} />
          ) : (
            <List
              dataSource={items}
              renderItem={(item) => {
                // 已读项不显示"标记已读"按钮，避免冗余操作
                const actions: ReactNode[] = []
                if (!item.read_at) {
                  actions.push(
                    <Button
                      key="read"
                      size="small"
                      type="link"
                      icon={<CheckOutlined />}
                      onClick={() => handleMarkRead(item)}
                    >
                      标记已读
                    </Button>,
                  )
                }
                actions.push(
                  <Popconfirm
                    key="del"
                    title="确认删除该通知？"
                    onConfirm={() => handleDelete(item.id)}
                    okText="删除"
                    cancelText="取消"
                    okButtonProps={{ danger: true }}
                  >
                    <Button size="small" type="link" danger icon={<DeleteOutlined />}>
                      删除
                    </Button>
                  </Popconfirm>,
                )
                return (
                <List.Item actions={actions}>
                  <List.Item.Meta
                    avatar={
                      // 视觉对齐：未读用小圆点提示，已读无标记
                      // S7735：反转条件避免否定
                      item.read_at ? null : (
                        <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#ff4d4f', marginTop: 8 }} />
                      )
                    }
                    title={
                      <Space size="small" wrap>
                        <Tag color={LEVEL_COLOR[item.level]}>{LEVEL_LABEL[item.level]}</Tag>
                        <Tag>{CATEGORY_LABEL[item.category]}</Tag>
                        <span style={{ fontWeight: item.read_at ? 'normal' : 600 }}>{item.title}</span>
                        <span style={{ fontSize: 12, color: 'var(--xh-text-tertiary)' }}>
                          {new Date(item.created_at).toLocaleString('zh-CN')}
                        </span>
                      </Space>
                    }
                    description={
                      <div>
                        <div style={{ color: 'var(--xh-text-secondary)' }}>{item.message}</div>
                        {item.link && (
                          <a href={item.link} target="_blank" rel="noreferrer" style={{ fontSize: 12 }}>
                            查看详情 →
                          </a>
                        )}
                      </div>
                    }
                  />
                </List.Item>
                )
              }}
            />
          )}
        </Spin>
      </Card>
    </div>
  )
}
