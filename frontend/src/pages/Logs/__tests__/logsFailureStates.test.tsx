/**
 * 实时日志页失败态（T02682）
 *
 * 失败不能再只弹 toast、让页面停留在「暂无日志」/「输入条件后搜索」：
 * 1. 原始日志加载失败 → 独立失败区块，透传后端 detail，且不出现「暂无日志」；
 * 2. 搜索失败 → 独立失败区块，透传后端 detail，且不出现「输入条件后搜索」；
 * 3. 两个区块都能重试，成功后失败区块消失。
 */
import { describe, it, expect, vi, beforeEach, beforeAll, afterAll } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

const { listMock, searchMock } = vi.hoisted(() => ({ listMock: vi.fn(), searchMock: vi.fn() }))

vi.mock('../../../api', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  const logApi = (actual as { logApi: Record<string, unknown> }).logApi
  return { ...actual, logApi: { ...logApi, list: listMock, search: searchMock } }
})

import Logs from '../Logs'

class FakeEventSource {
  addEventListener() {}
  close() {}
}

const LIST_OK = { items: [{ source: 'run.stdout.log', level: 'ERROR', lines: ['traceback ...'] }] }
const SEARCH_OK = {
  items: [{ id: '1', created_at: '2026-10-19T10:00:00', level: 'info', message: '命中的日志' }],
  count: 1,
  total_estimate: 1,
  matched_levels: {},
  matched_tags: {},
}

// 后端统一错误体：{ detail: "..." }，extractApiError 应原样透传
const apiError = (detail: string) => ({ response: { status: 500, data: { detail } } })

function renderLogs() {
  return render(
    <MemoryRouter initialEntries={['/logs']}>
      <Logs />
    </MemoryRouter>,
  )
}

beforeAll(() => {
  vi.stubGlobal('EventSource', FakeEventSource)
})

afterAll(() => {
  vi.unstubAllGlobals()
})

beforeEach(() => {
  listMock.mockReset()
  searchMock.mockReset()
})

describe('原始日志加载失败态', () => {
  it('显示失败区块与后端 detail，不用「暂无日志」冒充，重试成功后恢复正常', async () => {
    listMock.mockRejectedValueOnce(apiError('日志目录不可读')).mockResolvedValue(LIST_OK)
    const user = userEvent.setup()
    renderLogs()

    const title = await screen.findByText('日志加载失败')
    const alert = title.closest('.ant-alert') as HTMLElement
    expect(within(alert).getByText(/日志目录不可读/)).toBeTruthy()
    expect(within(alert).getByText(/本次一条日志都没取到/)).toBeTruthy()
    expect(screen.queryByText('暂无日志')).toBeNull()

    await user.click(within(alert).getByText(/重\s*试/))

    await waitFor(() => expect(listMock).toHaveBeenCalledTimes(2))
    expect(await screen.findByText(/traceback/)).toBeTruthy()
    expect(screen.queryByText('日志加载失败')).toBeNull()
  })

  it('有旧数据时失败区块说明下方是上一次成功结果', async () => {
    listMock.mockResolvedValueOnce(LIST_OK).mockRejectedValueOnce(apiError('读取超时'))
    const user = userEvent.setup()
    renderLogs()
    expect(await screen.findByText(/traceback/)).toBeTruthy()

    await user.click(screen.getByRole('button', { name: /刷新/ }))

    const alert = (await screen.findByText('日志加载失败')).closest('.ant-alert') as HTMLElement
    expect(within(alert).getByText(/读取超时/)).toBeTruthy()
    expect(within(alert).getByText(/下方仍是上一次成功加载的内容/)).toBeTruthy()
    expect(screen.getByText(/traceback/)).toBeTruthy()
  })
})

describe('日志搜索失败态', () => {
  it('显示失败区块与后端 detail，不用「输入条件后搜索」冒充，重试成功后出结果', async () => {
    listMock.mockResolvedValue(LIST_OK)
    searchMock.mockRejectedValueOnce(apiError('检索服务暂不可用')).mockResolvedValue(SEARCH_OK)
    const user = userEvent.setup()
    renderLogs()

    await user.click(await screen.findByRole('button', { name: /搜索/ }))

    const title = await screen.findByText('搜索结果加载失败')
    const alert = title.closest('.ant-alert') as HTMLElement
    expect(within(alert).getByText(/检索服务暂不可用/)).toBeTruthy()
    expect(within(alert).getByText(/本次没有取到任何结果/)).toBeTruthy()
    expect(screen.queryByText('输入条件后搜索')).toBeNull()

    await user.click(within(alert).getByText(/重\s*试/))

    await waitFor(() => expect(searchMock).toHaveBeenCalledTimes(2))
    expect(await screen.findByText('命中的日志')).toBeTruthy()
    expect(screen.queryByText('搜索结果加载失败')).toBeNull()
  })
})
