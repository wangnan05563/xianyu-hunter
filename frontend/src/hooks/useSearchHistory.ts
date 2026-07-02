import { useCallback, useEffect, useMemo, useState } from 'react'

// 搜索历史最大保留条数：超出时按时间倒序淘汰
const MAX_HISTORY_ITEMS = 20
const STORAGE_KEY_PREFIX = 'xh_search_history_'

interface UseSearchHistoryOptions {
  /** 命名空间：不同搜索页隔离历史记录（如 'chatbot' / 'items' / 'logs'） */
  namespace: string
  /** 最大保留条数，默认 20 */
  maxItems?: number
}

/**
 * 搜索历史 Hook：localStorage 持久化 + 去重 + 最近优先
 *
 * 设计要点：
 * - 去重：同一关键词多次搜索只保留最近一次
 * - 最近优先：新搜索插入到列表头部
 * - 容量限制：超过 maxItems 时淘汰尾部
 * - 命名空间隔离：不同搜索页的历史互不干扰
 *
 * 用法：
 *   const { history, add, clear } = useSearchHistory({ namespace: 'chatbot' })
 *   // 用户触发搜索时
 *   add(searchKeyword)
 *   // 渲染历史列表
 *   history.map(kw => <Tag key={kw} onClick={() => setSearch(kw)}>{kw}</Tag>)
 */
export function useSearchHistory(opts: UseSearchHistoryOptions) {
  const { namespace, maxItems = MAX_HISTORY_ITEMS } = opts
  // 用 useMemo 固定 storageKey：避免每次渲染生成新字符串导致 useCallback 依赖变化
  // 进而触发使用此 hook 的组件（如 Chatbot loadSessions）无意义重渲染
  const storageKey = useMemo(() => `${STORAGE_KEY_PREFIX}${namespace}`, [namespace])

  const [history, setHistory] = useState<string[]>([])

  // 初始化：从 localStorage 读取历史
  useEffect(() => {
    try {
      const raw = localStorage.getItem(storageKey)
      if (raw) {
        const parsed = JSON.parse(raw)
        if (Array.isArray(parsed)) {
          setHistory(parsed.slice(0, maxItems))
        }
      }
    } catch {
      // localStorage 不可用或数据损坏时静默降级（无历史记录）
    }
  }, [storageKey, maxItems])

  const add = useCallback((keyword: string) => {
    const trimmed = keyword.trim()
    if (!trimmed) return
    setHistory((prev) => {
      // 去重：移除已存在的相同关键词，再插入到头部
      const filtered = prev.filter((k) => k !== trimmed)
      const next = [trimmed, ...filtered].slice(0, maxItems)
      try {
        localStorage.setItem(storageKey, JSON.stringify(next))
      } catch {
        // localStorage 写入失败时静默降级（仅内存保留）
      }
      return next
    })
  }, [storageKey, maxItems])

  const clear = useCallback(() => {
    setHistory([])
    try {
      localStorage.removeItem(storageKey)
    } catch {
      // localStorage 不可用时静默降级
    }
  }, [storageKey])

  const remove = useCallback((keyword: string) => {
    setHistory((prev) => {
      const next = prev.filter((k) => k !== keyword)
      try {
        localStorage.setItem(storageKey, JSON.stringify(next))
      } catch {
        // 静默降级
      }
      return next
    })
  }, [storageKey])

  return { history, add, clear, remove }
}
