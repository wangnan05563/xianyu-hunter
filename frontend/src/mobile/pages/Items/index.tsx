// frontend/src/mobile/pages/Items/index.tsx
import { Card, Select, Tag, Spin, Empty, Image, App } from 'antd'
import { PictureOutlined } from '@ant-design/icons'
import { useEffect, useState, useCallback, type ReactNode } from 'react'
import { taskApi, taskLinkApi } from '../../../api'
import type { Task, TaskLink } from '../../../api/types'
import { extractApiError } from '../../../utils/apiError'
import PullToRefresh from '../../components/PullToRefresh'

// 时间本地化：后端返回 ISO 字符串，移动端按本地时区展示更直观
function formatLocalTime(raw?: string): string | null {
  if (!raw) return null
  const d = new Date(raw)
  if (Number.isNaN(d.getTime())) return null
  return d.toLocaleString('zh-CN', { hour12: false })
}

// 缩略图：闲鱼图床常有防盗链，加载失败时降级到占位图标
// 不直接用 antd Image fallback 属性：自定义占位风格更贴合移动端卡片
function Thumb({ url, title }: { readonly url?: string; readonly title: string }): ReactNode {
  const [errored, setErrored] = useState(false)
  // url 切换时重置错误状态，避免复用组件时残留旧错误态
  useEffect(() => { setErrored(false) }, [url])
  if (url && !errored) {
    return (
      <Image
        src={url}
        referrerPolicy="no-referrer"
        width={60}
        height={60}
        style={{ objectFit: 'cover', borderRadius: 6, background: '#f5f5f5' }}
        onError={() => setErrored(true)}
        alt={title}
      />
    )
  }
  return (
    <div
      style={{
        width: 60,
        height: 60,
        borderRadius: 6,
        background: '#f5f5f5',
        color: '#bbb',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
      aria-label={title ? '暂无图片' : undefined}
    >
      <PictureOutlined style={{ fontSize: 22 }} />
    </div>
  )
}

export default function MobileItems() {
  const { message } = App.useApp()
  const [tasks, setTasks] = useState<Task[]>([])
  const [selectedTaskId, setSelectedTaskId] = useState<string | undefined>(undefined)
  const [items, setItems] = useState<TaskLink[]>([])
  const [loading, setLoading] = useState(true)
  const [itemsLoading, setItemsLoading] = useState(false)

  // 首次进入只加载任务列表，让用户选择任务后才请求商品
  // 避免无选中任务时请求 links 接口报 422
  const fetchTasks = useCallback(async () => {
    try {
      const data = await taskApi.list()
      setTasks(data.items)
    } catch (e) {
      // 静默失败：弱网下保留已有数据不打断用户；仅打 warn 便于排查
      console.warn(extractApiError(e, '加载任务列表失败'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchTasks() }, [fetchTasks])

  // 拉取商品：必须带 taskId，未选中时直接清空
  const fetchItems = useCallback(async () => {
    if (!selectedTaskId) {
      setItems([])
      return
    }
    setItemsLoading(true)
    try {
      const data = await taskLinkApi.list(selectedTaskId, { type: 'item', limit: 50 })
      setItems(data.items)
    } catch (e) {
      // 弱网下保留已有数据，仅提示
      message.error(extractApiError(e, '加载商品失败'), 3)
    } finally {
      setItemsLoading(false)
    }
  }, [selectedTaskId, message])

  useEffect(() => {
    if (selectedTaskId) fetchItems()
    else setItems([])
  }, [selectedTaskId, fetchItems])

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Spin />
      </div>
    )
  }

  return (
    <PullToRefresh onRefresh={selectedTaskId ? fetchItems : fetchTasks}>
      <Select
        placeholder="选择任务"
        allowClear
        style={{ width: '100%', marginBottom: 12 }}
        value={selectedTaskId}
        onChange={(v: string | undefined) => setSelectedTaskId(v)}
        options={tasks.map((t) => ({ value: t.id, label: t.name }))}
      />
      {!selectedTaskId ? (
        <Empty description="请选择任务" />
      ) : itemsLoading ? (
        <div style={{ textAlign: 'center', padding: 24 }}><Spin /></div>
      ) : items.length === 0 ? (
        <Empty description="暂无商品" />
      ) : (
        items.map((item) => {
          // 移动端不做详情页，仅给提示，避免无效跳转
          const handleClick = () => message.info('请在桌面端查看详情')
          const publishTime = formatLocalTime(item.display.publish_time)
          return (
            <Card
              key={item.link_id}
              className="m-item-card"
              size="small"
              style={{ marginBottom: 12 }}
              onClick={handleClick}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  handleClick()
                }
              }}
            >
              <div style={{ display: 'flex', gap: 12 }}>
                <Thumb url={item.display.thumb_url} title={item.display.title} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontWeight: 600,
                    fontSize: 14,
                    marginBottom: 4,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical',
                  }}>
                    {item.display.title || '未命名商品'}
                  </div>
                  <div style={{ fontSize: 15, color: '#E20613', fontWeight: 600, marginBottom: 4 }}>
                    ¥{item.display.price}
                  </div>
                  <div style={{ fontSize: 12, color: '#999', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {publishTime && <span>{publishTime}</span>}
                    {typeof item.display.want_cnt === 'number' && (
                      <span>想要 {item.display.want_cnt}</span>
                    )}
                    {item.display.is_sold && <Tag color="red" style={{ marginInlineStart: 4 }}>已售</Tag>}
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
