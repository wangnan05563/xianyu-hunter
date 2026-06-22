import { create } from 'zustand'
import { AppConfig, configApi } from '../api'

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
  reset: () => void
  save: () => Promise<void>
  hasChanges: () => boolean
  // Diff 预览：dry_run 模式只返回变更不实际保存
  previewSave: () => Promise<DiffChange[]>
  // 确认保存：实际写入并更新 original
  confirmSave: () => Promise<void>
  // 字段级回滚：根据路径获取原始值
  getFieldOriginal: (path: string) => unknown
  // 字段级回滚：将指定路径恢复为原始值
  revertField: (path: string) => void
}

export const useConfigStore = create<ConfigState>((set, get) => ({
  config: null,
  loading: false,
  error: null,
  original: null,

  load: async () => {
    set({ loading: true, error: null })
    try {
      const config = await configApi.get()
      // 深拷贝作为原始值
      set({ config, original: JSON.parse(JSON.stringify(config)), loading: false })
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

  reset: () => {
    const { original } = get()
    if (original) {
      set({ config: JSON.parse(JSON.stringify(original)) })
    }
  },

  save: async () => {
    const { config, original } = get()
    if (!config || !original) return
    set({ loading: true, error: null })
    try {
      await configApi.save(config, false)
      set({ original: JSON.parse(JSON.stringify(config)), loading: false })
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

  previewSave: async () => {
    const { config } = get()
    if (!config) return []
    const res = await configApi.save(config, true)
    return (res?.changes || []) as DiffChange[]
  },

  confirmSave: async () => {
    const { config } = get()
    if (!config) return
    set({ loading: true, error: null })
    try {
      await configApi.save(config, false)
      set({ original: JSON.parse(JSON.stringify(config)), loading: false })
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
    // 深拷贝 config 避免引用问题
    const newConfig = JSON.parse(JSON.stringify(config)) as AppConfig
    const keys = path.split('.')
    let target: unknown = newConfig
    for (let i = 0; i < keys.length - 1; i++) {
      if (target == null || typeof target !== 'object') return
      target = (target as Record<string, unknown>)[keys[i]]
    }
    if (target == null || typeof target !== 'object') return
    ;(target as Record<string, unknown>)[keys[keys.length - 1]] = originalValue
    set({ config: newConfig })
  },
}))
