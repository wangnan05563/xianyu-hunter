import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { act } from '@testing-library/react'
import { useSheetStore } from '../sheetStore'
import { storage } from '../../utils/storage'

// Mock storage：用内存 Map 模拟，避免真实 localStorage 干扰
const memoryStore = new Map<string, string>()
vi.mock('../../utils/storage', () => ({
  storage: {
    get: vi.fn(<T>(key: string, defaultValue: T) => {
      const raw = memoryStore.get(key)
      if (!raw) return defaultValue
      try { return (JSON.parse(raw).data ?? defaultValue) as T } catch { return defaultValue }
    }),
    set: vi.fn((key: string, value: unknown) => {
      memoryStore.set(key, JSON.stringify({ __v: 1, data: value }))
      return true
    }),
    remove: vi.fn((key: string) => { memoryStore.delete(key) }),
    isAvailable: vi.fn(() => true),
  },
}))

// Mock sheetRegistry：避免引入真实懒加载组件
vi.mock('../../components/SheetWorkspace/sheetRegistry', () => ({
  sheetRegistry: [
    { path: '/', title: '仪表盘', icon: null, component: null },
    { path: '/tasks', title: '任务管理', icon: null, component: null },
    { path: '/tasks/:id', title: '任务详情', icon: null, component: null },
  ],
  findSheetMeta: (path: string) => {
    const items = [
      { path: '/', title: '仪表盘', icon: null, component: null },
      { path: '/tasks', title: '任务管理', icon: null, component: null },
      { path: '/tasks/:id', title: '任务详情', icon: null, component: null },
    ]
    if (items.find((i) => i.path === path)) return items.find((i) => i.path === path)
    return items.find((i) => i.path.includes(':') && new RegExp('^' + i.path.replace(/:[^/]+/g, '[^/]+') + '$').test(path))
  },
}))

let navigatorFn: ReturnType<typeof vi.fn>

beforeEach(() => {
  memoryStore.clear()
  vi.clearAllMocks()
  vi.useFakeTimers()
  navigatorFn = vi.fn()
  // 每个测试前重置 store 到初始状态
  useSheetStore.setState({
    sheets: [],
    activeId: null,
    preferences: { maxSheets: 5, enableAnimation: true, minimizeInsteadOfClose: false },
    isMobile: false,
    hydrated: false,
    _navigator: navigatorFn,
  })
})

afterEach(() => {
  vi.useRealTimers()
})

