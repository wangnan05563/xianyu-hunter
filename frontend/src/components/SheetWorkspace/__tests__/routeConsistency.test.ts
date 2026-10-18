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
