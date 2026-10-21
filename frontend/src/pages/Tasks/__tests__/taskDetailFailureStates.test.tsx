// frontend/src/pages/Tasks/__tests__/taskDetailFailureStates.test.tsx
// T02700：任务详情页 9 路数据原先统一 catch 成 null/[]，
// 后端故障时整页显示「任务不存在」，各 tab 显示「暂无××」，tab 标签上的数字变成 0。
// 钉住：每一路失败都要有自己的错误态与重试，数量未知要写「未知」而不是 0，
// 且空态与错误态互斥。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const { apiMocks } = vi.hoisted(() => ({
  apiMocks: {
    taskGet: vi.fn(),
    runs: vi.fn(),
    deps: vi.fn(),
    dependents: vi.fn(),
    evalList: vi.fn(),
    trend: vi.fn(),
    linkList: vi.fn(),
    taskList: vi.fn(),
  },
}))

vi.mock('../../../api', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  const a = actual as Record<string, Record<string, unknown>>
  return {
    ...actual,
    taskApi: { ...a.taskApi, get: apiMocks.taskGet, list: apiMocks.taskList },
    taskDetailApi: { ...a.taskDetailApi, runs: apiMocks.runs, deps: apiMocks.deps, dependents: apiMocks.dependents },
    evalApi: { ...a.evalApi, list: apiMocks.evalList },
    statsApi: { ...a.statsApi, trend: apiMocks.trend },
    taskLinkApi: { ...a.taskLinkApi, list: apiMocks.linkList },
  }
})

vi.mock('../../../components/charts/EChart', () => ({ default: () => null }))

import TaskDetail from '../TaskDetail'

const ERR = new Error('500')
const TASK = {
  id: 't1', name: '测试任务', keyword: 'iPhone', mode: 'keyword', status: 'stopped',
  cron: '*/10 * * * *', created_at: '2026-10-01T00:00:00', updated_at: '2026-10-02T00:00:00',
}
const RUNS = { runs: [{ start: '2026-10-02T00:00:00', end: '2026-10-02T00:05:00', duration_s: 300, event_count: 10, hit_count: 2, err_count: 0, warn_count: 0 }], idle_gaps: [] }
const EVALS = { items: [{ id: 1, task_id: 't1', item_id: 'i1', created_at: '2026-10-02T00:01:00', payload: { item_title: '二手 iPhone 13' } }] }

function setAllOk() {
  apiMocks.taskGet.mockResolvedValue(TASK)
  apiMocks.runs.mockResolvedValue(RUNS)
  apiMocks.deps.mockResolvedValue([])
  apiMocks.dependents.mockResolvedValue([])
  apiMocks.evalList.mockResolvedValue(EVALS)
  apiMocks.trend.mockResolvedValue({ metric: 'eval_score', series: [] })
  apiMocks.linkList.mockResolvedValue({ items: [], total_for_type: 0 })
  apiMocks.taskList.mockResolvedValue({ items: [] })
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/tasks/t1']}>
      <Routes>
        <Route path="/tasks/:id" element={<TaskDetail />} />
      </Routes>
    </MemoryRouter>,
  )
}

async function openTab(name: RegExp) {
  await waitFor(() => expect(screen.getByRole('tab', { name })).toBeInTheDocument())
  fireEvent.click(screen.getByRole('tab', { name }))
}

beforeEach(() => {
  Object.values(apiMocks).forEach((m) => m.mockReset())
  setAllOk()
})

describe('任务详情页失败态（T02700）', () => {
  it('全部成功时没有任何错误态，数量按真实条数显示', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('任务详情：测试任务')).toBeInTheDocument())
    expect(screen.queryByText(/加载失败/)).not.toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /运行历史 \(1\)/ })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /评估记录 \(1\)/ })).toBeInTheDocument()
  })

  it('任务配置失败：给错误态 + 重试，不能说「任务不存在」', async () => {
    apiMocks.taskGet.mockRejectedValue(ERR)
    renderPage()
    await waitFor(() => expect(screen.getByText('任务配置加载失败')).toBeInTheDocument())
    expect(screen.queryByText('任务不存在')).not.toBeInTheDocument()
  })

  it('两路趋势都失败：趋势卡片各自行使错误态，而不是「暂无数据」', async () => {
    apiMocks.trend.mockRejectedValue(ERR)
    renderPage()
    await waitFor(() => expect(screen.getByText('任务详情：测试任务')).toBeInTheDocument())
    expect(await screen.findByText('评估分趋势加载失败')).toBeInTheDocument()
    expect(screen.getByText('事件密度趋势加载失败')).toBeInTheDocument()
  })

  it('运行历史失败：标签写「数量未知」而不是 0，区块错误态与空态互斥', async () => {
    apiMocks.runs.mockRejectedValue(ERR)
    renderPage()
    await openTab(/运行历史 \(数量未知\)/)
    await waitFor(() => expect(screen.getByText('运行历史加载失败')).toBeInTheDocument())
    expect(screen.queryByText('暂无运行记录')).not.toBeInTheDocument()
  })

  it('评估记录失败：同上，标签与区块都显式声明取不到', async () => {
    apiMocks.evalList.mockRejectedValue(ERR)
    renderPage()
    await openTab(/评估记录 \(数量未知\)/)
    await waitFor(() => expect(screen.getByText('评估记录加载失败')).toBeInTheDocument())
    expect(screen.queryByText('暂无评估记录')).not.toBeInTheDocument()
  })

  it('上游/下游分开记账：只有上游失败时下游仍给真实数量', async () => {
    apiMocks.deps.mockRejectedValue(ERR)
    apiMocks.dependents.mockResolvedValue([{ task_id: 't2', task_name: '下游', depends_on: 't1' }])
    renderPage()
    await openTab(/依赖关系 \(上游未知\/下游1\)/)
    await waitFor(() => expect(screen.getByText('上游依赖加载失败')).toBeInTheDocument())
    expect(screen.queryByText('无上游依赖')).not.toBeInTheDocument()
    // 下游取到了 → 该区块保持真实状态，不被上游失败带偏
    expect(screen.queryByText('下游依赖加载失败')).not.toBeInTheDocument()
  })

  it('关联内容失败：标签「数量未知」+ 区块错误态，分页不冒充 0 条', async () => {
    apiMocks.linkList.mockRejectedValue(ERR)
    renderPage()
    await openTab(/闲鱼内容关联 \(数量未知\)/)
    await waitFor(() => expect(screen.getByText('闲鱼内容关联加载失败')).toBeInTheDocument())
    expect(screen.queryByText('暂无关联内容')).not.toBeInTheDocument()
  })

  it('刷新失败时保留上一次数据但标签转为未知，不给「一切正常」的假象', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByRole('tab', { name: /运行历史 \(1\)/ })).toBeInTheDocument())
    apiMocks.runs.mockRejectedValue(ERR)
    fireEvent.click(screen.getByText('刷新'))
    await waitFor(() => expect(screen.getByRole('tab', { name: /运行历史 \(数量未知\)/ })).toBeInTheDocument())
    // 数据留着，但标签与区块都声明了这次没取到
    expect(screen.getByRole('tab', { name: /评估记录 \(1\)/ })).toBeInTheDocument()
  })
})
