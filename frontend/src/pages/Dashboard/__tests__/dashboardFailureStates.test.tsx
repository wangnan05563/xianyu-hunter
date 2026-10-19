/**
 * 仪表盘假回执清零（T02586 / FR-H-2）
 *
 * 钉住的行为：接口失败必须被渲染成「加载失败 + 重试」，而不是渲染成「全 0 正常态」。
 * 回归点：原实现里 statsApi/priceApi/taskApi 的调用各自 .catch(() => null)，
 * 后端 500 时仪表盘看起来完全健康（0 单 / 无异常 / 暂无数据），用户无从分辨。
 */
import { describe, it, expect, vi, beforeAll, afterAll, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

class FakeEventSource {
  constructor(public url: string) {}
  addEventListener() {}
  close() {}
}

const { apiMocks } = vi.hoisted(() => ({
  apiMocks: {
    overview: vi.fn(),
    today: vi.fn(),
    businessKpi: vi.fn(),
    recentEvents: vi.fn(),
    trend: vi.fn(),
    evalFunnel: vi.fn(),
    histogram: vi.fn(),
    taskList: vi.fn(),
  },
}))

vi.mock('../../../api', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  const a = actual as { statsApi: Record<string, unknown>; priceApi: Record<string, unknown>; taskApi: Record<string, unknown> }
  return {
    ...actual,
    statsApi: {
      ...a.statsApi,
      overview: apiMocks.overview,
      today: apiMocks.today,
      businessKpi: apiMocks.businessKpi,
      recentEvents: apiMocks.recentEvents,
      trend: apiMocks.trend,
      evalFunnel: apiMocks.evalFunnel,
    },
    priceApi: { ...a.priceApi, histogram: apiMocks.histogram },
    taskApi: { ...a.taskApi, list: apiMocks.taskList },
  }
})

vi.mock('../../../components/charts/EChart', () => ({
  default: () => null,
}))

import Dashboard from '../index'

const ERR = new Error('500')

/** 默认全部失败，再用 overrides 把指定数据源指回成功 */
function setResponses(overrides: Partial<Record<keyof typeof apiMocks, unknown>> = {}) {
  const all: Record<keyof typeof apiMocks, unknown> = {
    overview: ERR, today: ERR, businessKpi: ERR, recentEvents: ERR,
    trend: ERR, evalFunnel: ERR, histogram: ERR, taskList: ERR,
  }
  Object.assign(all, overrides)
  for (const key of Object.keys(apiMocks) as Array<keyof typeof apiMocks>) {
    const v = all[key]
    if (v instanceof Error) apiMocks[key].mockRejectedValue(v)
    else apiMocks[key].mockResolvedValue(v)
  }
}

const OVERVIEW = {
  tasks: { running: 2, total: 5, paused: 1, stopped: 2 },
  orders: { pending: 3, succeeded: 7, failed: 1, total: 11 },
  events: { total: 11 },
  evaluation_count: 4,
  db_size: '1.2 MB',
  browser_dir: 'C:/tmp/profile',
  scheduler_running: true,
  ts: '2026-10-19T00:00:00',
}

beforeAll(() => {
  vi.stubGlobal('EventSource', FakeEventSource)
})

afterAll(() => {
  vi.unstubAllGlobals()
})

beforeEach(() => {
  localStorage.clear()
  Object.values(apiMocks).forEach((m) => m.mockReset())
})

describe('全部数据源失败', () => {
  it('顶部横幅点名失败数据源，统计卡与系统状态用 — 而不是 0', async () => {
    setResponses()
    render(<MemoryRouter><Dashboard /></MemoryRouter>)

    const banner = await screen.findByText(/个数据源加载失败/)
    expect(banner.textContent).toContain('统计卡')
    expect(banner.textContent).toContain('业务 KPI')
    expect(banner.textContent).toContain('评估漏斗')
    expect(banner.textContent).toContain('异常雷达')
    expect(banner.textContent).toContain('价格分布')

    // 回归点：失败时数字不能写成 0 —— 4 张统计卡应为 —
    await waitFor(() => expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(4))
    expect(screen.queryByText(/今日 0 单/)).not.toBeInTheDocument()
  })

  it('各区块给出自身的失败提示与重试入口，曲线声明加载失败', async () => {
    setResponses()
    render(<MemoryRouter><Dashboard /></MemoryRouter>)

    await screen.findByText('业务 KPI加载失败')
    expect(screen.getByText('评估漏斗加载失败')).toBeInTheDocument()
    expect(screen.getByText('事件流加载失败')).toBeInTheDocument()
    expect(screen.getByText('价格分布加载失败')).toBeInTheDocument()
    expect(screen.getByText('任务列表加载失败，筛选下拉的选项可能不完整')).toBeInTheDocument()
    expect(screen.getByText('预警接口失败，数字不代表今日真实状态')).toBeInTheDocument()

    // 4 张卡的 sparkline 各自失败：一条含糊的线不如明说失败
    expect(screen.getAllByText('趋势曲线加载失败')).toHaveLength(4)
    // 每个失败区块自带重试入口（antd 会在两字按钮中插空格，故用 \s? 匹配）
    expect(screen.getAllByText(/^重\s?试$/).length).toBeGreaterThanOrEqual(4)

    const callsBefore = apiMocks.businessKpi.mock.calls.length
    const retryAll = screen.getByText('全部重试').closest('button') as HTMLElement
    await userEvent.click(retryAll)
    await waitFor(() => expect(apiMocks.businessKpi.mock.calls.length).toBeGreaterThan(callsBefore))
  })
})

describe('部分数据源失败', () => {
  it('成功的区块照常出数，失败的区块单独表态', async () => {
    setResponses({
      overview: OVERVIEW,
      recentEvents: { events: [] },
      trend: { series: [], summary: null },
    })
    render(<MemoryRouter><Dashboard /></MemoryRouter>)

    // 失败区块仍在
    await screen.findByText('业务 KPI加载失败')
    // 成功区块出真实数字（回归点：原先会被失败连带成 0）
    expect((await screen.findAllByText('3')).length).toBeGreaterThan(0)
    expect(screen.getByText('待支付订单')).toBeInTheDocument()
    expect(screen.queryByText('事件流加载失败')).not.toBeInTheDocument()
    // 事件流空数组是真空态，不是失败态
    expect(screen.getByText('暂无事件')).toBeInTheDocument()
  })
})
