// frontend/src/pages/Orders/ItemSummaryCell.tsx
// T02674：抢单记录的「商品ID」列原先只是纯文本，抢单后想回看当时那个商品
// 只能手动去商品中心搜 ID。点开 Popover 用 /api/items/{id}/summary 取快照，
// 没有商品详情页路由，也不依赖后端补 url 字段（那是另一条线）。
import { useState } from 'react'
import { Button, Descriptions, Popover, Space, Spin, Typography } from 'antd'
import { itemApi, type ItemSummary } from '../../api'

type Load = 'idle' | 'loading' | 'ready' | 'failed'

export default function ItemSummaryCell({ itemId }: { readonly itemId: string }) {
  const [open, setOpen] = useState(false)
  const [state, setState] = useState<Load>('idle')
  const [summary, setSummary] = useState<ItemSummary | null>(null)

  const load = () => {
    setState('loading')
    itemApi.summary(itemId)
      .then((s) => {
        setSummary(s)
        setState('ready')
      })
      .catch(() => setState('failed'))
  }

  const onOpenChange = (next: boolean) => {
    setOpen(next)
    // 失败后重开 = 重试；不静默兜底，取不到就明说取不到
    if (next && (state === 'idle' || state === 'failed')) load()
  }

  let content = null
  if (state === 'loading') {
    content = <Space><Spin size="small" /><span>正在取商品快照…</span></Space>
  } else if (state === 'failed') {
    content = (
      <Space direction="vertical" size={4}>
        <span>商品快照取不到：商品可能已被平台删除或清理，抢单记录里的 ID 仍可用。</span>
        <Button size="small" onClick={load}>重试</Button>
      </Space>
    )
  } else if (state === 'ready' && summary) {
    content = (
      <Descriptions column={1} size="small" style={{ minWidth: 260 }}>
        <Descriptions.Item label="标题">{summary.title}</Descriptions.Item>
        <Descriptions.Item label="价格">￥{summary.price}</Descriptions.Item>
        {summary.seller_nick && (
          <Descriptions.Item label="卖家">{summary.seller_nick}</Descriptions.Item>
        )}
        {summary.seller_id && (
          <Descriptions.Item label="卖家ID">{summary.seller_id}</Descriptions.Item>
        )}
      </Descriptions>
    )
  }

  return (
    <Popover
      open={open}
      onOpenChange={onOpenChange}
      trigger="click"
      title="商品快照（抢单时看到的商品）"
      content={content}
    >
      <Typography.Link style={{ maxWidth: 180 }} ellipsis>{itemId}</Typography.Link>
    </Popover>
  )
}
