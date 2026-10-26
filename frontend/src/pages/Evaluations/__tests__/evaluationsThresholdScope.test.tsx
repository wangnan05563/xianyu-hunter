// frontend/src/pages/Evaluations/__tests__/evaluationsThresholdScope.test.tsx
// 评审 2.4-7：计算器三项（通过率/通过数/总数）都按当前页 items 算，
// 但「总数」用的是全量口吻的短标签，用户会当成整个任务的数据。
// 修法：三项统一标「本页」，另用分页接口 total 说明筛选后全量有多少条。
import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const { listMock, distMock, taskListMock, suggestMock } = vi.hoisted(() => ({
  listMock: vi.fn(),
  distMock: vi.fn(),
  taskListMock: vi.fn(),
  suggestMock: vi.fn(),
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
      thresholdSuggestion: suggestMock,
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
  suggestMock.mockReset()
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

// T02667 裁决：保留后端全量口径（evalApi.thresholdSuggestion），删除按本页样本另算一套建议阈值的旧卡。
describe('建议阈值只有一份来源（评审 2.4-6）', () => {
  it('页面上只有一处「目标通过率 + 建议阈值」，不会出现第二个可能不同的结果', async () => {
    mockList(57)
    renderPage()
    await waitFor(() => expect(screen.getByText(/目标通过率：/)).toBeInTheDocument())
    expect(screen.getAllByText(/目标通过率：/)).toHaveLength(1)
    expect(screen.queryByText(/按本页样本估算/)).not.toBeInTheDocument()
    expect(screen.queryByText(/的评估可通过/)).not.toBeInTheDocument()
  })

  it('建议阈值来自后端全量接口，样本数标明是全部评估', async () => {
    suggestMock.mockResolvedValue({ suggested_threshold: 73, current_pass_rate: 0.62 })
    mockList(57)
    renderPage()
    await waitFor(() => expect(screen.getByText('计算建议阈值')).toBeInTheDocument())
    fireEvent.click(screen.getByText('计算建议阈值'))
    await waitFor(() => expect(screen.getByText('73')).toBeInTheDocument())
    expect(screen.getByText('样本数：0（全部评估）')).toBeInTheDocument()
  })
})
