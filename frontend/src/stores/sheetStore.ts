import { create } from 'zustand'
import type { ReactNode } from 'react'
import { storage } from '../utils/storage'
import { findSheetMeta } from '../components/SheetWorkspace/sheetRegistry'
import type { SheetMeta } from '../components/SheetWorkspace/sheetRegistry'

export interface SheetItem {
  /** 唯一 ID（path + 打开时间戳，用于稳定 React key） */
  id: string
  /** 路由路径，如 '/tasks' 或 '/tasks/123' */
  path: string
  /** 标签栏标题（运行时从 registry 重建，不持久化） */
  title: string
  /** 标签栏图标（运行时从 registry 重建，不持久化） */
  icon: ReactNode
  /** 是否最小化（最小化后不渲染内容） */
  minimized: boolean
  /** 打开时间戳（FIFO 排序与调试） */
  openedAt: number
}

export interface SheetPreferences {
  /** 最大 sheet 数，范围 [1,10]，默认 5 */
  maxSheets: number
  /** 动画开关，默认 true */
  enableAnimation: boolean
  /** 关闭按钮行为：true=最小化 false=直接关闭，默认 false */
  minimizeInsteadOfClose: boolean
  /** 双击关闭开关：默认 false（保守默认，避免误触关闭未保存数据） */
  doubleClickCloseEnabled: boolean
  /** 双击判定间隔毫秒，范围 [200,800]，默认 350 */
  doubleClickInterval: number
  /** 缩略图模式：true=仅显示图标紧凑布局，默认 false */
  thumbnailMode: boolean
  /** 缩略图悬浮提示开关：默认 true */
  thumbnailTooltipEnabled: boolean
}

const DEFAULT_PREFERENCES: SheetPreferences = {
  maxSheets: 5,
  enableAnimation: true,
  minimizeInsteadOfClose: false,
  doubleClickCloseEnabled: false,
  doubleClickInterval: 350,
  thumbnailMode: false,
  thumbnailTooltipEnabled: true,
}

const STATE_KEY = 'xh.sheets.state'
const PREFS_KEY = 'xh.sheets.preferences'

interface PersistedState {
  sheets: Array<Omit<SheetItem, 'title' | 'icon'>>
  activeId: string | null
}

interface SheetState {
  sheets: SheetItem[]
  activeId: string | null
  preferences: SheetPreferences
  isMobile: boolean
  hydrated: boolean
  /** 注入的 navigate 函数（由 SheetWorkspace 通过 useNavigate 注入） */
  _navigator: ((path: string) => void) | null

  openSheet: (path: string) => { ok: boolean; reason?: 'limit' | 'not_found' }
  closeSheet: (id: string) => void
  activateSheet: (id: string) => void
  minimizeSheet: (id: string) => void
  restoreSheet: (id: string) => void
  closeAll: () => void
  setPreferences: (patch: Partial<SheetPreferences>) => void
  setMobileMode: (isMobile: boolean) => void
  setNavigator: (fn: (path: string) => void) => void
  hydrate: () => void
  /** 防抖持久化（内部调用） */
  persist: () => void
}

// 防抖定时器引用（模块级，跨 set 调用保持）
let persistTimer: ReturnType<typeof setTimeout> | null = null
const PERSIST_DEBOUNCE_MS = 300

function navigate(state: SheetState, path: string) {
  state._navigator?.(path)
}

/** 钳制 maxSheets 到 [1, 10] */
function clampMaxSheets(n: number): number {
  if (!Number.isInteger(n)) return DEFAULT_PREFERENCES.maxSheets
  return Math.max(1, Math.min(10, n))
}

/** 钳制 doubleClickInterval 到 [200, 800]，避免过短无效或过长误判 */
function clampDoubleClickInterval(n: number): number {
  if (!Number.isFinite(n)) return DEFAULT_PREFERENCES.doubleClickInterval
  return Math.max(200, Math.min(800, Math.round(n)))
}

/** 从 registry 重建 sheet 元数据（icon/title） */
function rebuildSheetMeta(path: string): { title: string; icon: ReactNode } | null {
  const meta: SheetMeta | undefined = findSheetMeta(path)
  if (!meta) return null
  return { title: meta.title, icon: meta.icon }
}

