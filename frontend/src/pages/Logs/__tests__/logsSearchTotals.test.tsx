/**
 * 日志搜索结果口径（T02678）
 *
 * 后端 total_estimate 是命中总数、items 是截断后的当页结果，两者不能混为一谈：
 * 1. 截断时标题区写「共 N 条，已展示 M 条」并提示缩小筛选范围；
 * 2. toast 不再用当页条数冒充总数；
 * 3. 级别分布/Top 标签明确标注「基于已展示 M 条」，与当页结果同源。
 */
import { describe, it, expect, vi, beforeEach, beforeAll, afterAll } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { message } from 'antd'
import type { LogEntry } from '../../../api'

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

const items = (n: number): LogEntry[] =>
  Array.from({ length: n }, (_, i) => ({
    id: String(i),
    created_at: '2026-10-19T10:00:00',
    level: i % 2 === 0 ? 'info' : 'err',
    message: `日志 ${i}`,
    stage: 'search',
  }))

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
  listMock.mockReset().mockResolvedValue({ items: [] })
  searchMock.mockReset()
})

describe('搜索总数与已展示条数分开', () => {
  it('截断时显示「共 57 条，已展示 5 条」并提示缩小范围，toast 不再冒充总数', async () => {
    const successSpy = vi.spyOn(message, 'success')
    successSpy.mockClear()
    searchMock.mockResolvedValue({
      items: items(5), count: 5, total_estimate: 57, matched_levels: {}, matched_tags: {},
    })
    const user = userEvent.setup()
    renderLogs()

    await user.click(await screen.findByRole('button', { name: /搜索/ }))

    const summary = await screen.findByTestId('search-total')
    expect(summary.textContent).toContain('共 57 条，已展示 5 条')
    expect(within(summary).getByText(/结果已截断，请缩小筛选范围/)).toBeTruthy()
    expect(successSpy).toHaveBeenCalledWith('共 57 条，已展示 5 条')
    expect(successSpy).not.toHaveBeenCalledWith('找到 5 条匹配')
    successSpy.mockRestore()
  })

  it('未截断时两者相等，不出现「结果已截断」提示', async () => {
    const successSpy = vi.spyOn(message, 'success')
    successSpy.mockClear()
    searchMock.mockResolvedValue({
      items: items(3), count: 3, total_estimate: 3, matched_levels: {}, matched_tags: {},
    })
    const user = userEvent.setup()
    renderLogs()

    await user.click(await screen.findByRole('button', { name: /搜索/ }))

    const summary = await screen.findByTestId('search-total')
    expect(summary.textContent).toContain('共 3 条，已展示 3 条')
    expect(within(summary).queryByText(/结果已截断/)).toBeNull()
    expect(successSpy).toHaveBeenCalledWith('找到 3 条匹配')
    successSpy.mockRestore()
  })

  it('级别分布与 Top 标签标注统计范围是「已展示」', async () => {
    searchMock.mockResolvedValue({
      items: items(5), count: 5, total_estimate: 57, matched_levels: {}, matched_tags: {},
    })
    const user = userEvent.setup()
    renderLogs()

    await user.click(await screen.findByRole('button', { name: /搜索/ }))

    expect(await screen.findByText('级别分布（基于已展示 5 条）：')).toBeTruthy()
    expect(screen.getByText('Top标签（基于已展示 5 条）：')).toBeTruthy()
  })
})
