import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { parseBackendTime, taskSilence } from '../taskSilence'

// T02652：沉默标签必须按「最近一次采集命中」判定。
// 原实现读 updated_at —— 编辑任务就会把长期零命中的任务刷成「活跃」。

const NOW = Date.parse('2026-10-24T00:00:00Z')
const daysAgo = (n: number) => new Date(NOW - n * 86_400_000).toISOString()

describe('taskSilence 判定口径', () => {
  it('久未命中但刚被编辑过：仍判沉默，不因编辑变活跃（回归点）', () => {
    // updated_at 不参与判定；这里模拟「40 天没命中」的任务
    expect(taskSilence({ created_at: daysAgo(400), last_seen_at: daysAgo(40) }, NOW))
      .toMatchObject({ level: 'silent30', basis: 'hit' })
  })

  it('按 7d / 30d 分层', () => {
    expect(taskSilence({ created_at: daysAgo(400), last_seen_at: daysAgo(2) }, NOW).level).toBe('active')
    expect(taskSilence({ created_at: daysAgo(400), last_seen_at: daysAgo(10) }, NOW).level).toBe('silent7')
    expect(taskSilence({ created_at: daysAgo(400), last_seen_at: daysAgo(31) }, NOW).level).toBe('silent30')
  })

  it('边界值：恰好 7 天算活跃，恰好 30 天算沉默7d+', () => {
    expect(taskSilence({ created_at: daysAgo(400), last_seen_at: daysAgo(7) }, NOW).level).toBe('active')
    expect(taskSilence({ created_at: daysAgo(400), last_seen_at: daysAgo(30) }, NOW).level).toBe('silent7')
  })

  it('从未命中：新建任务按创建时间判活跃，久建任务判沉默', () => {
    expect(taskSilence({ created_at: daysAgo(1), last_seen_at: null }, NOW))
      .toMatchObject({ level: 'active', basis: 'created' })
    expect(taskSilence({ created_at: daysAgo(90), last_seen_at: null }, NOW))
      .toMatchObject({ level: 'silent30', basis: 'created' })
  })

  it('last_seen_at 脏值回落到 created_at，两者都坏才 unknown', () => {
    expect(taskSilence({ created_at: daysAgo(10), last_seen_at: 'not-a-date' }, NOW))
      .toMatchObject({ level: 'silent7', basis: 'created' })
    expect(taskSilence({ created_at: 'bad', last_seen_at: 'bad' }, NOW))
      .toMatchObject({ level: 'unknown', basis: 'unknown', days: null })
  })

  it('未来时间（时钟漂移）按 0 天处理，不出现负数', () => {
    const future = new Date(NOW + 5 * 86_400_000).toISOString()
    expect(taskSilence({ created_at: daysAgo(1), last_seen_at: future }, NOW))
      .toMatchObject({ level: 'active', days: 0 })
  })
})

describe('后端时间解析', () => {
  it('无时区后缀按 UTC 解析，不受本机时区影响', () => {
    // 后端 SQLite 存 naive UTC；若按本地时间解析，东八区会整体偏移 8 小时
    const naive = parseBackendTime('2026-10-24T00:00:00')
    expect(naive).toBe(NOW)
  })

  it('显式时区/偏移原样尊重', () => {
    expect(parseBackendTime('2026-10-24T00:00:00Z')).toBe(NOW)
    expect(parseBackendTime('2026-10-24T08:00:00+08:00')).toBe(NOW)
    expect(parseBackendTime('')).toBeNaN()
    expect(parseBackendTime(null)).toBeNaN()
  })
})

// 静态守卫：防止组件退回 updated_at 口径
const stripComments = (s: string) =>
  s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')
const taskListSrc = stripComments(
  readFileSync(resolve(__dirname, '../../pages/Tasks/TaskList.tsx'), 'utf-8'),
)
const typesSrc = readFileSync(resolve(__dirname, '../../api/types.ts'), 'utf-8')

describe('TaskList 接入守卫', () => {
  it('沉默标签走 taskSilence，不再按 updated_at 算天数', () => {
    expect(taskListSrc).toContain('taskSilence(task)')
    expect(taskListSrc).not.toContain('daysSinceUpdate')
    expect(taskListSrc).not.toMatch(/getSilenceTag[\s\S]*?updated_at/)
    // 四个标签文案仍在，避免 helper 接入后被改成空白
    for (const label of ['活跃', '沉默7d+', '沉默30d+']) {
      expect(taskListSrc).toContain(label)
    }
  })

  it('Task 类型声明 last_seen_at，接口字段不被悄悄丢弃', () => {
    expect(typesSrc).toMatch(/last_seen_at\?:\s*string\s*\|\s*null/)
  })
})
