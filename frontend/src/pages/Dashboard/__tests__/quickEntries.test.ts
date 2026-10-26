// T02640 / 评审 2.1-3：快捷入口收敛为 6 项 + 「更多」下拉。
// 这里守的是「收敛不等于删入口」：11 个原入口一个不少，顺序保持原样，
// 前 6 个铺在卡片上，其余全部进「更多」。
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import {
  QUICK_ENTRIES,
  QUICK_ENTRY_VISIBLE,
  moreQuickEntries,
  visibleQuickEntries,
} from '../quickEntries'

const DASHBOARD_SOURCE = readFileSync(resolve(__dirname, '../index.tsx'), 'utf-8')

describe('快捷入口收敛（2.1-3）', () => {
  it('卡片上只铺 6 项，其余进「更多」', () => {
    expect(QUICK_ENTRY_VISIBLE).toBe(6)
    expect(visibleQuickEntries()).toHaveLength(6)
    expect(moreQuickEntries()).toHaveLength(QUICK_ENTRIES.length - 6)
  })

  it('收敛不删入口：原有 11 项一个不少，且顺序不变', () => {
    expect(QUICK_ENTRIES.map((e) => e.title)).toEqual([
      '任务创建', '价格策略', '评估规则', '通知渠道', 'AI 服务', '抢单策略',
      '搜索参数', '配置版本', '系统清理', '数据库维护', '反爬登录管理',
    ])
  })

  it('路径不重复，且被移出的项都还能从「更多」里点到', () => {
    const paths = QUICK_ENTRIES.map((e) => e.path)
    expect(new Set(paths).size).toBe(paths.length)
    const morePaths = moreQuickEntries().map((e) => e.path)
    expect(morePaths).toEqual(paths.slice(QUICK_ENTRY_VISIBLE))
    expect(morePaths.length).toBeGreaterThan(0)
  })

  it('Dashboard 用同一份清单渲染，不再手写 11 段重复卡片', () => {
    expect(DASHBOARD_SOURCE).toContain('visibleQuickEntries()')
    expect(DASHBOARD_SOURCE).toContain('moreQuickEntries()')
    expect(DASHBOARD_SOURCE).toContain('className="quick-entry-card"')
  })
})
