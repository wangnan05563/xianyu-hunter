import { Tag, Tooltip, Button, Descriptions } from 'antd'
import type { TimelineEntry } from '../../../api'
import {
  EVENT_TYPE_LABELS, SEVERITY_CONFIG,
} from '../../../constants/eventTypes'
import { ORDER_STATUS_CONFIG } from '../../../constants/orderStatus'
import { RISK_LEVEL_CONFIG } from '../../../constants/riskLevels'
import { parsePayload, formatRelativeTime } from '../utils'

interface TimelineItemProps {
  item: TimelineEntry
  index: number
  isExpanded: boolean
  onToggleExpand: (idx: number) => void
  // 任务名映射：task_id → 任务名（用于在事件项中显示人类可读的任务标识）
  taskMap: Map<string, string>
}

// 单条时间线项：根据 _kind 分发到订单详情或事件详情
export default function TimelineItem({
  item, index, isExpanded, onToggleExpand, taskMap,
}: TimelineItemProps) {
  if (item._kind === 'order') {
    return <OrderDetail item={item} taskMap={taskMap} />
  }
  return (
    <EventDetail
      item={item}
      idx={index}
      isExpanded={isExpanded}
      onToggleExpand={onToggleExpand}
      taskMap={taskMap}
    />
  )
}

interface EventDetailProps {
  item: TimelineEntry
  idx: number
  isExpanded: boolean
  onToggleExpand: (idx: number) => void
  taskMap: Map<string, string>
}

// 事件详情：事件类型 + 严重度 + 关键指标 + 可展开的 payload 详情
function EventDetail({ item, idx, isExpanded, onToggleExpand, taskMap }: EventDetailProps) {
  const payload = parsePayload(item)
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
            onClick={() => onToggleExpand(idx)}
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

interface OrderDetailProps {
  item: TimelineEntry
  taskMap: Map<string, string>
}

// 订单详情：状态 + 商品标题 + 金额
function OrderDetail({ item, taskMap }: OrderDetailProps) {
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
