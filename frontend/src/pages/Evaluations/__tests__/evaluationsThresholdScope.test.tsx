// frontend/src/pages/Evaluations/__tests__/evaluationsThresholdScope.test.tsx
// 评审 2.4-7：计算器三项（通过率/通过数/总数）都按当前页 items 算，
// 但「总数」用的是全量口吻的短标签，用户会当成整个任务的数据。
// 修法：三项统一标「本页」，另用分页接口 total 说明筛选后全量有多少条。
import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
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

function mockList(total: number) {
  listMock.mockResolvedValue({ items: pageItems, count: pageItems.length, total })
}

beforeAll(() => {
  Element.prototype.scrollIntoView = () => {}
})

beforeEach(() => {
  localStorage.clear()
  listMock.mockReset()
  distMock.mockReset()
  taskListMock.mockReset()
  distMock.mockResolvedValue(DIST)
  taskListMock.mockResolvedValue({ items: [], count: 0, total: 0 })
})

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/evaluations']}>
      <Evaluations />
    </MemoryRouter>,
  )
}

describe('阈值通过率计算器的统计口径（评审 2.4-7）', () => {
  it('三项都标「本页」，并通过总数说明筛选后还有多少条', async () => {
    mockList(57)
    renderPage()
    await waitFor(() => expect(screen.getByText('本页通过率')).toBeInTheDocument())
    expect(screen.getByText('本页通过数')).toBeInTheDocument()
    expect(screen.getByText('本页总数')).toBeInTheDocument()
    // 短标签「总数」会让人读成全量，必须不再以独立 Statistic 标题出现
    expect(screen.queryByText('总数')).not.toBeInTheDocument()
    expect(screen.getByText('当前筛选共 57 条，以上只统计本页 3 条，翻页后数值会变')).toBeInTheDocument()
  })

  it('筛选后恰好只有一页时，说明改为「按当前 N 条评估统计」，不虚构翻页', async () => {
    mockList(pageItems.length)
    renderPage()
    await waitFor(() => expect(screen.getByText('本页总数')).toBeInTheDocument())
    expect(screen.getByText('以上按当前 3 条评估统计')).toBeInTheDocument()
    expect(screen.queryByText(/翻页后数值会变/)).not.toBeInTheDocument()
  })

  it('通过数/通过率仍按本页样本计算（阈值 60：3 条里 2 条通过）', async () => {
    mockList(57)
    renderPage()
    await waitFor(() => expect(screen.getByText('本页通过率')).toBeInTheDocument())
    const statText = (title: string) =>
      screen.getByText(title).closest('.ant-statistic')?.textContent ?? ''
    // 72、65 通过；40 不通过；本页通过率 66.7%
    expect(statText('本页通过率')).toContain('66.7')
    expect(statText('本页通过数')).toContain('2')
    expect(statText('本页总数')).toContain('3')
  })
})
