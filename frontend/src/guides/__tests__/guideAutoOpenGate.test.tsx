/**
 * T02631：导览自动弹出的门不得再用「文档里任意 .page-container」
 *
 * 旧门 `document.querySelector('.page-container') === null → return` 有两个后果：
 * 1. MENU_GUIDES 29 条 route 里 7 条页面根本没有 `.page-container`，首访永远不弹；
 * 2. SheetWorkspace 多标签下后台 sheet 的旧 DOM 可能仍挂着同名节点，门反向误判通过。
 * 现在门只看激活 sheet 的内容根有没有子节点，页面没有 `.page-container` 是合法情形
 * （步骤目标查不到时由 resolveTourTarget 降级为居中气泡）。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { isPageRenderedForGuide } from '../autoOpenGate'
import { GuideController } from '../GuideController'
import { MENU_GUIDES } from '../menuGuides'
import { markGuideDone } from '../guideStorage'

// rAF 换成宏任务：测试要的是「下一帧再判」这个语义，不依赖 jsdom 的帧时序
vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) =>
  setTimeout(() => cb(Date.now()), 0) as unknown as number)
vi.stubGlobal('cancelAnimationFrame', (id: number) => clearTimeout(id))

function el(className: string, text: string): HTMLElement {
  const node = document.createElement('div')
  node.className = className
  node.textContent = text
  return node
}

/** 搭出激活 sheet 的内容根；children 为空串表示「容器在、页面还没渲染」 */
function mountArea(...children: HTMLElement[]): HTMLElement {
  const area = document.createElement('div')
  area.className = 'sheet-content-area'
  for (const child of children) area.appendChild(child)
  document.body.appendChild(area)
  return area
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <GuideController />
    </MemoryRouter>,
  )
}

/** 常驻悬浮按钮的 tooltip：用来确认控制器已挂载而 Tour 尚未弹出 */
async function waitForController() {
  await waitFor(() => {
    expect(document.querySelector('.ant-float-btn-group')).not.toBeNull()
  })
}

describe('isPageRenderedForGuide 门（纯函数）', () => {
  beforeEach(() => { document.body.innerHTML = '' })

  it('激活内容根已有子节点 → 放行（页面带不带 .page-container 都一样）', () => {
    expect(isPageRenderedForGuide(mountArea(el('cb-root', '客服')))).toBe(true)
    expect(isPageRenderedForGuide(mountArea(el('page-container', '仪表盘')))).toBe(true)
  })

  it('激活内容根还没有子节点 → 挡住，后台 sheet 残留同名节点也不放行', () => {
    const area = mountArea()
    // 旧实现会因为文档里存在 .page-container 而误判通过
    document.body.appendChild(el('page-container', '后台 sheet 残留'))
    expect(document.querySelector('.page-container')).not.toBeNull()
    expect(isPageRenderedForGuide(area.parentNode as ParentNode)).toBe(false)
  })

  it('不在 SheetWorkspace 内（无内容根）→ 不额外设门', () => {
    document.body.innerHTML = ''
    document.body.appendChild(el('page-container', '独立页'))
    expect(isPageRenderedForGuide()).toBe(true)
    document.body.innerHTML = ''
    document.body.appendChild(el('whatever', '什么都没有'))
    expect(isPageRenderedForGuide()).toBe(true)
  })
})

describe('GuideController 首访自动弹出', () => {
  beforeEach(() => {
    localStorage.clear()
    document.body.innerHTML = ''
  })
  afterEach(() => {
    cleanup()
    document.body.innerHTML = ''
  })

  it('页面无 .page-container 时（7 条受害 route 的形态）引导照样弹出', async () => {
    mountArea(el('ant-layout', '导出中心'))
    renderAt('/export')
    expect(await screen.findByText('数据导出')).toBeInTheDocument()
  })

  it('内容根尚未挂载子节点时不弹，避免弹在一堆旧节点上', async () => {
    mountArea()
    document.body.appendChild(el('page-container', '后台 sheet 残留'))
    renderAt('/export')
    await waitForController()
    expect(screen.queryByText('数据导出')).toBeNull()
  })

  it('已标记完成的路由不再自动弹出（门放行不等于每次都弹）', async () => {
    markGuideDone('/export')
    mountArea(el('ant-layout', '导出中心'))
    renderAt('/export')
    await waitForController()
    expect(screen.queryByText('数据导出')).toBeNull()
  })
})

describe('源码口径与配置事实（防退回假承诺）', () => {
  const controller = readFileSync(resolve(__dirname, '../GuideController.tsx'), 'utf-8')

  it('GuideController 不再拿 .page-container 当自动弹出的门', () => {
    expect(controller).not.toContain("document.querySelector('.page-container')")
    expect(controller).toContain('isPageRenderedForGuide()')
  })

  it('7 条无 .page-container 的 route 仍留在引导配置里（门放行后它们才谈得上弹）', () => {
    const routes = MENU_GUIDES.map((g) => g.route)
    for (const route of [
      '/anticrawl', '/chatbot', '/config/chatbot', '/export',
      '/maintenance/tunnel', '/menu-admin', '/price-dashboard',
    ]) {
      expect(routes, `route=${route} 缺引导配置`).toContain(route)
    }
  })
})
