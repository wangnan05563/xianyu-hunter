import { Tag, Tooltip, Descriptions } from 'antd'
import type { TimelineEntry } from '../../../api'
import { TipButton } from '@/components/TipButton'
import {
  EVENT_TYPE_LABELS, SEVERITY_CONFIG,
} from '../../../constants/eventTypes'
import { ORDER_STATUS_CONFIG } from '../../../constants/orderStatus'
import { RISK_LEVEL_CONFIG } from '../../../constants/riskLevels'
import { parsePayload, formatRelativeTime } from '../utils'

// payload 字段类型为 unknown，直接 String() 在值为对象/数组时会得到 [object Object]，
// 因此统一封装：对象用 JSON.stringify，其他用 toString，null/undefined 返回空串
const safeStr = (v: unknown): string => {
  if (v === null || v === undefined) return ''
  if (typeof v === 'object') return JSON.stringify(v)
  // 经过前面的 typeof 检查，v 必为基础类型，用 toString() 避免 S6551
  return (v as { toString: () => string }).toString()
}

interface TimelineItemProps {
  readonly item: TimelineEntry
  readonly index: number
  readonly isExpanded: boolean
  readonly onToggleExpand: (idx: number) => void
  // 任务名映射：task_id → 任务名（用于在事件项中显示人类可读的任务标识）
  readonly taskMap: Map<string, string>
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
  readonly item: TimelineEntry
  readonly idx: number
  readonly isExpanded: boolean
  readonly onToggleExpand: (idx: number) => void
  readonly taskMap: Map<string, string>
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
        {(() => {
          // 事件类型 Tag 三态：已知类型 / 未知类型 / 缺失
          if (typeInfo) {
            return <Tag color={typeInfo.color} icon={typeInfo.icon}>{typeInfo.label}</Tag>
          }
          if (eventType) {
            return <Tag color="default">{eventType.split('.').pop()}</Tag>
          }
          return <Tag color="default">事件</Tag>
        })()}
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
        <span style={{ color: 'var(--xh-text-tertiary)', fontSize: 11, marginLeft: 'auto' }}>
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
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', fontSize: 12, color: 'var(--xh-text-secondary)' }}>
          {payload.score !== undefined && payload.score !== null && (
            <span>
              评分：<strong style={{ color: (() => {
                // 评分色：≥80 绿 ≥60 橙 否则红
                const s = payload.score as number
                if (s >= 80) return '#52c41a'
                if (s >= 60) return '#faad14'
                return '#ff4d4f'
              })() }}>
                {payload.score as number}
              </strong>
            </span>
          )}
          {!!payload.risk_level && (
            <span>
              风险：<Tag color={RISK_LEVEL_CONFIG[safeStr(payload.risk_level)]?.color || 'default'} style={{ fontSize: 10 }}>
                {RISK_LEVEL_CONFIG[safeStr(payload.risk_level)]?.label || safeStr(payload.risk_level)}
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
            <Tooltip title={safeStr(payload.item_id)}>
              <span style={{ fontFamily: 'monospace', fontSize: 11 }}>
                ID: {safeStr(payload.item_id).slice(0, 12)}...
              </span>
            </Tooltip>
          )}
          {!!payload.data_quality && (
            <Tag color={(() => {
              // 数据质量色：full=绿 partial=橙 其他=default
              const dq = payload.data_quality
              if (dq === 'full') return 'green'
              if (dq === 'partial') return 'orange'
              return 'default'
            })()} style={{ fontSize: 10 }}>
              {'数据: ' + safeStr(payload.data_quality)}
            </Tag>
          )}
        </div>
      )}

      {/* 展开详情 */}
      {payload && (
        <>
          <TipButton
            tip="展开或收起该事件的详细载荷"
            type="link"
            size="small"
            style={{ padding: 0, fontSize: 11, color: 'var(--xh-text-tertiary)' }}
            onClick={() => onToggleExpand(idx)}
          >
            {isExpanded ? '收起详情' : '查看详情'}
          </TipButton>
          {isExpanded && (
            <div style={{
              marginTop: 8,
              padding: 8,
              background: 'var(--xh-bg-spotlight)',
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
                      {safeStr(v)}
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
  readonly item: TimelineEntry
  readonly taskMap: Map<string, string>
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
        <span style={{ color: 'var(--xh-text-tertiary)', fontSize: 11, marginLeft: 'auto' }}>
          {formatRelativeTime(item._ts)}
        </span>
      </div>

      {/* 第二行：商品标题 */}
      <div style={{ fontWeight: 500, marginBottom: 4 }}>
        {item.title || item.item_title || `订单 #${item.id || ''}`}
      </div>

      {/* 第三行：金额 + 其他信息 */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', fontSize: 12, color: 'var(--xh-text-secondary)' }}>
        {item.amount !== undefined && item.amount !== null && (
          <span style={{ color: '#f5222d', fontWeight: 600 }}>
            ¥{item.amount.toFixed(2)}
          </span>
        )}
        {!!payload?.item_id && (
          <Tooltip title={safeStr(payload.item_id)}>
            <span style={{ fontFamily: 'monospace', fontSize: 11 }}>
              ID: {safeStr(payload.item_id).slice(0, 12)}...
            </span>
          </Tooltip>
        )}
      </div>
    </div>
  )
}
