import { useEffect, useState, useCallback } from 'react'
import { Card, Tag, Select, Button, Space, Spin, Empty, message, Row, Col, Statistic, Badge, Tooltip, Descriptions, Pagination, Checkbox } from 'antd'
import { ReloadOutlined, ClockCircleOutlined, CheckCircleOutlined, CloseCircleOutlined, ExclamationCircleOutlined, InfoCircleOutlined, ShoppingOutlined, ThunderboltOutlined, SyncOutlined } from '@ant-design/icons'
import { timelineApi, taskApi, configApi, type TimelineEntry, type Task } from '../../api'
import {
  EVENT_TYPE_OPTIONS,
  ENUM_TO_DOT,
  EVENT_TYPE_LABELS,
  SEVERITY_CONFIG,
} from '../../constants/eventTypes'
import { ORDER_STATUS_CONFIG } from '../../constants/orderStatus'
import { RISK_LEVEL_CONFIG } from '../../constants/riskLevels'

// 解析 payload 为可读信息
function parsePayload(item: TimelineEntry) {
  let payload = item.payload
  if (typeof payload === 'string') {
    try { payload = JSON.parse(payload) } catch { return null }
  }
  if (typeof payload !== 'object' || payload === null) return null
  return payload as Record<string, unknown>
}

