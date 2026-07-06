import { useMemo, useState, useEffect } from 'react'
import { Tag, Button, Space, Tooltip, Image } from 'antd'
import {
  RobotOutlined, ThunderboltOutlined, CloudDownloadOutlined,
  EnvironmentOutlined, ClockCircleOutlined, UserOutlined,
  PictureOutlined, LinkOutlined,
  CheckCircleOutlined, WarningOutlined, CloseCircleOutlined,
} from '@ant-design/icons'
import type { EvalItem } from '../../../api'
import { RISK_LEVEL_CONFIG } from '../../../constants/riskLevels'
import { isDataInsufficient, getInsufficientReason, resolveActionDisplay, type ActionPlaceholderType } from '../utils'
import { translateDimension, translateRejectReason } from '../dimensionLabels'

const ACTION_PLACEHOLDER_TEXT: Record<Exclude<ActionPlaceholderType, null>, string> = {
  ordered: '已下单',
  sold: '已售',
  below_threshold: '未达阈值',
}

function ActionPlaceholder({ text }: { text: string }) {
  return <span style={{ color: 'var(--xh-text-quaternary)', fontSize: 11 }}>{text}</span>
}

function formatPublishTime(raw: string | number | null | undefined): string | null {
  if (raw === null || raw === undefined || raw === '') return null
  const d = new Date(raw)
  if (Number.isNaN(d.getTime())) return null
  return d.toLocaleString('zh-CN', { hour12: false })
}

