// frontend/src/mobile/__tests__/mobileTaskEditorMode.test.tsx
// T02850：移动端任务编辑器把 mode 兜底写成 'keyword' —— 那不是后端 TaskMode 的成员，
// 而 api_tasks.py 对未知 mode 直接抛 400（`未知 mode: keyword`），等于「移动端新建任务必失败」。
// 这个用例是那条缺陷的行为证明：提交体里的 mode 必须是合法成员，且编辑时不许把原值覆盖掉。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp } from 'antd'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { TASK_MODE, TASK_MODE_VALUES } from '../../constants/taskStatus'

const mocks = vi.hoisted(() => ({ create: vi.fn(), update: vi.fn(), get: vi.fn() }))

vi.mock('../../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api')>()
  return {
    ...actual,
    taskApi: { ...actual.taskApi, create: mocks.create, update: mocks.update, get: mocks.get },
  }
})

import MobileTaskEditor from '../pages/TaskEditor'

const wrap = (entry: string) =>
  render(
    <AntApp>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/m/tasks/new/" element={<MobileTaskEditor />} />
          <Route path="/m/tasks/:id/edit/" element={<MobileTaskEditor />} />
        </Routes>
      </MemoryRouter>
    </AntApp>,
  )

beforeEach(() => {
  mocks.create.mockReset().mockResolvedValue({ id: 't1' })
  mocks.update.mockReset().mockResolvedValue({ id: 't1' })
  mocks.get.mockReset()
})

describe('移动端任务编辑器的 mode 提交（T02850）', () => {
  it('新建：用户没有 mode 控件，提交的兜底值必须是合法 TaskMode 成员', async () => {
    wrap('/m/tasks/new/')
    await userEvent.type(await screen.findByPlaceholderText('关键词（必填）'), '球鞋')
    await userEvent.click(screen.getByRole('button', { name: /保.*存/ }))
    await waitFor(() => expect(mocks.create).toHaveBeenCalled())
    const body = mocks.create.mock.calls[0][0]
    expect(TASK_MODE_VALUES).toContain(body.mode)
    // 兜底取「仅通知」，与后端 TaskCreate.mode 的默认值同口径：新建不会默认开始抢单
    expect(body.mode).toBe(TASK_MODE.NOTIFY)
  })

  it('编辑：保留任务原有 mode，不被兜底值覆盖', async () => {
    mocks.get.mockResolvedValue({
      id: 't7', keyword: '球鞋', name: '', mode: TASK_MODE.SEMI_AUTO,
      min_price: null, max_price: null, max_publish_days: null, region: null, exclude_words: '[]',
    })
    wrap('/m/tasks/t7/edit/')
    // 等预填落地再提交：详情是异步 setFieldsValue，抢点保存会拿到 initialValues
    await screen.findByDisplayValue('球鞋')
    await userEvent.click(screen.getByRole('button', { name: /保.*存/ }))
    await waitFor(() => expect(mocks.update).toHaveBeenCalled())
    expect(mocks.update.mock.calls[0][0]).toBe('t7')
    expect(mocks.update.mock.calls[0][1].mode).toBe(TASK_MODE.SEMI_AUTO)
  })
})
