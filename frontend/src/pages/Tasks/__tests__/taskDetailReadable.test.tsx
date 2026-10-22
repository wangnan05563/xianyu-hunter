// frontend/src/pages/Tasks/__tests__/taskDetailReadable.test.tsx
// T02650：详情页把内部枚举原值与 JSON 字符串直接甩给用户。
// 钉住：状态/模式走常量表中文文案；未知枚举显式标「未知（原始码 xxx）」；
// 排除词/搜索过滤按标签展示，不再出现 ["a","b"] 这层原始 JSON。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import JsonListField from '../../../components/JsonListField'
import { taskModeLabel, taskStatusLabel } from '../../../constants/taskStatus'

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

const TASK = {
  id: 't1', name: '测试任务', keyword: 'iPhone', mode: 'confirm', status: 'running',
  cron: '*/10 * * * *', created_at: '2026-10-01T00:00:00', updated_at: '2026-10-02T00:00:00',
  exclude_words: '["抽奖","拼单"]', search_filters: '["personal_idle"]',
}

function setAllOk(task: Record<string, unknown> = TASK) {
  apiMocks.taskGet.mockResolvedValue(task)
  apiMocks.runs.mockResolvedValue({ runs: [], idle_gaps: [] })
  apiMocks.deps.mockResolvedValue([])
  apiMocks.dependents.mockResolvedValue([])
  apiMocks.evalList.mockResolvedValue({ items: [] })
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

beforeEach(() => {
  Object.values(apiMocks).forEach((m) => m.mockReset())
  setAllOk()
})

describe('JsonListField：任务里的 JSON 字符串字段', () => {
  it('字符串数组按标签展示，不露出原始 JSON', () => {
    const { container } = render(<JsonListField raw='["抽奖","拼单"]' />)
    expect(screen.getByText('抽奖')).toBeInTheDocument()
    expect(screen.getByText('拼单')).toBeInTheDocument()
    expect(container.textContent).not.toContain('["')
  })

  it('空数组与空串都显示空态文案', () => {
    const { rerender } = render(<JsonListField raw="[]" />)
    expect(screen.getByText('无')).toBeInTheDocument()
    rerender(<JsonListField raw="" emptyText="不限" />)
    expect(screen.getByText('不限')).toBeInTheDocument()
  })

  it('非 JSON 字符串原样显示，不吞成「无」', () => {
    render(<JsonListField raw="抽奖,拼单" />)
    expect(screen.getByText('抽奖,拼单')).toBeInTheDocument()
  })

  it('对象 JSON 格式化展示并带复制入口', () => {
    const { container } = render(<JsonListField raw='{"min_score":60}' />)
    expect(container.textContent).toContain('"min_score": 60')
    expect(container.querySelector('.ant-typography-copy')).toBeTruthy()
  })
})

describe('任务详情页可读性（T02650）', () => {
  it('状态/模式显示中文，排除词与搜索过滤不再输出原始 JSON', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('任务详情：测试任务')).toBeInTheDocument())

    expect(screen.getByText('运行中')).toBeInTheDocument()
    expect(screen.getByText('需确认')).toBeInTheDocument()
    expect(screen.getByText('抽奖')).toBeInTheDocument()
    expect(screen.getByText('personal_idle')).toBeInTheDocument()

    expect(screen.queryByText('running')).not.toBeInTheDocument()
    expect(screen.queryByText('confirm')).not.toBeInTheDocument()
    expect(screen.queryByText(/\["抽奖"/)).not.toBeInTheDocument()
  })

  it('未知枚举显式标出未知并保留原始码，不显示空白也不伪装成已识别', async () => {
    setAllOk({ ...TASK, status: 'weird_status', mode: 'weird_mode' })
    renderPage()
    await waitFor(() => expect(screen.getByText('任务详情：测试任务')).toBeInTheDocument())

    expect(screen.getByText('未知（原始码 weird_status）')).toBeInTheDocument()
    expect(screen.getByText('未知（原始码 weird_mode）')).toBeInTheDocument()
  })
})

describe('状态/模式文案兜底（constants/taskStatus）', () => {
  it('已知值取中文，未知值带原始码，空值用占位符', () => {
    expect(taskStatusLabel('running')).toBe('运行中')
    expect(taskStatusLabel('weird')).toBe('未知（原始码 weird）')
    expect(taskStatusLabel(null)).toBe('—')
    expect(taskModeLabel('confirm')).toBe('需确认')
    expect(taskModeLabel('weird')).toBe('未知（原始码 weird）')
  })
})
