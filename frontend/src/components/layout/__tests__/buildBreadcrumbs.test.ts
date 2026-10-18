import { describe, it, expect } from 'vitest'
import { buildBreadcrumbs } from '../breadcrumb'
import type { MenuItem } from '../../../api/menu'

// 面包屑纯函数单测（T02559 / 2.4）：过去只有「首页 > 当前页」两级，
// 分组层缺失、详情页无法回列表、菜单外的路径直接只剩「首页」。
function item(over: Partial<MenuItem> & Pick<MenuItem, 'key' | 'path' | 'label'>): MenuItem {
  return {
    icon: 'AppstoreOutlined',
    sort_order: 0,
    visible: true,
    category: 'data_view',
    ...over,
  }
}

const MENUS: MenuItem[] = [
  item({ key: 'dashboard', path: '/', label: '仪表盘', category: 'overview' }),
  item({ key: 'tasks', path: '/tasks', label: '任务管理', category: 'data_view' }),
  item({ key: 'logs', path: '/logs', label: '实时日志', category: 'data_view' }),
  item({ key: 'error_logs', path: '/logs/errors', label: '错误日志', category: 'data_view' }),
  item({ key: 'ai_config', path: '/config/ai', label: 'AI 服务', category: 'config' }),
]

describe('buildBreadcrumbs', () => {
  it('首页只有一级', () => {
    expect(buildBreadcrumbs('/', MENUS)).toEqual([{ label: '首页', href: '/', current: true }])
  })

  it('分组页补出「分组 > 页面」两级，分组名来自菜单 category', () => {
    expect(buildBreadcrumbs('/config/ai', MENUS)).toEqual([
      { label: '首页', href: '/' },
      { label: '配置管理' },
      { label: 'AI 服务', current: true },
    ])
  })

  it('详情页父级可点回所属列表', () => {
    const crumbs = buildBreadcrumbs('/tasks/123', MENUS)
    expect(crumbs.map((c) => c.label)).toEqual(['首页', '数据查看', '任务管理', '任务详情'])
    expect(crumbs[2].href).toBe('/tasks')
    expect(crumbs[3].current).toBe(true)
  })

  it('/logs/errors 命中自身而非前缀 /logs', () => {
    const crumbs = buildBreadcrumbs('/logs/errors', MENUS)
    expect(crumbs.at(-1)?.label).toBe('错误日志')
    expect(crumbs).toHaveLength(3)
  })

  it('菜单里没有的路径用 sheet 标题兜底，不再只剩「首页」', () => {
    const crumbs = buildBreadcrumbs('/confirm-buy', MENUS)
    expect(crumbs).toHaveLength(2)
    expect(crumbs[1]).toEqual({ label: '确认抢单', current: true })
  })

  it('完全未知的路径显示「独立页面」，且首页仍可点', () => {
    const crumbs = buildBreadcrumbs('/no-such-page', MENUS)
    expect(crumbs[1]).toEqual({ label: '独立页面', current: true })
    expect(crumbs[0].href).toBe('/')
  })

  it('菜单未加载时不崩，退化为「首页 > 页面名」两级', () => {
    // 页面名取自 sheetRegistry 兜底，菜单还在加载时也不会只剩一个「首页」
    expect(buildBreadcrumbs('/config/ai', [])).toEqual([
      { label: '首页', href: '/' },
      { label: 'AI 服务', current: true },
    ])
  })
})
