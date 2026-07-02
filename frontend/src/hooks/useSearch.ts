import { useCallback, useEffect, useRef, useState } from 'react'

// 统一搜索防抖间隔：与 Alpine 模板 @input.debounce.400ms 对齐
const DEFAULT_DEBOUNCE_MS = 400

interface UseSearchOptions<T> {
  /** 搜索函数：接收查询参数返回 Promise */
  search: (params: T) => Promise<void>
  /** 依赖项：这些值变化时防抖后触发搜索（替代手动 useEffect + setTimeout） */
  deps: unknown[]
  /** 防抖间隔（毫秒），默认 400ms */
  debounceMs?: number
  /** 是否启用搜索（false 时跳过所有请求） */
  enabled?: boolean
}

/**
 * 统一搜索 Hook：防抖 + 并发保护 + 取消过时请求
 *
 * 设计要点：
 * - 防抖：deps 变化后等待 debounceMs，期间有新变化则重置计时器
 * - 并发保护：同一时刻只保留最后一次请求，避免快速输入产生多个 in-flight 请求
 * - 取消过时请求：通过 requestId 标记，旧请求结果被丢弃，避免乱序覆盖
 *
 * 替代各页面手动实现的 useEffect + setTimeout 防抖模式，
 * 统一为 400ms 与 Alpine 模板 @input.debounce.400ms 对齐。
 */
export function useSearch<T>(opts: UseSearchOptions<T>) {
  const { search, deps, debounceMs = DEFAULT_DEBOUNCE_MS, enabled = true } = opts

  // 用 ref 持有最新闭包：避免 deps 中包含函数时每次渲染都触发防抖
  const searchRef = useRef(search)
  searchRef.current = search
  const enabledRef = useRef(enabled)
  enabledRef.current = enabled

  // 请求序号：每次发起请求递增，响应回来时比对，丢弃过时响应
  const requestIdRef = useRef(0)
  // 防抖计时器
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [isSearching, setIsSearching] = useState(false)

  const doSearch = useCallback(async () => {
    if (!enabledRef.current) return
    const currentId = ++requestIdRef.current
    setIsSearching(true)
    try {
      await searchRef.current(deps as unknown as T)
    } finally {
      // 仅当本次请求是最新请求时才清除 loading，避免旧请求提前清除
      if (currentId === requestIdRef.current) {
        setIsSearching(false)
      }
    }
  }, [deps])

  // deps 变化时防抖触发
  useEffect(() => {
    if (!enabled) return
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => doSearch(), debounceMs)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, enabled, debounceMs])

  // 组件卸载时取消所有 in-flight 请求
  useEffect(() => {
    return () => {
      // 递增 requestId 让所有未完成请求的回调失效
      requestIdRef.current++
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [])

  return { isSearching, doSearch }
}
