/**
 * 抢单记录页读取告警深链（T02620）
 *
 * 回归的缺陷：抽屉/雷达的跳转只到「页面级」，落地后看不出是哪一条异常——
 * 因为本页历史上只读 ?ref=，不读 ?status=，抽屉带过来的筛选参数被静默忽略。
 * 这里用真实挂载（MemoryRouter + 初始 URL）断言「URL 参数 → 筛选状态 → 请求参数」这条链。
 */
import { describe, it, expect, vi, beforeAll, afterAll, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { OrderItem } from '../../../api/types'

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

const STATS = {
  pending: 0, paid: 0, succeeded: 0, failed: 1, cancelled: 0, takeover: 0, total: 1,
}

function order(id: string, status: string): OrderItem {
  return {
    id, item_id: `i_${id}`, price: 99, status,
    created_at: '2026-10-21T00:00:00', confirmed_at: null,
  }
}

beforeAll(() => {
  vi.stubGlobal('EventSource', FakeEventSource)
  // jsdom 没实现 scrollIntoView：命中 ref 定位后本页会滚动该行，缺省实现会抛未捕获异常
  Element.prototype.scrollIntoView = () => {}
})
afterAll(() => { vi.unstubAllGlobals() })

beforeEach(() => {
  localStorage.clear()
  listMock.mockReset()
  listMock.mockResolvedValue({
    items: [order('o1', 'failed')], count: 1, total: 1, stats: STATS, by_status: { failed: 1 },
  })
})

function renderAt(entry: string) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Orders />
    </MemoryRouter>,
  )
}

describe('?status= 驱动状态筛选', () => {
  it('带 ?status=failed&ref=o1 落地：请求带 status=failed，下拉显示「已失败」', async () => {
    renderAt('/orders?status=failed&ref=o1')
    await waitFor(() => expect(listMock).toHaveBeenCalled())
    expect(listMock.mock.calls[0][0]).toMatchObject({ status: 'failed' })
    // 筛选控件必须可见地把「已按告警筛过」表达出来，否则用户仍以为看的是全量列表
    await waitFor(() => expect(document.querySelector('.ant-select-selection-item')?.getAttribute('title'))
      .toBe('已失败'))
  })

  it('超时告警的 pending_pay 同样被读取（后端超时口径）', async () => {
    renderAt('/orders?status=pending_pay&ref=o1')
    await waitFor(() => expect(listMock).toHaveBeenCalled())
    expect(listMock.mock.calls[0][0]).toMatchObject({ status: 'pending_pay' })
  })

  it('脏 status 值降级为不筛选，不进入请求参数', async () => {
    renderAt('/orders?status=%3Cscript%3E')
    await waitFor(() => expect(listMock).toHaveBeenCalled())
    expect(listMock.mock.calls[0][0].status).toBeUndefined()
  })

  it('无 ?status= 时保持原行为：不带筛选', async () => {
    renderAt('/orders')
    await waitFor(() => expect(listMock).toHaveBeenCalled())
    expect(listMock.mock.calls[0][0].status).toBeUndefined()
  })
})
