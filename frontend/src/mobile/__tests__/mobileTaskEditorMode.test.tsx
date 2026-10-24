// frontend/src/mobile/__tests__/mobileTaskEditorMode.test.tsx
// T02850：移动端任务编辑器把 mode 兜底写成 'keyword' —— 那不是后端 TaskMode 的成员，
// 而 api_tasks.py 对未知 mode 直接抛 400（`未知 mode: keyword`），等于「移动端新建任务必失败」。
// T02908：该页此前没有 mode 控件，只能建「仅通知」任务、也改不了已有任务的模式。
// 下面除保留「提交值必须是合法成员」外，补上「切档后提交体随之变化」这条行为证明。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp } from 'antd'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { TASK_MODE, TASK_MODE_HINTS, TASK_MODE_VALUES } from '../../constants/taskStatus'

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

const RISK = /会产生真实订单/

beforeEach(() => {
  mocks.create.mockReset().mockResolvedValue({ id: 't1' })
  mocks.update.mockReset().mockResolvedValue({ id: 't1' })
  mocks.get.mockReset()
})

describe('移动端任务编辑器的 mode 提交（T02850 / T02908）', () => {
  it('新建：不动模式控件时提交的兜底值必须是合法 TaskMode 成员', async () => {
    wrap('/m/tasks/new/')
    await userEvent.type(await screen.findByPlaceholderText('关键词（必填）'), '球鞋')
    await userEvent.click(screen.getByRole('button', { name: /保.*存/ }))
    await waitFor(() => expect(mocks.create).toHaveBeenCalled())
    const body = mocks.create.mock.calls[0][0]
    expect(TASK_MODE_VALUES).toContain(body.mode)
    // 兜底取「仅通知」，与后端 TaskCreate.mode 的默认值同口径：新建不会默认开始抢单
    expect(body.mode).toBe(TASK_MODE.NOTIFY)
  })

  it('新建：切到「半自动」后提交体随之变化，并显示真实订单风险提示', async () => {
    wrap('/m/tasks/new/')
    await userEvent.type(await screen.findByPlaceholderText('关键词（必填）'), '球鞋')
    // 仅通知档不该出现风险提示
    expect(screen.queryByText(RISK)).toBeNull()

    await userEvent.click(screen.getByText('半自动'))
    expect(await screen.findByText(RISK)).toBeTruthy()
    // 档位说明与桌面模式卡读同一份 TASK_MODE_HINTS
    expect(screen.getByText(TASK_MODE_HINTS[TASK_MODE.SEMI_AUTO])).toBeTruthy()

    await userEvent.click(screen.getByRole('button', { name: /保.*存/ }))
    await waitFor(() => expect(mocks.create).toHaveBeenCalled())
    expect(mocks.create.mock.calls[0][0].mode).toBe(TASK_MODE.SEMI_AUTO)
  })

  it('编辑：回填的模式在控件上选中，改成「全自动」后提交新值', async () => {
    mocks.get.mockResolvedValue({
      id: 't7', keyword: '球鞋', name: '', mode: TASK_MODE.SEMI_AUTO,
      min_price: null, max_price: null, max_publish_days: null, region: null, exclude_words: '[]',
    })
    wrap('/m/tasks/t7/edit/')
    await screen.findByDisplayValue('球鞋')

    const semi = screen.getByRole('radio', { name: '半自动' }) as HTMLInputElement
    expect(semi.checked).toBe(true)

    await userEvent.click(screen.getByText('全自动'))
    expect(await screen.findByText(TASK_MODE_HINTS[TASK_MODE.AUTO])).toBeTruthy()
    expect(screen.queryByText(TASK_MODE_HINTS[TASK_MODE.SEMI_AUTO])).toBeNull()

    await userEvent.click(screen.getByRole('button', { name: /保.*存/ }))
    await waitFor(() => expect(mocks.update).toHaveBeenCalled())
    expect(mocks.update.mock.calls[0][0]).toBe('t7')
    expect(mocks.update.mock.calls[0][1].mode).toBe(TASK_MODE.AUTO)
  })

  it('编辑：不动模式控件时保留任务原有 mode，不被兜底值覆盖', async () => {
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
