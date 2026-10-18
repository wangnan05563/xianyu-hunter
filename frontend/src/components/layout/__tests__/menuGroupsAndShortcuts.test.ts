import { describe, it, expect, afterEach } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { renderToStaticMarkup } from 'react-dom/server'
import type { ReactElement } from 'react'
import {
  MENU_GROUP_LABELS,
  menuGroupByKey,
  setMenuGroupIndex,
  setMenuLabelIndex,
} from '../../../api/menu'
import type { MenuItem, MenuGroup } from '../../../api/menu'
import { buildMenuItems } from '../../../hooks/useMenuConfig'
import { buildBreadcrumbs } from '../breadcrumb'
import { G_PREFIX_MAP, G_PREFIX_HINT, shortcutHintForPath } from '../shortcuts'

// 分组标题与图标的单源守卫（T02558 / FR-B-5、N4、N6）
// 此前 SubMenu 的图标取「组内第一个菜单项的图标」、名称靠前端内置表拼，
// 结果是多个分组图标雷同、分组名与 registry 里的定义各写一份。
const REGISTRY_SOURCE = readFileSync(
  resolve(__dirname, '../../../../../config/menu_registry.yaml'),
  'utf-8',
)

function leaf(key: string, label: string, path: string, icon: string, sortOrder: number): MenuItem {
  return {
    key,
    label,
    path,
    icon,
    sort_order: sortOrder,
    visible: true,
    category: 'data_view',
  }
}

function iconClass(node: unknown): string {
  return renderToStaticMarkup(node as ReactElement)
}

function registryPaths(): Set<string> {
  const paths = new Set<string>()
  for (const block of REGISTRY_SOURCE.split(/\n(?=\s*-\s*key:)/)) {
    const path = block.match(/\n\s+path:\s*(\S+)/)?.[1]
    if (path) paths.add(path)
  }
  return paths
}

describe('分组标题与图标单源（FR-B-5 / N6）', () => {
  afterEach(() => {
    setMenuGroupIndex([])
    setMenuLabelIndex([])
  })

  const dataView: MenuGroup[] = [{ key: 'data_view', label: '数据查看', icon: 'BarChartOutlined' }]
  const threeItems = [
    leaf('tasks', '任务管理', '/tasks', 'UnorderedListOutlined', 10),
    leaf('items', '商品中心', '/items', 'ShoppingOutlined', 11),
    leaf('orders', '抢单记录', '/orders', 'ThunderboltOutlined', 12),
  ]

  it('SubMenu 图标来自 groups.icon，不再复用组内首项图标', () => {
    const items = buildMenuItems(threeItems, dataView)
    const sub = items[0] as { key: string; icon: unknown; label: string; children: unknown[] }
    expect(sub.key).toBe('sub-data_view')
    expect(sub.label).toBe('数据查看')
    expect(iconClass(sub.icon)).toContain('anticon-bar-chart')
    // 子项图标不受影响
    const firstChild = sub.children[0] as { icon: unknown }
    expect(iconClass(firstChild.icon)).toContain('anticon-unordered-list')
  })

  it('groups 缺失时回退到内置中文表，旧后端响应不会让分组名变英文 key', () => {
    const items = buildMenuItems(threeItems)
    const sub = items[0] as { label: string }
    expect(sub.label).toBe(MENU_GROUP_LABELS.data_view)
  })

  it('registry 的每个 category 都有对应的 groups 定义（防前后端分组键漂移）', () => {
    const categories = new Set<string>()
    for (const block of REGISTRY_SOURCE.split(/\n(?=\s*-\s*key:)/)) {
      const category = block.match(/\n\s+category:\s*(\S+)/)?.[1]
      if (category) categories.add(category)
    }
    const groupKeys = new Set(
      [...REGISTRY_SOURCE.matchAll(/^\s{2}- key: (\S+)$/gm)].map((m) => m[1]),
    )
    expect(categories.size).toBeGreaterThanOrEqual(5)
    expect([...categories].filter((c) => !groupKeys.has(c))).toEqual([])
  })

  it('面包屑的分组层级同样取 groups 标题', () => {
    setMenuGroupIndex([{ key: 'data_view', label: '数据台账', icon: 'BarChartOutlined' }])
    setMenuLabelIndex(threeItems)
    expect(buildBreadcrumbs('/items', threeItems)[1].label).toBe('数据台账')
  })

  it('分组索引读写共享单源：menuGroupByKey 取到的是下发的那一条', () => {
    setMenuGroupIndex(dataView)
    expect(menuGroupByKey('data_view')?.label).toBe('数据查看')
    expect(menuGroupByKey('nope')).toBeUndefined()
  })
})

describe('g+X 键位与面板提示（N4）', () => {
  it('键位按 PRD 重排：i 指向商品中心、m 指向事件时间线', () => {
    expect(G_PREFIX_MAP.i).toBe('/items')
    expect(G_PREFIX_MAP.m).toBe('/timeline')
  })

  it('每个键位的目标都是 registry 里真实存在的菜单路径', () => {
    const paths = registryPaths()
    const missing = Object.entries(G_PREFIX_MAP)
      .filter(([, p]) => !paths.has(p))
      .map(([k, p]) => `${k}→${p}`)
    expect(missing).toEqual([])
  })

  it('面板右侧键位提示可反查，且底部说明文案存在', () => {
    expect(shortcutHintForPath('/items')).toBe('g+i')
    expect(shortcutHintForPath('/timeline')).toBe('g+m')
    expect(shortcutHintForPath('/no-such-page')).toBeUndefined()
    expect(G_PREFIX_HINT).toContain('g')
  })
})
