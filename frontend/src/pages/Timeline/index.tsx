import { useEffect, useState, useCallback } from 'react'
import { Card, Row, Col, Statistic, message } from 'antd'
import {
  ClockCircleOutlined, CheckCircleOutlined, CloseCircleOutlined, ShoppingOutlined,
} from '@ant-design/icons'
import { timelineApi, taskApi, configApi, type TimelineEntry, type Task } from '../../api'
import {
  EVENT_TYPE_OPTIONS, EVENT_TYPE_VALUES, ENUM_TO_DOT,
} from '../../constants/eventTypes'
import TimelineFilter from './components/TimelineFilter'
import TimelineList from './components/TimelineList'

const PAGE_SIZE = 30

export default function TimelinePage() {
  const [items, setItems] = useState<TimelineEntry[]>([])
  const [allItems, setAllItems] = useState<TimelineEntry[]>([]) // 全量数据，用于前端分页
  const [tasks, setTasks] = useState<Task[]>([])
  const [taskId, setTaskId] = useState<string | undefined>(undefined)
  const [types, setTypes] = useState<string>('orders,events')
  const [loading, setLoading] = useState(false)
  const [expandedItems, setExpandedItems] = useState<Set<number>>(new Set())
  const [page, setPage] = useState(1)
  // 事件类型过滤：空数组 = 不过滤（显示全部）
  const [eventTypeFilter, setEventTypeFilter] = useState<string[]>([])

  useEffect(() => {
    taskApi.list({ limit: 200 }).then((res) => setTasks(res.items || [])).catch(() => {})
  }, [])

  // 从通知配置同步事件订阅规则到过滤条件
  // 三段式判断，避免"配置映射出无效类型"导致所有事件被过滤掉的回归：
  //   1) 配置中没有合法枚举 → 不过滤（兜底，避免空过滤反而误过滤）
  //   2) 配置订阅了所有合法类型 → 不过滤（无需过滤）
  //   3) 部分订阅 → 仅保留 EVENT_TYPE_VALUES 中真实存在的值作为过滤项
  // 额外把无法识别的枚举打印到 console，让用户/开发者知道配置漂移
  const syncFromNotifier = useCallback(async () => {
    try {
      const cfg = await configApi.get()
      const subscribed: string[] = cfg?.notifier?.subscribed_events || []
      const validEnums = new Set(Object.keys(ENUM_TO_DOT))
      const recognized = subscribed.filter((e) => validEnums.has(e))
      const unknown = subscribed.filter((e) => !validEnums.has(e))
      if (unknown.length > 0) {
        console.warn(
          '[Timeline] subscribed_events 中存在无法识别的枚举，已忽略:',
          unknown,
        )
      }
      const mapped = recognized
        .map((e) => ENUM_TO_DOT[e])
        // 二次校验：mapped 的 value 必须落在 EVENT_TYPE_OPTIONS 中，
        // 否则同步后会导致 eventTypeFilter 包含"无人能匹配"的 type
        .filter((v) => EVENT_TYPE_VALUES.has(v))

      if (mapped.length === 0) {
        setEventTypeFilter([])
      } else if (mapped.length >= EVENT_TYPE_OPTIONS.length) {
        // 全部合法类型都订阅了 → 无需过滤
        setEventTypeFilter([])
      } else {
        setEventTypeFilter(mapped)
      }
    } catch { /* 静默忽略，保持当前过滤状态 */ }
  }, [])

  // 页面加载时自动从通知配置同步
  useEffect(() => {
    syncFromNotifier()
  }, [syncFromNotifier])

  const load = useCallback(() => {
    setLoading(true)
    timelineApi.list({ types, task_id: taskId, limit: 500 })
      .then((res) => {
        const data = res.items || []
        setAllItems(data)
        // 过滤后分页
        const filtered = eventTypeFilter.length > 0
          ? data.filter(it => it._kind === 'order' || eventTypeFilter.includes(it.type || ''))
          : data
        setItems(filtered.slice(0, PAGE_SIZE))
        setPage(1)
      })
      .catch(() => message.error('加载时间线失败'))
      .finally(() => setLoading(false))
  }, [types, taskId, eventTypeFilter])

  useEffect(() => { load() }, [load])

  // 客户端事件类型过滤
  const filteredItems = eventTypeFilter.length > 0
    ? allItems.filter(it => it._kind === 'order' || eventTypeFilter.includes(it.type || ''))
    : allItems

  // 前端分页切换
  const handlePageChange = (p: number) => {
    setPage(p)
    setItems(filteredItems.slice((p - 1) * PAGE_SIZE, p * PAGE_SIZE))
  }

  const toggleExpand = (idx: number) => {
    setExpandedItems(prev => {
      const next = new Set(prev)
      if (next.has(idx)) next.delete(idx)
      else next.add(idx)
      return next
    })
  }

  const orderCount = filteredItems.filter((i) => i._kind === 'order').length
  const eventCount = filteredItems.filter((i) => i._kind === 'event').length
  const succeededCount = filteredItems.filter((i) => i._kind === 'order' && i.status === 'succeeded').length
  const failedCount = filteredItems.filter((i) => i._kind === 'order' && i.status === 'failed').length

  // 任务名映射：task_id → 可读名称
  const taskMap = new Map(tasks.map(t => [t.id, t.name || t.keyword || t.id]))

  return (
    <div className="page-container">
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic title="订单事件" value={orderCount} prefix={<ShoppingOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="系统事件" value={eventCount} prefix={<ClockCircleOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="抢单成功"
              value={succeededCount}
              valueStyle={{ color: '#52c41a' }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="抢单失败"
              value={failedCount}
              valueStyle={{ color: failedCount > 0 ? '#ff4d4f' : undefined }}
              prefix={<CloseCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Card>
        <TimelineFilter
          types={types}
          taskId={taskId}
          tasks={tasks}
          loading={loading}
          eventTypeFilter={eventTypeFilter}
          onTypesChange={setTypes}
          onTaskIdChange={setTaskId}
          onReload={load}
          onSyncFromNotifier={syncFromNotifier}
          onEventTypeFilterChange={setEventTypeFilter}
        />

        <TimelineList
          items={items}
          page={page}
          pageSize={PAGE_SIZE}
          total={filteredItems.length}
          loading={loading}
          expandedItems={expandedItems}
          taskMap={taskMap}
          onPageChange={handlePageChange}
          onToggleExpand={toggleExpand}
        />
      </Card>
    </div>
  )
}
