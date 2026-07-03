import { describe, it, expect } from 'vitest'
import { sheetRegistry, findSheetMeta } from '../sheetRegistry'

describe('sheetRegistry', () => {
  it('注册了所有叶子路由 path（与 App.tsx 对齐）', () => {
    const expectedPaths = [
      '/',
      '/tasks',
      '/tasks/new',
      '/tasks/:id',
      '/tasks/:id/edit',
      '/items',
      '/orders',
      '/evaluations',
      '/timeline',
      '/logs',
      '/logs/errors',
      '/config/price',
      '/config/eval',
      '/config/notifier',
      '/config/version',
      '/config/ai',
      '/config/search',
      '/config/buyer',
      '/config/chatbot',
      '/maintenance',
      '/maintenance/db',
      '/maintenance/vector',
      '/batch-refresh',
      '/anticrawl',
      '/chatbot',
      '/about',
      '/help',
    ]
    const registeredPaths = sheetRegistry.map((s) => s.path).sort()
    expectedPaths.sort().forEach((p) => {
      expect(registeredPaths).toContain(p)
    })
  })

  it('findSheetMeta 精确匹配', () => {
    expect(findSheetMeta('/tasks')?.title).toBe('任务管理')
    expect(findSheetMeta('/')?.title).toBe('仪表盘')
  })

  it('findSheetMeta 对 :param 通配匹配', () => {
    expect(findSheetMeta('/tasks/123')?.title).toBe('任务详情')
    expect(findSheetMeta('/tasks/123/edit')?.title).toBe('编辑任务')
  })

  it('findSheetMeta 精确匹配优先于通配', () => {
    expect(findSheetMeta('/tasks/new')?.title).toBe('新建任务')
  })

  it('findSheetMeta 未匹配返回 undefined', () => {
    expect(findSheetMeta('/nonexistent/path')).toBeUndefined()
  })

  it('每项都有 title、icon、component', () => {
    for (const item of sheetRegistry) {
      expect(typeof item.title).toBe('string')
      expect(item.title.length).toBeGreaterThan(0)
      expect(item.icon).toBeDefined()
      expect(item.component).toBeDefined()
    }
  })
})
