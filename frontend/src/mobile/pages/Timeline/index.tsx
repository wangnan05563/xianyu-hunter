// frontend/src/mobile/pages/Timeline/index.tsx
import { Card, Tag, Spin, Empty, App } from 'antd'
import { useEffect, useState, useCallback } from 'react'
import { timelineApi } from '../../../api'
import type { TimelineEntry } from '../../../api/types'
import { extractApiError } from '../../../utils/apiError'
import PullToRefresh from '../../components/PullToRefresh'

// 时间线精简版：聚合订单事件与系统事件为统一时间线
// 移动端不提供筛选（精简版），仅展示最近 50 条
const TIMELINE_LIMIT = 50

export default function MobileTimeline() {
  const { message } = App.useApp()
  const [entries, setEntries] = useState<TimelineEntry[]>([])
  const [loading, setLoading] = useState(true)

  const fetchTimeline = useCallback(async () => {
    try {
      const data = await timelineApi.list({ limit: TIMELINE_LIMIT })
      setEntries(data.items)
    } catch (e) {
      // 弱网保留已有数据，仅提示用户
      message.error(extractApiError(e, '加载时间线失败'), 3)
    } finally {
      setLoading(false)
    }
  }, [message])

  useEffect(() => { fetchTimeline() }, [fetchTimeline])

  if (loading) return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>

  return (
    <PullToRefresh onRefresh={fetchTimeline}>
      {entries.length === 0 ? (
        <Empty description="暂无时间线" />
      ) : (
        entries.map((entry, idx) => {
          // Card 标题优先级：显式 title > 商品名 > 事件类型 > 通用兜底
          const cardTitle = entry.title || entry.item_title || entry.type || '事件'
          // 时间格式化交给宿主 Intl，避免引入 dayjs 增大移动端 bundle
          const timeText = entry._ts ? new Date(entry._ts).toLocaleString('zh-CN') : ''
          // Tag 颜色：订单事件=绿色，level 字段优先于其他判定（warning/err 是系统级严重度）
          let tagColor = 'blue'
          let tagText = '事件'
          if (entry._kind === 'order') {
            tagColor = 'green'
            tagText = '订单'
          } else if (entry.level === 'warn') {
            tagColor = 'orange'
            tagText = '警告'
          } else if (entry.level === 'err') {
            tagColor = 'red'
            tagText = '错误'
          }
          // 内容优先取 payload.message，回退到 status；金额用 ¥前缀
          const content = entry.payload?.message || entry.status || ''
          return (
            <Card
              key={`${entry._kind}-${entry._ts}-${idx}`}
              size="small"
              style={{ marginBottom: 12 }}
            >
              <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                <Tag color={tagColor} style={{ marginTop: 2 }}>{tagText}</Tag>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 4 }}>{cardTitle}</div>
                  {content && (
                    <div style={{ fontSize: 13, color: '#666', marginBottom: 4 }}>
                      {content}
                      {typeof entry.amount === 'number' ? ` · ¥${entry.amount}` : ''}
                      {typeof entry.score === 'number' ? ` · 评分 ${entry.score}` : ''}
                    </div>
                  )}
                  {timeText && (
                    <div style={{ fontSize: 12, color: '#999' }}>{timeText}</div>
                  )}
                </div>
              </div>
            </Card>
          )
        })
      )}
    </PullToRefresh>
  )
}
