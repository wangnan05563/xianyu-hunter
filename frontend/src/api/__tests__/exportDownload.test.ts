/**
 * 导出下载失败态与 0 行口径（T02587 / FR-C-2）
 *
 * 钉住两个回归点：
 * 1. 原 `download` 走 `location.href` 直跳 —— HTTP 500 会整页跳走且错误不可见；
 *    现在必须抛出可读错误（后端 detail / 状态码 / 网络不可达）。
 * 2. 原三处入口一律 `message.success('正在导出 …')` —— 0 行也报成功；
 *    现在 0 行只能出 warning，且不再出现「正在导出」字样。
 */
import { describe, it, expect, vi, beforeAll, afterAll, beforeEach } from 'vitest'

const { getMock } = vi.hoisted(() => ({ getMock: vi.fn() }))

vi.mock('../client', () => ({ default: { get: getMock } }))

import { exportApi } from '../export'
import { notifyExportResult, type MessageLike } from '../../utils/exportFeedback'

const createObjectURL = vi.fn(() => 'blob:export')
const revokeObjectURL = vi.fn()
const anchorClick = vi.fn()

beforeAll(() => {
  URL.createObjectURL = createObjectURL
  URL.revokeObjectURL = revokeObjectURL
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(anchorClick)
})

afterAll(() => {
  vi.restoreAllMocks()
})

beforeEach(() => {
  getMock.mockReset()
  createObjectURL.mockClear()
  anchorClick.mockClear()
})

function ok(rowsHeader?: string, disposition = 'attachment; filename="xh-items-20261019-000000.csv"') {
  const headers: Record<string, string> = { 'content-disposition': disposition }
  if (rowsHeader !== undefined) headers['x-export-rows'] = rowsHeader
  return { data: new Blob(['\ufeffid,title\n1,abc\n']), headers }
}

describe('exportApi.downloadFile', () => {
  it('成功时按 X-Export-Rows 报行数，并用隐藏 <a download> 触发保存', async () => {
    getMock.mockResolvedValue(ok('12'))
    const res = await exportApi.downloadFile('items', { limit: 5000 })
    expect(res).toEqual({ rows: 12, filename: 'xh-items-20261019-000000.csv' })
    expect(anchorClick).toHaveBeenCalledTimes(1)
    // responseType 必须是 blob，否则错误体拿不到（axios.get(url, config) → 第 2 个实参）
    expect(getMock.mock.calls[0]?.[1]).toMatchObject({ responseType: 'blob' })
  })

  it('老后端没回带行数时如实返回 null，不猜数字', async () => {
    getMock.mockResolvedValue(ok(undefined))
    const res = await exportApi.downloadFile('orders')
    expect(res.rows).toBeNull()
  })

  it('HTTP 500 时把 blob 错误体翻成后端 detail，且不发起页面跳转', async () => {
    getMock.mockRejectedValue({
      response: { status: 500, data: new Blob(['{"detail":"数据库被占用"}']) },
    })
    const before = globalThis.location.href
    await expect(exportApi.downloadFile('items')).rejects.toThrow('数据库被占用')
    expect(globalThis.location.href).toBe(before)
    expect(anchorClick).not.toHaveBeenCalled()
  })

  it('401 给出登录态失效口径，网络错误给出不误导状态码的提示', async () => {
    getMock.mockRejectedValue({ response: { status: 401, data: new Blob(['{}']) } })
    await expect(exportApi.downloadFile('items')).rejects.toThrow('登录态已失效或无权限')

    getMock.mockRejectedValue({ message: 'Network Error' })
    await expect(exportApi.downloadFile('items')).rejects.toThrow('网络不可达或服务未响应')
  })
})

describe('notifyExportResult', () => {
  function spy(): MessageLike & { success: ReturnType<typeof vi.fn>; warning: ReturnType<typeof vi.fn>; error: ReturnType<typeof vi.fn> } {
    return { success: vi.fn(), warning: vi.fn(), error: vi.fn() }
  }

  it('0 行只出 warning，且不出现「正在导出」字样', () => {
    const msg = spy()
    notifyExportResult(msg, { rows: 0, filename: 'x.csv' }, '商品列表')
    expect(msg.warning).toHaveBeenCalledTimes(1)
    expect(msg.success).not.toHaveBeenCalled()
    expect(String(msg.warning.mock.calls[0]?.[0])).toContain('0 行')
  })

  it('有数据时按真实行数报成功；行数未知时不谎报条数', () => {
    const msg = spy()
    notifyExportResult(msg, { rows: 7, filename: 'x.csv' }, '商品列表')
    expect(msg.success.mock.calls[0]?.[0]).toContain('7 行')

    const msg2 = spy()
    notifyExportResult(msg2, { rows: null, filename: 'x.csv' }, '商品列表')
    expect(String(msg2.success.mock.calls[0]?.[0])).not.toMatch(/\d+ 行/)
  })
})
