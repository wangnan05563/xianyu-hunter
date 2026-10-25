// T02738：浏览器 profile 的全量遍历移出请求路径后，前端必须先显示「统计中 N 项」，
// 再轮询 /cache-scan 续跑，扫完自动刷新概览或补发展示预览——不能退化成空白等待。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import type { StorageStatus } from '../../../api'

const apiMocks = vi.hoisted(() => ({
  getStorageStatus: vi.fn(),
  getCacheScan: vi.fn(),
  cleanup: vi.fn(),
}))

vi.mock('../../../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../api')>()
  return {
    ...actual,
    maintenanceApi: {
      ...actual.maintenanceApi,
      getStorageStatus: apiMocks.getStorageStatus,
      getCacheScan: apiMocks.getCacheScan,
      cleanup: apiMocks.cleanup,
    },
  }
})

import CleanupPage from '../Cleanup'

const statusOf = (state: 'done' | 'scanning'): StorageStatus => ({
  db: { db_size_mb: 12.5, tasks: 3, items: 40, events: 900 },
  logs: { total_size_mb: 1.25, file_count: 4 },
  cache: {
    browser_data_mb: state === 'done' ? 8.5 : 0,
    browser_data_files: state === 'done' ? 120 : 0,
    browser_data_exists: true,
    browser_data_path: 'C:/xianyu/browser-data',
    browser_data_scan: {
      path: 'C:/xianyu/browser-data',
      state,
      mb: state === 'done' ? 8.5 : 0,
      files: state === 'done' ? 120 : 0,
      scanned_entries: state === 'done' ? 122 : 37,
      elapsed_sec: 1.2,
    },
    pycache_mb: 0,
    pycache_count: 0,
    pycache_applicable: true,
  },
})

describe('缓存统计的渐进反馈（T02738）', () => {
  beforeEach(() => {
    apiMocks.getStorageStatus.mockReset()
    apiMocks.getCacheScan.mockReset()
    apiMocks.cleanup.mockReset()
  })

  it('概览：统计中先显示已遍历项数，轮询完成后自动刷新为终值', async () => {
    apiMocks.getStorageStatus
      .mockResolvedValueOnce(statusOf('scanning'))
      .mockResolvedValue(statusOf('done'))
    apiMocks.getCacheScan.mockResolvedValue({
      path: 'C:/xianyu/browser-data',
      state: 'done',
      mb: 8.5,
      files: 120,
      scanned_entries: 122,
      elapsed_sec: 1.4,
    })

    render(<CleanupPage />)
    await waitFor(() => expect(screen.getByText(/浏览器数据统计中（已遍历 37 项）/)).toBeTruthy())

    await waitFor(
      () => expect(screen.getByText(/浏览器 8\.5MB\/120 个文件/)).toBeTruthy(),
      { timeout: 5000 },
    )
    expect(apiMocks.getCacheScan).toHaveBeenCalled()
    expect(apiMocks.getStorageStatus).toHaveBeenCalledTimes(2)
  })

  it('预览：统计未完成时明确回「统计中」，扫完自动补发预览并展示结果', async () => {
    apiMocks.getStorageStatus.mockResolvedValue(statusOf('done'))
    apiMocks.getCacheScan.mockResolvedValue({
      path: 'C:/xianyu/browser-data',
      state: 'done',
      mb: 8.5,
      files: 120,
      scanned_entries: 122,
      elapsed_sec: 1.4,
    })
    apiMocks.cleanup
      .mockResolvedValueOnce({
        dry_run: true,
        pending: true,
        count: 0,
        cleaned: [],
        scan: {
          path: 'C:/xianyu/browser-data',
          state: 'scanning',
          mb: 0,
          files: 0,
          scanned_entries: 5,
          elapsed_sec: 0.3,
        },
      })
      .mockResolvedValueOnce({
        dry_run: true,
        pending: false,
        count: 1,
        cleaned: ['[预览] 将删除 C:/xianyu/browser-data（120 个文件 / 8.5 MB）'],
      })

    render(<CleanupPage />)
    await waitFor(() => expect(screen.getByText(/浏览器 8\.5MB\/120 个文件/)).toBeTruthy())

    screen.getByRole('button', { name: /清理缓存/ }).click()

    await waitFor(() => expect(apiMocks.cleanup).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(screen.getByText(/浏览器数据统计中：已遍历 5 项/)).toBeTruthy())

    await waitFor(
      () => expect(apiMocks.cleanup).toHaveBeenCalledTimes(2),
      { timeout: 5000 },
    )
    expect(apiMocks.cleanup.mock.calls[1][0]).toBe('cache')
    expect(apiMocks.cleanup.mock.calls[1][1]).toMatchObject({ target: 'all', dry_run: true })
    await waitFor(() => expect(screen.getByText('预览结果（未删除任何内容）')).toBeTruthy())
  })
})
