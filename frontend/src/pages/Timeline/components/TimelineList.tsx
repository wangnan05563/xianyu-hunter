import { Spin, Empty, Pagination } from 'antd'
import type { TimelineEntry } from '../../../api'
import TimelineItem from './TimelineItem'

interface TimelineListProps {
  items: TimelineEntry[]
  page: number
  pageSize: number
  total: number
  loading: boolean
  expandedItems: Set<number>
  taskMap: Map<string, string>
  onPageChange: (p: number) => void
  onToggleExpand: (idx: number) => void
}

export default function TimelineList({
  items, page, pageSize, total, loading, expandedItems, taskMap,
  onPageChange, onToggleExpand,
}: TimelineListProps) {
  return (
    <Spin spinning={loading}>
      {total === 0 ? (
        <Empty description="暂无匹配的时间线数据" />
      ) : (
        <>
          {/* 紧凑靠左列表：时间戳内联，释放横向空间 */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            {items.map((item, idx) => {
              const globalIdx = (page - 1) * pageSize + idx
              const isOrder = item._kind === 'order'
              const level = (item.level || '').toLowerCase()
              const eventType = item.type || ''
              const status = item.status || ''

              // 确定圆点颜色：订单按状态，事件按 level/类型
              let dotColor = '#1890ff'
              if (isOrder) {
                if (status === 'succeeded') dotColor = '#52c41a'
                else if (status === 'failed') dotColor = '#ff4d4f'
                else if (['pending', 'submitting', 'paying'].includes(status)) dotColor = '#faad14'
              } else {
                if (level === 'error' || level === 'err' || eventType === 'order.failed') dotColor = '#ff4d4f'
                else if (level === 'warning' || level === 'warn') dotColor = '#faad14'
                else if (eventType.startsWith('eval.passed') || eventType === 'order.paid') dotColor = '#52c41a'
              }

              const dotIcon = isOrder ? '🛒' : (level === 'error' || level === 'err' ? '🔴' : level === 'warning' || level === 'warn' ? '🟠' : '📌')

              return (
                <div
                  key={`${item.id || ''}-${idx}`}
                  style={{
                    display: 'flex',
                    gap: 12,
                    padding: '10px 0',
                    borderBottom: '1px solid #f0f0f0',
                  }}
                >
                  {/* 左侧：圆点 + 时间戳 */}
                  <div style={{
                    flexShrink: 0,
                    width: 120,
                    textAlign: 'right',
                    fontSize: 11,
                    color: 'var(--xh-text-tertiary)',
                    lineHeight: '20px',
                    paddingTop: 2,
                  }}>
                    {new Date(item._ts).toLocaleString('zh-CN', {
                      month: '2-digit', day: '2-digit',
                      hour: '2-digit', minute: '2-digit', second: '2-digit',
                    })}
                  </div>

                  {/* 圆点 */}
                  <div style={{ flexShrink: 0, paddingTop: 6 }}>
                    <span style={{ fontSize: 14 }}>{dotIcon}</span>
                    <span style={{
                      display: 'inline-block',
                      width: 8, height: 8, borderRadius: '50%',
                      backgroundColor: dotColor,
                      marginLeft: -10, marginRight: 2,
                      verticalAlign: 'middle',
                    }} />
                  </div>

                  {/* 右侧：内容区（占满剩余空间） */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <TimelineItem
                      item={item}
                      index={globalIdx}
                      isExpanded={expandedItems.has(globalIdx)}
                      onToggleExpand={onToggleExpand}
                      taskMap={taskMap}
                    />
                  </div>
                </div>
              )
            })}
          </div>

          {/* 分页 */}
          <div style={{ textAlign: 'right', marginTop: 16, paddingTop: 16, borderTop: '1px solid #f0f0f0' }}>
            <Pagination
              current={page}
              pageSize={pageSize}
              total={total}
              showTotal={(total) => `共 ${total} 条`}
              showSizeChanger={false}
              onChange={onPageChange}
              size="small"
            />
          </div>
        </>
      )}
    </Spin>
  )
}
