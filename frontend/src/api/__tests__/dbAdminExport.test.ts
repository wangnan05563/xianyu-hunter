/**
 * 数据库维护导出（T02707 / 同 T02587 家族）
 *
 * 钉住三个回归点：
 * 1. responseType:'blob' 时错误体是 Blob —— 必须解析出后端 detail，
 *    不能只显示「Request failed with status code 500」；
 * 2. 成功口径按 X-Export-Rows 回带真实行数，0 行才能被页面判成 warning；
 * 3. 下载 blob 不能同步 revoke，否则部分浏览器拿到空文件。
 */
import { describe, it, expect, vi, beforeAll, afterAll, beforeEach } from 'vitest'

const { getMock } = vi.hoisted(() => ({ getMock: vi.fn() }))

vi.mock('../client', () => ({ default: { get: getMock } }))

import { dbAdminApi } from '../dbAdmin'
import { triggerBlobDownload } from '../../utils/exportFeedback'

const createObjectURL = vi.fn(() => 'blob:db-export')
const revokeObjectURL = vi.fn()
const anchorClick = vi.fn()

beforeAll(() => {
  URL.createObjectURL = createObjectURL
  URL.revokeObjectURL = revokeObjectURL
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(anchorClick)
})

afterAll(() => {
  vi.restoreAllMocks()
  vi.useRealTimers()
})

beforeEach(() => {
  getMock.mockReset()
  createObjectURL.mockClear()
  revokeObjectURL.mockClear()
  anchorClick.mockClear()
})

function ok(headers: Record<string, string>) {
  return { data: new Blob(['\ufeffid\r\n1\r\n']), headers }
}

describe('dbAdminApi.exportRows', () => {
  it('成功时回带响应头里的行数与文件名', async () => {
    getMock.mockResolvedValue(
      ok({
        'content-disposition': 'attachment; filename="tasks_20261023_120000.csv"',
        'x-export-rows': '42',
      }),
    )
    const res = await dbAdminApi.exportRows('tasks', 'csv')
    expect(res.rows).toBe(42)
    expect(res.filename).toBe('tasks_20261023_120000.csv')
    expect(res.blob).toBeInstanceOf(Blob)
    // 没有 blob 类型响应就拿不到错误体 detail
    expect(getMock.mock.calls[0]?.[1]).toMatchObject({ responseType: 'blob' })
  })

  it('老后端没回带 X-Export-Rows / 文件名时给 null 与本地兜底名', async () => {
    getMock.mockResolvedValue(ok({}))
    const res = await dbAdminApi.exportRows('tasks', 'json')
    expect(res.rows).toBeNull()
    expect(res.filename).toBe('tasks.json')
  })

  it('0 行如实返回 0（页面据此走 warning 而不是 success）', async () => {
    getMock.mockResolvedValue(
      ok({ 'content-disposition': 'attachment; filename="tasks.csv"', 'x-export-rows': '0' }),
    )
    const res = await dbAdminApi.exportRows('tasks', 'csv')
    expect(res.rows).toBe(0)
  })

  it('500 时解析 blob 错误体的 detail，而不是只报状态码', async () => {
    getMock.mockRejectedValue({
      response: { status: 500, data: new Blob(['{"detail":"数据库被占用，稍后重试"}']) },
    })
    await expect(dbAdminApi.exportRows('orders', 'csv')).rejects.toThrow(
      '导出失败（数据表 orders）：数据库被占用，稍后重试',
    )
    expect(anchorClick).not.toHaveBeenCalled()
  })

  it('401 给登录态失效口径，网络错误不谎报状态码', async () => {
    getMock.mockRejectedValue({ response: { status: 401, data: new Blob(['{}']) } })
    await expect(dbAdminApi.exportRows('tasks', 'csv')).rejects.toThrow('登录态已失效或无权限')

    getMock.mockRejectedValue({ message: 'Network Error' })
    await expect(dbAdminApi.exportRows('tasks', 'csv')).rejects.toThrow('网络不可达或服务未响应')
  })
})

describe('triggerBlobDownload', () => {
  it('点击后延时 10s 才 revoke，避免下载未开始就被回收', () => {
    vi.useFakeTimers()
    triggerBlobDownload(new Blob(['a']), 'x.csv')
    expect(anchorClick).toHaveBeenCalledTimes(1)
    expect(revokeObjectURL).not.toHaveBeenCalled()
    vi.advanceTimersByTime(9999)
    expect(revokeObjectURL).not.toHaveBeenCalled()
    vi.advanceTimersByTime(1)
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:db-export')
    vi.useRealTimers()
  })
})
