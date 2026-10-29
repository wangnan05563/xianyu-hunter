import { create } from 'zustand'
import { AppConfig, configApi } from '../api'
import {
  applyDrafts,
  collectChangedPaths,
  filterChangedPaths,
  markScopeSaved,
  revertScope,
  scopedSubmitPayload,
} from './configDirty'

// Diff 变更项（后端 dry_run 返回格式）
export interface DiffChange {
  path: string
  old_value: unknown
  new_value: unknown
  op: 'add' | 'modify' | 'delete'
}

interface ConfigState {
  config: AppConfig | null
  loading: boolean
  error: string | null
  // 原始配置（用于对比改动）
  original: AppConfig | null

  load: () => Promise<void>
  update: (patch: Partial<AppConfig>) => void
  /** 传 scope 只回滚本页段（T02571 页段提交）；不传保持整份重置 */
  reset: (scope?: readonly string[]) => void
  save: () => Promise<void>
  hasChanges: () => boolean
  /** 与 original 相比有变化的点号路径（数组整体记一条，不拆下标） */
  changedPaths: () => string[]
  /** 只返回落在 scope（当前页可写配置段）内的变更路径 */
  dirtyPathsInScope: (scope: readonly string[]) => string[]
  // Diff 预览：dry_run 模式只返回变更不实际保存。传 scope 时只提交本页段
  previewSave: (scope?: readonly string[]) => Promise<DiffChange[]>
  // 确认保存：实际写入并更新 original。传 scope 时只提交本页段，
  // 且只把本页段的 original 认作已保存，别页草稿继续算脏
  confirmSave: (scope?: readonly string[]) => Promise<void>
  // 字段级回滚：根据路径获取原始值
  getFieldOriginal: (path: string) => unknown
  // 字段级回滚：将指定路径恢复为原始值
  revertField: (path: string) => void
}

/**
 * 提交体：传 scope 就只带本页写过的那几个顶层段（T02571「保存按页段提交」），
 * 段内无变化则整段不进载荷；返回 null 表示这次没有要提交的内容。
 * 不传 scope 保持整份提交（TaskEditor 等全局配置入口）。
 */
function submitPayload(
  config: AppConfig,
  original: AppConfig | null,
  scope?: readonly string[],
): Partial<AppConfig> | null {
  if (!scope || !original) return config
  const payload = scopedSubmitPayload(config, original, scope)
  return Object.keys(payload).length > 0 ? payload : null
}

export const useConfigStore = create<ConfigState>((set, get) => ({
  config: null,
  loading: false,
  error: null,
  original: null,

  // 切页 mount、TaskEditor 打开都会触发 load()；把未保存的草稿合并回去，
  // 否则一次载入就把草稿（本页的、别页的）一起抹掉（T02572 跨页污染）。
  load: async () => {
    set({ loading: true, error: null })
    try {
      const fresh = await configApi.get()
      const { config: draft, original } = get()
      const nextConfig = draft && original ? applyDrafts(fresh, draft, original) : fresh
      // 深拷贝作为原始值（structuredClone 性能更好且保留 Date 等类型，SonarQube S7784）
      set({ config: nextConfig, original: structuredClone(fresh), loading: false })
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '加载配置失败'
      set({ error: msg, loading: false })
    }
  },

  update: (patch) => {
    const { config } = get()
    if (!config) return
    set({ config: { ...config, ...patch } })
  },

  reset: (scope) => {
    const { config, original } = get()
    if (!original) return
    if (!scope) {
      set({ config: structuredClone(original) })
      return
    }
    if (!config) return
    set({ config: revertScope(config, original, scope) })
  },

  save: async () => {
    const { config, original } = get()
    if (!config || !original) return
    set({ loading: true, error: null })
    try {
      await configApi.save(config, false)
      set({ original: structuredClone(config), loading: false })
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '保存配置失败'
      set({ error: msg, loading: false })
      throw e
    }
  },

  hasChanges: () => {
    const { config, original } = get()
    if (!config || !original) return false
    return JSON.stringify(config) !== JSON.stringify(original)
  },

  changedPaths: () => {
    const { config, original } = get()
    if (!config || !original) return []
    return collectChangedPaths(config, original).sort((a, b) => a.localeCompare(b))
  },

  dirtyPathsInScope: (scope) => {
    const { config, original } = get()
    if (!config || !original) return []
    return filterChangedPaths(collectChangedPaths(config, original), scope)
  },

  previewSave: async (scope) => {
    const { config, original } = get()
    if (!config) return []
    const payload = submitPayload(config, original, scope)
    if (payload === null) return []
    const res = await configApi.save(payload, true)
    // 后端返回 { diffs: [{path, op, old, new}] }，op 取值 'add'|'modify'|'remove'
    // 前端 DiffChange 期望 {path, op, old_value, new_value}，op 取值 'add'|'modify'|'delete'
    // 在此做一次字段映射，避免每个配置页都要适配后端格式
    const diffs = (res?.diffs ?? []) as Array<{
      path: string
      op: string
      old: unknown
      new: unknown
    }>
    return diffs.map((d) => ({
      path: d.path,
      op: (d.op === 'remove' ? 'delete' : d.op) as DiffChange['op'],
      old_value: d.old,
      new_value: d.new,
    }))
  },

  confirmSave: async (scope) => {
    const { config, original } = get()
    if (!config || !original) return
    const payload = submitPayload(config, original, scope)
    if (payload === null) return
    set({ loading: true, error: null })
    try {
      await configApi.save(payload, false)
      // 页段提交只认本页段为已保存；别页草稿与 original 仍然不同，继续算脏
      const nextOriginal = scope
        ? markScopeSaved(original, config, scope)
        : structuredClone(config)
      set({ original: nextOriginal, loading: false })
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '保存配置失败'
      set({ error: msg, loading: false })
      throw e
    }
  },

  // 根据 path（如 "eval.pass_score"）从 original 中获取原始值
  getFieldOriginal: (path: string) => {
    const { original } = get()
    if (!original) return undefined
    const keys = path.split('.')
    let result: unknown = original
    for (const key of keys) {
      if (result == null || typeof result !== 'object') return undefined
      result = (result as Record<string, unknown>)[key]
    }
    return result
  },

  // 将 config 中指定 path 的值恢复为 original 中的值
  revertField: (path: string) => {
    const { config, original } = get()
    if (!config || !original) return
    const originalValue = get().getFieldOriginal(path)
    // 路径不存在时不写入，避免在 config 上创建 undefined 键
    if (originalValue === undefined) return
    // 深拷贝 config 避免引用问题（structuredClone 保留类型，无需 as 断言）
    const newConfig = structuredClone(config)
    const keys = path.split('.')
    let target: unknown = newConfig
    for (let i = 0; i < keys.length - 1; i++) {
      if (target == null || typeof target !== 'object') return
      target = (target as Record<string, unknown>)[keys[i]]
    }
    if (target == null || typeof target !== 'object') {
      // 加大括号避免 SonarQube S2681 误判下一条赋值语句属于 if 体
      return
    }
    ;(target as Record<string, unknown>)[keys[keys.length - 1]] = originalValue
    set({ config: newConfig })
  },
}))
