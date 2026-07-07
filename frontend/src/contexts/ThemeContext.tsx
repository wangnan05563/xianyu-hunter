import { createContext, useContext, useEffect, useState, useCallback, useMemo, type ReactNode } from 'react'
import { storage } from '../utils/storage'

/**
 * 全局主题 Context
 *
 * 为什么需要 Context：
 * 1. 主题状态需要在 Login 页（独立路由）和 MainLayout 包裹的页面之间共享
 * 2. 之前 isDark 状态只在 MainLayout 内部，导致 Login 页无法响应主题切换
 * 3. 顶层 ConfigProvider 也需要根据主题应用 algorithm
 */
type ThemeMode = 'light' | 'dark'

interface ThemeContextValue {
  isDark: boolean
  mode: ThemeMode
  setMode: (mode: ThemeMode) => void
  toggle: () => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

const STORAGE_KEY = 'xh.theme'

export function ThemeProvider({ children }: { readonly children: ReactNode }) {
  // 从 localStorage 读取初始值（兜底默认 light，避免在 SSR 环境下报错）
  // 为什么用 null 标识未设置：需要区分"用户未设置（跟随系统）"和"用户显式选择 light"
  const [mode, setModeState] = useState<ThemeMode>(() => {
    if (typeof globalThis.window === 'undefined') return 'light'
    const stored = storage.get<ThemeMode | null>(STORAGE_KEY, null)
    return stored === 'dark' ? 'dark' : 'light'
  })
  // 追踪用户是否显式设置过主题（未设置时跟随系统主题）
  const [userSet, setUserSet] = useState<boolean>(() => {
    if (typeof globalThis.window === 'undefined') return false
    return storage.get<ThemeMode | null>(STORAGE_KEY, null) !== null
  })

  // 同步到 document.documentElement，便于自定义 CSS 响应主题
  // 这样 .page-container 等使用 var(--xh-*) 的地方都能跟随主题
  // 使用 dataset 而非 setAttribute，符合 DOM 标准 API（S7761）
  useEffect(() => {
    document.documentElement.dataset.theme = mode
  }, [mode])

  // 监听 system 主题变化（仅当用户没有显式设置过主题时跟随）
  useEffect(() => {
    if (typeof globalThis.window === 'undefined') return
    const mq = globalThis.matchMedia('(prefers-color-scheme: dark)')
    const onChange = (e: MediaQueryListEvent) => {
      // 只在用户没有显式设置时跟随系统
      if (!userSet) {
        setModeState(e.matches ? 'dark' : 'light')
      }
    }
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [userSet])

  const setMode = useCallback((next: ThemeMode) => {
    setModeState(next)
    setUserSet(true)
    storage.set(STORAGE_KEY, next)
  }, [])

  const toggle = useCallback(() => {
    setModeState(prev => {
      const next = prev === 'dark' ? 'light' : 'dark'
      storage.set(STORAGE_KEY, next)
      return next
    })
    setUserSet(true)
  }, [])

  const value = useMemo<ThemeContextValue>(() => ({
    isDark: mode === 'dark',
    mode,
    setMode,
    toggle,
  }), [mode, setMode, toggle])

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) {
    throw new Error('useTheme must be used within ThemeProvider')
  }
  return ctx
}
