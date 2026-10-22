/**
 * 评估明细页品牌候选（T02662 / 评审 2.4-8）
 *
 * 原先品牌下拉只从「当前页 items」提取：翻页候选变，选中品牌后候选收缩到只剩
 * 该品牌，换品牌必须先清空。现在优先用后端全量 DISTINCT；请求失败静默回落当页，
 * 保证旧后端下行为不劣于修复前（与商品页 T02566 同口径）。
 */
import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

const { listMock, distMock, taskListMock, brandFacetsMock } = vi.hoisted(() => ({
  listMock: vi.fn(),
  distMock: vi.fn(),
  taskListMock: vi.fn(),
  brandFacetsMock: vi.fn(),
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
      brandFacets: brandFacetsMock,
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

// 当页只有罗技；全量候选另有雷蛇、双飞燕
const pageItems = [1, 2].map((i) => ({
  id: i, task_id: 't1', item_id: `i${i}`, created_at: '2026-10-01T00:00:00',
  payload: { score: 80, item_title: `罗技商品${i}`, brand: '罗技' },
}))

beforeAll(() => {
  Element.prototype.scrollIntoView = () => {}
})

beforeEach(() => {
  localStorage.clear()
  listMock.mockReset().mockResolvedValue({ items: pageItems, count: 2, total: 2 })
  distMock.mockReset().mockResolvedValue(DIST)
  taskListMock.mockReset().mockResolvedValue({ items: [], count: 0, total: 0 })
  brandFacetsMock.mockReset()
})

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/evaluations']}>
      <Evaluations />
    </MemoryRouter>,
  )
}

async function openBrandSelect() {
  // 品牌 Select 的 value 是空串（不是 undefined），antd 不渲染 placeholder；
  // 按筛选栏顺序取第二个 combobox：任务 → 品牌 → 状态
  await waitFor(() => expect(screen.getAllByRole('combobox').length).toBeGreaterThanOrEqual(2))
  const combobox = screen.getAllByRole('combobox')[1]
  await userEvent.click(combobox)
  await waitFor(() => expect(document.querySelector('.ant-select-dropdown')).toBeTruthy())
  return document.querySelector('.ant-select-dropdown') as HTMLElement
}

describe('评估明细品牌候选（T02662）', () => {
  it('下拉使用全量 DISTINCT，当页之外、被价格/状态过滤掉的品牌也能选', async () => {
    brandFacetsMock.mockResolvedValue(['双飞燕', '罗技', '雷蛇'])
    renderPage()

    const dropdown = await openBrandSelect()
    await waitFor(() => expect(dropdown.textContent).toContain('双飞燕'))
    expect(dropdown.textContent).toContain('雷蛇')
    expect(dropdown.textContent).toContain('罗技')

    // 选中品牌后列表会被过滤，但候选集不跟着收缩（这里直接断言请求入参不含品牌）
    expect(brandFacetsMock).toHaveBeenCalledWith(undefined)
  })

  it('全量接口失败时静默回落当页提取，下拉仍可用', async () => {
    brandFacetsMock.mockRejectedValue(new Error('503 Service Unavailable'))
    renderPage()

    const dropdown = await openBrandSelect()
    await waitFor(() => expect(dropdown.textContent).toContain('罗技'))
    expect(dropdown.textContent).not.toContain('双飞燕')
  })
})
