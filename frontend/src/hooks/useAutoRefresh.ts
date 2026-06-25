import { useEffect, useRef, useState, useCallback } from 'react'

// 轮询频率范围（秒）
const MIN_INTERVAL = 10
const MAX_INTERVAL = 120
const DEFAULT_INTERVAL = 30

// 最大重试次数
const MAX_RETRIES = 3
// 重试基础间隔（毫秒），实际间隔 = base * attempt（递增）
const RETRY_BASE_MS = 1000
// 防抖间隔（毫秒），避免短时间内多次触发刷新
const DEBOUNCE_MS = 500
// 页面不可见时的降频倍数
const BACKGROUND_SLOWDOWN = 3

interface AutoRefreshOptions {
  /** 是否启用实时刷新 */
  enabled: boolean
  /** 兜底轮询间隔（秒）：SSE 事件驱动为主，定时轮询为兜底，防止 SSE 断线期间遗漏更新 */
  intervalSec?: number
  /** 刷新回调：返回 Promise，reject 时触发重试 */
  refresh: () => Promise<void>
  /** 是否暂停刷新（如实时搜索模式下不需要刷新 DB） */
  paused?: boolean
  /** 依赖项：这些值变化时防抖后立即触发一次刷新并重置计时器 */
  deps?: unknown[]
}

interface AutoRefreshState {
  /** 上次刷新时间（时间戳 ms），null 表示从未刷新 */
  lastRefreshAt: number | null
  /** 是否正在刷新（含重试） */
  refreshing: boolean
  /** 连续失败次数 */
  failCount: number
  /** 下次兜底轮询时间（时间戳 ms），null 表示未调度或已暂停 */
  nextRefreshAt: number | null
}

/**
 * 触发式实时刷新 Hook（SSE 事件驱动 + 定时兜底轮询）
 *
 * 设计要点：
 * - 触发式为主：由外部事件（SSE 通知、用户操作）通过 triggerRefresh 驱动刷新
 * - 定时兜底：intervalSec > 0 时启动定时轮询，防止 SSE 断线期间遗漏更新
 * - 防抖：triggerRefresh 经过 DEBOUNCE_MS 防抖，避免短时间内重复请求
 * - 并发保护：refreshingRef 防止多个触发源同时发起刷新
 * - 页面不可见时自动降频（间隔 ×3），减少后台请求
 * - refresh 失败时自动重试（最多 3 次，间隔递增）
 * - 通过 ref 持有最新值，避免闭包陈旧
 * - 组件卸载时自动清理所有 timer
 */
export function useAutoRefresh(opts: AutoRefreshOptions) {
  const { enabled, intervalSec = DEFAULT_INTERVAL, refresh, paused = false, deps } = opts

  const [state, setState] = useState<AutoRefreshState>({
    lastRefreshAt: null,
    refreshing: false,
    failCount: 0,
    nextRefreshAt: null,
  })

  const refreshRef = useRef(refresh)
  refreshRef.current = refresh
  const enabledRef = useRef(enabled)
  enabledRef.current = enabled
  const pausedRef = useRef(paused)
  pausedRef.current = paused
  const intervalRef = useRef(intervalSec)
  intervalRef.current = intervalSec

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const retryRef = useRef(0)
  // 组件是否已卸载：防止卸载后异步 setState
  const mountedRef = useRef(true)
  // 并发刷新保护：防止多个触发源同时发起刷新
  const refreshingRef = useRef(false)
  // 用 ref 持有 scheduleNext，打破 doRefresh → scheduleNext → doRefresh 的循环依赖
  const scheduleNextRef = useRef<() => void>(() => {})

  // 组件卸载时标记 + 清理所有 timer
  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      if (debounceRef.current) clearTimeout(debounceRef.current)
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current)
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])

  const doRefresh = useCallback(async (isRetry = false) => {
    if (!enabledRef.current || !mountedRef.current) return
    if (pausedRef.current) {
      // paused 时跳过本次刷新，但仍调度下一次兜底轮询
      scheduleNextRef.current()
      return
    }
    // 并发保护：已有刷新在进行中时跳过，避免重复请求
    // 重试时跳过此检查（isRetry=true），因为锁在重试期间保持以防止其他触发源干扰
    if (!isRetry && refreshingRef.current) return

    refreshingRef.current = true
    setState((s) => ({ ...s, refreshing: true }))
    try {
      await refreshRef.current()
      retryRef.current = 0
      if (mountedRef.current) {
        setState((s) => ({ ...s, refreshing: false, failCount: 0, lastRefreshAt: Date.now() }))
      }
    } catch (_err) {
      retryRef.current += 1
      if (retryRef.current <= MAX_RETRIES) {
        const delay = RETRY_BASE_MS * retryRef.current
        // 传 isRetry=true 跳过并发锁检查，否则 doRefresh 会被 refreshingRef 挡住永远无法执行
        retryTimerRef.current = setTimeout(() => doRefresh(true), delay)
        return
      } else {
        retryRef.current = 0
        if (mountedRef.current) {
          setState((s) => ({ ...s, refreshing: false, failCount: s.failCount + 1, lastRefreshAt: Date.now() }))
        }
      }
    }
    refreshingRef.current = false
    // 刷新完成后调度下一次兜底轮询
    scheduleNextRef.current()
  }, [])

  // 兜底轮询调度：SSE 断线期间的保底刷新机制
  const scheduleNext = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
    if (!enabledRef.current || pausedRef.current) {
      if (mountedRef.current) {
        setState((s) => ({ ...s, nextRefreshAt: null }))
      }
      return
    }
    const visible = document.visibilityState === 'visible'
    const multiplier = visible ? 1 : BACKGROUND_SLOWDOWN
    const intervalMs = intervalRef.current * 1000 * multiplier
    const nextAt = Date.now() + intervalMs
    timerRef.current = setTimeout(() => doRefresh(), intervalMs)
    if (mountedRef.current) {
      setState((s) => ({ ...s, nextRefreshAt: nextAt }))
    }
  }, [doRefresh])

  // 保持 ref 最新
  scheduleNextRef.current = scheduleNext

  // 页面可见性变化时重新调度
  useEffect(() => {
    const onVisibility = () => scheduleNext()
    document.addEventListener('visibilitychange', onVisibility)
    return () => document.removeEventListener('visibilitychange', onVisibility)
  }, [scheduleNext])

  // enabled/interval/paused 变化时重新调度
  useEffect(() => {
    scheduleNext()
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, intervalSec, paused, scheduleNext])

  // 触发刷新（防抖 DEBOUNCE_MS）
  // 供外部调用：SSE 事件通知、用户操作等场景
  // 触发后重置兜底轮询计时器，避免事件触发后紧接着又定时触发
  const triggerRefresh = useCallback(() => {
    if (!enabledRef.current || pausedRef.current) return
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      doRefresh()
    }, DEBOUNCE_MS)
  }, [doRefresh])

  // deps 变化时防抖触发一次立即刷新 + 重置计时器
  // 用户输入搜索内容时暂停轮询，停止输入 500ms 后恢复轮询
  useEffect(() => {
    if (!deps || deps.length === 0) return
    if (!enabledRef.current || pausedRef.current) return
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      doRefresh()
      scheduleNext()
    }, DEBOUNCE_MS)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return { ...state, triggerRefresh }
}

export { MIN_INTERVAL, MAX_INTERVAL, DEFAULT_INTERVAL }
