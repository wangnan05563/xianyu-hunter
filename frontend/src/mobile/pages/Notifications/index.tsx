// frontend/src/mobile/pages/Notifications/index.tsx
import { Card, Tag, Spin, Empty, App, Select, Button, Popconfirm, Badge, Space } from 'antd'
import { formatDateTime } from '../../../utils/timeFormat'
import { useCallback, useEffect, useState } from 'react'
import { notificationApi } from '../../../api'
import {
  NOTIFICATION_CATEGORY_LABEL,
  NOTIFICATION_LEVEL_COLOR,
} from '../../../api/notifications'
import type { NotificationItem, NotificationStatus } from '../../../api/notifications'
import { extractApiError } from '../../../utils/apiError'
import { useFailedSources } from '../../../hooks/useFailedSources'
import LoadFailedBar from '../../components/LoadFailedBar'
import PullToRefresh from '../../components/PullToRefresh'

// category / level 文案与颜色取自 api/notifications 共享常量（T02619）：
// 与桌面端同一张表，后端 domain/notification.py 是唯一事实源
// （原先这里自带一份 CATEGORY_LABELS，把 auth 翻成「认证」，与桌面端「登录」不一致）
const CATEGORY_LABELS = NOTIFICATION_CATEGORY_LABEL
const LEVEL_COLORS = NOTIFICATION_LEVEL_COLOR

// 与桌面通知中心同口径（T02621）：一页 20 条，靠后端 total 决定还能不能继续加载。
// 原先是「一次拉满就完」的单发请求，拉到的条数即全部，超出部分在移动端翻不到。
export const PAGE_SIZE = 20
// 重取时保留「已加载窗口」的上限：后端 list 的 limit 有 `le=200` 校验，
// 超限值会被 422 打回、刷新静默失败，所以前端不能假装能一次取完。
export const MAX_WINDOW = 200

/** 重取时的 limit：既不小于首屏一页，也不超过后端上限 */
export const reloadWindowLimit = (loaded: number) =>
  Math.min(Math.max(loaded, PAGE_SIZE), MAX_WINDOW)

// 数据源（T02718）：加载失败时「暂无通知」与「取到 0 条」必须可区分
type NotificationsSource = 'list'
const SOURCE_LABELS: Record<NotificationsSource, string> = {
  list: '通知列表',
}

export default function MobileNotifications() {
  const { message } = App.useApp()
  const [items, setItems] = useState<NotificationItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [filterStatus, setFilterStatus] = useState<NotificationStatus>(undefined)
  const { failed, mark } = useFailedSources<NotificationsSource>()

  // offset/limit 由调用方显式传入，不进 useCallback 依赖：
  // 依赖里带上 items.length 会让回调每次加载后换身份，首屏 effect 于是自激重跑。
  const load = useCallback(
    async (offset: number, limit: number) => {
      try {
        const data = await notificationApi.list({ status: filterStatus, limit, offset })
        setTotal(data.total)
        setItems((prev) => (offset === 0 ? data.items : [...prev, ...data.items]))
        mark('list', true)
      } catch (e) {
        // 弱网保留已有数据，但把失败声明出来
        mark('list', false)
        message.error(extractApiError(e, '加载通知失败'), 3)
      } finally {
        setLoading(false)
        setLoadingMore(false)
      }
    },
    [filterStatus, message, mark],
  )

  useEffect(() => {
    load(0, PAGE_SIZE)
  }, [load])

  // 下拉刷新 / 单条操作后的重取：保持已加载的条数，别把用户翻到的第 3 页甩回第 1 页
  const refreshKeepingWindow = () => load(0, reloadWindowLimit(items.length))

  const hasMore = items.length < total

  // 追加下一页：已加载条数即下一页的 offset
  const handleLoadMore = async () => {
    if (loadingMore) return
    setLoadingMore(true)
    await load(items.length, PAGE_SIZE)
  }

  // 标记单条已读：成功后重新拉取保证计数与列表状态一致
  const handleMarkRead = async (id: number) => {
    try {
      await notificationApi.markRead(id)
      message.success('已标记已读')
      refreshKeepingWindow()
    } catch (e) {
      message.error(extractApiError(e, '标记已读失败'), 3)
    }
  }

  // 全部已读：批量操作，重新拉取列表
  const handleMarkAllRead = async () => {
    try {
      await notificationApi.markAllRead()
      message.success('全部已读')
      refreshKeepingWindow()
    } catch (e) {
      message.error(extractApiError(e, '操作失败'), 3)
    }
  }

  // 删除单条：Popconfirm 防止误触
  const handleDelete = async (id: number) => {
    try {
      await notificationApi.delete(id)
      message.success('已删除')
      refreshKeepingWindow()
    } catch (e) {
      message.error(extractApiError(e, '删除失败'), 3)
    }
  }

  if (loading) return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>

  return (
    <PullToRefresh onRefresh={refreshKeepingWindow}>
      {failed.list && (
        <LoadFailedBar
          source={SOURCE_LABELS.list}
          note="下方条数与「没有更多了」都不可信"
          onRetry={refreshKeepingWindow}
        />
      )}
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
        failed.list ? null : <Empty description="暂无通知" />
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
                      {formatDateTime(item.created_at)}
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

      {/* 分页尾部：移动端用「加载更多」追加，而不是桌面的页码控件（T02973） */}
      {items.length > 0 && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 8,
            padding: '4px 2px 12px',
          }}
        >
          <span style={{ fontSize: 12, color: '#999' }}>
            已加载 {items.length} / 共 {total} 条
          </span>
          {hasMore ? (
            <Button size="small" loading={loadingMore} onClick={handleLoadMore}>
              加载更多
            </Button>
          ) : (
            <span style={{ fontSize: 12, color: '#999' }}>没有更多了</span>
          )}
        </div>
      )}
    </PullToRefresh>
  )
}
