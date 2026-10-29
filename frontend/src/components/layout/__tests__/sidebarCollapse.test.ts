import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { collapseByUser, collapseOnResize, expandByUser, initialCollapseState } from '../sidebarCollapse'
import { NARROW_DESKTOP_MAX_PX, NARROW_MAX_PX, isNarrowDesktopViewport } from '../../../hooks/breakpoints'

// 源码守卫：resize 监听必须走 collapseOnResize 这个决策，且旧的「只收不放」不能回来。
// 与 firstScreenLoading.test.tsx 读 MainLayout 源码的做法一致——纯函数覆盖不到接线错误。
const LAYOUT_SOURCE = readFileSync(resolve(__dirname, '../MainLayout.tsx'), 'utf-8')

// T02632 条目 1：侧栏收起原本是单向的——窗口拉宽后不自动展开（实测 768→900px 停在 64px）。
// 改成对称，但只撤销「系统因窗口窄而自己收起的那次」；用户手动开合代表显式意图，不覆盖。

describe('侧栏收起的对称恢复（条目 1）', () => {
  it('变窄：自动收起并记住这次收起是系统做的', () => {
    expect(collapseOnResize(initialCollapseState(false), true)).toEqual({
      collapsed: true,
      autoCollapsed: true,
    })
  })

  it('拉宽：撤销系统自己做过的那次收起', () => {
    const narrow = collapseOnResize(initialCollapseState(false), true)
    expect(collapseOnResize(narrow, false)).toEqual({ collapsed: false, autoCollapsed: false })
  })

  it('首屏就是窄窗（收起态由宽度造成）时，拉宽同样恢复——实测那条路径', () => {
    const atMount = initialCollapseState(true)
    expect(atMount).toEqual({ collapsed: true, autoCollapsed: true })
    expect(collapseOnResize(atMount, false).collapsed).toBe(false)
  })

  it('用户自己收起后拉宽：不擅自展开（显式意图优先）', () => {
    const userCollapsed = collapseByUser(initialCollapseState(false))
    expect(collapseOnResize(userCollapsed, false)).toEqual({ collapsed: true, autoCollapsed: false })
  })

  it('用户手动展开过：反复跨断点仍回到他选的那一面', () => {
    let state = collapseOnResize(initialCollapseState(false), true) // 系统收起
    state = expandByUser(state) // 用户手动展开（仍在窄窗）
    expect(state.autoCollapsed).toBe(false)
    const widened = collapseOnResize(state, false) // 拉宽：用户本就展开，保持
    expect(widened).toEqual({ collapsed: false, autoCollapsed: false })
    // 再窄回去是系统收起，再宽回来把系统那次撤掉——最终仍是用户选择的展开态
    const narrowedAgain = collapseOnResize(widened, true)
    expect(narrowedAgain).toEqual({ collapsed: true, autoCollapsed: true })
    expect(collapseOnResize(narrowedAgain, false)).toEqual({ collapsed: false, autoCollapsed: false })
  })

  it('已经收起时再变窄不重复打标记（避免把用户自己收起的记成系统的）', () => {
    const state = collapseByUser(initialCollapseState(false))
    expect(collapseOnResize(state, true)).toBe(state)
  })
})

describe('桌面窄窗判定（沿用 breakpoints 单源）', () => {
  it('边界：768 属移动端档，769–992 属桌面窄窗，993 起不算', () => {
    expect(isNarrowDesktopViewport(NARROW_MAX_PX)).toBe(false)
    expect(isNarrowDesktopViewport(NARROW_MAX_PX + 1)).toBe(true)
    expect(isNarrowDesktopViewport(NARROW_DESKTOP_MAX_PX)).toBe(true)
    expect(isNarrowDesktopViewport(NARROW_DESKTOP_MAX_PX + 1)).toBe(false)
  })
})

describe('MainLayout 接线（纯函数覆盖不到的部分）', () => {
  it('resize 监听走 collapseOnResize，旧的「只在变窄时收起」已删除', () => {
    expect(LAYOUT_SOURCE).toContain('collapseOnResize(prev, isNarrowViewport())')
    expect(LAYOUT_SOURCE).not.toContain('if (isNarrowViewport()) setCollapsed(true)')
    // 首屏收起态由 initialCollapseState 生成，别再写回裸布尔
    expect(LAYOUT_SOURCE).toContain('initialCollapseState(isNarrowViewport())')
  })
})
