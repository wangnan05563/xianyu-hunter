/**
 * 接管失败透传后端原因 + 空态文案统一（T02676）
 *
 * 回归的缺陷：接管失败只弹「接管失败」，登录态失效/风控/超时一概不可见，
 * 用户只能盲重试；空态写「暂无订单记录」而菜单/页面叫「抢单记录」，两套口径。
 * 透传只展示 detail、不改写不做子串判定（后端语义不进前端逻辑）。
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

const { listMock, takeoverMock } = vi.hoisted(() => ({ listMock: vi.fn(), takeoverMock: vi.fn() }))

vi.mock('../../../api', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  const orderApi = (actual as { orderApi: Record<string, unknown> }).orderApi
  return { ...actual, orderApi: { ...orderApi, list: listMock, takeover: takeoverMock } }
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
  listMock.mockResolvedValue({
    items: [pendingOrder()], count: 1, total: 1, stats: STATS, by_status: { pending_pay: 1 },
  })
})

function axiosLikeError(detail: unknown) {
  // 只还原前端用到的形状：err.response.data.detail
  return { response: { data: { detail } } }
}

async function openModalAndTakeover() {
  render(
    <MemoryRouter initialEntries={['/orders']}>
      <Orders />
    </MemoryRouter>,
  )
  const takeoverBtn = await screen.findByRole('button', { name: /接管/ })
  await userEvent.click(takeoverBtn)
  const confirmBtn = await screen.findByRole('button', { name: /确认接管/ })
  await userEvent.click(confirmBtn)
}

function messageText(): string {
  return Array.from(document.querySelectorAll('.ant-message-notice-content'))
    .map((n) => n.textContent)
    .join('|')
}

describe('接管失败透传原因（T02676）', () => {
  it('后端带 detail 时原样展示，不再只有「接管失败」', async () => {
    takeoverMock.mockRejectedValue(axiosLikeError('登录态已失效，请重新登录'))
    await openModalAndTakeover()
    await waitFor(() => expect(messageText()).toContain('登录态已失效，请重新登录'))
  })

  it('无 detail 或非字符串 detail 时给通用兜底文案，不弹 [object Object]', async () => {
    takeoverMock.mockRejectedValue(axiosLikeError({ code: 500 }))
    await openModalAndTakeover()
    await waitFor(() => expect(messageText()).toContain('接管失败'))
    expect(messageText()).not.toContain('[object')
  })

  it('网络层错误（无 response）同样落到兜底文案', async () => {
    takeoverMock.mockRejectedValue(new Error('Network Error'))
    await openModalAndTakeover()
    await waitFor(() => expect(messageText()).toContain('接管失败'))
  })
})

// 静态守卫：三段 catch 都必须走 takeoverErrMsg（确认/取消与接管是同一缺陷家族），
// 空态必须是「抢单记录」口径
describe('文案与透传接线（静态守卫）', () => {
  const src = readFileSync(resolve(__dirname, '../Orders.tsx'), 'utf-8')
  it('接管/确认/取消三处 catch 均透传 detail', () => {
    expect(src.match(/message\.error\(takeoverErrMsg\(err, /g)?.length).toBe(3)
    expect(src).not.toContain("message.error('接管失败')")
  })
  it('空态文案是「抢单记录」口径', () => {
    expect(src).toContain('暂无抢单记录')
    expect(src).not.toContain('暂无订单记录')
  })
})
