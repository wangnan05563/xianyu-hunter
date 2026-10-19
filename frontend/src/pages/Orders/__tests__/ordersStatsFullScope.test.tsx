/**
 * 抢单记录页状态卡口径（T02568 / 评审 2.5-1 / REQ-036）
 *
 * 回归的是「四张卡按当前页 items 现算」这个缺陷：翻到第 2 页数字全变、
 * 且 pending 桶漏掉后端实际写入的 pending_pay 导致「待处理」恒显示 0。
 * 本页现在直接读 list 响应里的 stats，所以断言方式是：
 * 让「当前页数据」与「后端全量 stats」故意不一致，看卡片听谁的。
 */
import { describe, it, expect, vi, beforeAll, afterAll, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { OrderItem } from '../../../api/types'

// jsdom 没有 EventSource，而本页挂载时会开 SSE 自动刷新；给个不说话的替身，
// 断言只关心 stats 渲染，不关心事件流
class FakeEventSource {
  constructor(public url: string) {}
  addEventListener() {}
  close() {}
}

const { listMock } = vi.hoisted(() => ({ listMock: vi.fn() }))

vi.mock('../../../api', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  const orderApi = (actual as { orderApi: Record<string, unknown> }).orderApi
  return { ...actual, orderApi: { ...orderApi, list: listMock } }
})

import Orders from '../Orders'

const FULL_STATS = {
  pending: 3, paid: 0, succeeded: 7, failed: 1, cancelled: 0, takeover: 2, total: 13,
}

function order(id: string, status: string): OrderItem {
  return {
    id, item_id: `i_${id}`, price: 99, status,
    created_at: '2026-10-19T00:00:00', confirmed_at: null,
  }
}

/** 取某张状态卡的文本（标题在同一 DOM 内，能避开筛选下拉里的同名文本） */
function statText(label: string): string {
  const node = screen.getAllByText(label).find((n) => n.closest('.ant-statistic'))
  return node?.closest('.ant-statistic')?.textContent ?? ''
}

beforeAll(() => {
  vi.stubGlobal('EventSource', FakeEventSource)
})

afterAll(() => {
  vi.unstubAllGlobals()
})

beforeEach(() => {
  localStorage.clear()
  listMock.mockReset()
})

describe('抢单记录状态卡', () => {
  it('读后端全量 stats，而不是当前页 items 现算', async () => {
    // 当前页只有 1 条 succeeded，全量 stats 说 7 条：卡片必须显示 7
    listMock.mockResolvedValue({
      items: [order('o1', 'succeeded')],
      count: 1,
      total: 13,
      stats: FULL_STATS,
      by_status: { succeeded: 7, pending_pay: 3, failed: 1, takeover_pending: 2 },
    })
    render(
      <MemoryRouter initialEntries={['/orders']}>
        <Orders />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getAllByText('已成功').length).toBeGreaterThan(0))
    expect(statText('已成功')).toContain('7')
    expect(statText('已失败')).toContain('1')
    expect(statText('人工接管')).toContain('2')
    // 口径说明挂在卡片标题上，避免用户把四卡读成当前页统计
    expect(statText('已成功')).toContain('已成功')
  })

  it('「待处理」显示 pending_pay 合并后的全量数，不随本页内容归零', async () => {
    // 当前页全是 pending_pay（库里真实写入值），旧实现按 status==='pending' filter 会显示 0
    listMock.mockResolvedValue({
      items: [order('o2', 'pending_pay'), order('o3', 'pending_pay')],
      count: 2,
      total: 2,
      stats: { ...FULL_STATS, pending: 3, total: 13 },
      by_status: { pending_pay: 2, pending: 1 },
    })
    render(
      <MemoryRouter initialEntries={['/orders']}>
        <Orders />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getAllByText('待处理').length).toBeGreaterThan(0))
    expect(statText('待处理')).toContain('3')
  })

  it('请求列表时把分页与状态筛选传给后端，由后端算 stats', async () => {
    listMock.mockResolvedValue({
      items: [], count: 0, total: 0, stats: FULL_STATS, by_status: {},
    })
    render(
      <MemoryRouter initialEntries={['/orders']}>
        <Orders />
      </MemoryRouter>,
    )

    await waitFor(() => expect(listMock).toHaveBeenCalled())
    expect(listMock.mock.calls[0][0]).toMatchObject({ page_num: 1 })
  })
})