export const useSheetStore = create<SheetState>((set, get) => ({
  sheets: [],
  activeId: null,
  preferences: DEFAULT_PREFERENCES,
  isMobile: false,
  hydrated: false,
  _navigator: null,

  openSheet: (path) => {
    const state = get()

    // 已存在同 path → 仅激活（优先于 limit：用户点击已存在 tab 应激活而非拒绝）
    const existing = state.sheets.find((s) => s.path === path)
    if (existing) {
      const next: SheetState = { ...state, activeId: existing.id }
      set({ activeId: existing.id })
      navigate(next, path)
      get().persist()
      return { ok: true }
    }

    // 桌面端：检查上限（先于 registry，避免无谓查找；测试约定栈满时优先返回 limit）
    if (!state.isMobile && state.sheets.length >= state.preferences.maxSheets) {
      return { ok: false, reason: 'limit' }
    }

    const meta = findSheetMeta(path)
    if (!meta) return { ok: false, reason: 'not_found' }

    // 移动端单 sheet 模式：替换当前激活 sheet
    if (state.isMobile && state.activeId) {
      const current = state.sheets.find((s) => s.id === state.activeId)
      if (current && current.path !== path) {
        // 关闭当前，不触发级联 navigate（仅替换，由下方新 sheet 统一 navigate）
        const newSheets = state.sheets.filter((s) => s.id !== state.activeId)
        const newSheet: SheetItem = {
          id: `${path}-${Date.now()}`,
          path,
          title: meta.title,
          icon: meta.icon,
          minimized: false,
          openedAt: Date.now(),
        }
        const next: SheetState = { ...state, sheets: [...newSheets, newSheet], activeId: newSheet.id }
        set({ sheets: [...newSheets, newSheet], activeId: newSheet.id })
        navigate(next, path)
        get().persist()
        return { ok: true }
      }
    }

    // 新建 sheet
    const newSheet: SheetItem = {
      id: `${path}-${Date.now()}`,
      path,
      title: meta.title,
      icon: meta.icon,
      minimized: false,
      openedAt: Date.now(),
    }
    const next: SheetState = { ...state, sheets: [...state.sheets, newSheet], activeId: newSheet.id }
    set({ sheets: [...state.sheets, newSheet], activeId: newSheet.id })
    navigate(next, path)
    get().persist()
    return { ok: true }
  },

  closeSheet: (id) => {
    const state = get()
    const idx = state.sheets.findIndex((s) => s.id === id)
    if (idx === -1) return

    const newSheets = state.sheets.filter((s) => s.id !== id)
    let newActiveId = state.activeId
    let navigatePath: string | null = null

    if (state.activeId === id) {
      // 关闭激活项：优先激活右侧相邻（idx 位置在新数组中即原 idx），无则左侧
      const nextActive = newSheets[idx] || newSheets[idx - 1] || null
      newActiveId = nextActive?.id ?? null
      navigatePath = nextActive?.path ?? '/'
    }

    const next: SheetState = { ...state, sheets: newSheets, activeId: newActiveId }
    set({ sheets: newSheets, activeId: newActiveId })
    if (navigatePath) navigate(next, navigatePath)
    get().persist()
  },

  activateSheet: (id) => {
    const state = get()
    const target = state.sheets.find((s) => s.id === id)
    if (!target) return
    // 激活最小化 sheet 时同时恢复：否则 SheetContent 因 minimized=true 显示空状态，
    // 用户点击 tab 后看不到内容，体验上等同"无反应"
    const needRestore = target.minimized
    const next: SheetState = needRestore
      ? { ...state, sheets: state.sheets.map((s) => (s.id === id ? { ...s, minimized: false } : s)), activeId: id }
      : { ...state, activeId: id }
    set(needRestore ? { sheets: next.sheets, activeId: id } : { activeId: id })
    navigate(next, target.path)
    get().persist()
  },

  minimizeSheet: (id) => {
    const state = get()
    const idx = state.sheets.findIndex((s) => s.id === id)
    if (idx === -1) return

    const newSheets = state.sheets.map((s) => (s.id === id ? { ...s, minimized: true } : s))
    let newActiveId = state.activeId
    let navigatePath: string | null = null

    if (state.activeId === id) {
      // 最小化激活项：激活下一个非最小化 sheet
      const candidates = newSheets.filter((s) => !s.minimized)
      const nextActive = candidates[idx] || candidates[idx - 1] || null
      newActiveId = nextActive?.id ?? null
      navigatePath = nextActive?.path ?? null
    }

    const next: SheetState = { ...state, sheets: newSheets, activeId: newActiveId }
    set({ sheets: newSheets, activeId: newActiveId })
    if (navigatePath) navigate(next, navigatePath)
    get().persist()
  },

  restoreSheet: (id) => {
    const state = get()
    const newSheets = state.sheets.map((s) => (s.id === id ? { ...s, minimized: false } : s))
    set({ sheets: newSheets })
    // 恢复不自动激活
    get().persist()
  },

  closeAll: () => {
    set({ sheets: [], activeId: null })
    get().persist()
  },

  setPreferences: (patch) => {
    const current = get().preferences
    const merged: SheetPreferences = { ...current, ...patch }
    // maxSheets 钳制
    if (patch.maxSheets !== undefined) merged.maxSheets = clampMaxSheets(patch.maxSheets)
    // doubleClickInterval 钳制
    if (patch.doubleClickInterval !== undefined) {
      merged.doubleClickInterval = clampDoubleClickInterval(patch.doubleClickInterval)
    }
    set({ preferences: merged })
    // 偏好独立持久化
    storage.set(PREFS_KEY, merged)
  },

  setMobileMode: (isMobile) => set({ isMobile }),

  setNavigator: (fn) => set({ _navigator: fn }),

  hydrate: () => {
    // 恢复偏好
    const savedPrefs = storage.get<SheetPreferences>(PREFS_KEY, DEFAULT_PREFERENCES, (v): v is SheetPreferences => {
      return v !== null && typeof v === 'object' && typeof (v as SheetPreferences).maxSheets === 'number'
    })
    const preferences: SheetPreferences = {
      ...DEFAULT_PREFERENCES,
      ...savedPrefs,
      maxSheets: clampMaxSheets(savedPrefs.maxSheets),
      // 兼容旧版本持久化数据：缺失字段时回退默认值
      doubleClickInterval: clampDoubleClickInterval(
        typeof savedPrefs.doubleClickInterval === 'number'
          ? savedPrefs.doubleClickInterval
          : DEFAULT_PREFERENCES.doubleClickInterval,
      ),
      doubleClickCloseEnabled: typeof savedPrefs.doubleClickCloseEnabled === 'boolean'
        ? savedPrefs.doubleClickCloseEnabled
        : DEFAULT_PREFERENCES.doubleClickCloseEnabled,
      thumbnailMode: typeof savedPrefs.thumbnailMode === 'boolean'
        ? savedPrefs.thumbnailMode
        : DEFAULT_PREFERENCES.thumbnailMode,
      thumbnailTooltipEnabled: typeof savedPrefs.thumbnailTooltipEnabled === 'boolean'
        ? savedPrefs.thumbnailTooltipEnabled
        : DEFAULT_PREFERENCES.thumbnailTooltipEnabled,
    }

    // 恢复 sheet 栈（丢弃 registry 中已不存在的 path，重建 icon/title）
    const saved = storage.get<PersistedState>(STATE_KEY, { sheets: [], activeId: null }, (v): v is PersistedState => {
      return v !== null && typeof v === 'object' && Array.isArray((v as PersistedState).sheets)
    })

    const validSheets: SheetItem[] = []
    for (const s of saved.sheets) {
      const meta = rebuildSheetMeta(s.path)
      if (!meta) continue // path 已失效，静默丢弃
      validSheets.push({
        id: s.id,
        path: s.path,
        title: meta.title,
        icon: meta.icon,
        minimized: s.minimized,
        openedAt: s.openedAt,
      })
    }

    // activeId 校验：若指向被丢弃的 sheet，重置为剩余最后一个或 null
    let activeId = saved.activeId
    if (activeId && !validSheets.some((s) => s.id === activeId)) {
      activeId = validSheets.length > 0 ? validSheets[validSheets.length - 1].id : null
    }

    set({ sheets: validSheets, activeId, preferences, hydrated: true })
  },

  persist: () => {
    if (persistTimer) clearTimeout(persistTimer)
    persistTimer = setTimeout(() => {
      const state = get()
      // 仅持久化可序列化字段，过滤掉 icon/title（运行时从 registry 重建）
      const toSave: PersistedState = {
        sheets: state.sheets.map((s) => ({
          id: s.id,
          path: s.path,
          minimized: s.minimized,
          openedAt: s.openedAt,
        })),
        activeId: state.activeId,
      }
      storage.set(STATE_KEY, toSave)
    }, PERSIST_DEBOUNCE_MS)
  },
}))
