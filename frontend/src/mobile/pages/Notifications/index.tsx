// frontend/src/mobile/pages/Notifications/index.tsx
import { Card, Tag, Spin, Empty, App, Select, Button, Popconfirm, Badge, Space } from 'antd'
import { useCallback, useEffect, useState } from 'react'
import { notificationApi } from '../../../api'
import type { NotificationItem, NotificationStatus } from '../../../api/notifications'
import { extractApiError } from '../../../utils/apiError'
import PullToRefresh from '../../components/PullToRefresh'

// category 中文标签：与后端 NotificationRow.category 字段对齐
const CATEGORY_LABELS: Record<NotificationItem['category'], string> = {
  order: '订单',
  auth: '认证',
  system: '系统',
  config: '配置',
  task: '任务',
}

// level 颜色：与 antd Tag 颜色映射，severity 递增色阶加深
const LEVEL_COLORS: Record<NotificationItem['level'], string> = {
  info: 'blue',
  warn: 'orange',
  err: 'red',
}

const LIST_LIMIT = 50

export default function MobileNotifications() {
  const { message } = App.useApp()
  const [items, setItems] = useState<NotificationItem[]>([])
  const [loading, setLoading] = useState(true)
  const [filterStatus, setFilterStatus] = useState<NotificationStatus>(undefined)

  const fetchList = useCallback(async () => {
    try {
      const data = await notificationApi.list({ status: filterStatus, limit: LIST_LIMIT })
      setItems(data.items)
    } catch (e) {
      // 弱网保留已有数据，仅提示用户
      message.error(extractApiError(e, '加载通知失败'), 3)
    } finally {
      setLoading(false)
    }
  }, [filterStatus, message])

  useEffect(() => { fetchList() }, [fetchList])

  // 标记单条已读：成功后重新拉取保证计数与列表状态一致
  const handleMarkRead = async (id: number) => {
    try {
      await notificationApi.markRead(id)
      message.success('已标记已读')
      fetchList()
    } catch (e) {
      message.error(extractApiError(e, '标记已读失败'), 3)
    }
  }

  // 全部已读：批量操作，重新拉取列表
  const handleMarkAllRead = async () => {
    try {
      await notificationApi.markAllRead()
      message.success('全部已读')
      fetchList()
    } catch (e) {
      message.error(extractApiError(e, '操作失败'), 3)
    }
  }

  // 删除单条：Popconfirm 防止误触
  const handleDelete = async (id: number) => {
    try {
      await notificationApi.delete(id)
      message.success('已删除')
      fetchList()
    } catch (e) {
      message.error(extractApiError(e, '删除失败'), 3)
    }
  }

  if (loading) return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>

  return (
    <PullToRefresh onRefresh={fetchList}>
      {/* 状态筛选 + 全部已读：单行紧凑布局 */}
      <Space style={{ width: '100%', marginBottom: 12 }} direction="horizontal">
        <Select
          placeholder="全部状态"
          allowClear
          style={{ flex: 1, minWidth: 140 }}
          onChange={(v: NotificationStatus) => setFilterStatus(v)}
          options={[
            { value: 'unread', label: '未读' },
            { value: 'read', label: '已读' },
          ]}
        />
        <Button size="small" onClick={handleMarkAllRead}>全部已读</Button>
      </Space>

      {items.length === 0 ? (
        <Empty description="暂无通知" />
      ) : (
        items.map((item) => {
          const unread = item.read_at === null
          return (
            <Card
              key={item.id}
              size="small"
              style={{ marginBottom: 12 }}
            >
              {/* 未读：左侧用 Badge 蓝点强化视觉提示 */}
              <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                {unread ? (
                  <Badge status="processing" style={{ marginTop: 6 }} />
                ) : (
                  <span style={{ width: 6 }} />
                )}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', gap: 6, marginBottom: 4, flexWrap: 'wrap' }}>
                    <span style={{ fontWeight: 600, fontSize: 15 }}>{item.title}</span>
                    <Tag color={LEVEL_COLORS[item.level]}>
                      {CATEGORY_LABELS[item.category]}
                    </Tag>
                  </div>
                  <div style={{ fontSize: 13, color: '#666', marginBottom: 8 }}>{item.message}</div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 12, color: '#999' }}>
                      {new Date(item.created_at).toLocaleString('zh-CN')}
                    </span>
                    <Space size="small">
                      {/* 仅未读显示标记已读按钮，避免冗余操作 */}
                      {unread && (
                        <Button size="small" type="link" onClick={() => handleMarkRead(item.id)}>
                          标记已读
                        </Button>
                      )}
                      <Popconfirm
                        title="确认删除该通知？"
                        onConfirm={() => handleDelete(item.id)}
                        okText="删除"
                        cancelText="取消"
                      >
                        <Button size="small" type="link" danger>删除</Button>
                      </Popconfirm>
                    </Space>
                  </div>
                </div>
              </div>
            </Card>
          )
        })
      )}
    </PullToRefresh>
  )
}
