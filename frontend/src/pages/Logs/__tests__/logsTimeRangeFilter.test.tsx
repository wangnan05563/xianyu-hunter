/**
 * 日志时间范围筛选（T02679）
 *
 * 后端 /api/logs/search 与 /export 一直支持 start/end，前端却没有入口：
 * 1. URL 带 start/end 时恢复选择器，搜索与 CSV 导出都带上时间参数；
 * 2. 手动选择时间后，URL 同步 start/end（刷新/分享不丢筛选）；
 * 3. URL 里的非法时间按未设置处理，页面不崩、不把坏值传给后端。
 */
import { describe, it, expect, vi, beforeEach, beforeAll, afterAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'

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

function LocationProbe() {
  const loc = useLocation()
  return <div data-testid="location-search">{loc.search}</div>
}

function renderLogs(entry = '/logs') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Logs />
      <LocationProbe />
    </MemoryRouter>,
  )
}

const okSearch = { items: [], count: 0, total_estimate: 0, matched_levels: {}, matched_tags: {} }

beforeAll(() => {
  vi.stubGlobal('EventSource', FakeEventSource)
})

afterAll(() => {
  vi.unstubAllGlobals()
})

beforeEach(() => {
  listMock.mockReset().mockResolvedValue({ items: [] })
  searchMock.mockReset().mockResolvedValue(okSearch)
})

describe('URL 恢复时间范围', () => {
  it('搜索与 CSV 导出都带上 start/end，并显示当前生效范围', async () => {
    const user = userEvent.setup()
    renderLogs('/logs?start=2026-10-01T00:00:00&end=2026-10-02T00:00:00')

    expect(await screen.findByText(/当前时间范围：2026-10-01 00:00:00 ~ 2026-10-02 00:00:00/)).toBeTruthy()

    await user.click(await screen.findByRole('button', { name: /搜索/ }))
    await waitFor(() => expect(searchMock).toHaveBeenCalled())
    expect(searchMock.mock.calls[0][0]).toMatchObject({
      start: '2026-10-01T00:00:00',
      end: '2026-10-02T00:00:00',
    })

    const href = decodeURIComponent(screen.getByText('导出CSV').closest('a')?.getAttribute('href') ?? '')
    expect(href).toContain('start=2026-10-01T00:00:00')
    expect(href).toContain('end=2026-10-02T00:00:00')
  }, 20000)

  it('非法 URL 时间不传给后端，也不显示范围提示', async () => {
    const user = userEvent.setup()
    renderLogs('/logs?start=not-a-date')

    expect(screen.queryByText(/当前时间范围/)).toBeNull()
    await user.click(await screen.findByRole('button', { name: /搜索/ }))
    await waitFor(() => expect(searchMock).toHaveBeenCalled())
    expect(searchMock.mock.calls[0][0].start).toBeUndefined()
  })
})

describe('选择时间后回写 URL', () => {
  it('手动输入起止时间后，URL 同步 start/end 且搜索参数一致', async () => {
    const user = userEvent.setup()
    renderLogs()

    const [startInput, endInput] = screen.getAllByPlaceholderText(/开始时间|结束时间/)
    await user.type(startInput, '2026-10-01 00:00:00{enter}')
    await user.type(endInput, '2026-10-02 00:00:00{enter}')

    await waitFor(() => {
      const search = screen.getByTestId('location-search').textContent ?? ''
      expect(decodeURIComponent(search)).toContain('start=2026-10-01T00:00:00')
      expect(decodeURIComponent(search)).toContain('end=2026-10-02T00:00:00')
    })

    await user.click(screen.getByRole('button', { name: /搜索/ }))
    await waitFor(() => expect(searchMock).toHaveBeenCalled())
    expect(searchMock.mock.calls[0][0]).toMatchObject({
      start: '2026-10-01T00:00:00',
      end: '2026-10-02T00:00:00',
    })
  }, 20000)
})
