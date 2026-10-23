// @vitest-environment node
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// T02649（评审 2.2-7）：卡片视图分页器与表格视图不一致的回归契约。
// 原状：表格用 antd 分页器（共 N 条 + 每页条数切换），卡片视图只有「上一页 / 第 x 页 / 下一页」，
// 用户切视图后分页控件换了长相、能力也变弱（看不到总数、改不了每页条数）。
// 现在两个视图共用同一份 paginationConfig（同一 page/pageSize 持久化状态、同一个 onChange）。

const stripComments = (s: string) =>
  s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')

const list = stripComments(readFileSync(resolve(__dirname, '../TaskList.tsx'), 'utf-8'))

describe('任务列表分页单源（T02649）', () => {
  it('卡片视图不再自带「上一页 / 下一页」裸按钮', () => {
    expect(list).not.toContain('上一页')
    expect(list).not.toContain('下一页')
  })

  it('两个视图读同一份 paginationConfig', () => {
    expect(list).toMatch(/const paginationConfig: TablePaginationConfig = \{/)
    expect(list).toMatch(/<Table[\s\S]*?pagination=\{paginationConfig\}/)
    expect(list).toMatch(/<Pagination \{\.\.\.paginationConfig\}/)
    // 主表分页只有一份配置：其余两处内联分页属于「闲鱼内容关联」面板（linkTotal / 常量 pageSize=10），
    // 与本口径无关，但它们也不许再各自声明 `current: page` 造成第二套任务分页状态
    expect(list.match(/current: page/g) ?? []).toHaveLength(1)
  })

  it('分页状态仍是持久化的 page/pageSize（切视图不丢位置）', () => {
    expect(list).toContain("usePersistentState<number>('xh.tasks.pageSize'")
  })

  it('改每页条数回到第 1 页，单纯翻页不动 pageSize', () => {
    expect(list).toMatch(
      /if \(ps === pageSize\) \{\s*setPage\(p\)\s*\} else \{\s*setPageSize\(ps\)\s*setPage\(1\)\s*\}/,
    )
  })

  it('卡片视图分页器以 total 为显示判据：翻到范围外的空页也留得下退路', () => {
    expect(list).toMatch(/\{total > 0 && \(\s*<div style=\{\{ textAlign: 'center', marginTop: 16 \}\}>\s*<Pagination \{\.\.\.paginationConfig\}/)
  })

  it('批量操作口径不变：仍只作用本页', () => {
    expect(list).toContain('启动本页')
    expect(list).toMatch(/tip=\{`一键启动本页/)
  })
})
