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
  /**
   * 循环替换开关：开启后，达到 maxSheets 上限时会自动淘汰最旧的非激活 sheet。
   * 关闭时，超限返回 { ok: false, reason: 'limit' } 由调用方处理。
   * 默认 false（保守默认：升级后行为不变，用户主动开启）。
   */
  circularReplaceEnabled: boolean
}

export const DEFAULT_PREFERENCES: SheetPreferences = {
  maxSheets: 5,
  enableAnimation: true,
  minimizeInsteadOfClose: false,
  doubleClickCloseEnabled: false,
  doubleClickInterval: 350,
  thumbnailMode: false,
  thumbnailTooltipEnabled: true,
  circularReplaceEnabled: false,
}

/**
 * 被循环替换淘汰的 sheet 摘要（轻量、无 icon，用于回收栈 + 返回值）
 * 为什么独立于 SheetItem：返回值不携带 ReactNode，序列化/UI 显示更轻便
 */
export interface ReplacedSheet {
  /** 原始 id（用户撤销时用于匹配回收栈项） */
  id: string
  /** 路由路径（用于恢复时查找 meta 与重新打开） */
  path: string
  /** 显示标题（从 registry 复制的字符串，无需再次查找） */
  title: string
  /** 被替换时间戳（用于调试/排序） */
  replacedAt: number
}

/** 回收栈最大保留条数：5 条足够覆盖用户连续操作窗口，又不会无限增长 */
const REPLACED_HISTORY_MAX = 5

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
  /**
   * 回收栈：最近被循环替换淘汰的 sheet 摘要（FIFO，最多 REPLACED_HISTORY_MAX 条）
   * 为什么只存摘要不存 SheetItem：避免 ReactNode 持久化，恢复时按 path 重新查 registry 即可
   */
  replacedHistory: ReplacedSheet[]

  /**
   * 打开或激活 sheet
   * - 桌面端 + 未达上限：新建 sheet
   * - 桌面端 + 达到上限 + circularReplaceEnabled=true：淘汰最旧非激活 sheet 后新建，返回 replacedSheet
   * - 桌面端 + 达到上限 + circularReplaceEnabled=false：返回 { ok: false, reason: 'limit' }
   * - 移动端：单 sheet 替换（不受循环替换影响）
   * - path 已存在：仅激活（不触发 replacedSheet）
   */
  openSheet: (path: string) => {
    ok: boolean
    reason?: 'limit' | 'not_found'
    /** 仅循环替换触发时返回，调用方可用其发 Toast 通知 + 撤销 */
    replacedSheet?: ReplacedSheet
  }
  closeSheet: (id: string) => void
  activateSheet: (id: string) => void
  minimizeSheet: (id: string) => void
  restoreSheet: (id: string) => void
  closeAll: () => void
  /**
   * 从回收栈恢复被替换的 sheet
   * - 命中：恢复为新 sheet（生成新 id，保持原 openedAt 顺序），从回收栈移除
   * - path 已重新存在于栈：仅激活那个 sheet（不重复开）
   * - 当前栈已满：返回 { ok: false, reason: 'limit' }
   * - id 不存在：返回 { ok: false, reason: 'not_found' }
   */
  restoreReplaced: (id: string) => { ok: boolean; reason?: 'not_found' | 'limit' }
  /** 清空回收栈（暴露给偏好/调试使用） */
  clearReplacedHistory: () => void
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

/** openSheet 操作签名（set/get 为 zustand 提供的写入与读取函数） */
type SetFn = (
  partial:
    | Partial<SheetState>
    | ((state: SheetState) => Partial<SheetState>),
) => void
type GetFn = () => SheetState

/**
 * openSheet 子流程：命中已存在 path 时激活它（必要时恢复最小化）。
 * 为什么独立：openSheet 主体有 4 个分支，拆出"激活现有"可让主函数保持线性。
 */
function activateExistingSheet(
  set: SetFn,
  get: GetFn,
  state: SheetState,
  existing: SheetItem,
  path: string,
): { ok: boolean } {
  const needRestore = existing.minimized
  const next: SheetState = needRestore
    ? { ...state, sheets: state.sheets.map((s) => (s.id === existing.id ? { ...s, minimized: false } : s)), activeId: existing.id }
    : { ...state, activeId: existing.id }
  set(needRestore ? { sheets: next.sheets, activeId: existing.id } : { activeId: existing.id })
  navigate(next, path)
  get().persist()
  return { ok: true }
}

