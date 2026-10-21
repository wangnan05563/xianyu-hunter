/**
 * 评估明细页读取告警深链（T02620）
 *
 * 抽屉「低分评估」项现在跳 `/evaluations?item_id=<id>&score_max=<0-100>`；
 * 本页历史上完全不读 URL 参数，落地看不出是哪一条。此处用真实挂载断言
 * 「URL → 筛选 state → 请求参数 → 可见定位提示」这条链，以及脏参数降级。
 */
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
      sellerTrend: vi.fn().mockResolvedValue({ points: [] }),
      thresholdSuggestion: vi.fn().mockResolvedValue({ suggestions: [] }),
    },
    taskApi: { ...taskApi, list: taskListMock },
  }
})

// echarts 在 jsdom 下没有 canvas（getContext 返回 null），实例卸载时 zrender 会抛
// clearRect of null 把整页打挂；图表与本页要验证的「URL → 筛选」链无关，
// 按仓库既有做法（dashboardFailureStates.test.tsx）整体桩掉
vi.mock('../../../components/charts/EChart', () => ({
  default: () => null,
}))

import Evaluations from '../index'

// 完整 DistResponse 形状：ResultCategoryCards 会直接读 dist.marginals.result.auto/pass/fail
// 与 dist.price_range，缺字段会让整页在 jsdom 里抛 TypeError 渲染成空壳（曾经的失败原因）
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

beforeAll(() => {
  // jsdom 未实现 scrollIntoView，列表定位/锚点滚动会抛 TypeError
  Element.prototype.scrollIntoView = () => {}
})

beforeEach(() => {
  localStorage.clear()
  listMock.mockReset()
  listMock.mockResolvedValue({ items: [], count: 0, total: 0 })
  distMock.mockResolvedValue(DIST)
  taskListMock.mockResolvedValue({ items: [], count: 0, total: 0 })
})

function renderAt(entry: string) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Evaluations />
    </MemoryRouter>,
  )
}

describe('告警深链落到评估明细', () => {
  it('?item_id=&score_max= 会变成真实筛选条件并带上定位说明', async () => {
    renderAt('/evaluations?item_id=ITEM-9&score_max=42')
    await waitFor(() => expect(listMock).toHaveBeenCalled())
    // 深链触发的第二次请求才带筛选（首次是挂载默认加载）
    await waitFor(() => expect(listMock.mock.calls.some((c) => {
      const p = c[0] as Record<string, unknown>
      return p.item_id === 'ITEM-9' && p.max_score === 42
    })).toBe(true))
    expect(await screen.findByText(/已按告警定位到商品 ITEM-9/)).toBeTruthy()
    expect(screen.getByText(/评分 ≤ 42/)).toBeTruthy()
  })

  it('只有 item_id 时不硬塞分数条件', async () => {
    renderAt('/evaluations?item_id=ITEM-7')
    await waitFor(() => expect(listMock).toHaveBeenCalled())
    await waitFor(() => expect(listMock.mock.calls.some((c) => (c[0] as Record<string, unknown>).item_id === 'ITEM-7')).toBe(true))
    expect(listMock.mock.calls.at(-1)![0]).not.toHaveProperty('max_score')
  })

  it('脏参数（越界分数/注入式 id）降级为普通列表', async () => {
    renderAt('/evaluations?item_id=%22%3E%3Cscript%3E&score_max=999')
    await waitFor(() => expect(listMock).toHaveBeenCalled())
    const last = listMock.mock.calls.at(-1)![0] as Record<string, unknown>
    expect(last).not.toHaveProperty('item_id')
    expect(last).not.toHaveProperty('max_score')
    expect(screen.queryByText(/已按告警定位到商品/)).toBeNull()
  })

  it('「清除定位」把筛选复位并重新加载，不留住半截深链视图', async () => {
    renderAt('/evaluations?item_id=ITEM-5&score_max=30')
    await waitFor(() => expect(listMock.mock.calls.some((c) => (c[0] as Record<string, unknown>).item_id === 'ITEM-5')).toBe(true))
    const callsBefore = listMock.mock.calls.length
    fireEvent.click(screen.getByText('清除定位'))
    await waitFor(() => expect(listMock.mock.calls.length).toBeGreaterThan(callsBefore))
    const last = listMock.mock.calls.at(-1)![0] as Record<string, unknown>
    expect(last).not.toHaveProperty('item_id')
    expect(last).not.toHaveProperty('max_score')
    // 提示条随 URL 参数一起消失
    await waitFor(() => expect(screen.queryByText(/已按告警定位到商品/)).toBeNull())
  })

  it('无深链参数时不显示定位说明（保持原视图）', async () => {
    renderAt('/evaluations')
    await waitFor(() => expect(listMock).toHaveBeenCalled())
    expect(screen.queryByText(/已按告警定位到商品/)).toBeNull()
  })
})
