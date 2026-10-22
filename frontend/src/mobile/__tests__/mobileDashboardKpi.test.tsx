// frontend/src/mobile/__tests__/mobileDashboardKpi.test.tsx
// T02588 / FR-G-1：移动端 KPI 必须取真实字段，且请求失败时不能显示 0
// FR-G-2：接管倒计时组件的三种状态（剩余/已超时/未知）
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const mocks = vi.hoisted(() => ({
  overview: vi.fn(),
  today: vi.fn(),
}))

vi.mock('../../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api')>()
  return { ...actual, statsApi: { ...actual.statsApi, overview: mocks.overview, today: mocks.today } }
})

vi.mock('../../components/charts/EChart', () => ({ default: () => null }))

import MobileDashboard from '../pages/Dashboard'
import TakeoverCountdown from '../components/TakeoverCountdown'

const OVERVIEW = {
  // tasks.total = 9 是「任务数」：如果 KPI 还错绑到它，断言 231 就会失败
  tasks: { running: 2, total: 9, paused: 5, stopped: 2 },
  orders: { pending: 1, succeeded: 7, failed: 4, total: 12 },
  events: { total: 555 },
  evaluation_count: 100,
  metrics: { items_discovered: 231, eval_pass: 42, notify_failed: 3 },
  db_size: '1 MB',
  browser_dir: '—',
  scheduler_running: true,
  ts: '2026-10-19T00:00:00',
}

function renderDashboard() {
  return render(
    <MemoryRouter initialEntries={['/m/']}>
      <MobileDashboard />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mocks.overview.mockReset()
  mocks.today.mockReset()
  mocks.today.mockResolvedValue({
    alerts: { counts: { failed: 0, timeout: 0, low_eval: 0 } },
  } as never)
})

describe('移动端 KPI 口径（FR-G-1）', () => {
  it('四个卡片分别绑定真实字段，不再用任务数/评估总数/订单失败数冒充', async () => {
    mocks.overview.mockResolvedValue(OVERVIEW as never)
    renderDashboard()
    await waitFor(() => expect(screen.getByText('发现商品')).toBeInTheDocument())

    // 发现商品 = metrics.items_discovered(231)，不是 tasks.total(9)
    expect(screen.getByText('231')).toBeInTheDocument()
    expect(screen.queryByText('9')).not.toBeInTheDocument()
    // 评估通过 = metrics.eval_pass(42)，不是 evaluation_count(100)
    expect(screen.getByText('42')).toBeInTheDocument()
    expect(screen.queryByText('100')).not.toBeInTheDocument()
    // 通知失败 = metrics.notify_failed(3)，不是 orders.failed(4)
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('7')).toBeInTheDocument()   // 成功抢单
    expect(screen.queryByText('4')).not.toBeInTheDocument()
    // 标签与桌面统一：「成功抢单」而不是「抢单成功」
    expect(screen.getByText('成功抢单')).toBeInTheDocument()
    expect(screen.queryByText('抢单成功')).not.toBeInTheDocument()
    // 评估通过卡片补充总数上下文，读者不会把 42 当成评估总数
    expect(screen.getByText('共 100 条评估记录')).toBeInTheDocument()
  })

  it('后端未下发 metrics 时显示 — 而不是 0（不把缺数据说成正常）', async () => {
    const legacy = { ...OVERVIEW } as Record<string, unknown>
    delete legacy.metrics
    mocks.overview.mockResolvedValue(legacy as never)
    renderDashboard()
    await waitFor(() => expect(screen.getByText('发现商品')).toBeInTheDocument())
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(3)
    expect(screen.queryByText('231')).not.toBeInTheDocument()
  })

  it('两个数据源都失败时给出错误态，数字显示 — 而不是 0', async () => {
    mocks.overview.mockRejectedValue(new Error('boom'))
    mocks.today.mockRejectedValue(new Error('boom'))
    renderDashboard()
    await waitFor(() => expect(screen.getByText('发现商品（统计接口失败）')).toBeInTheDocument())
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(4)
    expect(screen.queryByText('0')).not.toBeInTheDocument()
    expect(screen.getByText('统计接口（/api/stats）加载失败')).toBeInTheDocument()
    // 今日告警：请求失败时不给「0 条告警」的正常态
    expect(screen.getByText('今日告警加载失败')).toBeInTheDocument()
  })
})

describe('接管倒计时（FR-G-2）', () => {
  // 单位词表交给 utils/timeFormat 的 formatDuration（T02901）：中文单位带空格、整分也念秒，
  // 倒计时经过整分那一秒才不会看着像停了
  it('有剩余秒数时按分秒显示', () => {
    render(<TakeoverCountdown remainingSec={125} deadline={null} />)
    expect(screen.getByText('剩 2 分 5 秒')).toBeInTheDocument()
  })

  it('整分那一秒仍然念秒', () => {
    render(<TakeoverCountdown remainingSec={600} deadline={null} />)
    expect(screen.getByText('剩 10 分 0 秒')).toBeInTheDocument()
  })

  it('剩余 0 显示已超时而不是剩 0 秒', () => {
    render(<TakeoverCountdown remainingSec={0} deadline={null} />)
    expect(screen.getByText('接管已超时')).toBeInTheDocument()
  })

  it('两个字段都缺省时如实说明未知，绝不显示 0', () => {
    render(<TakeoverCountdown />)
    expect(screen.getByText('接管截止未知')).toBeInTheDocument()
  })

  it('只有 deadline 时按 naive UTC 解析并给出剩余', () => {
    const future = new Date(Date.now() + 10 * 60 * 1000)
    const iso = `${future.toISOString().slice(0, 19)}`
    render(<TakeoverCountdown deadline={iso} />)
    expect(screen.getByText(/剩 \d+ 分 \d+ 秒/)).toBeInTheDocument()
  })
})
