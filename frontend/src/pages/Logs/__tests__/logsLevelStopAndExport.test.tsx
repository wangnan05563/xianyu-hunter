/**
 * 实时日志页：级别归一化展示 + 停止/暂停图标 + 导出拼筛选（T02569 / REQ-037、038、039）
 *
 * 三条回归：
 * 1. 规范级别（error/warning/info）都计入对应桶，级别 Tag 不恒灰（T02683 后库内只此一种写法）；
 * 2. 主开关「停止实时流」用 StopOutlined，与内层「暂停」的 PauseCircleOutlined 区分开；
 * 3. 导出 CSV 的链接必须带上当前筛选参数（关键词/级别/任务 ID），导出 LOG 是全量原始文件、不拼参数。
 */
import { describe, it, expect, vi, beforeEach, beforeAll, afterAll } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import type { LogEntry } from '../../../api'

const { listMock, searchMock } = vi.hoisted(() => ({ listMock: vi.fn(), searchMock: vi.fn() }))

vi.mock('../../../api', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  const logApi = (actual as { logApi: Record<string, unknown> }).logApi
  return { ...actual, logApi: { ...logApi, list: listMock, search: searchMock } }
})

import Logs from '../Logs'

// 后端 events.level 归一后的规范值（小写全词）
const SEARCH_ITEMS: LogEntry[] = [
  { id: '1', created_at: '2026-10-19T10:00:00', level: 'error', message: '数据库连接失败', stage: 'db' },
  { id: '2', created_at: '2026-10-19T10:00:01', level: 'error', message: '采集异常' },
  { id: '3', created_at: '2026-10-19T10:00:02', level: 'warning', message: '价格偏离预警' },
  { id: '4', created_at: '2026-10-19T10:00:03', level: 'info', message: '开始搜索' },
]

class FakeEventSource {
  addEventListener() {}
  close() {}
}

function renderLogs(initialEntry = '/logs') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
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
  listMock.mockReset().mockResolvedValue({
    items: [{ source: 'run.stdout.log', level: 'ERROR', lines: ['traceback ...'] }],
  })
  searchMock.mockReset().mockResolvedValue({ items: SEARCH_ITEMS, count: SEARCH_ITEMS.length })
})

describe('级别归一化展示（REQ-037）', () => {
  it('规范级别计入对应桶，Tag 取到红色而非恒灰', async () => {
    const user = userEvent.setup()
    renderLogs()
    await user.click(await screen.findByRole('button', { name: /搜索/ }))

    // 分布条：两个 error 行计入 ERROR 2，warning 计入 WARNING 1
    expect(await screen.findByText('ERROR 2')).toBeTruthy()
    expect(screen.getByText('WARNING 1')).toBeTruthy()
    expect(screen.getByText('INFO 1')).toBeTruthy()
    expect(screen.getByText('DEBUG 0')).toBeTruthy()
    expect(screen.getByText('ERROR 2')).toHaveClass('ant-tag-red')

    // 结果行：统一按规范键取色并显示统一名称
    // 限定在结果列表内取，原始日志面板那行本身就写全称 ERROR，不参与本条断言
    const list = (await screen.findByText('数据库连接失败')).closest('.ant-list') as HTMLElement
    const rowTags = within(list).getAllByText('ERROR')
    expect(rowTags).toHaveLength(2)
    rowTags.forEach((tag) => expect(tag).toHaveClass('ant-tag-red'))
    expect(within(list).getByText('WARNING')).toHaveClass('ant-tag-orange')
    expect(within(list).getByText('INFO')).toHaveClass('ant-tag-blue')
  })

  it('原始日志行的全称大写级别取色不受影响', async () => {
    renderLogs()
    const rawTag = await screen.findByText('ERROR')
    expect(rawTag).toHaveClass('ant-tag-red')
  })
})

describe('停止与暂停图标区分（REQ-038）', () => {
  it('主开关用 StopOutlined，内层暂停仍是 PauseCircleOutlined', async () => {
    const user = userEvent.setup()
    renderLogs()
    await user.click(await screen.findByRole('button', { name: /开启实时流/ }))

    const stopBtn = await screen.findByRole('button', { name: /停止实时流/ })
    expect(stopBtn.querySelector('.anticon-stop')).toBeTruthy()
    expect(stopBtn.querySelector('.anticon-pause-circle')).toBeNull()

    const pauseBtn = screen.getByRole('button', { name: /暂停/ })
    expect(pauseBtn.querySelector('.anticon-pause-circle')).toBeTruthy()

    // 暂停态切到「恢复」用播放图标，主开关不跟着变
    await user.click(pauseBtn)
    expect(screen.getByRole('button', { name: /恢复/ }).querySelector('.anticon-play-circle')).toBeTruthy()
    // 主开关不随暂停状态改图标，仍是「停止」语义
    expect(screen.getByRole('button', { name: /停止实时流/ }).querySelector('.anticon-stop')).toBeTruthy()
  })
})

describe('导出参数拼合（REQ-039）', () => {
  it('CSV 导出链接带当前筛选条件，LOG 导出保持全量文件', () => {
    renderLogs('/logs?query=timeout&level=error&task_id=t-9')
    const csv = screen.getByText('导出CSV').closest('a')
    const log = screen.getByText('导出LOG').closest('a')
    expect(csv?.getAttribute('href')).toContain('format=csv')
    expect(csv?.getAttribute('href')).toContain('q=timeout')
    expect(csv?.getAttribute('href')).toContain('level=error')
    expect(csv?.getAttribute('href')).toContain('task_id=t-9')
    expect(log?.getAttribute('href')).not.toContain('q=')
    expect(log?.getAttribute('href')).not.toContain('task_id=')
  })

  it('无筛选条件时只带 format 参数，不出现空值 query', async () => {
    renderLogs()
    await waitFor(() => expect(listMock).toHaveBeenCalled())
    const href = screen.getByText('导出CSV').closest('a')?.getAttribute('href') ?? ''
    expect(href.endsWith('api/logs/export?format=csv')).toBe(true)
    expect(href).not.toContain('&')
  })
})
