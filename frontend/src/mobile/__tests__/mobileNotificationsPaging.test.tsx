// frontend/src/mobile/__tests__/mobileNotificationsPaging.test.tsx
// T02973（T02621 派生）：移动端通知页原先是「一次拉满就完」的单发请求，拉到的条数即全部，
// 超出部分在移动端根本翻不到；而且没有任何翻页控件。
// 本单改成桌面同口径（20 条/页 + 后端 total），移动端用「加载更多」追加而不是页码。
// 另一条容易丢的语义：单条操作后的重取必须保持「已加载窗口」，
// 否则用户翻到最后一页点一下「标记已读」就被甩回第 1 页。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { readFileSync } from 'node:fs'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp } from 'antd'

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  markRead: vi.fn(),
  markAllRead: vi.fn(),
  delete: vi.fn(),
}))

vi.mock('../../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api')>()
  return {
    ...actual,
    notificationApi: {
      ...actual.notificationApi,
      list: mocks.list,
      markRead: mocks.markRead,
      markAllRead: mocks.markAllRead,
      delete: mocks.delete,
    },
  }
})

import MobileNotifications, { MAX_WINDOW, PAGE_SIZE, reloadWindowLimit } from '../pages/Notifications'

// 26 条：正好越过一页（20），第二页 6 条，既能量出「追加」也压得起 jsdom 的渲染成本
const ALL = Array.from({ length: 26 }, (_, i) => ({
  id: i + 1,
  level: 'info' as const,
  category: 'order' as const,
  title: `通知 ${i + 1}`,
  message: `正文 ${i + 1}`,
  dedup_key: `k${i + 1}`,
  // 奇偶交替：未读 13 / 已读 13，换筛选时两个池子都够测
  read_at: i % 2 === 0 ? null : '2026-10-24T00:00:00',
  created_at: '2026-10-24T00:00:00',
}))

// 后端契约：按 status/limit/offset 切片，并回全量 total
const serve = (params?: { status?: string; limit?: number; offset?: number }) => {
  const limit = params?.limit ?? 20
  const offset = params?.offset ?? 0
  const pool =
    params?.status === 'read'
      ? ALL.filter((x) => x.read_at !== null)
      : params?.status === 'unread'
        ? ALL.filter((x) => x.read_at === null)
        : ALL
  return {
    items: pool.slice(offset, offset + limit),
    count: Math.max(0, Math.min(limit, pool.length - offset)),
    total: pool.length,
    limit,
    offset,
    status: params?.status ?? 'all',
  }
}

const lastCall = () => mocks.list.mock.calls[mocks.list.mock.calls.length - 1][0]

// 等「已加载 N / 共 M 条」落到 DOM：比等某条标题更能说明一次追加真的结束了。
// loading 中的按钮可访问名是「loading加载更多」，所以中途再点会被按钮自己的守卫吃掉，
// 用例一律等落定再点下一次。
const SETTLE = { timeout: 8_000, interval: 50 }
const seeLoaded = (loaded: number, total: number) =>
  waitFor(() => expect(screen.getByText(`已加载 ${loaded} / 共 ${total} 条`)).toBeTruthy(), SETTLE)

const moreButton = () => screen.getByRole('button', { name: /加载更多/ })

const wrap = () => render(<AntApp><MobileNotifications /></AntApp>)

beforeEach(() => {
  mocks.list.mockReset().mockImplementation(serve)
  mocks.markRead.mockReset().mockResolvedValue({ ok: true, id: 1, newly_read: true })
  mocks.markAllRead.mockReset().mockResolvedValue({ ok: true, updated: 13 })
  mocks.delete.mockReset().mockResolvedValue({ ok: true, id: 1, deleted: true })
})

