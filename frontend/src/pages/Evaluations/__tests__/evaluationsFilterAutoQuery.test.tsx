// frontend/src/pages/Evaluations/__tests__/evaluationsFilterAutoQuery.test.tsx
// T02669 裁决（方向 2）：评估页筛选时机统一为「改完 300ms 自动查」。
// 两条边界必须一起守住：文本框不逐字发请求（中文输入法会被打断），
// 「查询」按钮仍是立即执行并取消尚未到点的自动查询（否则会查两次）。
import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const { listMock, distMock, taskListMock } = vi.hoisted(() => ({
  listMock: vi.fn(),
  distMock: vi.fn(),
  taskListMock: vi.fn(),
}))

vi.mock('../../../api', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  const evalApi = (actual as { evalApi: Record<string, unknown> }).evalApi
  const taskApi = (actual as { taskApi: Record<string, unknown> }).taskApi
  return {
    ...actual,
    evalApi: {
      ...evalApi,
      list: listMock,
      distribution: distMock,
      thresholdSuggestion: vi.fn(),
      sellerTrend: vi.fn().mockResolvedValue({ points: [] }),
    },
    taskApi: { ...taskApi, list: taskListMock },
  }
})

vi.mock('../../../components/charts/EChart', () => ({ default: () => null }))

import Evaluations from '../index'

const DIST = {
  buckets: [],
  marginals: { price: [], score: [], result: { pass: 0, auto: 0, fail: 0 } },
  distribution: [],
  suggested_threshold: { score: 70, pass_rate: 0.5 },
  total: 0,
  insufficient_count: 0,
  price_range: [0, 0] as [number, number],
  thresholds: { pass_score: 60, auto_buy_score: 80 },
}

const pageItems = [72, 65, 40].map((score, i) => ({
  id: i + 1, task_id: 't1', item_id: `i${i}`, created_at: '2026-10-01T00:00:00',
  payload: { score, item_title: `商品${i}` },
}))

beforeAll(() => {
  Element.prototype.scrollIntoView = () => {}
})

beforeEach(() => {
  localStorage.clear()
  listMock.mockReset().mockResolvedValue({ items: pageItems, count: pageItems.length, total: 9 })
  distMock.mockReset().mockResolvedValue(DIST)
  taskListMock.mockReset().mockResolvedValue({ items: [], count: 0, total: 0 })
})

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/evaluations']}>
      <Evaluations />
    </MemoryRouter>,
  )
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

// 首屏挂载本身会发不止一次请求（pageSize 走持久化，读数后会补一次 load），
// 先把这段噪声等过去再计数，否则「有没有自动查询」会被挂载噪声盖掉。
async function settleAfterMount() {
  await waitFor(() => expect(listMock).toHaveBeenCalled())
  await sleep(600)
}

// 这一页首屏渲染很重（十余个模块 + 表格），本机单条用例就要 4~6s，默认 5s 计时会误报超时
describe('筛选改完自动查询（2.4-9）', { timeout: 30000 }, () => {
  it('勾选「显示超范围」只补一次查询，且参数带上了新条件', async () => {
    renderPage()
    await settleAfterMount()
    const before = listMock.mock.calls.length
    fireEvent.click(screen.getByText('显示超范围'))
    // 具体等多少毫秒由 useDebouncedAction 单测（假计时器）定死，这里只验「一次改动 = 一次查询」
    await waitFor(
      () => expect(listMock.mock.calls.length).toBe(before + 1),
      { timeout: 3000 },
    )
    await sleep(600)
    expect(listMock.mock.calls.length).toBe(before + 1)
    const params = listMock.mock.calls[listMock.mock.calls.length - 1][0] as Record<string, unknown>
    expect(params.include_out_of_range).toBe(true)
  })

  it('商品ID 逐字输入不发请求，回车或移出输入框才查', async () => {
    renderPage()
    await settleAfterMount()
    const before = listMock.mock.calls.length
    const input = screen.getByPlaceholderText('模糊匹配')
    fireEvent.change(input, { target: { value: '苹果手' } })
    await sleep(500)
    expect(listMock.mock.calls.length).toBe(before)
    fireEvent.blur(input)
    await waitFor(
      () => expect(listMock.mock.calls.length).toBe(before + 1),
      { timeout: 2000 },
    )
  })

  it('「查询」按钮立即执行，并把尚未到点的自动查询取消掉（不查第二次）', async () => {
    renderPage()
    await settleAfterMount()
    const before = listMock.mock.calls.length
    fireEvent.click(screen.getByText('显示超范围'))
    fireEvent.click(screen.getByText('查询'))
    expect(listMock.mock.calls.length).toBe(before + 1)
    await sleep(600)
    expect(listMock.mock.calls.length).toBe(before + 1)
  })
})