describe('sheetStore', () => {
  describe('openSheet', () => {
    it('新 path 开新 sheet 并激活，navigate 同步 URL', () => {
      const result = useSheetStore.getState().openSheet('/tasks')
      expect(result).toEqual({ ok: true })
      const state = useSheetStore.getState()
      expect(state.sheets).toHaveLength(1)
      expect(state.sheets[0].path).toBe('/tasks')
      expect(state.sheets[0].title).toBe('任务管理')
      expect(state.activeId).toBe(state.sheets[0].id)
      expect(navigatorFn).toHaveBeenCalledWith('/tasks')
    })

    it('已存在的 path 不重复打开，仅激活', () => {
      useSheetStore.getState().openSheet('/tasks')
      const firstId = useSheetStore.getState().sheets[0].id
      navigatorFn.mockClear()

      const result = useSheetStore.getState().openSheet('/tasks')
      expect(result).toEqual({ ok: true })
      expect(useSheetStore.getState().sheets).toHaveLength(1)
      expect(useSheetStore.getState().activeId).toBe(firstId)
      expect(navigatorFn).toHaveBeenCalledWith('/tasks')
    })

    it('达到 maxSheets 上限时阻止并返回 reason: limit', () => {
      // 预置 5 个 sheet
      for (let i = 0; i < 5; i++) {
        useSheetStore.getState().openSheet(`/tasks/${i}`)
      }
      expect(useSheetStore.getState().sheets).toHaveLength(5)

      const result = useSheetStore.getState().openSheet('/items')
      expect(result).toEqual({ ok: false, reason: 'limit' })
      expect(useSheetStore.getState().sheets).toHaveLength(5)
    })

    it('registry 中不存在的 path 返回 not_found', () => {
      const result = useSheetStore.getState().openSheet('/nonexistent')
      expect(result).toEqual({ ok: false, reason: 'not_found' })
      expect(useSheetStore.getState().sheets).toHaveLength(0)
    })

    it('触发持久化（防抖 300ms）', () => {
      useSheetStore.getState().openSheet('/tasks')
      // 防抖期间不应写入
      expect(storage.set).not.toHaveBeenCalled()
      act(() => { vi.advanceTimersByTime(300) })
      expect(storage.set).toHaveBeenCalledWith('xh.sheets.state', expect.objectContaining({
        sheets: expect.arrayContaining([expect.objectContaining({ path: '/tasks' })]),
      }))
    })

    it('移动端模式下：已有激活 sheet 且新 path 不同时替换（不累计栈）', () => {
      useSheetStore.setState({ isMobile: true })
      useSheetStore.getState().openSheet('/tasks')
      expect(useSheetStore.getState().sheets).toHaveLength(1)

      useSheetStore.getState().openSheet('/')
      // 移动端单 sheet：替换而非累计
      expect(useSheetStore.getState().sheets).toHaveLength(1)
      expect(useSheetStore.getState().sheets[0].path).toBe('/')
    })

    it('移动端模式下不受 maxSheets 限制', () => {
      useSheetStore.setState({ isMobile: true, preferences: { maxSheets: 5, enableAnimation: true, minimizeInsteadOfClose: false } })
      // 连续开多个，每次替换，始终 1 个
      for (let i = 0; i < 10; i++) {
        const r = useSheetStore.getState().openSheet(`/tasks/${i}`)
        expect(r.ok).toBe(true)
      }
      expect(useSheetStore.getState().sheets).toHaveLength(1)
    })
  })

  describe('closeSheet', () => {
    it('关闭非激活项：仅移除，activeId 不变', () => {
      useSheetStore.getState().openSheet('/tasks')
      useSheetStore.getState().openSheet('/')
      const tasksId = useSheetStore.getState().sheets[0].id
      const homeId = useSheetStore.getState().sheets[1].id
      // 当前激活 home
      expect(useSheetStore.getState().activeId).toBe(homeId)
      navigatorFn.mockClear()

      useSheetStore.getState().closeSheet(tasksId)
      expect(useSheetStore.getState().sheets).toHaveLength(1)
      expect(useSheetStore.getState().activeId).toBe(homeId)
      // 关闭非激活项不触发 navigate
      expect(navigatorFn).not.toHaveBeenCalled()
    })

    it('关闭激活项：激活右侧相邻 sheet 并 navigate', () => {
      useSheetStore.getState().openSheet('/tasks')
      useSheetStore.getState().openSheet('/')
      // 栈顺序：[tasks, home]，激活 home
      const homeId = useSheetStore.getState().sheets[1].id
      navigatorFn.mockClear()

      useSheetStore.getState().closeSheet(homeId)
      // 关闭激活项后应激活右侧相邻（无右侧则左侧），这里 home 是最后一个，应激活 tasks
      expect(useSheetStore.getState().sheets).toHaveLength(1)
      expect(useSheetStore.getState().sheets[0].path).toBe('/tasks')
      expect(useSheetStore.getState().activeId).toBe(useSheetStore.getState().sheets[0].id)
      expect(navigatorFn).toHaveBeenCalledWith('/tasks')
    })

    it('栈空时 activeId 为 null', () => {
      useSheetStore.getState().openSheet('/tasks')
      const id = useSheetStore.getState().sheets[0].id
      navigatorFn.mockClear()

      useSheetStore.getState().closeSheet(id)
      expect(useSheetStore.getState().sheets).toHaveLength(0)
      expect(useSheetStore.getState().activeId).toBeNull()
      expect(navigatorFn).toHaveBeenCalledWith('/')
    })
  })

  describe('activateSheet', () => {
    it('切换激活并 navigate 到该 sheet path', () => {
      useSheetStore.getState().openSheet('/tasks')
      useSheetStore.getState().openSheet('/')
      const tasksId = useSheetStore.getState().sheets[0].id
      navigatorFn.mockClear()

      useSheetStore.getState().activateSheet(tasksId)
      expect(useSheetStore.getState().activeId).toBe(tasksId)
      expect(navigatorFn).toHaveBeenCalledWith('/tasks')
    })
  })

  describe('minimizeSheet / restoreSheet', () => {
    it('最小化激活项：自动激活下一个非最小化 sheet', () => {
      useSheetStore.getState().openSheet('/tasks')
      useSheetStore.getState().openSheet('/')
      const homeId = useSheetStore.getState().sheets[1].id
      navigatorFn.mockClear()

      useSheetStore.getState().minimizeSheet(homeId)
      const state = useSheetStore.getState()
      const minimized = state.sheets.find((s) => s.id === homeId)
      expect(minimized?.minimized).toBe(true)
      // 应激活 tasks（唯一非最小化）
      expect(state.activeId).toBe(state.sheets[0].id)
      expect(navigatorFn).toHaveBeenCalledWith('/tasks')
    })

    it('恢复最小化项：不自动激活', () => {
      useSheetStore.getState().openSheet('/tasks')
      const id = useSheetStore.getState().sheets[0].id
      useSheetStore.getState().minimizeSheet(id)
      // 栈空后 activeId 为 null
      expect(useSheetStore.getState().activeId).toBeNull()

      useSheetStore.getState().restoreSheet(id)
      expect(useSheetStore.getState().sheets[0].minimized).toBe(false)
      // 不自动激活
      expect(useSheetStore.getState().activeId).toBeNull()
    })
  })

  describe('setPreferences', () => {
    it('动态更新偏好并持久化', () => {
      useSheetStore.getState().setPreferences({ maxSheets: 3 })
      expect(useSheetStore.getState().preferences.maxSheets).toBe(3)
      act(() => { vi.advanceTimersByTime(300) })
      expect(storage.set).toHaveBeenCalledWith('xh.sheets.preferences', expect.objectContaining({ maxSheets: 3 }))
    })

    it('maxSheets 钳制到 [1, 10]', () => {
      useSheetStore.getState().setPreferences({ maxSheets: 0 })
      expect(useSheetStore.getState().preferences.maxSheets).toBe(1)
      useSheetStore.getState().setPreferences({ maxSheets: 99 })
      expect(useSheetStore.getState().preferences.maxSheets).toBe(10)
    })
  })

  describe('hydrate', () => {
    it('从 localStorage 恢复 sheets + activeId + preferences', () => {
      const savedState = {
        sheets: [{ id: 's1', path: '/tasks', title: '任务管理', minimized: false, openedAt: 1000 }],
        activeId: 's1',
      }
      memoryStore.set('xh.sheets.state', JSON.stringify({ __v: 1, data: savedState }))
      memoryStore.set('xh.sheets.preferences', JSON.stringify({ __v: 1, data: { maxSheets: 7, enableAnimation: false, minimizeInsteadOfClose: true } }))

      useSheetStore.getState().hydrate()
      const state = useSheetStore.getState()
      expect(state.hydrated).toBe(true)
      expect(state.sheets).toHaveLength(1)
      expect(state.sheets[0].path).toBe('/tasks')
      expect(state.sheets[0].icon).toBeDefined() // icon 从 registry 重建
      expect(state.activeId).toBe('s1')
      expect(state.preferences.maxSheets).toBe(7)
      expect(state.preferences.enableAnimation).toBe(false)
    })

    it('path 已不在 registry 的 sheet 静默丢弃', () => {
      const savedState = {
        sheets: [
          { id: 's1', path: '/tasks', title: '任务管理', minimized: false, openedAt: 1000 },
          { id: 's2', path: '/removed-page', title: '已删除', minimized: false, openedAt: 2000 },
        ],
        activeId: 's2',
      }
      memoryStore.set('xh.sheets.state', JSON.stringify({ __v: 1, data: savedState }))

      useSheetStore.getState().hydrate()
      const state = useSheetStore.getState()
      // /removed-page 被丢弃
      expect(state.sheets).toHaveLength(1)
      expect(state.sheets[0].path).toBe('/tasks')
      // activeId 指向被丢弃的项 → 重置为剩余最后一个或 null
      expect(state.activeId).toBe('s1')
    })

    it('脏数据/解析失败回退默认空状态', () => {
      memoryStore.set('xh.sheets.state', 'not-json')
      useSheetStore.getState().hydrate()
      const state = useSheetStore.getState()
      expect(state.sheets).toHaveLength(0)
      expect(state.activeId).toBeNull()
      expect(state.preferences.maxSheets).toBe(5) // 默认
      expect(state.hydrated).toBe(true)
    })
  })

  describe('persist 字段过滤', () => {
    it('不持久化 icon（ReactNode）', () => {
      useSheetStore.getState().openSheet('/tasks')
      act(() => { vi.advanceTimersByTime(300) })
      const setCall = (storage.set as ReturnType<typeof vi.fn>).mock.calls.find(
        (c: unknown[]) => c[0] === 'xh.sheets.state',
      )
      const persisted = setCall![1] as { sheets: Array<{ path: string; icon?: unknown }> }
      // 持久化对象不应包含 icon 字段
      expect(persisted.sheets[0].icon).toBeUndefined()
    })
  })

  describe('closeAll', () => {
    it('清空所有 sheet，activeId 为 null', () => {
      useSheetStore.getState().openSheet('/tasks')
      useSheetStore.getState().openSheet('/')
      navigatorFn.mockClear()

      useSheetStore.getState().closeAll()
      expect(useSheetStore.getState().sheets).toHaveLength(0)
      expect(useSheetStore.getState().activeId).toBeNull()
      // closeAll 不 navigate（用于登出场景，由调用方负责跳转）
      expect(navigatorFn).not.toHaveBeenCalled()
    })
  })

  describe('setMobileMode', () => {
    it('切换 isMobile 标志', () => {
      useSheetStore.getState().setMobileMode(true)
      expect(useSheetStore.getState().isMobile).toBe(true)
      useSheetStore.getState().setMobileMode(false)
      expect(useSheetStore.getState().isMobile).toBe(false)
    })
  })

  describe('setNavigator', () => {
    it('注入 navigator 函数供 store 内部 navigate 调用', () => {
      const fn = vi.fn()
      useSheetStore.getState().setNavigator(fn)
      useSheetStore.getState().openSheet('/tasks')
      expect(fn).toHaveBeenCalledWith('/tasks')
    })
  })
})
