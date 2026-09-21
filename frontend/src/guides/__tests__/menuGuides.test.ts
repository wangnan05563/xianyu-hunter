import { describe, it, expect } from 'vitest'
import {
  MENU_GUIDES,
  GUIDE_ROUTES,
  findMenuGuide,
} from '../menuGuides'

describe('menuGuides 配置完整性', () => {
  it('至少为三分之一的业务页面提供引导', () => {
    // 覆盖度断言：引导配置数量应足够覆盖主要业务菜单（不强制全量，保证主流程可用）
    expect(MENU_GUIDES.length).toBeGreaterThanOrEqual(20)
  })

  it('每个引导流程至少包含一条步骤', () => {
    for (const g of MENU_GUIDES) {
      expect(g.steps.length, `route=${g.route} 缺步骤`).toBeGreaterThanOrEqual(1)
    }
  })

  it('每条步骤都有标题与说明', () => {
    for (const g of MENU_GUIDES) {
      for (const s of g.steps) {
        expect(s.title, `route=${g.route} 步骤缺标题`).toBeTruthy()
        expect(s.description, `route=${g.route} 步骤缺说明`).toBeTruthy()
      }
    }
  })

  it('route 唯一（无重复键）', () => {
    const routes = MENU_GUIDES.map((g) => g.route)
    expect(new Set(routes).size).toBe(routes.length)
  })

  it('GUIDE_ROUTES 与 MENU_GUIDES 同步', () => {
    expect(GUIDE_ROUTES).toEqual(MENU_GUIDES.map((g) => g.route))
  })

  it('所有页面首选步骤使用 .page-container 作为页面总览高亮目标', () => {
    // 约定：第一个步骤用于覆盖主体容器，确保至少有一个稳定可高亮目标
    for (const g of MENU_GUIDES) {
      expect(
        g.steps[0].selector,
        `route=${g.route} 首选步骤未使用 .page-container`,
      ).toBe('.page-container')
    }
  })
})

describe('findMenuGuide 路由匹配', () => {
  it('精确匹配路由', () => {
    const guide = findMenuGuide('/tasks')
    expect(guide?.route).toBe('/tasks')
  })

  it('动态路由 /tasks/:id 匹配具体 id', () => {
    const guide = findMenuGuide('/tasks/abc-123')
    expect(guide?.route).toBe('/tasks/:id')
  })

  it('未配置的路由返回 undefined', () => {
    expect(findMenuGuide('/login')).toBeUndefined()
    expect(findMenuGuide('/not-exist')).toBeUndefined()
  })

  it('动态路由不会误匹配深层路径', () => {
    // /tasks/:id 应匹配 /tasks/123，但不应匹配 /tasks/123/edit（那是另一条路由）
    expect(findMenuGuide('/tasks/123/edit')?.route).not.toBe('/tasks/:id')
  })
})