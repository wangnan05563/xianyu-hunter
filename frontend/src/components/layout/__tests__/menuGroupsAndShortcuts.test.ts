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

describe('分组形状与可见项数解耦（T02607）', () => {
  afterEach(() => {
    setMenuGroupIndex([])
    setMenuLabelIndex([])
  })

  const groups: MenuGroup[] = [
    { key: 'overview', label: '总览', icon: 'FundOutlined' },
    { key: 'data_view', label: '数据查看', icon: 'BarChartOutlined' },
  ]
  const dashboard: MenuItem = {
    key: 'dashboard',
    label: '仪表盘',
    path: '/',
    icon: 'DashboardOutlined',
    sort_order: 1,
    visible: true,
    category: 'overview',
  }
  const dataViewItems: MenuItem[] = [
    leaf('tasks', '任务管理', '/tasks', 'UnorderedListOutlined', 10),
    leaf('items', '商品中心', '/items', 'ShoppingOutlined', 11),
    leaf('orders', '抢单记录', '/orders', 'ThunderboltOutlined', 12),
  ]

  it('登记分组只剩 1 个可见项时仍是 SubMenu，组标题与组图标不消失', () => {
    const items = buildMenuItems([dashboard, ...dataViewItems], groups)
    const overview = items.find((i) => (i as { key?: string }).key === 'sub-overview') as
      | { key: string; label: string; icon: unknown; children: unknown[] }
      | undefined
    expect(overview).toBeDefined()
    expect(overview?.label).toBe('总览')
    expect(overview?.children).toHaveLength(1)
    expect(overview?.children[0]).toMatchObject({ key: '/', label: '仪表盘' })
    expect(iconClass(overview?.icon)).toContain('anticon-fund')
  })

  it('隐藏同组其他项后形状不翻转：可见项从 3 变 1，组还是那个组', () => {
    const before = buildMenuItems(dataViewItems, groups)
    const after = buildMenuItems(
      [
        dataViewItems[0],
        { ...dataViewItems[1], visible: false },
        { ...dataViewItems[2], visible: false },
      ],
      groups,
    )
    expect(before[0]).toMatchObject({ key: 'sub-data_view', label: '数据查看' })
    expect(after[0]).toMatchObject({ key: 'sub-data_view', label: '数据查看' })
    expect((before[0] as { children: unknown[] }).children).toHaveLength(3)
    expect((after[0] as { children: unknown[] }).children).toHaveLength(1)
    expect(after).toHaveLength(1)
  })

  it('未登记分组的单项（category 为空）仍作为顶层单项，不包一层空壳 SubMenu', () => {
    const orphan: MenuItem = { ...dashboard, key: 'bookmark', path: '/timeline', category: '' }
    const items = buildMenuItems([orphan], groups)
    expect(items).toHaveLength(1)
    expect(items[0]).toMatchObject({ key: '/timeline', label: '仪表盘' })
    expect((items[0] as { children?: unknown[] }).children).toBeUndefined()
  })

  it('登记口径不依赖后端 groups 是否下发：旧响应（无 groups）下单项 overview 依旧成组', () => {
    const items = buildMenuItems([dashboard, ...dataViewItems])
    expect(items.some((i) => (i as { key?: string }).key === 'sub-overview')).toBe(true)
  })

  it('后端新增的自定义分组键（不在内置表里）同样按 groups 成组、按 groups 取名', () => {
    const custom: MenuGroup[] = [{ key: 'reports', label: '报表', icon: 'FileTextOutlined' }]
    const one: MenuItem = { ...dashboard, key: 'export', path: '/export', category: 'reports' }
    const items = buildMenuItems([one], custom)
    expect(items[0]).toMatchObject({ key: 'sub-reports', label: '报表' })
    expect((items[0] as { children: unknown[] }).children).toHaveLength(1)
  })

  it('真实 registry：每个登记分组都成组，overview 只有 1 项也不再退化为顶层单项', () => {
    const menusSection = REGISTRY_SOURCE.slice(REGISTRY_SOURCE.indexOf('\nmenus:') + 1)
    const parsed: MenuItem[] = []
    for (const block of menusSection.split(/\n(?=\s*-\s*key:)/)) {
      const key = block.match(/^\s*-\s*key:\s*(\S+)/m)?.[1]
      const path = block.match(/\n\s+path:\s*(\S+)/)?.[1]
      if (!key || !path) continue
      parsed.push({
        key,
        label: block.match(/\n\s+label:\s*(.+)$/m)?.[1].trim() || key,
        path,
        icon: block.match(/\n\s+icon:\s*(\S+)/)?.[1] || '',
        sort_order: Number(block.match(/\n\s+sort_order:\s*(\d+)/)?.[1] ?? 0),
        visible: (block.match(/\n\s+default_visible:\s*(\S+)/)?.[1] ?? 'true') !== 'false',
        category: block.match(/\n\s+category:\s*(\S+)/)?.[1] || '',
      })
    }
    const groups: MenuGroup[] = [...REGISTRY_SOURCE.matchAll(/^  - key: (\S+)\n\s+label: (.+)$/gm)].map(
      (m) => ({ key: m[1], label: m[2].trim(), icon: '' }),
    )
    expect(parsed.length).toBeGreaterThan(10)

    const built = buildMenuItems(parsed, groups)
    const subKeys = built
      .filter((i) => Array.isArray((i as { children?: unknown[] }).children))
      .map((i) => (i as { key: string }).key)
    // 每个「有可见项」的登记分组都必须以 SubMenu 出现
    const expectedSubs = groups
      .filter((g) => parsed.some((m) => m.visible && m.category === g.key))
      .map((g) => `sub-${g.key}`)
    expect(subKeys).toEqual(expect.arrayContaining(expectedSubs))
    expect(subKeys).toContain('sub-overview')
    // overview 在 registry 里只有仪表盘一项——这正是本单修的退化点
    const overview = built.find((i) => (i as { key?: string }).key === 'sub-overview') as {
      label: string
      children: unknown[]
    }
    expect(overview.label).toBe('总览')
    expect(overview.children).toHaveLength(1)
    // 顶层只允许「不属于任何登记分组」的项（含 system 区）；登记分组的项不许裸放顶层
    const catByPath = new Map(parsed.map((m) => [m.path, m.category] as const))
    const registered = new Set(groups.map((g) => g.key))
    const topLevelLeaves = built
      .filter((i) => !('type' in i) && !Array.isArray((i as { children?: unknown[] }).children))
      .map((i) => (i as { key: string }).key)
    const offending = topLevelLeaves.filter((path) => registered.has(catByPath.get(path) || ''))
    expect(offending).toEqual([])
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
