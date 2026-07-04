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
    _navigator: navigatorFn,
    // 回收栈独立于 sheets，必须显式重置，否则前一轮循环替换项会泄漏到本轮
    replacedHistory: [],
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

    describe('循环替换（circularReplaceEnabled）', () => {
      // 循环替换依赖 Date.now() 用于 openedAt 与 replacedAt
      // 用 Date.now spy 控制时间，避免依赖不可预测的递增
      let nowSpy: ReturnType<typeof vi.spyOn>
      let nowValue: number

      beforeEach(() => {
        nowValue = 1_000_000
        nowSpy = vi.spyOn(Date, 'now').mockImplementation(() => nowValue)
      })
      afterEach(() => {
        nowSpy.mockRestore()
      })

      // 工具：填充到上限（按时间顺序让 openedAt 严格递增，便于断言最旧）
      function fillToMax(max: number) {
        for (let i = 0; i < max; i++) {
          // 推进时间确保 openedAt 严格递增
          nowValue += 10
          useSheetStore.getState().openSheet(`/tasks/${i}`)
        }
        expect(useSheetStore.getState().sheets).toHaveLength(max)
      }

      it('circularReplaceEnabled=true 时达到上限自动淘汰最旧非激活 sheet', () => {
        useSheetStore.getState().setPreferences({ maxSheets: 3, circularReplaceEnabled: true })
        fillToMax(3)
        // sheets 按 openedAt 升序：[/tasks/0, /tasks/1, /tasks/2]
        // 当前激活是 /tasks/2（最后开的）
        const oldActiveId = useSheetStore.getState().activeId

        const result = useSheetStore.getState().openSheet('/')
        // 返回 ok + replacedSheet
        expect(result.ok).toBe(true)
        expect(result.replacedSheet).toBeDefined()
        expect(result.replacedSheet?.path).toBe('/tasks/0')
        // 栈仍为 3，新 sheet 是 /
        const sheets = useSheetStore.getState().sheets
        expect(sheets).toHaveLength(3)
        expect(sheets.find((s) => s.path === '/tasks/0')).toBeUndefined()
        expect(sheets.find((s) => s.path === '/')).toBeDefined()
        // 激活的 sheet（/tasks/2）应保留（保护激活 sheet）
        expect(sheets.find((s) => s.id === oldActiveId)).toBeDefined()
        // 新的 activeId 指向新 sheet
        expect(useSheetStore.getState().activeId).toBe(useSheetStore.getState().sheets.find((s) => s.path === '/')?.id)
        // 回收栈应包含被淘汰的项
        expect(useSheetStore.getState().replacedHistory[0].path).toBe('/tasks/0')
      })

      it('circularReplaceEnabled=false（默认）仍返回 limit（保持向后兼容）', () => {
        useSheetStore.getState().setPreferences({ maxSheets: 3, circularReplaceEnabled: false })
        fillToMax(3)
        const result = useSheetStore.getState().openSheet('/')
        expect(result).toEqual({ ok: false, reason: 'limit' })
        // replacedHistory 不应变化
        expect(useSheetStore.getState().replacedHistory).toHaveLength(0)
      })

      it('保护 activeId：非激活 sheet 中按 openedAt 升序选最旧', () => {
        useSheetStore.getState().setPreferences({ maxSheets: 3, circularReplaceEnabled: true })
        // 1) 开 3 个（按时间顺序：0, 1, 2；激活为 2）
        fillToMax(3)
        // 2) 激活 0（最早的），此时 0 是 activeId，1 和 2 是非激活
        const firstId = useSheetStore.getState().sheets.find((s) => s.path === '/tasks/0')!.id
        useSheetStore.getState().activateSheet(firstId)
        // 此时非激活的是 /tasks/1 (openedAt=中间) 和 /tasks/2 (openedAt=最新)
        // 循环替换应淘汰非激活中最旧的 /tasks/1，而不是 activeId 指向的 /tasks/0
        nowValue += 10
        const result = useSheetStore.getState().openSheet('/')
        expect(result.replacedSheet?.path).toBe('/tasks/1')
        // 激活的 /tasks/0 应保留
        const sheets = useSheetStore.getState().sheets
        expect(sheets.find((s) => s.path === '/tasks/0')).toBeDefined()
      })

      it('极端情况：所有 sheet 都是激活态时退回全体 openedAt 升序', () => {
        // 模拟 maxSheets=1 + 唯一 sheet 是 activeId
        useSheetStore.getState().setPreferences({ maxSheets: 1, circularReplaceEnabled: true })
        nowValue += 10
        useSheetStore.getState().openSheet('/tasks/0')
        expect(useSheetStore.getState().sheets).toHaveLength(1)
        expect(useSheetStore.getState().activeId).not.toBeNull()
        // 此时没有"非激活" sheet，应退回到全体替换
        nowValue += 10
        const result = useSheetStore.getState().openSheet('/')
        expect(result.ok).toBe(true)
        expect(result.replacedSheet?.path).toBe('/tasks/0')
        expect(useSheetStore.getState().sheets).toHaveLength(1)
        expect(useSheetStore.getState().sheets[0].path).toBe('/')
      })

      it('循环替换 FIFO 截断回收栈到最多 5 条', () => {
        useSheetStore.getState().setPreferences({ maxSheets: 2, circularReplaceEnabled: true })
        // 连续替换 7 次，每次淘汰最旧的
        // 注：每次新开 sheet 时它的 openedAt 是当前 nowValue，淘汰时按当前栈的 openedAt 升序选
        for (let i = 0; i < 7; i++) {
          nowValue += 10
          const r = useSheetStore.getState().openSheet(`/tasks/${i}`)
          expect(r.ok).toBe(true)
        }
        // 回收栈最多 5 条
        expect(useSheetStore.getState().replacedHistory).toHaveLength(5)
        // 栈仍为 2
        expect(useSheetStore.getState().sheets).toHaveLength(2)
      })

      it('path 已存在时仅激活，不触发 replacedSheet', () => {
        useSheetStore.getState().setPreferences({ maxSheets: 3, circularReplaceEnabled: true })
        fillToMax(3)
        // 第一个 sheet 的 path 已存在，再次 openSheet 不应替换
        const result = useSheetStore.getState().openSheet('/tasks/0')
        expect(result).toEqual({ ok: true })
        expect(result.replacedSheet).toBeUndefined()
        // sheets 数量不变
        expect(useSheetStore.getState().sheets).toHaveLength(3)
        // replacedHistory 不变
        expect(useSheetStore.getState().replacedHistory).toHaveLength(0)
      })

      it('移动端模式不受 circularReplaceEnabled 影响', () => {
        useSheetStore.setState({ isMobile: true })
        useSheetStore.getState().setPreferences({ maxSheets: 5, circularReplaceEnabled: true })
        // 移动端单 sheet 替换：连续开多个始终 1 个，不进回收栈
        for (let i = 0; i < 3; i++) {
          nowValue += 10
          const r = useSheetStore.getState().openSheet(`/tasks/${i}`)
          expect(r.ok).toBe(true)
          // 移动端不进入循环替换分支
          expect(r.replacedSheet).toBeUndefined()
        }
        expect(useSheetStore.getState().sheets).toHaveLength(1)
        expect(useSheetStore.getState().replacedHistory).toHaveLength(0)
      })
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

    it('doubleClickInterval 钳制到 [200, 800]', () => {
      useSheetStore.getState().setPreferences({ doubleClickInterval: 100 })
      expect(useSheetStore.getState().preferences.doubleClickInterval).toBe(200)
      useSheetStore.getState().setPreferences({ doubleClickInterval: 1000 })
      expect(useSheetStore.getState().preferences.doubleClickInterval).toBe(800)
    })

    it('doubleClickInterval 非法值回退默认 350', () => {
      useSheetStore.getState().setPreferences({ doubleClickInterval: NaN })
      expect(useSheetStore.getState().preferences.doubleClickInterval).toBe(350)
    })

    it('双击关闭与缩略图模式开关正常切换并持久化', () => {
      useSheetStore.getState().setPreferences({ doubleClickCloseEnabled: true, thumbnailMode: true })
      expect(useSheetStore.getState().preferences.doubleClickCloseEnabled).toBe(true)
      expect(useSheetStore.getState().preferences.thumbnailMode).toBe(true)
      act(() => { vi.advanceTimersByTime(300) })
      expect(storage.set).toHaveBeenCalledWith('xh.sheets.preferences', expect.objectContaining({
        doubleClickCloseEnabled: true,
        thumbnailMode: true,
      }))
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

    it('旧版本持久化数据缺失新字段时回退默认值', () => {
      // 模拟旧版本：仅含 maxSheets/enableAnimation/minimizeInsteadOfClose
      memoryStore.set('xh.sheets.preferences', JSON.stringify({
        __v: 1,
        data: { maxSheets: 4, enableAnimation: true, minimizeInsteadOfClose: false },
      }))
      useSheetStore.getState().hydrate()
      const prefs = useSheetStore.getState().preferences
      // 旧字段保留
      expect(prefs.maxSheets).toBe(4)
      expect(prefs.enableAnimation).toBe(true)
      // 新字段回退默认
      expect(prefs.doubleClickCloseEnabled).toBe(false)
      expect(prefs.doubleClickInterval).toBe(350)
      expect(prefs.thumbnailMode).toBe(false)
      expect(prefs.thumbnailTooltipEnabled).toBe(true)
    })

    it('恢复时 doubleClickInterval 超界会被钳制', () => {
      memoryStore.set('xh.sheets.preferences', JSON.stringify({
        __v: 1,
        data: { maxSheets: 5, doubleClickInterval: 5000 },
      }))
      useSheetStore.getState().hydrate()
      expect(useSheetStore.getState().preferences.doubleClickInterval).toBe(800)
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

  describe('restoreReplaced', () => {
    // 同样依赖 Date.now 控制时间
    let nowSpy: ReturnType<typeof vi.spyOn>
    let nowValue: number

    beforeEach(() => {
      nowValue = 1_000_000
      nowSpy = vi.spyOn(Date, 'now').mockImplementation(() => nowValue)
    })
    afterEach(() => {
      nowSpy.mockRestore()
    })

    // 工具：先开 2 个 sheet，然后开第 3 个触发循环替换
    function setupWithReplacedItem() {
      useSheetStore.getState().setPreferences({ maxSheets: 2, circularReplaceEnabled: true })
      nowValue += 10
      useSheetStore.getState().openSheet('/tasks/0')
      nowValue += 10
      useSheetStore.getState().openSheet('/tasks/1')
      nowValue += 10
      const result = useSheetStore.getState().openSheet('/')
      // /tasks/0 被淘汰
      const replaced = result.replacedSheet!
      return { replaced }
    }

    it('从回收栈恢复被替换的 sheet，生成新 id，保持原 openedAt', () => {
      const { replaced } = setupWithReplacedItem()
      navigatorFn.mockClear()
      const beforeCount = useSheetStore.getState().sheets.length

      const result = useSheetStore.getState().restoreReplaced(replaced.id)
      expect(result.ok).toBe(true)
      const state = useSheetStore.getState()
      // 栈数量 +1
      expect(state.sheets).toHaveLength(beforeCount + 1)
      // 找到恢复的 sheet（path 是 /tasks/0）
      const restored = state.sheets.find((s) => s.path === '/tasks/0')!
      expect(restored).toBeDefined()
      // id 是新生成的（不与原 id 相同）
      expect(restored.id).not.toBe(replaced.id)
      // openedAt 保持原 replacedAt（保持时间顺序）
      expect(restored.openedAt).toBe(replaced.replacedAt)
      // activeId 指向新 sheet
      expect(state.activeId).toBe(restored.id)
      // 回收栈移除
      expect(state.replacedHistory.find((r) => r.id === replaced.id)).toBeUndefined()
      // navigate 到恢复的 path
      expect(navigatorFn).toHaveBeenCalledWith('/tasks/0')
    })

    it('id 不存在时返回 not_found', () => {
      const result = useSheetStore.getState().restoreReplaced('nonexistent-id')
      expect(result).toEqual({ ok: false, reason: 'not_found' })
    })

    it('栈满时恢复仍允许（撤销动作不应被拒绝，可能临时超 maxSheets）', () => {
      useSheetStore.getState().setPreferences({ maxSheets: 2, circularReplaceEnabled: true })
      nowValue += 10
      useSheetStore.getState().openSheet('/tasks/0')
      nowValue += 10
      useSheetStore.getState().openSheet('/tasks/1')
      nowValue += 10
      const r1 = useSheetStore.getState().openSheet('/')
      // 此时栈满（2 个），回收栈有 1 个被淘汰项
      // 恢复（撤销）应直接成功，不应循环替换
      const result = useSheetStore.getState().restoreReplaced(r1.replacedSheet!.id)
      expect(result.ok).toBe(true)
      // sheets 临时为 3（超 maxSheets=2），下次 openSheet 会再触发循环替换平衡
      expect(useSheetStore.getState().sheets).toHaveLength(3)
      // 回收栈移除该条
      expect(useSheetStore.getState().replacedHistory).toHaveLength(0)
    })

    it('被恢复的 path 已重新存在于栈时：仅激活现有那个 + 从回收栈移除', () => {
      const { replaced } = setupWithReplacedItem()
      // 此时栈中是 /tasks/1, /，已满（maxSheets=2）
      // 先关闭一项腾出空间，避免重新 openSheet 触发循环替换污染回收栈
      const homeId = useSheetStore.getState().sheets.find((s) => s.path === '/')!.id
      useSheetStore.getState().closeSheet(homeId)
      expect(useSheetStore.getState().sheets).toHaveLength(1)
      // 重新打开 /tasks/0（不触发循环替换，因为未达上限）
      useSheetStore.getState().openSheet('/tasks/0')
      expect(useSheetStore.getState().sheets).toHaveLength(2)
      expect(useSheetStore.getState().sheets.find((s) => s.path === '/tasks/0')).toBeDefined()
      // 回收栈不变（仍是 setup 时的 1 项）
      expect(useSheetStore.getState().replacedHistory).toHaveLength(1)
      // 现在调用 restoreReplaced：应只激活现有的 /tasks/0，不重复创建
      const result = useSheetStore.getState().restoreReplaced(replaced.id)
      expect(result.ok).toBe(true)
      // sheets 仍为 2（/tasks/0 + /tasks/1）
      expect(useSheetStore.getState().sheets).toHaveLength(2)
      // activeId 是 /tasks/0 的 id
      const existing = useSheetStore.getState().sheets.find((s) => s.path === '/tasks/0')!
      expect(useSheetStore.getState().activeId).toBe(existing.id)
      // 回收栈移除
      expect(useSheetStore.getState().replacedHistory).toHaveLength(0)
    })

    it('registry 中已不存在的 path 返回 not_found', () => {
      const { replaced } = setupWithReplacedItem()
      // 模拟 path 已不在 registry：手动注入一个"幽灵"项
      const ghostId = 'ghost-id'
      useSheetStore.setState({
        replacedHistory: [
          { id: ghostId, path: '/removed-path', title: '已删除', replacedAt: Date.now() },
          ...useSheetStore.getState().replacedHistory,
        ],
      })
      const result = useSheetStore.getState().restoreReplaced(ghostId)
      // 找不到 meta → not_found
      expect(result).toEqual({ ok: false, reason: 'not_found' })
    })
  })

  describe('clearReplacedHistory', () => {
    it('清空回收栈', () => {
      useSheetStore.getState().setPreferences({ maxSheets: 2, circularReplaceEnabled: true })
      useSheetStore.getState().openSheet('/tasks/0')
      useSheetStore.getState().openSheet('/tasks/1')
      const r = useSheetStore.getState().openSheet('/')
      expect(useSheetStore.getState().replacedHistory).toHaveLength(1)

      useSheetStore.getState().clearReplacedHistory()
      expect(useSheetStore.getState().replacedHistory).toHaveLength(0)
      // 验证 r 仍可访问（变量提示）
      expect(r.replacedSheet).toBeDefined()
    })
  })

  describe('hydrate 兼容 circularReplaceEnabled 字段', () => {
    it('旧版本持久化数据缺失 circularReplaceEnabled 时回退默认 false', () => {
      // 模拟旧版本偏好：仅含 maxSheets（无 circularReplaceEnabled）
      memoryStore.set('xh.sheets.preferences', JSON.stringify({
        __v: 1,
        data: { maxSheets: 4, enableAnimation: true, minimizeInsteadOfClose: false },
      }))
      useSheetStore.getState().hydrate()
      expect(useSheetStore.getState().preferences.circularReplaceEnabled).toBe(false)
    })

    it('新版本持久化数据保留 circularReplaceEnabled=true', () => {
      memoryStore.set('xh.sheets.preferences', JSON.stringify({
        __v: 1,
        data: {
          maxSheets: 5,
          enableAnimation: true,
          minimizeInsteadOfClose: false,
          circularReplaceEnabled: true,
        },
      }))
      useSheetStore.getState().hydrate()
      expect(useSheetStore.getState().preferences.circularReplaceEnabled).toBe(true)
    })
  })
})
