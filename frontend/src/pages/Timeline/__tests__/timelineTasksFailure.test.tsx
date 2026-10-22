// frontend/src/pages/Timeline/__tests__/timelineTasksFailure.test.tsx
// T02899：时间线页的「任务筛选」下拉原先 taskApi.list().catch(() => {})，
// 后端 500 时下拉只剩「全部任务」，与「这个账号下确实没有任务」是同一个画面。
// 钉住：失败要显示错误条（可重试），而不是静默留空；成功时不显示。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const { apiMocks } = vi.hoisted(() => ({
  apiMocks: {
    taskList: vi.fn(),
    timelineList: vi.fn(),
    configGet: vi.fn(),
  },
}))

vi.mock('../../../api', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  const a = actual as Record<string, Record<string, unknown>>
  return {
    ...actual,
    taskApi: { ...a.taskApi, list: apiMocks.taskList },
    timelineApi: { ...a.timelineApi, list: apiMocks.timelineList },
    configApi: { ...a.configApi, get: apiMocks.configGet },
  }
})

import TimelinePage from '../index'

const ERR = new Error('500')

beforeEach(() => {
  vi.clearAllMocks()
  apiMocks.timelineList.mockResolvedValue({ items: [], total: 0 })
  apiMocks.configGet.mockResolvedValue({})
})

function renderPage() {
  return render(
    <MemoryRouter>
      <TimelinePage />
    </MemoryRouter>,
  )
}

describe('时间线页任务列表的失败态（T02899）', () => {
  it('任务列表请求失败时给出错误条与重试入口，而不是静默的空下拉', async () => {
    apiMocks.taskList.mockRejectedValue(ERR)
    renderPage()

    await waitFor(() => {
      expect(screen.getByText(/任务列表加载失败/)).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: /重\s*试/ })).toBeInTheDocument()
    // 时间线本身取成功（0 条）—— 那是它自己的空态，不该被拿来冒充任务列表的状态
    expect(screen.getByText(/暂无匹配的时间线数据/)).toBeInTheDocument()
  })

  it('重试成功后错误条消失', async () => {
    apiMocks.taskList.mockRejectedValueOnce(ERR)
    renderPage()
    await waitFor(() => expect(screen.getByText(/任务列表加载失败/)).toBeInTheDocument())

    apiMocks.taskList.mockResolvedValueOnce({ items: [{ id: 't1', name: 'A', keyword: 'iPhone' }] })
    fireEvent.click(screen.getByRole('button', { name: /重\s*试/ }))

    await waitFor(() => expect(screen.queryByText(/任务列表加载失败/)).not.toBeInTheDocument())
    expect(apiMocks.taskList).toHaveBeenCalledTimes(2)
  })

  it('任务列表取成功时不显示错误条（失败账不会常驻）', async () => {
    apiMocks.taskList.mockResolvedValue({ items: [] })
    renderPage()

    await waitFor(() => expect(apiMocks.taskList).toHaveBeenCalled())
    await waitFor(() => expect(screen.queryByText(/任务列表加载失败/)).not.toBeInTheDocument())
  })
})