// 格式化相对时间
function formatRelativeTime(ts: string): string {
  const d = new Date(ts.replace(' ', 'T'))
  if (isNaN(d.getTime())) return ts.slice(0, 19)
  const now = Date.now()
  const diff = now - d.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
  if (diff < 604800000) return `${Math.floor(diff / 86400000)} 天前`
  return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

export default function TimelinePage() {
  const [items, setItems] = useState<TimelineEntry[]>([])
  const [allItems, setAllItems] = useState<TimelineEntry[]>([]) // 全量数据，用于前端分页
  const [tasks, setTasks] = useState<Task[]>([])
  const [taskId, setTaskId] = useState<string | undefined>(undefined)
  const [types, setTypes] = useState<string>('orders,events')
  const [loading, setLoading] = useState(false)
  const [expandedItems, setExpandedItems] = useState<Set<number>>(new Set())
  const [page, setPage] = useState(1)
  const pageSize = 30
  // 事件类型过滤：空数组 = 不过滤（显示全部）
  const [eventTypeFilter, setEventTypeFilter] = useState<string[]>([])

  useEffect(() => {
    taskApi.list({ limit: 200 }).then((res) => setTasks(res.items || [])).catch(() => {})
  }, [])

  // 从通知配置同步事件订阅规则到过滤条件
  const syncFromNotifier = useCallback(async () => {
    try {
      const cfg = await configApi.get()
      const subscribed: string[] = cfg?.notifier?.subscribed_events || []
      const mapped = subscribed.map(e => ENUM_TO_DOT[e]).filter(Boolean) as string[]
      if (mapped.length > 0 && mapped.length < EVENT_TYPE_OPTIONS.length) {
        setEventTypeFilter(mapped)
      } else {
        // 全部订阅或空订阅 → 不过滤
        setEventTypeFilter([])
      }
    } catch (_) {}
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
        setItems(filtered.slice(0, pageSize))
        setPage(1)
      })
      .catch(() => message.error('加载时间线失败'))
      .finally(() => setLoading(false))
  }, [types, taskId, eventTypeFilter])

  useEffect(() => { load() }, [load])

  // 前端分页切换
  const handlePageChange = (p: number) => {
    setPage(p)
    setItems(filteredItems.slice((p - 1) * pageSize, p * pageSize))
  }

  // 客户端事件类型过滤
  const filteredItems = eventTypeFilter.length > 0
    ? allItems.filter(it => it._kind === 'order' || eventTypeFilter.includes(it.type || ''))
    : allItems

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

  // 任务名映射
  const taskMap = new Map(tasks.map(t => [t.id, t.name || t.keyword || t.id]))

  // 渲染事件详情
  const renderEventDetail = (item: TimelineEntry, idx: number) => {
    const payload = parsePayload(item)
    const isExpanded = expandedItems.has(idx)
    const eventType = item.type || ''
    const level = (item.level || '').toLowerCase()
    const severity = SEVERITY_CONFIG[level] || SEVERITY_CONFIG.info
    const typeInfo = EVENT_TYPE_LABELS[eventType]

    return (
      <div style={{ padding: '4px 0' }}>
        {/* 第一行：事件类型 + 严重度 + 时间 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, flexWrap: 'wrap' }}>
          {typeInfo ? (
            <Tag color={typeInfo.color} icon={typeInfo.icon}>{typeInfo.label}</Tag>
          ) : eventType ? (
            <Tag color="default">{eventType.split('.').pop()}</Tag>
          ) : (
            <Tag color="default">事件</Tag>
          )}
          {level && level !== 'info' && (
            <Tag color={severity.color} icon={severity.icon}>{level.toUpperCase()}</Tag>
          )}
          {item.task_id && (
            <Tooltip title={`任务 ID: ${item.task_id}`}>
              <Tag color="geekblue" style={{ cursor: 'pointer' }}>
                📋 {taskMap.get(item.task_id) || item.task_id.slice(-6)}
              </Tag>
            </Tooltip>
          )}
          <span style={{ color: '#999', fontSize: 11, marginLeft: 'auto' }}>
            {formatRelativeTime(item._ts)}
          </span>
        </div>

        {/* 第二行：主要信息 */}
        <div style={{ marginBottom: 4 }}>
          {item.payload?.message && (
            <div style={{ fontWeight: 500, marginBottom: 2 }}>{item.payload.message}</div>
          )}
          {!item.payload?.message && item.item_title && (
            <div style={{ fontWeight: 500 }}>{item.item_title}</div>
          )}
        </div>

        {/* 第三行：关键指标 */}
        {payload && (
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', fontSize: 12, color: '#666' }}>
            {payload.score !== undefined && payload.score !== null && (
              <span>
                评分：<strong style={{ color: (payload.score as number) >= 80 ? '#52c41a' : (payload.score as number) >= 60 ? '#faad14' : '#ff4d4f' }}>
                  {payload.score as number}
                </strong>
              </span>
            )}
            {!!payload.risk_level && (
              <span>
                风险：<Tag color={RISK_LEVEL_CONFIG[String(payload.risk_level)]?.color || 'default'} style={{ fontSize: 10 }}>
                  {RISK_LEVEL_CONFIG[String(payload.risk_level)]?.label || String(payload.risk_level)}
                </Tag>
              </span>
            )}
            {payload.is_passed !== undefined && (
              <span>
                结果：{(payload.is_passed as boolean) ? (
                  <Tag color="green" style={{ fontSize: 10 }}>通过</Tag>
                ) : (
                  <Tag color="red" style={{ fontSize: 10 }}>未通过</Tag>
                )}
              </span>
            )}
            {payload.found !== undefined && (
              <span>找到 {payload.found as number} 件</span>
            )}
            {payload.evaluated !== undefined && (
              <span>评估 {payload.evaluated as number} 件</span>
            )}
            {payload.passed !== undefined && (
              <span>通过 {payload.passed as number} 件</span>
            )}
            {!!payload.item_id && (
              <Tooltip title={String(payload.item_id)}>
                <span style={{ fontFamily: 'monospace', fontSize: 11 }}>
                  ID: {String(payload.item_id).slice(0, 12)}...
                </span>
              </Tooltip>
            )}
            {!!payload.data_quality && (
              <Tag color={payload.data_quality === 'full' ? 'green' : payload.data_quality === 'partial' ? 'orange' : 'default'} style={{ fontSize: 10 }}>
                {'数据: ' + String(payload.data_quality)}
              </Tag>
            )}
          </div>
        )}

        {/* 展开详情 */}
        {payload && (
          <>
            <Button
              type="link"
              size="small"
              style={{ padding: 0, fontSize: 11, color: '#999' }}
              onClick={() => toggleExpand(idx)}
            >
              {isExpanded ? '收起详情' : '查看详情'}
            </Button>
            {isExpanded && (
              <div style={{
                marginTop: 8,
                padding: 8,
                background: '#fafafa',
                borderRadius: 4,
                fontSize: 11,
                fontFamily: 'monospace',
                maxHeight: 200,
                overflow: 'auto',
              }}>
                <Descriptions size="small" column={2} bordered>
                  {Object.entries(payload)
                    .filter(([k]) => !['message'].includes(k))
                    .slice(0, 12)
                    .map(([k, v]) => (
                      <Descriptions.Item key={k} label={k}>
                        {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                      </Descriptions.Item>
                    ))}
                </Descriptions>
              </div>
            )}
          </>
        )}
      </div>
    )
  }

  // 渲染订单详情
  const renderOrderDetail = (item: TimelineEntry) => {
    const statusConfig = ORDER_STATUS_CONFIG[item.status || ''] || { color: 'default', label: item.status || '未知' }
    const payload = parsePayload(item)

    return (
      <div style={{ padding: '4px 0' }}>
        {/* 第一行：状态 + 时间 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, flexWrap: 'wrap' }}>
          <Tag color={statusConfig.color}>{statusConfig.label}</Tag>
          {item.task_id && (
            <Tooltip title={`任务 ID: ${item.task_id}`}>
              <Tag color="geekblue" style={{ cursor: 'pointer' }}>
                📋 {taskMap.get(item.task_id) || item.task_id.slice(-6)}
              </Tag>
            </Tooltip>
          )}
          <span style={{ color: '#999', fontSize: 11, marginLeft: 'auto' }}>
            {formatRelativeTime(item._ts)}
          </span>
        </div>

        {/* 第二行：商品标题 */}
        <div style={{ fontWeight: 500, marginBottom: 4 }}>
          {item.title || item.item_title || `订单 #${item.id || ''}`}
        </div>

        {/* 第三行：金额 + 其他信息 */}
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', fontSize: 12, color: '#666' }}>
          {item.amount !== undefined && item.amount !== null && (
            <span style={{ color: '#f5222d', fontWeight: 600 }}>
              ¥{item.amount.toFixed(2)}
            </span>
          )}
          {!!payload?.item_id && (
            <Tooltip title={String(payload.item_id)}>
              <span style={{ fontFamily: 'monospace', fontSize: 11 }}>
                ID: {String(payload.item_id).slice(0, 12)}...
              </span>
            </Tooltip>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="page-container">
      <h2 style={{ marginBottom: 16 }}>📡 事件时间线</h2>

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
        <Space style={{ marginBottom: 16 }} wrap>
          <span>事件类型：</span>
          <Select
            style={{ width: 200 }}
            value={types}
            onChange={(v) => setTypes(v)}
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
            onChange={(v) => setTaskId(v)}
            options={tasks.map((t) => ({ label: `${t.name}（${t.keyword}）`, value: t.id }))}
          />
          <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>刷新</Button>
        </Space>

        {/* 事件类型过滤（与通知订阅联动） */}
        <div style={{ marginBottom: 16, padding: '8px 12px', background: '#fafafa', borderRadius: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span style={{ fontWeight: 500, fontSize: 13 }}>事件类型过滤</span>
            <Button size="small" icon={<SyncOutlined />} onClick={syncFromNotifier} title="从通知配置同步订阅规则">
              同步订阅
            </Button>
            {eventTypeFilter.length > 0 && (
              <Button size="small" type="link" onClick={() => setEventTypeFilter([])}>
                清除过滤
              </Button>
            )}
            <span style={{ color: '#999', fontSize: 11, marginLeft: 'auto' }}>
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
                      setEventTypeFilter([opt.value])
                    } else if (eventTypeFilter.includes(opt.value)) {
                      const next = eventTypeFilter.filter(v => v !== opt.value)
                      setEventTypeFilter(next.length === 0 ? [] : next)
                    } else {
                      setEventTypeFilter([...eventTypeFilter, opt.value])
                    }
                  }}
                >
                  {opt.label}
                </Tag>
              )
            })}
          </div>
        </div>

        <Spin spinning={loading}>
          {filteredItems.length === 0 ? (
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

                  // 确定圆点颜色
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
                        color: '#999',
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
                        {isOrder ? renderOrderDetail(item) : renderEventDetail(item, globalIdx)}
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
                  total={filteredItems.length}
                  showTotal={(total) => `共 ${total} 条`}
                  showSizeChanger={false}
                  onChange={handlePageChange}
                  size="small"
                />
              </div>
            </>
          )}
        </Spin>
      </Card>
    </div>
  )
}
