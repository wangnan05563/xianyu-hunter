/**
 * T01713 回归测试：导览步骤目标解析
 *
 * 背景（用户反馈「导览对话框在左上角显示，边缘被截断」）：
 * 旧实现把 `document.querySelector()` 的结果直接放进 useMemo，得到静态 DOM 引用。
 * SPA 内路由切换时 useMemo 重算发生在 React 提交之前，命中「即将卸载的旧页面节点」；
 * 提交后该节点脱离文档，rc-tour 取 getBoundingClientRect() 得到全 0，
 * 按 placement=bottom 算出 ≈(x:-34, y:18) —— 气泡跑到左上角且左边缘被裁切。
 *
 * 本文件锁死修复后的三条契约：
 * 1. target 必须是**惰性函数**（DOM 变化后重新解析，不持有已卸载节点）；
 * 2. 查不到 / 已脱离文档 / 尚无布局 → 返回 null（antd 走居中）；
 * 3. 整页容器（尺寸 ≥ 视口 90%）→ 返回 null（避免 scrollIntoView 把气泡甩出视口）。
 */
import { describe, it, expect, beforeAll, afterEach } from 'vitest'
import { resolveTourTarget, MAX_TARGET_VIEWPORT_RATIO } from '../target'

/** 视口尺寸固定，避免依赖 jsdom 默认值（默认 1024×768） */
const VIEW_W = 1024
const VIEW_H = 768

type TargetResolver = () => HTMLElement | null

/** 取出惰性解析函数并断言其为函数（顺带收窄类型） */
function asResolver(target: ReturnType<typeof resolveTourTarget>): TargetResolver {
  expect(typeof target).toBe('function')
  return target as unknown as TargetResolver
}

/** jsdom 不做布局，getBoundingClientRect 恒为 0 —— 需显式注入可预测尺寸 */
function stubRect(el: Element, width: number, height: number, x = 0, y = 0): void {
  el.getBoundingClientRect = () =>
    ({
      x,
      y,
      width,
      height,
      top: y,
      left: x,
      right: x + width,
      bottom: y + height,
      toJSON: () => ({}),
    }) as DOMRect
}

/** 造一个命中 selector 的页面容器元素（默认尺寸落在「可高亮」区间） */
function mountPage(className = 'page-container', width = 800, height = 300): HTMLElement {
  const el = document.createElement('div')
  el.className = className
  stubRect(el, width, height)
  document.body.appendChild(el)
  return el
}

beforeAll(() => {
  Object.defineProperty(window, 'innerWidth', { value: VIEW_W, configurable: true })
  Object.defineProperty(window, 'innerHeight', { value: VIEW_H, configurable: true })
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('resolveTourTarget', () => {
  it('未配置 selector 时返回 undefined（antd 视为无目标 → 居中）', () => {
    expect(resolveTourTarget()).toBeUndefined()
    expect(resolveTourTarget(undefined)).toBeUndefined()
  })

  it('selector 查不到元素时返回 null（居中兜底，不抛错）', () => {
    const resolve = asResolver(resolveTourTarget('.missing-element'))
    expect(resolve()).toBeNull()
  })

  it('命中元素且尺寸正常时返回该元素（保留高亮定位能力）', () => {
    const page = mountPage()
    const resolve = asResolver(resolveTourTarget('.page-container'))
    expect(resolve()).toBe(page)
  })

  it('元素尺寸为 0（尚未布局）时返回 null，避免用 0 rect 算出越界坐标', () => {
    mountPage('page-container', 0, 0)
    const resolve = asResolver(resolveTourTarget('.page-container'))
    expect(resolve()).toBeNull()
  })

  it('元素虽可查询但已脱离文档时返回 null', () => {
    const detached = document.createElement('div')
    detached.className = 'page-container'
    stubRect(detached, 800, 300)
    // 刻意不 appendChild：isConnected 为 false 时不应被当作有效目标
    const resolve = asResolver(resolveTourTarget('.page-container'))
    expect(detached.isConnected).toBe(false)
    expect(resolve()).toBeNull()
  })

  it('整页容器（高度 ≥ 视口 90%）降级为居中，避免 scrollIntoView 把气泡甩出视口', () => {
    mountPage('page-container', 800, Math.ceil(VIEW_H * MAX_TARGET_VIEWPORT_RATIO))
    const resolve = asResolver(resolveTourTarget('.page-container'))
    expect(resolve()).toBeNull()
  })

  it('超宽容器（宽度 ≥ 视口 90%）同样降级为居中', () => {
    mountPage('page-container', Math.ceil(VIEW_W * MAX_TARGET_VIEWPORT_RATIO), 200)
    const resolve = asResolver(resolveTourTarget('.page-container'))
    expect(resolve()).toBeNull()
  })

  it('恰好低于阈值的小元素仍保留高亮（不误伤真实功能块）', () => {
    const card = mountPage('quick-entry-card', 256, 125)
    const resolve = asResolver(resolveTourTarget('.quick-entry-card'))
    expect(resolve()).toBe(card)
  })

  it('返回惰性函数：路由切换后重新解析，不持有已卸载的旧页面节点（T01713 回归）', () => {
    const oldPage = mountPage()
    const resolve = asResolver(resolveTourTarget('.page-container'))
    expect(resolve()).toBe(oldPage)

    // 模拟 SPA 路由切换：旧页面卸载 → 新页面挂载
    oldPage.remove()
    const newPage = mountPage()

    // 若实现退化为「渲染期快照」，这里仍会返回已卸载的 oldPage → 气泡左边缘被裁切
    expect(resolve()).toBe(newPage)
  })

  it('旧节点已卸载、新节点尚未挂载的中间态返回 null（而非 0 尺寸节点）', () => {
    const oldPage = mountPage()
    const resolve = asResolver(resolveTourTarget('.page-container'))
    expect(resolve()).toBe(oldPage)

    oldPage.remove()
    expect(resolve()).toBeNull()
  })
})
