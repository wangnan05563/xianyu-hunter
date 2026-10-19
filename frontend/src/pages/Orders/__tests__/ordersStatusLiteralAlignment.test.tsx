/**
 * 抢单记录页：接管入口与状态字面值同源（T02585 / 3.7）
 *
 * 钉住一个过去完全没有测试覆盖的缺陷：后端 orders.status 写的是 `pending_pay`，
 * 而本页的判断写死 `pending` → 「接管」按钮永不渲染、行内状态显示原始英文、
 * 筛选「待处理」传 status=pending 命中 0 条。三条都靠页面与枚举同源才能修好。
 */
import { describe, it, expect, vi, beforeAll, afterAll, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import type { OrderItem } from '../../../api/types'

// jsdom 没有 EventSource：本页挂载即开 SSE 自动刷新
class FakeEventSource {
  constructor(public url: string) {}
  addEventListener() {}
  close() {}
}

const { listMock, takeoverMock } = vi.hoisted(() => ({
  listMock: vi.fn(),
  takeoverMock: vi.fn(),
}))

vi.mock('../../../api', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  const orderApi = (actual as { orderApi: Record<string, unknown> }).orderApi
  return { ...actual, orderApi: { ...orderApi, list: listMock, takeover: takeoverMock } }
})

import Orders from '../Orders'

const STATS = {
  pending: 1, succeeded: 0, failed: 0, cancelled: 0, takeover: 1, total: 2,
}

function order(id: string, status: string): OrderItem {
  return {
    id, item_id: `i_${id}`, price: 99, status,
    created_at: '2026-10-19T00:00:00', confirmed_at: null,
  }
}

function listResponse(items: OrderItem[]) {
  return { items, count: items.length, total: items.length, stats: STATS, by_status: {} }
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
  takeoverMock.mockReset()
  takeoverMock.mockResolvedValue({
    ok: true, id: 'o1', status: 'takeover_pending',
    takeover_at: '2026-10-19T00:00:00', takeover_deadline: '2026-10-19T00:30:00', timeout_min: 30,
  })
})

describe('接管入口', () => {
  it('pending_pay 行渲染「接管」按钮，takeover_pending 行渲染「查看」', async () => {
    listMock.mockResolvedValue(listResponse([order('o1', 'pending_pay'), order('o2', 'takeover_pending')]))
    render(<MemoryRouter><Orders /></MemoryRouter>)

    // 回归点：判断写成 status === 'pending' 时这里永远找不到按钮（后端写的是 pending_pay）
    const takeoverBtn = await screen.findByRole('button', { name: /接管/ })
    await userEvent.click(takeoverBtn)
    await waitFor(() => expect(document.querySelector('.ant-modal')).not.toBeNull())

    // 接管入口打开的是多步向导弹窗，不直接调接口
    await expect(screen.findByRole('button', { name: /查看/ })).resolves.toBeInTheDocument()
  }, 20000)

  it('行内状态显示中文「待支付」而不是原始英文 pending_pay', async () => {
    listMock.mockResolvedValue(listResponse([order('o1', 'pending_pay')]))
    render(<MemoryRouter><Orders /></MemoryRouter>)

    await screen.findByText('待支付')
    expect(screen.queryByText('pending_pay')).not.toBeInTheDocument()
  })
})

describe('状态筛选与后端枚举同源', () => {
  it('选「待支付」时请求带 status=pending_pay（不是历史的 pending）', async () => {
    listMock.mockResolvedValue(listResponse([order('o1', 'pending_pay')]))
    render(<MemoryRouter><Orders /></MemoryRouter>)

    await screen.findByRole('button', { name: /接管/ })
    // 用占位符定位「状态筛选」下拉：页面里还有分页尺寸等其它 Select
    // 占位符所在节点 pointer-events:none，点它所在的 .ant-select-selector
    const selectEl = (screen.getByText('全部状态').closest('.ant-select') as HTMLElement)
      .querySelector('.ant-select-selector') as HTMLElement
    await userEvent.click(selectEl)
    const option = await waitFor(() => {
      const found = Array.from(document.querySelectorAll('.ant-select-item-option'))
        .filter((n) => n.textContent?.includes('待支付'))
      if (!found.length) throw new Error('下拉未出现「待支付」选项')
      return found[0] as HTMLElement
    })
    await userEvent.click(option)

    await waitFor(() => {
      const last = listMock.mock.calls.at(-1)?.[0] as Record<string, unknown> | undefined
      expect(last?.status).toBe('pending_pay')
    })
  })
})
