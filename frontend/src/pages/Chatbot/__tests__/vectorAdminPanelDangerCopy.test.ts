// @vitest-environment node
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

// T02577 D-9：向量库维护只留「客服配置 › 向量库维护」一套入口，
// 危险操作的确认强度必须统一到 confirmDanger 四要素（C 档），
// 且「数量」用后端真实 chunk 数，不许写死。
const SRC = readFileSync(
  resolve(__dirname, '../components/VectorAdminPanel.tsx'),
  'utf8',
)

describe('向量库维护面板：危险操作确认口径（T02577 D-9）', () => {
  it('四个危险操作全部走 confirmDanger', () => {
    const calls = SRC.match(/await confirmDanger\(/g) ?? []
    expect(calls.length).toBe(4)
  })

  it('不再使用 Popconfirm 这类弱确认', () => {
    expect(SRC).not.toContain('Popconfirm')
  })

  it('清空集合与恢复快照的数量取自后端真实 chunk 数', () => {
    expect(SRC).toContain('count: status?.chunk_count ?? null')
  })

  it('按来源删除拿不到预先统计，必须显式声明未知而不是省略数量', () => {
    expect(SRC).toContain('count: COUNT_UNKNOWN')
    expect(SRC).toContain("from '@/components/DangerSummary'")
  })
})
