// T02771 / PRD 4.4-2：触发前的范围预估必须诚实——统计失败不能显示 0，
// 无数据要显示真实 0，断点续传要把三个数都摊开。
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, it, expect } from 'vitest'
import {
  triggerPreviewDescription,
  type TriggerPreviewState,
} from '../BatchRefresh'
import type { BatchRefreshTriggerPreview } from '../../../api/batchRefresh'

const read = (rel: string) =>
  readFileSync(resolve(__dirname, '../../../../src', rel), 'utf-8').replace(/\r\n/g, '\n')

const PAGE = read('pages/Maintenance/BatchRefresh.tsx')
const MOBILE = read('mobile/pages/BatchRefresh/index.tsx')

const ready = (data: BatchRefreshTriggerPreview): TriggerPreviewState => ({ status: 'ready', data })

const base: BatchRefreshTriggerPreview = {
  pending: 12, limit: 100, at_limit: false, resumed: false, resumed_processed: 0, resumed_total: 0,
}

describe('triggerPreviewDescription：四种状态各说各的真话', () => {
  it('统计中：明确在统计，不给数字', () => {
    const text = triggerPreviewDescription({ status: 'loading' })
    expect(text).toContain('正在统计')
    expect(text).not.toMatch(/\d+ 个/)
    // 首次打开弹窗时 state 还是 undefined，必须落在「统计中」而不是失败/空批
    expect(triggerPreviewDescription(undefined)).toBe(text)
  })

  it('统计失败：禁用式话术，绝不出现「0 个」或「无待处理」', () => {
    const text = triggerPreviewDescription({ status: 'error' })
    expect(text).toContain('统计失败')
    expect(text).toContain('重试')
    expect(text).not.toContain('0 个')
    expect(text).not.toContain('无待处理')
  })

  it('真实 0 条：说「本批无待处理商品」并写明不会启动浏览器', () => {
    const text = triggerPreviewDescription(ready({ ...base, pending: 0 }))
    expect(text).toContain('本批无待处理商品')
    expect(text).toContain('不会启动浏览器')
  })

  it('正常批次：报本批条数与单次上限', () => {
    const text = triggerPreviewDescription(ready(base))
    expect(text).toContain('12 个在售商品')
    expect(text).toContain('上限 100')
  })

  it('顶到上限：如实说「已达上限」而不是假装全量', () => {
    const text = triggerPreviewDescription(ready({ ...base, pending: 100, at_limit: true }))
    expect(text).toContain('已达单次上限 100')
    expect(text).toContain('本轮只跑这些')
  })

  it('断点续传：剩余/已处理/原批次总数三个数都出现', () => {
    const text = triggerPreviewDescription(
      ready({ ...base, pending: 6, resumed: true, resumed_processed: 4, resumed_total: 10 }),
    )
    expect(text).toContain('断点续传')
    expect(text).toContain('共 10 个')
    expect(text).toContain('已处理 4 个')
    expect(text).toContain('剩余 6 个')
  })
})

describe('触发入口：先预估再确认', () => {
  it('桌面：触发按钮包在 Popconfirm 里，打开时拉预估，失败/空批不许确认', () => {
    expect(PAGE).toContain("batchRefreshApi.triggerPreview()")
    expect(PAGE).toContain('onOpenChange={(open) => {')
    expect(PAGE).toContain('okButtonProps={{ disabled: !canConfirmTrigger, loading: triggering }}')
    // 空批次时按钮文案不再假装会跑
    expect(PAGE).toContain("okText={previewEmpty ? '本批无待处理商品' : '开始采集'}")
    // 预估失败走 error 态，不得塞 0
    expect(PAGE).not.toMatch(/catch[^}]*setTriggerPreview\(\{ status: 'ready', data: \{[^}]*pending: 0/)
  })

  it('移动端：点击先取预估 + 四要素确认，确认后才 doAction', () => {
    expect(MOBILE).toContain('batchRefreshApi.triggerPreview()')
    expect(MOBILE).toContain('await confirmDanger({')
    expect(MOBILE).toContain("if (ok) await doAction('trigger')")
    // 原零确认入口不得残留
    expect(MOBILE).not.toContain("onClick={() => void doAction('trigger')}")
  })

  it('移动端预估失败直接返回，不降级触发', () => {
    const start = MOBILE.indexOf('const triggerWithConfirm')
    const fn = MOBILE.slice(start, MOBILE.indexOf('// 保存配置热更新'))
    const failBranch = fn.slice(fn.indexOf('catch (e)'), fn.indexOf('if (preview.pending === 0)'))
    expect(failBranch).toContain('return')
    expect(failBranch).not.toContain('doAction')
  })
})
