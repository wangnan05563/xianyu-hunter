import { describe, it, expect, beforeAll, beforeEach, vi, afterEach } from 'vitest'
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

// antd Drawer/Grid 等组件内部依赖 responsiveObserver → window.matchMedia
// jsdom 默认不提供 matchMedia，必须 mock 否则 Drawer 打开时报错
beforeAll(() => {
  if (!window.matchMedia) {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      configurable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(() => false),
      })),
    })
  }
})

beforeEach(() => {
  mockState.isMobile = false
  // 重置 store：避免测试间状态泄漏
  useSheetStore.setState({
    sheets: [],
    activeId: null,
    preferences: {
      maxSheets: 5,
      enableAnimation: true,
      minimizeInsteadOfClose: false,
      doubleClickCloseEnabled: false,
      doubleClickInterval: 350,
      thumbnailMode: false,
      thumbnailTooltipEnabled: true,
      circularReplaceEnabled: false,
    },
    isMobile: false,
    hydrated: false,
    _navigator: null,
    replacedHistory: [],
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

  describe('双击关闭', () => {
    // 双击关闭依赖 Date.now() 时间戳判定
    // 为什么用 Date.now spy 而非 vi.useFakeTimers：避免干扰 React 内部调度
    let nowSpy: ReturnType<typeof vi.spyOn>
    let nowValue: number

    beforeEach(() => {
      nowValue = 1000
      nowSpy = vi.spyOn(Date, 'now').mockImplementation(() => nowValue)
    })
    afterEach(() => {
      nowSpy.mockRestore()
    })

    it('启用双击关闭后，快速双击激活 tab 触发关闭', async () => {
      const { container } = renderSheetWorkspace('/tasks')
      await screen.findByText('任务管理')
      // 再打开一个 sheet，避免栈空时 closeSheet 跳转 '/' 触发 useSheetSync 重新打开
      act(() => {
        useSheetStore.getState().openSheet('/items')
      })
      act(() => {
        useSheetStore.getState().setPreferences({ doubleClickCloseEnabled: true, doubleClickInterval: 350 })
      })
      expect(useSheetStore.getState().sheets).toHaveLength(2)
      // 当前激活 /items
      const tabEl = container.querySelector('.sheet-tab-active') as HTMLElement
      expect(tabEl).toBeTruthy()
      // 第一击
      fireEvent.click(tabEl)
      // 推进 100ms（间隔内）
      nowValue += 100
      fireEvent.click(tabEl)
      // /items 被关闭，剩 /tasks
      const state = useSheetStore.getState()
      expect(state.sheets).toHaveLength(1)
      expect(state.sheets[0].path).toBe('/tasks')
    })

    it('双击间隔超过阈值时不触发关闭', async () => {
      const { container } = renderSheetWorkspace('/tasks')
      await screen.findByText('任务管理')
      act(() => {
        useSheetStore.getState().setPreferences({ doubleClickCloseEnabled: true, doubleClickInterval: 300 })
      })
      const tabEl = container.querySelector('.sheet-tab-active') as HTMLElement
      fireEvent.click(tabEl)
      // 间隔 400ms > 阈值 300ms
      nowValue += 400
      fireEvent.click(tabEl)
      expect(useSheetStore.getState().sheets).toHaveLength(1)
    })

    it('未启用双击关闭时单击仅激活，双击不关闭', async () => {
      const { container } = renderSheetWorkspace('/tasks')
      await screen.findByText('任务管理')
      // 默认 doubleClickCloseEnabled=false
      const tabEl = container.querySelector('.sheet-tab-active') as HTMLElement
      fireEvent.click(tabEl)
      nowValue += 100
      fireEvent.click(tabEl)
      expect(useSheetStore.getState().sheets).toHaveLength(1)
    })

    // I2 回归测试：双击关闭与 minimizeInsteadOfClose 偏好的组合行为
    // 为什么单独覆盖：onClose 在容器层根据偏好分发为 minimize 或 close，
    // 双击路径同样经过 onClose，必须验证偏好生效，避免回归成"双击总是真关闭"
    it('minimizeInsteadOfClose=true 时双击触发最小化而非关闭', async () => {
      const { container } = renderSheetWorkspace('/tasks')
      await screen.findByText('任务管理')
      act(() => {
        useSheetStore.getState().openSheet('/items')
      })
      // 同时启用双击关闭与"关闭即最小化"偏好
      act(() => {
        useSheetStore.getState().setPreferences({
          doubleClickCloseEnabled: true,
          doubleClickInterval: 350,
          minimizeInsteadOfClose: true,
        })
      })
      expect(useSheetStore.getState().sheets).toHaveLength(2)
      // 当前激活 /items
      const itemsSheet = useSheetStore.getState().sheets.find((s) => s.path === '/items')!
      const tabEl = container.querySelector('.sheet-tab-active') as HTMLElement
      expect(tabEl).toBeTruthy()
      // 双击
      fireEvent.click(tabEl)
      nowValue += 100
      fireEvent.click(tabEl)
      const state = useSheetStore.getState()
      // 关键断言：sheet 仍在栈中（未被关闭），但被最小化
      expect(state.sheets).toHaveLength(2)
      const minimizedSheet = state.sheets.find((s) => s.id === itemsSheet.id)
      expect(minimizedSheet?.minimized).toBe(true)
    })
  })

  describe('缩略图模式', () => {
    it('启用缩略图模式后容器宽度收窄', async () => {
      const { container } = renderSheetWorkspace('/tasks')
      await screen.findByText('任务管理')
      const tabsEl = container.querySelector('.sheet-tabs') as HTMLElement
      // 标准模式宽度 80px
      expect(tabsEl.style.width).toBe('80px')
      act(() => {
        useSheetStore.getState().setPreferences({ thumbnailMode: true })
      })
      // 缩略图模式宽度 56px
      expect(tabsEl.style.width).toBe('56px')
    })

    it('缩略图模式下不渲染纵向标题', async () => {
      const { container } = renderSheetWorkspace('/tasks')
      await screen.findByText('任务管理')
      act(() => {
        useSheetStore.getState().setPreferences({ thumbnailMode: true })
      })
      // 缩略图模式只有图标，标题不渲染为纵向文字
      const verticalTitles = container.querySelectorAll('[style*="writing-mode"]')
      expect(verticalTitles.length).toBe(0)
    })

    it('缩略图模式可切换至禁用悬浮提示', async () => {
      const { container } = renderSheetWorkspace('/tasks')
      await screen.findByText('任务管理')
      act(() => {
        useSheetStore.getState().setPreferences({ thumbnailMode: true, thumbnailTooltipEnabled: false })
      })
      // 禁用 Tooltip 后不应渲染 .ant-tooltip 触发器包裹层（仅渲染 .sheet-tab）
      // 这里验证缩略图 div 仍存在即可（Tooltip 关闭时直接返回 tabContent）
      const tabEl = container.querySelector('.sheet-tab') as HTMLElement
      expect(tabEl).toBeTruthy()
    })

    // C1 回归测试：缩略图模式激活态必须有可点击的关闭按钮
    // 为什么单独覆盖：此前缩略图分支完全省略关闭按钮，双击关闭禁用时用户无法关闭 sheet
    it('缩略图模式激活态显示关闭按钮，点击后关闭当前 sheet', async () => {
      const { container } = renderSheetWorkspace('/tasks')
      await screen.findByText('任务管理')
      act(() => {
        useSheetStore.getState().openSheet('/items')
      })
      act(() => {
        // 双击关闭保持禁用（默认值），确保关闭路径只能走关闭按钮
        useSheetStore.getState().setPreferences({ thumbnailMode: true })
      })
      // 激活 tab（/items）上应存在缩略图关闭按钮
      const closeBtn = container.querySelector('[data-testid="sheet-thumbnail-close"]') as HTMLElement
      expect(closeBtn).toBeTruthy()
      fireEvent.click(closeBtn)
      // /items 被关闭，剩 /tasks
      const state = useSheetStore.getState()
      expect(state.sheets).toHaveLength(1)
      expect(state.sheets[0].path).toBe('/tasks')
    })

    it('缩略图模式非激活 tab 不渲染关闭按钮', async () => {
      const { container } = renderSheetWorkspace('/tasks')
      await screen.findByText('任务管理')
      act(() => {
        useSheetStore.getState().openSheet('/items')
      })
      act(() => {
        useSheetStore.getState().setPreferences({ thumbnailMode: true })
      })
      // 当前激活 /items，仅激活态有关闭按钮 → 全局应只有 1 个
      const closeBtns = container.querySelectorAll('[data-testid="sheet-thumbnail-close"]')
      expect(closeBtns.length).toBe(1)
    })
  })

  describe('循环替换状态徽标', () => {
    it('circularReplaceEnabled=true 时标签栏顶部显示状态指示', async () => {
      const { container } = renderSheetWorkspace('/tasks')
      await screen.findByText('任务管理')
      // 默认 false：徽标不显示
      expect(container.querySelector('[data-testid="sheet-circular-indicator"]')).toBeNull()
      // 开启后显示
      act(() => {
        useSheetStore.getState().setPreferences({ circularReplaceEnabled: true })
      })
      const indicator = container.querySelector('[data-testid="sheet-circular-indicator"]')
      expect(indicator).toBeTruthy()
      // 徽标内的 SwapOutlined 图标存在
      expect(indicator?.querySelector('.anticon-swap')).toBeTruthy()
    })

    it('circularReplaceEnabled=false 时不显示状态徽标（默认）', async () => {
      const { container } = renderSheetWorkspace('/tasks')
      await screen.findByText('任务管理')
      expect(container.querySelector('[data-testid="sheet-circular-indicator"]')).toBeNull()
    })

    it('循环替换触发后状态徽标持续显示（状态指示是偏好，不是临时状态）', async () => {
      const { container } = renderSheetWorkspace('/tasks')
      useSheetStore.getState().setPreferences({ maxSheets: 2, circularReplaceEnabled: true })
      await screen.findByText('任务管理')
      // 开第 2、3 个 sheet 触发循环替换
      act(() => { useSheetStore.getState().openSheet('/items') })
      act(() => { useSheetStore.getState().openSheet('/') })
      // 徽标仍应显示（用户应能继续识别"循环替换"是开启的）
      const indicator = container.querySelector('[data-testid="sheet-circular-indicator"]')
      expect(indicator).toBeTruthy()
    })
  })

  describe('回收栈 UI', () => {
    it('替换产生历史项后，偏好面板中显示回收栈入口', async () => {
      renderSheetWorkspace('/tasks')
      useSheetStore.getState().setPreferences({ maxSheets: 2, circularReplaceEnabled: true })
      await screen.findByText('任务管理')
      // 触发循环替换
      act(() => { useSheetStore.getState().openSheet('/items') })
      act(() => { useSheetStore.getState().openSheet('/') })
      // 打开偏好设置：偏好按钮在标签栏 .sheet-tabs 最后一个子 div
      const prefBtn = document.body.querySelector('.sheet-tabs > div:last-child button') as HTMLElement
      fireEvent.click(prefBtn)
      // 回收栈标题出现
      expect(await screen.findByText('回收栈')).toBeInTheDocument()
      // Drawer 内容用 Portal 渲染到 document.body → 在 document 上查询 data-testid
      const items = document.body.querySelectorAll('[data-testid="replaced-sheet-item"]')
      expect(items.length).toBeGreaterThan(0)
      const paths = Array.from(items).map((el) => (el as HTMLElement).dataset.sheetPath)
      expect(paths).toContain('/tasks')
      // 文本中包含标题「任务管理」
      expect(items[0].textContent).toContain('任务管理')
    })
  })
})
