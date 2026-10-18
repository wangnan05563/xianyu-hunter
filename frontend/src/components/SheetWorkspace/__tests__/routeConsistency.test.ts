import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { sheetRegistry } from '../sheetRegistry'

// 一致性守卫（T02584/FR-A-2）：sheetRegistry 里每个可打开的路径，App.tsx 必须有对应 <Route>。
// 缺路由时 URL 会落到兜底分支，菜单点开却是「回到首页」——价格行情、数据导出就是这么丢的。
// 用源码文本比对而非运行时匹配：路由表是 JSX 声明，无法在测试里安全求值。
const APP_SOURCE = readFileSync(resolve(__dirname, '../../../App.tsx'), 'utf-8')

function declaredRoutePaths(source: string): Set<string> {
  const paths = new Set<string>()
  for (const m of source.matchAll(/<Route\s+path="([^"]*)"/g)) {
    const raw = m[1]
    // 子路由 path 不带前导斜杠（挂在 <Route path="/"> 下），统一补齐后再比对
    paths.add(raw.startsWith('/') ? raw : `/${raw}`)
  }
  if (/<Route\s+index\b/.test(source)) paths.add('/')
  return paths
}

describe('sheetRegistry ↔ App.tsx 路由表一致性', () => {
  const routes = declaredRoutePaths(APP_SOURCE)

  it('sheetRegistry 的每个路径都有已声明的路由', () => {
    const missing = sheetRegistry
      .map((s) => s.path)
      .filter((p) => !routes.has(p))
    expect(missing).toEqual([])
  })

  it('价格行情与数据导出这两条已注册菜单可达', () => {
    for (const p of ['/price-dashboard', '/export']) {
      expect(sheetRegistry.some((s) => s.path === p)).toBe(true)
      expect(routes.has(p)).toBe(true)
    }
  })

  it('路由表不再把未知路径静默送回首页', () => {
    expect(APP_SOURCE).not.toMatch(/<Route path="\*" element=\{<Navigate to="\/" replace \/>/)
  })
})

// 入口完整性守卫（T02557/2.2）：反向检查——页面已实现却没有菜单入口，就是「隐藏页面」。
// 历史教训：向量库维护、菜单管理、帮助文档都有路由、有 sheet 注册，但菜单里点不到，
// 只能靠命令面板或手敲 URL 进入，等价于功能不存在。
// 允许表只收「参数化/整页路由」两类不该进左侧菜单的页面，新增项必须显式登记理由。
const REGISTRY_SOURCE = readFileSync(
  resolve(__dirname, '../../../../../config/menu_registry.yaml'),
  'utf-8',
)
const REGISTRY_PATHS = new Set(
  [...REGISTRY_SOURCE.matchAll(/^\s+path:\s*(\S+)\s*$/gm)].map((m) => m[1]),
)
const NO_MENU_ENTRY = new Set([
  '/tasks/new', // 任务新建：从任务列表按钮进入，带表单上下文
  '/tasks/:id', // 详情页：需 :id 参数
  '/tasks/:id/edit', // 编辑页：需 :id 参数
  '/confirm-buy', // 确认抢单：由通知回链带 item_id 打开
])

describe('sheetRegistry ↔ menu_registry.yaml 入口完整性', () => {
  it('每个已实现页面都有菜单入口，或显式登记为免菜单页', () => {
    const orphans = sheetRegistry
      .map((s) => s.path)
      .filter((p) => !REGISTRY_PATHS.has(p) && !NO_MENU_ENTRY.has(p))
    expect(orphans).toEqual([])
  })

  it('菜单项指向的页面都已在 sheetRegistry 注册', () => {
    const registered = new Set(sheetRegistry.map((s) => s.path))
    const dead = [...REGISTRY_PATHS].filter((p) => !registered.has(p))
    expect(dead).toEqual([])
  })

  it('历史隐藏页（向量库/菜单管理/帮助）均已补入口', () => {
    for (const p of ['/maintenance/vector', '/menu-admin', '/help']) {
      expect(REGISTRY_PATHS.has(p), `${p} 缺菜单入口`).toBe(true)
    }
  })
})
