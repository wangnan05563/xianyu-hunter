import { useEffect, useState, useCallback, type ReactNode } from 'react'
import { formatDateTime } from '../../utils/timeFormat'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { TipButton } from '@/components/TipButton'
import {
  Card, Space, Tag, Empty, Spin, message, Row, Col, Statistic,
  List, Popconfirm, Checkbox,
} from 'antd'
import {
  ReloadOutlined, CheckOutlined, CheckSquareOutlined, DeleteOutlined, ClearOutlined,
} from '@ant-design/icons'
import {
  notificationApi,
  NOTIFICATION_CATEGORY_LABEL,
  NOTIFICATION_LEVEL_COLOR,
  NOTIFICATION_LEVEL_LABEL,
  type NotificationItem,
} from '../../api'
import { invalidateNotificationCounts } from '../../hooks/useNotificationModel'

// level / category 的取值与中文文案一律取自 api/notifications 的共享常量（T02619）：
// 后端 domain/notification.py 是唯一事实源，桌面端与移动端共用同一张表，
// 避免此前「桌面 auth=登录、移动 auth=认证」两套文案各自漂移。

type FilterStatus = 'all' | 'unread' | 'read'

// URL 查询参数 ↔ FilterStatus 映射：刷新页面可恢复筛选状态
function parseStatus(value: string | null): FilterStatus {
  if (value === 'unread' || value === 'read') return value
  return 'all'
}