/**
 * openSheet 子流程：循环替换路径——淘汰最旧非激活 sheet 并新建。
 * 为什么独立：原 openSheet 内嵌 30+ 行替换逻辑（含回收栈、victim 选取、排序），
 *             抽离后让主函数只负责"分流"。
 */
function performCircularReplace(
  set: SetFn,
  get: GetFn,
  state: SheetState,
  path: string,
  meta: SheetMeta,
): { ok: boolean; replacedSheet?: ReplacedSheet; reason?: 'limit' | 'not_found' } {
  // 保护 activeId：优先从"非激活"sheet 中按 openedAt 升序选最旧
  // 极端情况（所有 sheet 都激活，例如 maxSheets=1 + 唯一 sheet 是激活态）→ 退回全体选择
  const inactivePool = state.sheets.filter((s) => s.id !== state.activeId)
  const victimPool = inactivePool.length > 0 ? inactivePool : state.sheets
  // 升序排序：openedAt 最小的在最前
  const victim = [...victimPool].sort((a, b) => a.openedAt - b.openedAt)[0]
  if (!victim) return { ok: false, reason: 'limit' } // 理论不可达（sheets.length >= 1）

  const replaced: ReplacedSheet = {
    id: victim.id,
    path: victim.path,
    title: victim.title,
    replacedAt: Date.now(),
  }
  const remainingSheets = state.sheets.filter((s) => s.id !== victim.id)
  const newSheet: SheetItem = {
    id: `${path}-${Date.now()}`,
    path,
    title: meta.title,
    icon: meta.icon,
    minimized: false,
    openedAt: Date.now(),
  }
  // 新 sheet 直接成为激活项
  const newActiveId = newSheet.id
  // 回收栈：FIFO 截断到最多 REPLACED_HISTORY_MAX 条
  const newHistory = [replaced, ...state.replacedHistory].slice(0, REPLACED_HISTORY_MAX)
  const next: SheetState = {
    ...state,
    sheets: [...remainingSheets, newSheet],
    activeId: newActiveId,
    replacedHistory: newHistory,
  }
  set({ sheets: [...remainingSheets, newSheet], activeId: newActiveId, replacedHistory: newHistory })
  navigate(next, path)
  get().persist()
  return { ok: true, replacedSheet: replaced }
}

/**
 * openSheet 子流程：移动端单 sheet 模式——若当前激活 sheet 路径不同则替换。
 * 返回 null 表示"未发生替换"（同 path 时由调用方走 createNewSheet）。
 */
