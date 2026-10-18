import { describe, it, expect, afterEach } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { setMenuLabelIndex } from '../../../api/menu'
import type { MenuItem } from '../../../api/menu'
import { sheetRegistry, findSheetMeta } from '../sheetRegistry'
import { buildCommandItems } from '../../../hooks/useMenuConfig'

// 导航文案单一事实源守卫（T02556 / FR-B-4）
// 背景：同一个页面曾在侧栏、面包屑、命令面板、标签栏四处各有叫法
// （/items 商品中心 vs 商品列表、/evaluations 卖家评估 vs 评估明细、/chatbot 智能客服 vs 智能客服对话），
// 根因是四套并存的常量表。现在 /api/menu 是唯一权威源，本测试锁住两件事：
// 1) 兜底表（sheetRegistry title）与 registry label 不得漂移——菜单加载前的首帧也必须是同一个名字；
// 2) 已删除的重复文案表不得复活。
const REGISTRY_SOURCE = readFileSync(
  resolve(__dirname, '../../../../../config/menu_registry.yaml'),
  'utf-8',
)
const LAYOUT_SOURCE = readFileSync(resolve(__dirname, '../../layout/MainLayout.tsx'), 'utf-8')

function parseRegistryLabels(): Map<string, string> {
  const map = new Map<string, string>()
  for (const block of REGISTRY_SOURCE.split(/\n(?=\s*-\s*key:)/)) {
    const path = block.match(/\n\s+path:\s*(\S+)/)?.[1]
    const label = block.match(/\n\s+label:\s*(.+?)\s*$/m)?.[1]
    if (path && label) map.set(path, label)
  }
  return map
}

function menuItem(key: string, label: string, path: string): MenuItem {
  return {
    key,
    label,
    path,
    icon: 'AppstoreOutlined',
    sort_order: 0,
    visible: true,
    category: 'data_view',
  }
}

describe('导航文案单一事实源（T02556 / FR-B-4）', () => {
  afterEach(() => setMenuLabelIndex([]))

  it('menu_registry.yaml 的每个菜单页，sheetRegistry 兜底标题与 label 一致', () => {
    const labels = parseRegistryLabels()
    // registry 条目数骤降说明解析失效（YAML 结构被改动），先让守卫本身可信
    expect(labels.size).toBeGreaterThanOrEqual(29)
    const drifted: string[] = []
    for (const s of sheetRegistry) {
      const label = labels.get(s.path)
      if (label && label !== s.title) drifted.push(`${s.path}: registry=${label} sheet=${s.title}`)
    }
    expect(drifted).toEqual([])
  })

  it('标签栏标题跟随 /api/menu：菜单 label 与兜底标题不同时以菜单为准', () => {
    setMenuLabelIndex([menuItem('items', '商品台账', '/items')])
    expect(findSheetMeta('/items')?.title).toBe('商品台账')
  })

  it('菜单尚未到达时回退到 sheetRegistry 兜底标题', () => {
    setMenuLabelIndex([])
    expect(findSheetMeta('/items')?.title).toBe('商品中心')
  })

  it('非菜单子页面（/tasks/:id）不受菜单索引影响，仍用本地标题', () => {
    setMenuLabelIndex([menuItem('tasks', '任务管理', '/tasks')])
    expect(findSheetMeta('/tasks/123')?.title).toBe('任务详情')
  })

  it('MainLayout 不再维护 ROUTE_LABELS / COMMAND_ITEMS 重复文案表', () => {
    for (const dead of ['ROUTE_LABELS', 'COMMAND_ITEMS']) {
      expect(LAYOUT_SOURCE).not.toContain(dead)
    }
  })

  it('命令面板项由菜单派生，名称与侧栏一致', () => {
    const items = buildCommandItems([
      menuItem('items', '商品中心', '/items'),
      menuItem('orders', '抢单记录', '/orders'),
    ])
    expect(items.map((i) => [i.key, i.label])).toEqual([
      ['/items', '商品中心'],
      ['/orders', '抢单记录'],
    ])
    expect(items[0].icon).toBeTruthy()
  })

  it('用户隐藏的菜单项同样不出现在命令面板', () => {
    const hidden = menuItem('chatbot', '智能客服', '/chatbot')
    expect(buildCommandItems([{ ...hidden, visible: false }])).toEqual([])
  })
})
