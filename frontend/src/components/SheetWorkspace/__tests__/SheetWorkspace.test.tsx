import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { App } from 'antd'

// hoisted state：vi.mock 工厂引用的变量必须 hoisted，否则 ReferenceError
const mockState = vi.hoisted(() => ({ isMobile: false }))

// Mock lazyRetry：避免真实 chunk 加载，用 React.lazy 包装被 mock 的页面组件
// 为什么用 async 工厂：工厂中不能直接 import React（hoisting 时机问题），用 dynamic import
vi.mock('../../../utils/lazyRetry', async () => {
  const { lazy, createElement, Fragment } = await import('react')
  return {
    lazyRetry: (factory: () => Promise<any>) => lazy(factory),
    LazyErrorBoundary: ({ children }: { children: any }) => createElement(Fragment, null, children),
    isChunkLoadError: () => false,
  }
})

// Mock 页面组件（测试只渲染 /tasks, /, /items 三个路径）
vi.mock('../../../pages/Dashboard', () => ({
  default: () => <div data-testid="page-dashboard">Dashboard Page</div>,
}))
vi.mock('../../../pages/Tasks/TaskList', () => ({
  default: () => <div data-testid="page-tasks">TaskList Page</div>,
}))
vi.mock('../../../pages/Items/ItemList', () => ({
  default: () => <div data-testid="page-items">ItemList Page</div>,
}))

// Mock useIsMobile：默认桌面端，测试中通过 mockState.isMobile 切换
vi.mock('../../../hooks/useIsMobile', () => ({
  useIsMobile: () => mockState.isMobile,
}))

import { SheetWorkspace } from '../index'
import { useSheetStore } from '../../../stores/sheetStore'

function renderSheetWorkspace(initialPath = '/') {
  return render(
    <App>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/*" element={<SheetWorkspace />} />
        </Routes>
      </MemoryRouter>
    </App>,
  )
}

beforeEach(() => {
  mockState.isMobile = false
  // 重置 store：避免测试间状态泄漏
  useSheetStore.setState({
    sheets: [],
    activeId: null,
    preferences: { maxSheets: 5, enableAnimation: true, minimizeInsteadOfClose: false },
    isMobile: false,
    hydrated: false,
    _navigator: null,
  })
})

afterEach(() => {
  vi.clearAllMocks()
  vi.clearAllTimers()
})

describe('SheetWorkspace', () => {
  it('空状态显示提示', () => {
    // 访问不在 registry 中的路径，openSheet 返回 not_found，sheets 保持空
    renderSheetWorkspace('/nonexistent')
    expect(screen.getByText('未打开任何页面，请从左侧菜单选择')).toBeInTheDocument()
  })

  it('桌面端渲染标签栏', async () => {
    renderSheetWorkspace('/tasks')
    // useSheetSync 自动打开 /tasks sheet，标签栏渲染"任务管理"标题
    expect(await screen.findByText('任务管理')).toBeInTheDocument()
  })

  it('点击 Tab 切换激活', async () => {
    renderSheetWorkspace('/tasks')
    await screen.findByText('任务管理')
    // 再打开 / sheet
    act(() => {
      useSheetStore.getState().openSheet('/')
    })
    // 两个 tab 都应渲染
    expect(screen.getByText('任务管理')).toBeInTheDocument()
    expect(screen.getByText('仪表盘')).toBeInTheDocument()
    // 当前激活的是 /，点击任务管理 tab 切换
    fireEvent.click(screen.getByText('任务管理'))
    const state = useSheetStore.getState()
    const activeSheet = state.sheets.find((s) => s.id === state.activeId)
    expect(activeSheet?.path).toBe('/tasks')
  })

  it('点击关闭按钮关闭 sheet', async () => {
    const { container } = renderSheetWorkspace('/tasks')
    await screen.findByText('任务管理')
    // 再打开 /items sheet
    act(() => {
      useSheetStore.getState().openSheet('/items')
    })
    expect(screen.getByText('商品列表')).toBeInTheDocument()
    // 当前激活 /items，点击关闭按钮（激活 tab 中的 danger button）
    const closeBtn = container.querySelector('.sheet-tab-active .ant-btn-dangerous') as HTMLElement
    expect(closeBtn).toBeTruthy()
    fireEvent.click(closeBtn)
    // /items 被关闭，剩 /tasks
    expect(useSheetStore.getState().sheets).toHaveLength(1)
    expect(useSheetStore.getState().sheets[0].path).toBe('/tasks')
  })

  it('未达上限时可继续打开新 sheet', async () => {
    renderSheetWorkspace('/tasks')
    await screen.findByText('任务管理')
    // 设置 maxSheets=3，已打开 1 个，还可打开 2 个
    act(() => {
      useSheetStore.getState().setPreferences({ maxSheets: 3 })
    })
    let result: { ok: boolean; reason?: string } | undefined
    act(() => {
      result = useSheetStore.getState().openSheet('/')
    })
    expect(result?.ok).toBe(true)
    expect(useSheetStore.getState().sheets).toHaveLength(2)
  })

  it('打开偏好设置面板', async () => {
    const { container } = renderSheetWorkspace('/tasks')
    await screen.findByText('任务管理')
    // 偏好设置按钮在 .sheet-tabs 的最后一个子 div 中（SheetTabs 底部）
    const prefBtn = container.querySelector('.sheet-tabs > div:last-child button') as HTMLElement
    expect(prefBtn).toBeTruthy()
    fireEvent.click(prefBtn)
    // Drawer 打开，显示偏好设置表单
    expect(await screen.findByText('最大 Sheet 数量')).toBeInTheDocument()
  })
})