function replaceMobileActiveSheet(
  set: SetFn,
  get: GetFn,
  state: SheetState,
  path: string,
  meta: SheetMeta,
): { ok: boolean } | null {
  if (!state.activeId) return null
  const current = state.sheets.find((s) => s.id === state.activeId)
  if (!current || current.path === path) return null

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

/**
 * openSheet 子流程：纯新建 sheet（无冲突、未达上限、移动端无激活项）。
 * 为什么独立：openSheet 默认分支，5 行内可表达"追加 + 激活 + 持久化"。
 */
function createNewSheet(
  set: SetFn,
  get: GetFn,
  state: SheetState,
  path: string,
  meta: SheetMeta,
): { ok: boolean } {
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
}

export const useSheetStore = create<SheetState>((set, get) => ({
  sheets: [],
  activeId: null,
  preferences: DEFAULT_PREFERENCES,
  isMobile: false,
  hydrated: false,
  _navigator: null,
  replacedHistory: [],

  openSheet: (path) => {
    const state = get()
    const meta = findSheetMeta(path)

    // 已存在同 path → 仅激活（优先于 limit：用户点击已存在 tab 应激活而非拒绝）
    const existing = state.sheets.find((s) => s.path === path)
    if (existing) {
      return activateExistingSheet(set, get, state, existing, path)
    }

    // 桌面端：检查上限（先于 registry，避免无谓查找；测试约定栈满时优先返回 limit）
    if (!state.isMobile && state.sheets.length >= state.preferences.maxSheets) {
      if (!state.preferences.circularReplaceEnabled) {
        return { ok: false, reason: 'limit' }
      }
      if (!meta) return { ok: false, reason: 'not_found' }
      return performCircularReplace(set, get, state, path, meta)
    }

    if (!meta) return { ok: false, reason: 'not_found' }

    // 移动端单 sheet 模式：替换当前激活 sheet
    if (state.isMobile && state.activeId) {
      const replaced = replaceMobileActiveSheet(set, get, state, path, meta)
      if (replaced) return replaced
    }

    return createNewSheet(set, get, state, path, meta)
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

  restoreReplaced: (id) => {
    const state = get()
    const target = state.replacedHistory.find((r) => r.id === id)
    if (!target) return { ok: false, reason: 'not_found' }

    // 防御：被恢复的 path 已重新存在于栈 → 激活现有那个，从回收栈移除
    const existing = state.sheets.find((s) => s.path === target.path)
    if (existing) {
      const needRestore = existing.minimized
      const newSheets = needRestore
        ? state.sheets.map((s) => (s.id === existing.id ? { ...s, minimized: false } : s))
        : state.sheets
      const newHistory = state.replacedHistory.filter((r) => r.id !== id)
      const next: SheetState = { ...state, sheets: newSheets, activeId: existing.id, replacedHistory: newHistory }
      set(needRestore ? { sheets: newSheets, activeId: existing.id, replacedHistory: newHistory } : { activeId: existing.id, replacedHistory: newHistory })
      navigate(next, target.path)
      get().persist()
      return { ok: true }
    }

    // 注意：不检查 maxSheets 上限。"恢复"是用户对刚才循环替换的撤销操作，
    // 应当始终成功（可能临时超过 maxSheets，下次 openSheet 会再触发循环替换平衡）。
    // 这与 openSheet 路径的"栈满 → 替换"语义不同：用户主动撤销自己的动作不应被拒绝。

    const meta = findSheetMeta(target.path)
    if (!meta) return { ok: false, reason: 'not_found' }

    // 恢复为新 sheet：保持原 openedAt 顺序（用 replacedAt 还原相对时序）
    const newSheet: SheetItem = {
      id: `${target.path}-${Date.now()}`,
      path: target.path,
      title: meta.title,
      icon: meta.icon,
      minimized: false,
      openedAt: target.replacedAt,
    }
    const newSheets = [...state.sheets, newSheet]
    const newHistory = state.replacedHistory.filter((r) => r.id !== id)
    const next: SheetState = {
      ...state,
      sheets: newSheets,
      activeId: newSheet.id,
      replacedHistory: newHistory,
    }
    set({ sheets: newSheets, activeId: newSheet.id, replacedHistory: newHistory })
    navigate(next, target.path)
    get().persist()
    return { ok: true }
  },

  clearReplacedHistory: () => {
    set({ replacedHistory: [] })
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
      // 兼容旧版本持久化数据：缺失/类型错误字段回退默认值
      // number 字段用 ??（clampDoubleClickInterval 内部已处理非有限值），boolean 字段保留 typeof 检查防御类型污染
      doubleClickInterval: clampDoubleClickInterval(savedPrefs.doubleClickInterval ?? DEFAULT_PREFERENCES.doubleClickInterval),
      doubleClickCloseEnabled: typeof savedPrefs.doubleClickCloseEnabled === 'boolean' ? savedPrefs.doubleClickCloseEnabled : DEFAULT_PREFERENCES.doubleClickCloseEnabled,
      thumbnailMode: typeof savedPrefs.thumbnailMode === 'boolean' ? savedPrefs.thumbnailMode : DEFAULT_PREFERENCES.thumbnailMode,
      thumbnailTooltipEnabled: typeof savedPrefs.thumbnailTooltipEnabled === 'boolean' ? savedPrefs.thumbnailTooltipEnabled : DEFAULT_PREFERENCES.thumbnailTooltipEnabled,
      circularReplaceEnabled: typeof savedPrefs.circularReplaceEnabled === 'boolean' ? savedPrefs.circularReplaceEnabled : DEFAULT_PREFERENCES.circularReplaceEnabled,
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

    // replacedHistory 不持久化恢复：回收栈依赖 replacedAt 计算 5 秒撤销窗口，
    // 重启后时间戳已过期，恢复无意义且可能导致撤销按钮指向已失效的 sheet
    set({ sheets: validSheets, activeId, preferences, replacedHistory: [], hydrated: true })
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