describe('移动端通知分页（T02973 / 加载更多）', () => {
  it('首屏按 20 条/页取数，并把后端 total 说清楚', async () => {
    wrap()
    await seeLoaded(20, 26)
    expect(lastCall()).toEqual({ status: undefined, limit: 20, offset: 0 })
    expect(moreButton()).toBeTruthy()
    expect(screen.queryByText('没有更多了')).toBeNull()
  }, 20_000)

  it('点「加载更多」按已加载条数续取，追加而非替换', async () => {
    wrap()
    await seeLoaded(20, 26)
    await userEvent.click(moreButton())

    await seeLoaded(26, 26)
    expect(lastCall()).toEqual({ status: undefined, limit: 20, offset: 20 })
    // 第一页的行还在：追加不是重排
    expect(screen.getByText('通知 1')).toBeTruthy()
    expect(mocks.list).toHaveBeenCalledTimes(2)
  }, 20_000)

  it('取完后不再发请求，按钮换成「没有更多了」', async () => {
    wrap()
    await seeLoaded(20, 26)
    await userEvent.click(moreButton())
    await seeLoaded(26, 26)

    expect(screen.queryByRole('button', { name: /加载更多/ })).toBeNull()
    expect(screen.getByText('没有更多了')).toBeTruthy()
    // 「共 N 条」与已加载条数相等时不该再留一个点了没反应的按钮
    await waitFor(() => expect(mocks.list).toHaveBeenCalledTimes(2), SETTLE)
  }, 20_000)

  it('切换状态筛选回到第 1 页，且不带着已加载的旧窗口', async () => {
    wrap()
    await seeLoaded(20, 26)
    await userEvent.click(moreButton())
    await seeLoaded(26, 26)

    // 点 placeholder 的 SPAN 会撞上 rc-select 的 pointer-events:none，直接操作 combobox
    await userEvent.click(screen.getByRole('combobox'))
    await userEvent.click(screen.getByText('已读'))

    await waitFor(() => expect(mocks.list.mock.calls.length).toBe(3), SETTLE)
    expect(lastCall()).toEqual({ status: 'read', limit: 20, offset: 0 })
    // 已读池只有 13 条：上一页的 26 条不能被算成「已加载」
    await seeLoaded(13, 13)
    expect(screen.queryByText('通知 3')).toBeNull()
  }, 20_000)

  it('单条操作后重取保持已加载窗口（limit 跟着已加载条数走）', async () => {
    wrap()
    await seeLoaded(20, 26)
    await userEvent.click(moreButton())
    await seeLoaded(26, 26)

    await userEvent.click(screen.getAllByRole('button', { name: '标记已读' })[0])
    await waitFor(() => expect(mocks.markRead).toHaveBeenCalled(), SETTLE)

    // 26 而不是 20：重取如果退回首屏一页，用户就被甩回第 1 页
    await waitFor(() => expect(lastCall()).toEqual({ status: undefined, limit: 26, offset: 0 }), SETTLE)
  }, 20_000)

  it('重取窗口上限：翻过 10 页后按 200 收口（后端 limit 校验 le=200）', () => {
    // 这一条走纯函数：真在 jsdom 里渲染 200 张 Card 再点 9 次「加载更多」，
    // 单次渲染就吃掉整轮 timeout 预算，验的是同一件事实却贵一个数量级。
    expect(PAGE_SIZE).toBe(20)
    expect(reloadWindowLimit(0)).toBe(PAGE_SIZE)
    expect(reloadWindowLimit(20)).toBe(20)
    expect(reloadWindowLimit(120)).toBe(120)
    expect(reloadWindowLimit(260)).toBe(MAX_WINDOW)
    expect(MAX_WINDOW).toBe(200)
  }, 20_000)
})

describe('移动端通知页的源码口径（防退回）', () => {
  const src = readFileSync('src/mobile/pages/Notifications/index.tsx', 'utf8')

  it('不再一次性拉满、也不再写死 50 条', () => {
    expect(src).not.toContain('LIST_LIMIT')
    expect(src).toContain('export const PAGE_SIZE = 20')
  })

  it('列表请求带 offset，页大小与桌面同口径', () => {
    expect(src).toMatch(/notificationApi\.list\(\{ status: filterStatus, limit, offset \}\)/)
    expect(src).toContain('load(items.length, PAGE_SIZE)')
  })

  it('「加载更多」与「没有更多了」两种终态都在，不靠静默停止', () => {
    expect(src).toContain('加载更多')
    expect(src).toContain('没有更多了')
    expect(src).toContain('已加载 {items.length} / 共 {total} 条')
  })

  it('重取走窗口函数，不在调用点重算 min/max', () => {
    expect(src).toContain('load(0, reloadWindowLimit(items.length))')
  })
})
