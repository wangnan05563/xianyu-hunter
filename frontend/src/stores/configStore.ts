import { create } from 'zustand'
import { AppConfig, configApi } from '../api'

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
}))
