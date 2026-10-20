import { describe, expect, it, vi } from 'vitest'

import { notifyExportResult } from '../exportFeedback'

/**
 * T02581 / 6.1 指标 3 的前端一侧：导出 0 行必须走 warning，不得弹 success。
 *
 * 为什么单独锁：后端 `X-Export-Rows` 已经如实回带 0，但如果前端把「拿到响应」
 * 一律当成功，用户依旧会在筛选写错时看到「正在导出…」，指标 3 等于没落地。
 * 这条断言与 `tests/test_regress_ux_phase3_metrics.py` 里的 0 行导出断言配对，
 * 任一侧被改坏都会在测试里失败。
 */
function fakeMessage() {
  return { success: vi.fn(), warning: vi.fn(), error: vi.fn() }
}

describe('notifyExportResult', () => {
  it('0 行只报 warning，绝不报 success', () => {
    const msg = fakeMessage()
    notifyExportResult(msg, { rows: 0, filename: 'xh-orders-1.csv' }, '导出订单')

    expect(msg.warning).toHaveBeenCalledTimes(1)
    expect(msg.success).not.toHaveBeenCalled()
    expect(msg.warning.mock.calls[0][0]).toContain('0 行')
    expect(msg.warning.mock.calls[0][0]).toContain('只有表头')
  })

  it('有数据时报出真实行数', () => {
    const msg = fakeMessage()
    notifyExportResult(msg, { rows: 37, filename: 'xh-orders-2.csv' }, '导出订单')

    expect(msg.success).toHaveBeenCalledTimes(1)
    expect(msg.warning).not.toHaveBeenCalled()
    expect(msg.success.mock.calls[0][0]).toContain('37 行')
  })

  it('后端没回带行数时只说已保存，不谎报条数', () => {
    const msg = fakeMessage()
    notifyExportResult(msg, { rows: null, filename: 'xh-orders-3.csv' }, '导出订单')

    expect(msg.success).toHaveBeenCalledTimes(1)
    const text = msg.success.mock.calls[0][0]
    expect(text).toContain('已保存')
    expect(text).not.toMatch(/\d+ 行/)
  })
})