function ThumbCell({ url, title }: { readonly url?: string | null; readonly title?: string | null }) {
  const [errored, setErrored] = useState(false)
  useEffect(() => { setErrored(false) }, [url])
  if (url && !errored) {
    return (
      <Image
        src={url}
        referrerPolicy="no-referrer"
        width={50}
        height={50}
        style={{ objectFit: 'cover', borderRadius: 6, background: 'var(--xh-bg-code)' }}
        preview={{ mask: '预览' }}
        onError={() => setErrored(true)}
        alt={title || ''}
      />
    )
  }
  return (
    <div
      style={{
        width: 50, height: 50, borderRadius: 6,
        background: '#f5f5f5', color: 'var(--xh-text-quaternary)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
      title={title || '暂无图片'}
    >
      <PictureOutlined style={{ fontSize: 20 }} />
    </div>
  )
}

interface UseEvalColumnsParams {
  autoBuyScore: number
  passScore: number
  collecting: Record<string, boolean>
  feedbackSubmitting: Record<string, boolean>
  manualTaking: Record<string, boolean>
  onAIEval: (itemId: string) => Promise<void>
  onDeepAnalyze: (itemId: string) => Promise<void>
  onCollectOfficial: (r: EvalItem) => Promise<void>
  onFeedback: (r: EvalItem, feedback: 'accurate' | 'inaccurate' | 'partial') => Promise<void>
  onManualTakeover: (r: EvalItem) => Promise<void>
  onTitleClick: (e: React.MouseEvent, r: EvalItem, url: string) => void
}

export function useEvalColumns(params: UseEvalColumnsParams) {
  const {
    autoBuyScore, passScore, collecting, feedbackSubmitting, manualTaking,
    onAIEval, onDeepAnalyze, onCollectOfficial, onFeedback, onManualTakeover, onTitleClick,
  } = params

  return useMemo(() => [
    {
      title: '任务ID', dataIndex: 'task_id', key: 'task_id', width: 120,
      ellipsis: true,
      responsive: ['sm'] as ('sm' | 'md')[],
      render: (v: string) => <Tooltip title={v}>{v?.slice(0, 10)}...</Tooltip>,
    },
    {
      title: '图片', key: 'thumb', width: 70,
      render: (_: unknown, r: EvalItem) => {
        const url = r.payload?.thumb_url as string | undefined
        return <ThumbCell url={url} title={r.payload?.item_title} />
      },
    },
    {
      title: '标题', key: 'title', width: 200, ellipsis: true,
      render: (_: unknown, r: EvalItem) => {
        const title = r.payload?.item_title || '—'
        const url = `https://www.goofish.com/item?id=${r.item_id}`
        return (
          <Tooltip title={`${title}（点击采集更新品牌等字段）`}>
            <a
              href={url}
              onClick={(e) => onTitleClick(e, r, url)}
              style={{ cursor: 'pointer' }}
            >
              {title} <LinkOutlined />
            </a>
          </Tooltip>
        )
      },
    },
    {
      title: '价格', key: 'price', width: 90,
      sorter: (a: EvalItem, b: EvalItem) =>
        (a.payload?.item_price ?? 0) - (b.payload?.item_price ?? 0),
      render: (_: unknown, r: EvalItem) => r.payload?.item_price == null
        ? <span style={{ color: 'var(--xh-text-quaternary)' }}>—</span>
        : <span style={{ color: '#f5222d', fontWeight: 600 }}>¥{Number(r.payload.item_price).toFixed(2)}</span>,
    },
    {
      title: '卖家', key: 'seller', width: 170, ellipsis: true,
      render: (_: unknown, r: EvalItem) => {
        const nick = r.payload?.seller_nick
        const id = r.payload?.seller_id
        const credit = r.payload?.seller_credit as string | undefined
        const hasNick = !!nick?.trim()
        const displayName = (() => {
          if (hasNick) return nick
          if (id) return `用户 ${id.slice(0, 8)}`
          return '—'
        })()
        return (
          <div style={{ lineHeight: 1.3 }}>
            <div>
              <UserOutlined style={{ marginRight: 4, color: hasNick ? '#1890ff' : 'var(--xh-text-quaternary)' }} />
              <Tooltip title={hasNick ? nick : (id || '无卖家信息')}>
                <span>{displayName}</span>
              </Tooltip>
            </div>
            {credit && (
              <div style={{ fontSize: 11, color: '#52c41a', marginTop: 2 }}>
                信用 {credit}
              </div>
            )}
          </div>
        )
      },
    },
    {
      title: '地区', key: 'region', width: 90,
      render: (_: unknown, r: EvalItem) => {
        const region = r.payload?.region as string | undefined
        if (region) {
          return (
            <span>
              <EnvironmentOutlined style={{ marginRight: 4, color: '#fa8c16' }} />
              {region}
            </span>
          )
        }
        return <span style={{ color: 'var(--xh-text-quaternary)' }}>—</span>
      },
    },
    {
      title: '品牌', key: 'brand', width: 90, ellipsis: true,
      render: (_: unknown, r: EvalItem) => {
        const brand = r.payload?.brand
        if (brand) {
          return <Tooltip title={brand}>{brand}</Tooltip>
        }
        return <span style={{ color: 'var(--xh-text-quaternary)' }}>—</span>
      },
    },
    {
      title: '想要', key: 'want', width: 60,
      render: (_: unknown, r: EvalItem) => {
        const w = r.payload?.want_cnt as number | undefined
        return w == null ? <span style={{ color: 'var(--xh-text-quaternary)' }}>—</span> : <span>{w}</span>
      },
    },
    {
      title: '浏览', key: 'view', width: 60,
      render: (_: unknown, r: EvalItem) => {
        const v = r.payload?.view_cnt as number | undefined
        return v == null ? <span style={{ color: 'var(--xh-text-quaternary)' }}>—</span> : <span>{v}</span>
      },
    },
    {
      title: '发布时间', key: 'publish', width: 160,
      responsive: ['md'] as ('sm' | 'md')[],
      render: (_: unknown, r: EvalItem) => {
        const formatted = formatPublishTime(r.payload?.publish_time as string | undefined)
        if (formatted) {
          return (
            <Tooltip title={formatted}>
              <span>
                <ClockCircleOutlined style={{ marginRight: 4, color: '#1890ff' }} />
                {formatted}
              </span>
            </Tooltip>
          )
        }
        const text = r.payload?.publish_time_text as string | undefined
        if (text) {
          return <span style={{ color: '#faad14' }}>{text}</span>
        }
        return <span style={{ color: 'var(--xh-text-quaternary)' }}>—</span>
      },
    },
    {
      title: '状态', key: 'is_sold', width: 80,
      render: (_: unknown, r: EvalItem) => {
        const isSold = r.payload?.is_sold
        return isSold ? <Tag color="red">已售</Tag> : <Tag color="green">在售</Tag>
      },
    },
    {
      title: '成色', key: 'condition', width: 110,
      filters: [
        { text: '全新', value: '全新' },
        { text: '近全新', value: '近全新' },
        { text: '正常使用', value: '正常使用' },
        { text: '明显使用', value: '明显使用' },
        { text: '有故障/维修', value: '有故障/维修' },
        { text: '未注明', value: '未注明' },
        { text: '未知', value: '未知' },
      ],
      onFilter: (val: unknown, r: EvalItem) => r.condition_label === val,
      render: (_: unknown, r: EvalItem) => {
        const label = r.condition_label || '未知'
        const score = r.condition_score || 0
        const colorMap: Record<string, string> = {
          '全新': 'green',
          '近全新': 'cyan',
          '正常使用': 'default',
          '明显使用': 'orange',
          '有故障/维修': 'red',
          '未注明': 'default',
          '未知': 'default',
        }
        return (
          <div>
            <Tag color={colorMap[label] || 'default'}>{label}</Tag>
            {score !== 0 && (
              <span style={{ fontSize: 11, marginLeft: 4, color: score > 0 ? '#52c41a' : '#ff4d4f' }}>
                {score > 0 ? `+${score}` : score}分
              </span>
            )}
            {r.is_branded_new && (
              <Tag color="green" style={{ fontSize: 10, lineHeight: '16px', padding: '0 4px', margin: '2px 0 0 0' }}>全新</Tag>
            )}
            {r.has_repair && (
              <Tag color="red" style={{ fontSize: 10, lineHeight: '16px', padding: '0 4px', margin: '2px 0 0 4px' }}>有维修</Tag>
            )}
          </div>
        )
      },
    },
    {
      title: '成色标签', key: 'condition_tags', width: 150,
      render: (_: unknown, r: EvalItem) => {
        const tags = r.condition_tags || []
        if (tags.length === 0) return '—'
        return (
          <span style={{ fontSize: 11 }}>
            {tags.slice(0, 3).map((t, i) => (
              <Tag key={`${t.label}-${i}`} style={{ marginBottom: 2 }} color="blue">{t.label}</Tag>
            ))}
            {tags.length > 3 && <span style={{ color: 'var(--xh-text-tertiary)' }}>+{tags.length - 3}</span>}
          </span>
        )
      },
    },
    {
      title: '评分', key: 'score', width: 80,
      sorter: (a: EvalItem, b: EvalItem) => (a.payload.score ?? 0) - (b.payload.score ?? 0),
      render: (_: unknown, r: EvalItem) => {
        if (isDataInsufficient(r)) {
          return <Tag color="default">{getInsufficientReason(r)}</Tag>
        }
        const s = r.payload.score
        const color = (() => {
          if (s >= autoBuyScore) return '#52c41a'
          if (s >= passScore) return '#faad14'
          return '#ff4d4f'
        })()
        const dq = r.payload?.data_quality as string | undefined
        const dqColorMap: Record<string, string> = { full: 'green', partial: 'orange', insufficient: 'red' }
        const dqLabelMap: Record<string, string> = { full: '完整', partial: '部分', insufficient: '不足' }
        return (
          <div>
            <span style={{ color, fontWeight: 600, fontSize: 15 }}>{s.toFixed(1)}</span>
            {dq && dqLabelMap[dq] && (
              <div>
                <Tag color={dqColorMap[dq]} style={{ fontSize: 10, lineHeight: '14px', padding: '0 4px', margin: 0 }}>
                  {dqLabelMap[dq]}
                </Tag>
              </div>
            )}
          </div>
        )
      },
    },
    {
      title: '风险', key: 'risk', width: 70,
      render: (_: unknown, r: EvalItem) => {
        const level = r.payload?.risk_level || 'unknown'
        const cfg = RISK_LEVEL_CONFIG[level] || RISK_LEVEL_CONFIG.unknown
        return <Tag color={cfg.color}>{cfg.label}</Tag>
      },
    },
    {
      title: 'AI', key: 'ai', width: 110,
      render: (_: unknown, r: EvalItem) => (
        <Space size={4}>
          <Tooltip title="AI 成色评估">
            <Button
              size="small"
              icon={<RobotOutlined />}
              onClick={() => onAIEval(r.item_id)}
              disabled={isDataInsufficient(r) && (r.payload.score ?? 0) < 60}
            />
          </Tooltip>
          <Tooltip title="深度鉴伪（盗图/损坏/一致性/模板）">
            <Button
              size="small"
              icon={<ThunderboltOutlined />}
              onClick={() => onDeepAnalyze(r.item_id)}
              disabled={isDataInsufficient(r) && (r.payload.score ?? 0) < 60}
            />
          </Tooltip>
        </Space>
      ),
    },
    {
      title: '官方采集', key: 'collect', width: 90,
      render: (_: unknown, r: EvalItem) => (
        <Tooltip title="访问闲鱼官方页面采集完整数据并重新评估">
          <Button
            size="small"
            type="default"
            icon={<CloudDownloadOutlined />}
            loading={collecting[r.item_id]}
            onClick={() => onCollectOfficial(r)}
          />
        </Tooltip>
      ),
    },
    {
      title: '反馈', key: 'feedback', width: 110,
      render: (_: unknown, r: EvalItem) => {
        const current = r.payload?.feedback as 'accurate' | 'inaccurate' | 'partial' | undefined
        const submitting = feedbackSubmitting[r.item_id]
        const btn = (
          type: 'accurate' | 'inaccurate' | 'partial',
          icon: React.ReactNode,
          color: string,
          title: string,
        ) => (
          <Tooltip title={title}>
            <Button
              size="small"
              type={current === type ? 'primary' : 'text'}
              ghost={current === type}
              icon={icon}
              loading={submitting}
              onClick={() => onFeedback(r, type)}
              style={current === type ? { background: color, borderColor: color } : { color }}
            />
          </Tooltip>
        )
        return (
          <Space size={2}>
            {btn('accurate', <CheckCircleOutlined />, '#52c41a', '准确')}
            {btn('partial', <WarningOutlined />, '#faad14', '部分准确')}
            {btn('inaccurate', <CloseCircleOutlined />, '#ff4d4f', '不准确')}
          </Space>
        )
      },
    },
    {
      title: '订单', key: 'order_status', width: 90,
      render: (_: unknown, r: EvalItem) => {
        const status = r.payload?.order_status
        if (status) {
          const statusMap: Record<string, { color: string; label: string }> = {
            pending_pay: { color: 'orange', label: '待支付' },
            paid: { color: 'blue', label: '已支付' },
            succeeded: { color: 'green', label: '已成功' },
            takeover_pending: { color: 'gold', label: '接管中' },
            cancelled: { color: 'default', label: '已取消' },
            failed: { color: 'red', label: '失败' },
          }
          const cfg = statusMap[status] || { color: 'default', label: status }
          return <Tag color={cfg.color}>{cfg.label}</Tag>
        }
        return <span style={{ color: 'var(--xh-text-quaternary)' }}>—</span>
      },
    },
    {
      title: '操作', key: 'action', width: 80, fixed: 'right' as const,
      render: (_: unknown, r: EvalItem) => {
        const placeholder = resolveActionDisplay(r, autoBuyScore)
        if (placeholder) {
          const soldHint = placeholder === 'ordered' && r.payload?.is_sold ? '（已售）' : ''
          return <ActionPlaceholder text={`${ACTION_PLACEHOLDER_TEXT[placeholder]}${soldHint}`} />
        }
        const score = r.payload.score ?? 0
        return (
          <Tooltip title={`手动抢单（评分 ${score.toFixed(0)} ≥ ${autoBuyScore}）`}>
            <Button
              size="small"
              type="primary"
              ghost
              icon={<ThunderboltOutlined />}
              loading={manualTaking[r.item_id]}
              onClick={() => onManualTakeover(r)}
            />
          </Tooltip>
        )
      },
    },
  ], [
    autoBuyScore, passScore, collecting, feedbackSubmitting, manualTaking,
    onAIEval, onDeepAnalyze, onCollectOfficial, onFeedback, onManualTakeover, onTitleClick,
  ])
}
