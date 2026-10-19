/**
 * 通知中心：勾选批量删除 + 「查看详情」站内跳转（T02568 / 评审 2.9-5、2.9-4 / PRD FR-C-3）
 *
 * 两条回归：
 * 1. 「查看详情」原先是 `<a href={link} target="_blank">`，link 存的是站内路径（/orders?ref=x），
 *    绕过 SPA basename（/xianyu）后新标签页直接 404，而且跳完仍未读，回到列表还得再点一次。
 *    现在走 navigate(link) 并顺带标记已读。
 * 2. 批量删除走 POST /api/notifications/batch-delete，只删勾中的那几条。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import type { NotificationItem } from '../../../api/notifications'

const { listMock, countsMock, markReadMock, markAllReadMock, deleteMock, deleteBatchMock, clearMock } =
  vi.hoisted(() => ({
    listMock: vi.fn(),
    countsMock: vi.fn(),
    markReadMock: vi.fn(),
    markAllReadMock: vi.fn(),
    deleteMock: vi.fn(),
    deleteBatchMock: vi.fn(),
    clearMock: vi.fn(),
  }))

const { invalidateMock } = vi.hoisted(() => ({ invalidateMock: vi.fn() }))

vi.mock('../../../api', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  const notificationApi = (actual as { notificationApi: Record<string, unknown> }).notificationApi
  return {
    ...actual,
    notificationApi: {
      ...notificationApi,
      list: listMock,
      counts: countsMock,
      markRead: markReadMock,
      markAllRead: markAllReadMock,
      delete: deleteMock,
      deleteBatch: deleteBatchMock,
      clear: clearMock,
    },
  }
})

vi.mock('../../../hooks/useNotificationModel', () => ({
  invalidateNotificationCounts: invalidateMock,
}))

import Notifications from '../index'

function notif(id: number, overrides: Partial<NotificationItem> = {}): NotificationItem {
  return {
    id,
    level: 'warn',
    category: 'order',
    title: `订单超时 ${id}`,
    message: '有订单待支付超过 5 分钟',
    link: `/orders?ref=o${id}`,
    dedup_key: `ux568-${id}`,
    read_at: null,
    created_at: '2026-10-19T00:00:00',
    ...overrides,
  }
}

function seed(items: NotificationItem[]) {
  listMock.mockResolvedValue({
    items, count: items.length, total: items.length, limit: 100, offset: 0, status: 'all',
  })
  countsMock.mockResolvedValue({
    unread: items.filter((i) => !i.read_at).length,
    read: items.filter((i) => i.read_at).length,
    total: items.length,
  })
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/notifications']}>
      <Routes>
        <Route path="/notifications" element={<Notifications />} />
        <Route path="/orders" element={<div>ORDERS_PAGE_SENTINEL</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  seed([notif(101), notif(102), notif(103, { read_at: '2026-10-19T01:00:00' })])
  markReadMock.mockResolvedValue({ ok: true, id: 101, newly_read: true })
  markAllReadMock.mockResolvedValue({ ok: true, updated: 0 })
  deleteMock.mockResolvedValue({ ok: true, id: 101, deleted: true })
  clearMock.mockResolvedValue({ ok: true, deleted: 0, status: 'read' })
  deleteBatchMock.mockResolvedValue({ ok: true, deleted: 2, requested: 2 })
})

describe('通知中心勾选批量删除', () => {
  it('未勾选时不出现批量删除按钮', async () => {
    renderPage()
    await screen.findByText('订单超时 101')
    expect(screen.queryByText(/删除选中/)).toBeNull()
  })

  it('勾选两条 → 确认 → 只删这两条，并按后端 deleted 提示', async () => {
    renderPage()
    await screen.findByText('订单超时 101')

    await userEvent.click(screen.getByLabelText('选择通知 101'))
    await userEvent.click(screen.getByLabelText('选择通知 102'))
    expect(screen.getByText(/删除选中 2/)).toBeInTheDocument()

    fireEvent.click(screen.getByText(/删除选中 2/))
    const pop = await waitFor(() => {
      const el = document.querySelector('.ant-popover:not(.ant-popover-hidden) .ant-btn-dangerous')
      if (!el) throw new Error('popconfirm 未打开')
      return el as HTMLElement
    })
    deleteBatchMock.mockResolvedValue({ ok: true, deleted: 2, requested: 2 })
    fireEvent.click(pop)

    await waitFor(() => expect(deleteBatchMock).toHaveBeenCalledWith([101, 102]))
    await screen.findByText('已删除 2 条通知')
    // 删除后重取列表与计数（不在前端猜未读/已读各减多少）
    expect(listMock.mock.calls.length).toBeGreaterThanOrEqual(2)
    expect(countsMock.mock.calls.length).toBeGreaterThanOrEqual(2)
  })

  it('后端 deleted 小于 requested 时如实说明有几条已不存在', async () => {
    renderPage()
    await screen.findByText('订单超时 101')
    await userEvent.click(screen.getByLabelText('选择通知 101'))
    await userEvent.click(screen.getByLabelText('选择通知 102'))
    fireEvent.click(screen.getByText(/删除选中 2/))
    const pop = await waitFor(() => {
      const el = document.querySelector('.ant-popover:not(.ant-popover-hidden) .ant-btn-dangerous')
      if (!el) throw new Error('popconfirm 未打开')
      return el as HTMLElement
    })
    deleteBatchMock.mockResolvedValue({ ok: true, deleted: 1, requested: 2 })
    fireEvent.click(pop)

    await screen.findByText('已删除 1 条，1 条已不存在')
  })

  it('全选勾中当前列表全部条目', async () => {
    renderPage()
    await screen.findByText('订单超时 101')
    await userEvent.click(screen.getByRole('checkbox', { name: '全选' }))
    expect(deleteBatchMock).not.toHaveBeenCalled()
    expect(screen.getByText(/删除选中 3/)).toBeInTheDocument()
  })
})

describe('通知「查看详情」跳转', () => {
  it('站内链接走 SPA 路由（不再新标签页 404），并顺带标记已读', async () => {
    renderPage()
    await screen.findByText('订单超时 101')

    fireEvent.click(screen.getAllByText('查看详情 →')[0])

    expect(await screen.findByText('ORDERS_PAGE_SENTINEL')).toBeInTheDocument()
    await waitFor(() => expect(markReadMock).toHaveBeenCalledWith(101))
  })

  it('不再渲染 target=_blank 的外链锚点', async () => {
    renderPage()
    await screen.findByText('订单超时 101')
    expect(document.querySelector('a[target="_blank"]')).toBeNull()
  })
})
