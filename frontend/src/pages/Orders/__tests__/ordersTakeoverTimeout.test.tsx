/**
 * 接管倒计时归零后的语义说明（T02675）
 *
 * 回归的缺陷：倒计时到 0 只显红色「已超时」，确认/取消按钮原样可点却无任何
 * 说明——涉及真金白银的接管决策，语义不能模棱两可。
 *
 * 先查清的后端事实（决定文案走向）：confirm/cancel 只校验状态不校验 deadline，
 * 超时窗口内仍接受确认；超时清理调度器（5 分钟一扫）稍后把过期单转 failed。
 * 因此走「仍可确认，但风险自负」分支：按钮保持可点，补说明条。
 */
import { describe, it, expect, vi, beforeAll, afterAll, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { MemoryRouter } from 'react-router-dom'
import type { OrderItem } from '../../../api/types'

class FakeEventSource {
  constructor(public url: string) {}
  addEventListener() {}
  close() {}
}

const { listMock, takeoverMock, confirmMock } = vi.hoisted(() => ({
  listMock: vi.fn(), takeoverMock: vi.fn(), confirmMock: vi.fn(),
}))

vi.mock('../../../api', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  const orderApi = (actual as { orderApi: Record<string, unknown> }).orderApi
  return { ...actual, orderApi: { ...orderApi, list: listMock, takeover: takeoverMock, confirmTakeover: confirmMock } }
})

import Orders from '../Orders'

const STATS = {
  pending: 1, paid: 0, succeeded: 0, failed: 0, cancelled: 0, takeover: 0, total: 1,
}

function pendingOrder(): OrderItem {
  return {
    id: 'o1', item_id: 'i_1', price: 99, status: 'pending_pay',
    created_at: '2026-10-21T00:00:00', confirmed_at: null,
  }
}

beforeAll(() => {
  vi.stubGlobal('EventSource', FakeEventSource)
  Element.prototype.scrollIntoView = () => {}
})
afterAll(() => { vi.unstubAllGlobals() })

beforeEach(() => {
  localStorage.clear()
  listMock.mockReset()
  takeoverMock.mockReset()
  confirmMock.mockReset()
  listMock.mockResolvedValue({
    items: [pendingOrder()], count: 1, total: 1, stats: STATS, by_status: { pending_pay: 1 },
  })
})

async function takeoverWith(deadline: string) {
  takeoverMock.mockResolvedValue({
    ok: true, id: 'o1', status: 'takeover_pending',
    takeover_at: '2026-10-21T00:00:00', takeover_deadline: deadline, timeout_min: 30,
  })
  render(
    <MemoryRouter initialEntries={['/orders']}>
      <Orders />
    </MemoryRouter>,
  )
  await userEvent.click(await screen.findByRole('button', { name: /接管/ }))
  await userEvent.click(await screen.findByRole('button', { name: /确认接管/ }))
  await screen.findByText('闲鱼支付中')
}

describe('倒计时归零语义（T02675）', () => {
  it('已超时：显示说明条（仍可确认但风险自负），按钮保持可点', async () => {
    await takeoverWith('2026-10-20T00:00:00') // 过去的 deadline
    expect(await screen.findByText('接管已超时')).toBeInTheDocument()
    expect(screen.getByText(/风险自负/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /确认完成/ })).not.toBeDisabled()
    expect(screen.getByRole('button', { name: /取消接管/ })).not.toBeDisabled()
  })

  it('未超时：不出现超时说明条', async () => {
    await takeoverWith('2099-01-01T00:00:00')
    expect(screen.queryByText('接管已超时')).not.toBeInTheDocument()
  })

  it('超时后确认按钮仍能发请求（不因超时被禁用）', async () => {
    confirmMock.mockResolvedValue({ ok: true })
    await takeoverWith('2026-10-20T00:00:00')
    await userEvent.click(await screen.findByRole('button', { name: /确认完成/ }))
    await waitFor(() => expect(confirmMock).toHaveBeenCalledWith('o1'))
  })
})

// 静态守卫：说明条必须挂在 remaining<=0 的条件上且把「转失败单」说清楚
describe('超时说明接线（静态守卫）', () => {
  const src = readFileSync(resolve(__dirname, '../Orders.tsx'), 'utf-8')
  it('说明条挂在 remaining <= 0 上，并交代超时清理后果', () => {
    const at = src.indexOf('接管已超时"')
    expect(at).toBeGreaterThan(0)
    const ctx = src.slice(Math.max(0, at - 600), at)
    expect(ctx).toContain('remaining <= 0')
    expect(src.slice(at, at + 400)).toContain('转为失败单')
  })
})
