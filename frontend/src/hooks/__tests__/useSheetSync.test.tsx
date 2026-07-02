import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { MemoryRouter, useLocation, useNavigate } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useSheetSync } from '../useSheetSync'
import { useSheetStore } from '../../stores/sheetStore'

// Mock sheetRegistry
vi.mock('../../components/SheetWorkspace/sheetRegistry', () => ({
  sheetRegistry: [
    { path: '/', title: '仪表盘', icon: null, component: null },
    { path: '/tasks', title: '任务管理', icon: null, component: null },
  ],
  findSheetMeta: (path: string) => {
    const items = [
      { path: '/', title: '仪表盘', icon: null, component: null },
      { path: '/tasks', title: '任务管理', icon: null, component: null },
    ]
    return items.find((i) => i.path === path)
  },
}))

// 测试用 wrapper：MemoryRouter 让 useLocation/useNavigate 可用
function makeWrapper(initialPath: string) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={[initialPath]}>
        {children}
      </MemoryRouter>
    )
  }
}

beforeEach(() => {
  useSheetStore.setState({
    sheets: [],
    activeId: null,
    preferences: { maxSheets: 5, enableAnimation: true, minimizeInsteadOfClose: false },
    isMobile: false,
    hydrated: true,
    _navigator: null,
  })
})

describe('useSheetSync', () => {
  it('URL path 对应的 sheet 未开时自动 openSheet', () => {
    const wrapper = makeWrapper('/tasks')
    renderHook(() => useSheetSync(), { wrapper })

    const state = useSheetStore.getState()
    expect(state.sheets).toHaveLength(1)
    expect(state.sheets[0].path).toBe('/tasks')
    expect(state.activeId).toBe(state.sheets[0].id)
  })

  it('URL path 与当前激活 sheet path 相同时不重复操作（防循环）', () => {
    // 预置已激活的 sheet，path 与 URL 一致
    useSheetStore.setState({
      sheets: [{ id: 's1', path: '/tasks', title: '任务管理', icon: null, minimized: false, openedAt: 1000 }],
      activeId: 's1',
    })
    const wrapper = makeWrapper('/tasks')
    renderHook(() => useSheetSync(), { wrapper })

    // 不应新增 sheet
    expect(useSheetStore.getState().sheets).toHaveLength(1)
  })

  it('URL 变化时同步到 sheet 栈', () => {
    // 通过 navigate 改变 URL（rerender 不会更新 wrapper，需用 router 自身能力切换路径）
    let navigate!: (path: string) => void
    const wrapper = makeWrapper('/tasks')
    renderHook(() => {
      navigate = useNavigate()
      useSheetSync()
    }, { wrapper })
    expect(useSheetStore.getState().sheets[0].path).toBe('/tasks')

    // 模拟路由变化：/tasks → /
    act(() => {
      navigate('/')
    })
    // 此时 URL 是 /，应开新 sheet 或激活已有
    const state = useSheetStore.getState()
    const homeSheet = state.sheets.find((s) => s.path === '/')
    expect(homeSheet).toBeDefined()
    expect(state.activeId).toBe(homeSheet!.id)
  })
})
