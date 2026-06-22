import { Space, Select, Button, Tag } from 'antd'
import { ReloadOutlined, SyncOutlined } from '@ant-design/icons'
import { EVENT_TYPE_OPTIONS } from '../../../constants/eventTypes'
import type { Task } from '../../../api'

interface TimelineFilterProps {
  types: string
  taskId: string | undefined
  tasks: Task[]
  loading: boolean
  eventTypeFilter: string[]
  onTypesChange: (v: string) => void
  onTaskIdChange: (v: string | undefined) => void
  onReload: () => void
  onSyncFromNotifier: () => void
  onEventTypeFilterChange: (filter: string[]) => void
}

export default function TimelineFilter({
  types, taskId, tasks, loading, eventTypeFilter,
  onTypesChange, onTaskIdChange, onReload, onSyncFromNotifier, onEventTypeFilterChange,
}: TimelineFilterProps) {
  return (
    <>
      <Space style={{ marginBottom: 16 }} wrap>
        <span>事件类型：</span>
        <Select
          style={{ width: 200 }}
          value={types}
          onChange={(v) => onTypesChange(v)}
          options={[
            { label: '全部（订单+事件）', value: 'orders,events' },
            { label: '仅订单', value: 'orders' },
            { label: '仅事件', value: 'events' },
          ]}
        />
        <span>任务筛选：</span>
        <Select
          style={{ width: 250 }}
          allowClear
          placeholder="全部任务"
          value={taskId}
          onChange={(v) => onTaskIdChange(v)}
          options={tasks.map((t) => ({ label: `${t.name}（${t.keyword}）`, value: t.id }))}
        />
        <Button icon={<ReloadOutlined />} onClick={onReload} loading={loading}>刷新</Button>
      </Space>

      {/* 事件类型过滤（与通知订阅联动） */}
      <div style={{ marginBottom: 16, padding: '8px 12px', background: 'var(--xh-bg-spotlight)', borderRadius: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <span style={{ fontWeight: 500, fontSize: 13 }}>事件类型过滤</span>
          <Button size="small" icon={<SyncOutlined />} onClick={onSyncFromNotifier} title="从通知配置同步订阅规则">
            同步订阅
          </Button>
          {eventTypeFilter.length > 0 && (
            <Button size="small" type="link" onClick={() => onEventTypeFilterChange([])}>
              清除过滤
            </Button>
          )}
          <span style={{ color: 'var(--xh-text-tertiary)', fontSize: 11, marginLeft: 'auto' }}>
            {eventTypeFilter.length > 0
              ? `已选 ${eventTypeFilter.length} / ${EVENT_TYPE_OPTIONS.length} 种`
              : '显示全部事件类型'}
          </span>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {EVENT_TYPE_OPTIONS.map(opt => {
            const isActive = eventTypeFilter.length === 0 || eventTypeFilter.includes(opt.value)
            const severityColor = opt.severity === 'critical' ? 'red' : opt.severity === 'important' ? 'orange' : 'blue'
            return (
              <Tag
                key={opt.value}
                color={isActive ? severityColor : 'default'}
                style={{ cursor: 'pointer', opacity: isActive ? 1 : 0.4, margin: 0 }}
                onClick={() => {
                  if (eventTypeFilter.length === 0) {
                    // 当前是"全部"模式 → 点击后只选这一个
                    onEventTypeFilterChange([opt.value])
                  } else if (eventTypeFilter.includes(opt.value)) {
                    const next = eventTypeFilter.filter(v => v !== opt.value)
                    onEventTypeFilterChange(next.length === 0 ? [] : next)
                  } else {
                    onEventTypeFilterChange([...eventTypeFilter, opt.value])
                  }
                }}
              >
                {opt.label}
              </Tag>
            )
          })}
        </div>
      </div>
    </>
  )
}
