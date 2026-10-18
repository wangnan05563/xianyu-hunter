import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { summarizeDryRunTasks } from '../DryRunBanner'
import { NARROW_MAX_PX, MOBILE_MEDIA_QUERY } from '../../../hooks/breakpoints'

// SheetWorkspace 布局与响应式守卫（T02562 / 2.7：横幅裁底、滚动重置、标签栏、断点统一）
const LAYOUT_SOURCE = readFileSync(resolve(__dirname, '../MainLayout.tsx'), 'utf-8')
const SHEET_CSS = readFileSync(resolve(__dirname, '../../SheetWorkspace/sheet.css'), 'utf-8')
const TABS_SOURCE = readFileSync(resolve(__dirname, '../../SheetWorkspace/SheetTabs.tsx'), 'utf-8')
const SHEET_NOTIFY_SOURCE = readFileSync(
  resolve(__dirname, '../../SheetWorkspace/sheetNotifications.tsx'),
  'utf-8',
)
const IS_MOBILE_SOURCE = readFileSync(resolve(__dirname, '../../../hooks/useIsMobile.ts'), 'utf-8')

describe('演练横幅文案折叠（2.7 维度4）', () => {
  it('同名任务去重，不再逐个拼接', () => {
    expect(summarizeDryRunTasks(['演练测试', '演练测试', '演练测试'])).toBe('演练测试（共 3 个任务）')
  })

  it('超过 3 个任务折叠为「A、B、C 等 N 个任务」', () => {
    const names = ['A', 'B', 'C', 'D', 'E']
    expect(summarizeDryRunTasks(names)).toBe('A、B、C 等 5 个任务')
  })

  it('不超上限时原名罗列', () => {
    expect(summarizeDryRunTasks(['甲', '乙'])).toBe('甲、乙')
  })

  it('结论前置：横幅正文先说不产生真实订单', () => {
    expect(LAYOUT_SOURCE).toContain('<DryRunBanner />')
    const banner = readFileSync(resolve(__dirname, '../DryRunBanner.tsx'), 'utf-8')
    const message = banner.match(/message=\{`([^`]+)`\}/)?.[1] ?? ''
    expect(message.indexOf('不产生真实订单')).toBeLessThan(message.indexOf('${summarize'))
  })
})

describe('横幅不再裁掉页面底部（2.7 维度3）', () => {
  it('Content 改为 flex 列', () => {
    expect(LAYOUT_SOURCE).toContain("display: 'flex', flexDirection: 'column'")
  })

  it('.sheet-workspace 用 flex:1 + min-height:0 取代 height:100%', () => {
    const block = SHEET_CSS.match(/\.sheet-workspace\s*\{[^}]*\}/)?.[0] ?? ''
    expect(block).toContain('flex: 1')
    expect(block).toContain('min-height: 0')
    expect(block).not.toContain('height: 100%')
  })
})

describe('滚动重置打到真实滚动容器（2.7 维度5）', () => {
  it('切路由时滚 .sheet-content-area，而不是 overflow:hidden 的 #main-content', () => {
    expect(LAYOUT_SOURCE).toContain("querySelector<HTMLElement>('.sheet-content-area')")
    expect(LAYOUT_SOURCE).not.toContain("getElementById('main-content')")
  })
})

describe('标签栏标题不再被裁（2.7 维度2）', () => {
  it('纵向标题上限放宽到 9 字，长标题仍有 title/Tooltip 兜住', () => {
    expect(TABS_SOURCE).toContain('maxHeight: 112')
    expect(TABS_SOURCE).not.toContain('maxHeight: 80')
    expect(TABS_SOURCE).toContain('title={sheet.title}')
  })

  it('替换通知写明上限与常驻入口（FR-B-7）', () => {
    expect(SHEET_NOTIFY_SOURCE).toContain('maxSheets')
    expect(SHEET_NOTIFY_SOURCE).toContain('回收栈')
    expect(SHEET_NOTIFY_SOURCE).toContain("placement: 'bottomRight'")
  })
})

describe('断点收敛为单一常量（2.7 维度3/6）', () => {
  it('常量口径：窄屏 768，移动端媒体查询取 767', () => {
    expect(NARROW_MAX_PX).toBe(768)
    expect(MOBILE_MEDIA_QUERY).toBe('(max-width: 767px)')
  })

  it('MainLayout 不再散落字面量 768', () => {
    expect(LAYOUT_SOURCE).toContain("import { isNarrowViewport } from '../../hooks/breakpoints'")
    expect(LAYOUT_SOURCE).not.toMatch(/innerWidth\s*<=\s*768/)
  })

  it('useIsMobile 从常量派生查询', () => {
    expect(IS_MOBILE_SOURCE).toContain('MOBILE_MEDIA_QUERY')
    expect(IS_MOBILE_SOURCE).not.toContain("'(max-width: 767px)'")
  })
})

describe('页面挂载层参与内容区高度分配（2.7 维度3 追加）', () => {
  const CONTENT_SOURCE = readFileSync(resolve(__dirname, '../../SheetWorkspace/SheetContent.tsx'), 'utf-8')

  it('.sheet-content-area 是 flex 列，页面挂载层可铺满', () => {
    const area = SHEET_CSS.match(/\.sheet-content-area\s*\{[^}]*\}/s)?.[0] ?? ''
    expect(area).toContain('display: flex')
    expect(SHEET_CSS).toContain('.sheet-page-mount')
    expect(CONTENT_SOURCE).toContain('fade-in-up sheet-page-mount')
  })

  it('客服页根布局不再用旧 Header 高度 56 反推视口', () => {
    const css = readFileSync(resolve(__dirname, '../../../pages/Chatbot/chatbot.css'), 'utf-8')
    const root = css.match(/根布局[\s\S]*?\.cb-root\s*\{[^}]*\}/)?.[0] ?? ''
    expect(root).toContain('height: 100%')
    // 仅剩 ≤768px 的移动端抽屉覆盖还在用 vh 反推（dvh + vh 兜底各一行），那处口径归 T02588
    expect((css.match(/:\s*calc\(100vh - 56px\)/g) ?? []).length).toBe(1)
  })
})
