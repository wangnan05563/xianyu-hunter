// frontend/src/pages/Tasks/__tests__/taskEditorConfigFailure.test.tsx
// T02939（源自 T02899）：任务编辑器全局配置失败原先只有文案级证据。
// 钉住渲染级行为：配置 reject 时顶部错误条出现、点「直接创建」被提交守卫拦住，
// 重试成功后错误条消失；成功路径不得常驻错误条。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const { apiMocks } = vi.hoisted(() => ({
  apiMocks: {
    configGet: vi.fn(),
    taskCreate: vi.fn(),
    taskUpdate: vi.fn(),
  },
}))

vi.mock('../../../api', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  const a = actual as Record<string, Record<string, unknown>>
  return {
    ...actual,
    configApi: { ...a.configApi, get: apiMocks.configGet },
    taskApi: { ...a.taskApi, create: apiMocks.taskCreate, update: apiMocks.taskUpdate },
  }
})

import TaskEditor from '../TaskEditor'

const ERR = new Error('500')
const CFG = {
  search: { page_size: 50, sort_type: 'default', timeout: 30, regions: '', filter_tags: [] },
  eval: { pass_score: 60 },
  antidetect: { qps: 1, min_delay_ms: 200, max_delay_ms: 1500, fail_pause_threshold: 3, fail_window_sec: 3600 },
}

function renderNew() {
  return render(
    <MemoryRouter initialEntries={['/tasks/new?keyword=iPhone']}>
      <Routes>
        <Route path="/tasks/new" element={<TaskEditor />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  Object.values(apiMocks).forEach((m) => m.mockReset())
  apiMocks.configGet.mockResolvedValue(CFG)
  apiMocks.taskCreate.mockResolvedValue({ id: 't1' })
})

describe('任务编辑器全局配置失败态（T02939）', () => {
  it('配置取不到：向导顶部出现错误条与重试，说明参考值是内置默认值', async () => {
    apiMocks.configGet.mockRejectedValue(ERR)
    renderNew()

    await waitFor(() => {
      expect(screen.getByText('全局配置加载失败')).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: /重\s*试/ })).toBeInTheDocument()
    expect(screen.getByText(/内置默认值而不是你的真实配置/)).toBeInTheDocument()
  })

  it('配置未就绪时「直接创建」被提交守卫拦住，不发请求', async () => {
    apiMocks.configGet.mockRejectedValue(ERR)
    renderNew()
    await waitFor(() => expect(screen.getByText('全局配置加载失败')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /直接创建/ }))

    await waitFor(() => {
      expect(screen.getByText(/全局配置加载失败，风险探测拿不到全局值/)).toBeInTheDocument()
    })
    expect(apiMocks.taskCreate).not.toHaveBeenCalled()
  })

  it('点重试后重新取配置，成功后错误条消失', async () => {
    apiMocks.configGet.mockRejectedValueOnce(ERR)
    renderNew()
    await waitFor(() => expect(screen.getByText('全局配置加载失败')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /重\s*试/ }))

    await waitFor(() => {
      expect(screen.queryByText('全局配置加载失败')).not.toBeInTheDocument()
    })
    expect(apiMocks.configGet).toHaveBeenCalledTimes(2)
  })

  it('配置正常时不显示错误条（失败账不会常驻）', async () => {
    const { container } = renderNew()
    await waitFor(() => expect(apiMocks.configGet).toHaveBeenCalled())
    // 只看本页渲染结果：上一条用例的 message.warning 可能还挂在 body 上
    expect(within(container).queryByText(/全局配置加载失败/)).not.toBeInTheDocument()
  })
})