export default function Notifications() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [filter, setFilter] = useState<FilterStatus>(parseStatus(searchParams.get('status')))

  const [items, setItems] = useState<NotificationItem[]>([])
  // 勾选批量删除（评审 2.9-5）：只保存当前可见列表里的 id，重取列表即清空
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  // 三个计数一律来自后端全量口径：列表的 total 随筛选变化，拿它算已读会恒 0 或错算（2.9-3）
  const [unreadCount, setUnreadCount] = useState(0)
  const [readCount, setReadCount] = useState(0)
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
        setSelectedIds([])
      })
      .catch(() => message.error('加载通知失败'))
      .finally(() => setLoading(false))
  }, [filter])

  // 本页计数变化 = 全局未读变化：广播让 Header 铃铛立刻跟上，不等 30s 轮询（T02561 / badge 与已读联动）
  const loadCounts = useCallback(() => {
    notificationApi
      .counts()
      .then((res) => {
        setUnreadCount(res.unread)
        setReadCount(res.read)
        invalidateNotificationCounts()
      })
      .catch(() => { /* 静默：未读数加载失败不阻塞列表 */ })
  }, [])

  useEffect(() => { loadList() }, [loadList])
  useEffect(() => { loadCounts() }, [loadCounts])

  // 单条标记已读：乐观更新，失败回滚
  const handleMarkRead = async (item: NotificationItem) => {
    if (item.read_at) return
    setItems((prev) => prev.map((it) => (it.id === item.id ? { ...it, read_at: new Date().toISOString() } : it)))
    setUnreadCount((c) => Math.max(0, c - 1))
    setReadCount((c) => c + 1)
    try {
      await notificationApi.markRead(item.id)
      invalidateNotificationCounts()
      // 「未读」筛选下这条已不属于当前视图，留着会让用户以为没点到（2.9-7）
      if (filter === 'unread') {
        setItems((prev) => prev.filter((it) => it.id !== item.id))
      }
    } catch {
      message.error('标记已读失败')
      setItems((prev) => prev.map((it) => (it.id === item.id ? { ...it, read_at: null } : it)))
      setUnreadCount((c) => c + 1)
      setReadCount((c) => Math.max(0, c - 1))
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
      // 筛选态下列表形状会变（未读筛选下应清空），交回后端重取，不在前端猜
      loadList()
      loadCounts()
    } catch {
      message.error('全部标记已读失败')
    } finally {
      setActionLoading(false)
    }
  }

  // 删除单条：乐观更新（未读/已读两个计数各自减一，不靠 total 反算）
  const handleDelete = async (id: number) => {
    const prev = items
    const target = prev.find((it) => it.id === id)
    const wasUnread = !!target && !target.read_at
    setItems((p) => p.filter((it) => it.id !== id))
    setSelectedIds((p) => p.filter((x) => x !== id))
    const bump = (delta: number) => {
      if (wasUnread) setUnreadCount((c) => Math.max(0, c + delta))
      else setReadCount((c) => Math.max(0, c + delta))
    }
    bump(-1)
    try {
      await notificationApi.delete(id)
      invalidateNotificationCounts()
    } catch {
      message.error('删除失败')
      setItems(prev)
      bump(1)
    }
  }

  // 清空已读：默认仅清已读，避免误删未读
  const handleClearRead = async () => {
    setActionLoading(true)
    try {
      const res = await notificationApi.clear('read')
      message.success(`已清空 ${res.deleted} 条已读通知`)
      loadList()
      loadCounts()
    } catch {
      message.error('清空失败')
    } finally {
      setActionLoading(false)
    }
  }

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  const allSelected = items.length > 0 && items.every((it) => selectedIds.includes(it.id))
  const toggleSelectAll = () => {
    setSelectedIds(allSelected ? [] : items.map((it) => it.id))
  }

  // 批量删除（评审 2.9-5）：不走乐观更新——删除后每条对未读/已读计数影响不同，
  // 交回后端重取比在前端猜准确
  const handleBatchDelete = async () => {
    if (selectedIds.length === 0) return
    setActionLoading(true)
    try {
      const res = await notificationApi.deleteBatch(selectedIds)
      message.success(
        res.deleted === res.requested
          ? `已删除 ${res.deleted} 条通知`
          : `已删除 ${res.deleted} 条，${res.requested - res.deleted} 条已不存在`,
      )
      loadList()
      loadCounts()
    } catch {
      message.error('批量删除失败')
    } finally {
      setActionLoading(false)
    }
  }

  // 「查看详情」跳转（PRD FR-C-3 / 评审 2.9-4）：
  // 原先 <a href={link} target="_blank"> 绕过 SPA basename（/xianyu），新标签页直接 404；
  // 且跳转后通知仍未读，回到列表还要再点一次。站内链接一律走 navigate 并顺带标已读。
  const openLinked = (item: NotificationItem) => {
    const link = item.link ?? ''
    if (!link) return
    void handleMarkRead(item)
    if (link.startsWith('/')) {
      navigate(link)
      return
    }
    window.open(link, '_blank', 'noopener,noreferrer')
  }

  return (
    <div className="page-container">
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
              <TipButton
                tip="将所有未读通知标记为已读"
                type="primary"
                icon={<CheckSquareOutlined />}
                onClick={handleMarkAllRead}
                loading={actionLoading}
                disabled={unreadCount === 0}
                block
              >
                全部标记已读
              </TipButton>
              <Popconfirm
                title="确认清空所有已读通知？"
                description="此操作不可恢复，未读通知将保留。"
                onConfirm={handleClearRead}
                okText="清空"
                cancelText="取消"
                okButtonProps={{ danger: true }}
              >
                <TipButton tip="清空所有已读通知（不可恢复）" icon={<ClearOutlined />} danger disabled={readCount === 0} block>
                  清空已读
                </TipButton>
              </Popconfirm>
            </Space>
          </Card>
        </Col>
      </Row>

      <Card
        title={
          <Space>
            <span>通知列表</span>
            <TipButton tip="刷新通知列表与计数" icon={<ReloadOutlined />} onClick={() => { loadList(); loadCounts() }} size="small" />
          </Space>
        }
        extra={
          // 内联 Tabs 替代方案：用按钮组切换筛选，避免 Tabs 与 URL 同步的额外复杂度
          <Space>
            {items.length > 0 && (
              <Checkbox
                checked={allSelected}
                indeterminate={selectedIds.length > 0 && !allSelected}
                onChange={toggleSelectAll}
              >
                全选
              </Checkbox>
            )}
            {selectedIds.length > 0 && (
              <Popconfirm
                title={`确认删除选中的 ${selectedIds.length} 条通知？`}
                description="此操作不可恢复。"
                onConfirm={handleBatchDelete}
                okText="删除"
                cancelText="取消"
                okButtonProps={{ danger: true }}
              >
                <TipButton
                  tip="删除勾选的通知（不可恢复）"
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  loading={actionLoading}
                >
                  删除选中 {selectedIds.length}
                </TipButton>
              </Popconfirm>
            )}
            {(['all', 'unread', 'read'] as FilterStatus[]).map((s) => {
              // S3358：嵌套三元拆为独立 if/else，便于阅读
              let label = '已读'
              if (s === 'all') label = '全部'
              else if (s === 'unread') label = '未读'
              const filterTip = s === 'all' ? '显示全部通知' : s === 'unread' ? '仅显示未读通知' : '仅显示已读通知'
              return (
                <TipButton
                  key={s}
                  tip={filterTip}
                  size="small"
                  type={filter === s ? 'primary' : 'default'}
                  onClick={() => setFilter(s)}
                >
                  {label}
                </TipButton>
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
                    <TipButton
                      key="read"
                      tip="标记该通知为已读"
                      size="small"
                      type="link"
                      icon={<CheckOutlined />}
                      onClick={() => handleMarkRead(item)}
                    >
                      标记已读
                    </TipButton>,
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
                    <TipButton tip="删除该通知（不可恢复）" size="small" type="link" danger icon={<DeleteOutlined />}>
                      删除
                    </TipButton>
                  </Popconfirm>,
                )
                return (
                <List.Item actions={actions}>
                  <List.Item.Meta
                    avatar={
                      // 勾选框用于批量删除（2.9-5）；未读用小圆点提示，已读无标记
                      // S7735：反转条件避免否定
                      <Space size={6} align="center" style={{ marginTop: 6 }}>
                        <Checkbox
                          checked={selectedIds.includes(item.id)}
                          onChange={() => toggleSelect(item.id)}
                          aria-label={`选择通知 ${item.id}`}
                        />
                        {item.read_at ? null : (
                          <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#ff4d4f' }} />
                        )}
                      </Space>
                    }
                    title={
                      <Space size="small" wrap>
                        <Tag color={NOTIFICATION_LEVEL_COLOR[item.level]}>{NOTIFICATION_LEVEL_LABEL[item.level]}</Tag>
                        <Tag>{NOTIFICATION_CATEGORY_LABEL[item.category]}</Tag>
                        <span style={{ fontWeight: item.read_at ? 'normal' : 600 }}>{item.title}</span>
                        <span style={{ fontSize: 12, color: 'var(--xh-text-tertiary)' }}>
                          {formatDateTime(item.created_at)}
                        </span>
                      </Space>
                    }
                    description={
                      <div>
                        <div style={{ color: 'var(--xh-text-secondary)' }}>{item.message}</div>
                        {item.link && (
                          <TipButton
                            tip={`跳转 ${item.link}，并标记该通知为已读`}
                            size="small"
                            type="link"
                            style={{ height: 'auto', padding: 0, fontSize: 12 }}
                            onClick={() => openLinked(item)}
                          >
                            查看详情 →
                          </TipButton>
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
