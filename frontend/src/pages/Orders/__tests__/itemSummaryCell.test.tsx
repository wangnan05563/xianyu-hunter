/**
 * 抢单记录「商品ID」列弹商品快照（T02674）
 *
 * 回归的缺陷：该列原先只是纯文本，抢单后想回看当时那个商品只能手动去商品中心搜 ID。
 * 现在点 ID 弹 Popover，用 itemApi.summary 取快照；取不到时明说取不到并提供重试，
 * 不允许出现「弹层打开但内容为空」的静默兜底。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const { summaryMock } = vi.hoisted(() => ({ summaryMock: vi.fn() }))

vi.mock('../../../api', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  const itemApi = (actual as { itemApi: Record<string, unknown> }).itemApi
  return { ...actual, itemApi: { ...itemApi, summary: summaryMock } }
})

import ItemSummaryCell from '../ItemSummaryCell'

const SUMMARY = {
  item_id: 'i_1001',
  title: '九成新蓝牙耳机',
  price: 59.9,
  seller_id: 's_7',
  seller_nick: '老王出闲置',
}

beforeEach(() => {
  summaryMock.mockReset()
})

async function openPopover() {
  render(<ItemSummaryCell itemId="i_1001" />)
  await userEvent.click(screen.getByText('i_1001'))
}

describe('ItemSummaryCell（T02674）', () => {
  it('点开弹层取快照：展示标题/价格/卖家', async () => {
    summaryMock.mockResolvedValue(SUMMARY)
    await openPopover()
    expect(await screen.findByText('九成新蓝牙耳机')).toBeInTheDocument()
    expect(screen.getByText('￥59.9')).toBeInTheDocument()
    expect(screen.getByText('老王出闲置')).toBeInTheDocument()
    expect(summaryMock).toHaveBeenCalledWith('i_1001')
  })

  it('取不到就明说取不到，绝不渲染空弹层装没事', async () => {
    summaryMock.mockRejectedValue(new Error('404'))
    await openPopover()
    expect(await screen.findByText(/商品快照取不到/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /重\s*试/ })).toBeInTheDocument()
    expect(screen.queryByText('￥')).not.toBeInTheDocument()
  })

  it('失败后点重试会再取一次并成功渲染', async () => {
    summaryMock.mockRejectedValueOnce(new Error('500')).mockResolvedValueOnce(SUMMARY)
    await openPopover()
    await screen.findByText(/商品快照取不到/)
    await userEvent.click(screen.getByRole('button', { name: /重\s*试/ }))
    expect(await screen.findByText('九成新蓝牙耳机')).toBeInTheDocument()
    expect(summaryMock).toHaveBeenCalledTimes(2)
  })

  it('失败后关闭再重开同样触发重试（不用非得停在弹层里点按钮）', async () => {
    summaryMock.mockRejectedValueOnce(new Error('500')).mockResolvedValueOnce(SUMMARY)
    await openPopover()
    await screen.findByText(/商品快照取不到/)
    await userEvent.click(screen.getByText('i_1001')) // 关闭
    await userEvent.click(screen.getByText('i_1001')) // 重开
    expect(await screen.findByText('九成新蓝牙耳机')).toBeInTheDocument()
  })
})

// 接错对象守卫：render 必须挂在 item_id 列上且喂的是该列的值，
// 挂到 id/price 列或写成常量都会让弹层展示错误的商品
describe('Orders 列接线（静态守卫）', () => {
  const src = readFileSync(resolve(__dirname, '../Orders.tsx'), 'utf-8')
  const line = src.split('\n').find((l) => l.includes("dataIndex: 'item_id'") && l.includes('title'))
  it('item_id 列的 render 挂 ItemSummaryCell 且取值来自该列', () => {
    expect(line).toBeDefined()
    expect(line).toContain('render: (v: string) => <ItemSummaryCell itemId={v} />')
  })
  it('没有把别的列也接上快照弹层', () => {
    const wired = src.split('\n').filter((l) => l.includes('<ItemSummaryCell'))
    expect(wired.length).toBe(1)
  })
})
