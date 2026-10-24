// T02739：打包版没有源码树，「Python 编译缓存」恒为 0——界面必须标「不适用」并置灰，
// 不能留一个永远清不掉的按钮。判定由后端 status 接口回带，前端只负责如实呈现。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { cacheTargetOptions, PYCACHE_NOT_APPLICABLE_HINT } from '@/utils/cacheTargets'
import type { StorageStatus } from '../../../api'

const apiMocks = vi.hoisted(() => ({
  getStorageStatus: vi.fn(),
  cleanup: vi.fn(),
}))

vi.mock('../../../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../api')>()
  return {
    ...actual,
    maintenanceApi: {
      ...actual.maintenanceApi,
      getStorageStatus: apiMocks.getStorageStatus,
      cleanup: apiMocks.cleanup,
    },
  }
})

import CleanupPage from '../Cleanup'

const statusOf = (pycacheApplicable: boolean): StorageStatus => ({
  db: { db_size_mb: 12.5, tasks: 3, items: 40, events: 900 },
  logs: { total_size_mb: 1.25, file_count: 4 },
  cache: {
    browser_data_mb: 8.5,
    browser_data_files: 120,
    browser_data_exists: true,
    browser_data_path: 'C:/xianyu/browser-data',
    pycache_mb: 0,
    pycache_count: 0,
    pycache_applicable: pycacheApplicable,
  },
})

describe('缓存清理范围：打包版「Python 编译缓存」标不适用', () => {
  beforeEach(() => {
    apiMocks.getStorageStatus.mockReset()
    apiMocks.cleanup.mockReset()
  })

  it('选项表：不适用时置灰并写明原因，「全部缓存」收窄为浏览器数据', () => {
    const frozen = cacheTargetOptions(false)
    const pycache = frozen.find((o) => o.value === 'pycache')
    const all = frozen.find((o) => o.value === 'all')
    expect(pycache?.disabled).toBe(true)
    expect(pycache?.label).toContain('不适用')
    expect(all?.label).toBe('全部缓存（浏览器数据）')
    // 浏览器数据这一档在任何形态下都必须可点
    expect(frozen.find((o) => o.value === 'browser_data')?.disabled).toBe(false)
  })

  it('选项表：开发模式保持原样，不能因为修打包版把正常功能一起关掉', () => {
    const dev = cacheTargetOptions(true)
    expect(dev.find((o) => o.value === 'pycache')?.disabled).toBe(false)
    expect(dev.find((o) => o.value === 'pycache')?.label).toBe('Python 编译缓存（__pycache__）')
    expect(dev.find((o) => o.value === 'all')?.label).toBe('全部缓存')
  })

  it('页面：回带不适用时展示说明，概览不再写「0 个目录/0MB」', async () => {
    apiMocks.getStorageStatus.mockResolvedValue(statusOf(false))
    render(<CleanupPage />)

    await waitFor(() => expect(screen.getByText(PYCACHE_NOT_APPLICABLE_HINT)).toBeTruthy())
    expect(screen.queryByText(/编译缓存 0 个目录\/0MB/)).toBeNull()
    expect(screen.getByText(/编译缓存 不适用（打包版无源码字节码缓存）/)).toBeTruthy()
    // 卡片说明也不能再承诺清理字节码缓存
    expect(screen.queryByText(/清理 Python 字节码缓存与浏览器用户数据目录/)).toBeNull()
  })

  it('页面：开发模式照常展示目录数与体积', async () => {
    apiMocks.getStorageStatus.mockResolvedValue({
      ...statusOf(true),
      cache: { ...statusOf(true).cache, pycache_mb: 2.5, pycache_count: 7 },
    })
    render(<CleanupPage />)

    await waitFor(() => expect(screen.getByText(/编译缓存 7 个目录\/2\.5MB/)).toBeTruthy())
    expect(screen.queryByText(PYCACHE_NOT_APPLICABLE_HINT)).toBeNull()
  })
})
