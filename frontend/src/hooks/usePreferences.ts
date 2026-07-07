import { useCallback, useEffect, useState } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import { preferencesApi } from '../api/preferences'
import type { PreferenceValue } from '../api/preferences'

/**
 * 集成计划（MU6 用户偏好隔离）—— 已就绪，待逐步替换 usePersistentState
 *
 * 当前状态：Hook + /api/preferences 后端 + AccountSwitcher 切换时调用
 *           invalidatePreferenceCache() 失效缓存 已完成。
 * 待集成路径（按优先级）：
 *   1. Tasks 页面：列表分页大小 / 列可见性（原 usePersistentState('task_list_columns')）
 *   2. Evaluations 页面：评分阈值 / 过滤状态
 *   3. Chatbot 页面：会话窗口高度 / 默认模型
 *   4. Config 页面：表单草稿暂存
 * 替换模式：
 *   const [columns, setColumns] = usePersistentState('task_list_columns', default)
 *   → const [columns, setColumns] = usePreferences('task_list_columns', default)
 * 注意事项：
 *   - usePreferences 返回 [value, setter, { loading, error, remove }]，
 *     比 usePersistentState 多第 3 项 meta，调用方需调整解构
 *   - 切换账号时已在 AccountSwitcher 调用 invalidatePreferenceCache()，
 *     新用户首次访问会自动从后端拉取
 *   - MainLayout 可在 mount 时调用 prefetchPreferences(['task_list_columns', ...])
 *     减少首屏闪烁
 */

// 模块级偏好缓存：key → value
// 为什么用模块级缓存：多个 hook 实例可能读取同一 key（如不同组件读取分页大小），
// 缓存避免重复请求；同时提供同步初始化值，避免 UI 闪烁
const preferenceCache = new Map<string, PreferenceValue>()
// 进行中的请求：避免同一 key 并发触发多次请求
const inflightRequests = new Map<string, Promise<PreferenceValue | undefined>>()
// 防抖写入定时器：key → timer
// 为什么用模块级：多个 hook 实例写入同一 key 时共享防抖，避免重复写入
const writeTimers = new Map<string, ReturnType<typeof setTimeout>>()

// S2004 修复：以下辅助函数提取到模块级，避免 setAndPersist 内嵌套超过 4 层
// 写入错误处理：统一错误转换逻辑
const handleWriteError = (
  err: unknown,
  setError: (e: Error) => void,
) => {
  const e = err instanceof Error ? err : new Error(String(err))
  setError(e)
}

// 创建防抖写入函数：从 setAndPersist 抽出，减少嵌套层级
// 返回一个清理函数，用于 hook 卸载时取消定时器
const createDebouncedWriter = (
  key: string,
  value: PreferenceValue,
  setError: (e: Error) => void,
) => {
  const existingTimer = writeTimers.get(key)
  if (existingTimer) clearTimeout(existingTimer)
  const timer = setTimeout(() => {
    preferencesApi.set(key, value).catch((err) => handleWriteError(err, setError))
    writeTimers.delete(key)
  }, 400)
  writeTimers.set(key, timer)
}

// 计算下一个值：从 setAndPersist 的 setValue 回调内抽出，减少嵌套
const computeNextValue = <T extends PreferenceValue>(
  updater: SetStateAction<T>,
  prev: T,
): T => {
  return typeof updater === 'function' ? (updater as (p: T) => T)(prev) : updater
}

/**
 * 用户偏好 Hook —— 从后端 /api/preferences 读写用户级偏好
 *
 * 为什么需要这个 Hook：
 * 1. 多账号场景下偏好需按 user_id 隔离，localStorage 无法区分用户
 * 2. 后端 user_preferences 表已就绪，user_id 由中间件注入，前端只需传 key
 * 3. 接口与 useState 兼容，可平滑替代 usePersistentState
 *
 * 与 usePersistentState 的差异：
 * - 初始化：模块级缓存命中则同步返回，否则用 defaultValue 并后台拉取
 * - 写入：异步调用 PUT /api/preferences/{key}，失败时回滚 state
 * - 跨用户隔离：切换账号后需调用 invalidatePreferenceCache() 清除缓存
 *
 * @param key 偏好键名（如 'task_list_columns'）
 * @param defaultValue 默认值（加载失败或未设置时使用）
 */
export function usePreferences<T extends PreferenceValue>(
  key: string,
  defaultValue: T,
): [T, Dispatch<SetStateAction<T>>, { loading: boolean; error: Error | null; remove: () => void }] {
  const [value, setValue] = useState<T>(preferenceCache.has(key) ? (preferenceCache.get(key) as T) : defaultValue)
  const [loading, setLoading] = useState<boolean>(!preferenceCache.has(key))
  const [error, setError] = useState<Error | null>(null)

  // 拉取单个偏好值
  const fetchValue = useCallback(async (): Promise<void> => {
    // 已有进行中的请求：复用，避免并发
    if (inflightRequests.has(key)) {
      try {
        const v = await inflightRequests.get(key)
        if (v !== undefined) {
          setValue(v as T)
          preferenceCache.set(key, v)
        }
      } catch {
        // 忽略，下次再试
      } finally {
        setLoading(false)
      }
      return
    }
    setLoading(true)
    setError(null)
    const promise = preferencesApi.get(key)
      .then((v) => {
        if (v !== null && v !== undefined) {
          preferenceCache.set(key, v)
          setValue(v as T)
        } else {
          // 后端无值：用默认值，但不写缓存（避免默认值被误认为已设置）
          setValue(defaultValue)
        }
        return v ?? undefined
      })
      .catch((err) => {
        const e = err instanceof Error ? err : new Error(String(err))
        setError(e)
        // 失败时保留默认值，不阻塞 UI
        return undefined
      })
      .finally(() => {
        inflightRequests.delete(key)
        setLoading(false)
      })
    inflightRequests.set(key, promise)
    await promise
  }, [key, defaultValue])

  useEffect(() => {
    // 缓存命中：跳过请求
    if (preferenceCache.has(key)) {
      setValue(preferenceCache.get(key) as T)
      setLoading(false)
      return
    }
    void fetchValue()
  }, [key, fetchValue])

  // S2004 修复：setAndPersist 内嵌套原超过 4 层，
  // 内层逻辑提取到模块级 computeNextValue/createDebouncedWriter/handleWriteError，
  // 主函数只剩 2 层嵌套（useCallback → setValue）
  const setAndPersist = useCallback<Dispatch<SetStateAction<T>>>((updater) => {
    setValue((prev) => {
      const next = computeNextValue(updater, prev)
      preferenceCache.set(key, next)
      createDebouncedWriter(key, next, setError)
      return next
    })
  }, [key])

  // 清除偏好：删除后端记录 + 清除缓存 + 重置为默认值
  const remove = useCallback(() => {
    preferenceCache.delete(key)
    setValue(defaultValue)
    preferencesApi.remove(key).catch(() => { /* 忽略，下次拉取会用默认值 */ })
  }, [key, defaultValue])

  // 卸载时清理防抖定时器：从模块级 writeTimers 中清理当前 key 的定时器
  useEffect(() => {
    return () => {
      const timer = writeTimers.get(key)
      if (timer) {
        clearTimeout(timer)
        writeTimers.delete(key)
      }
    }
  }, [key])

  return [value, setAndPersist, { loading, error, remove }]
}

/**
 * 失效全部偏好缓存：切换账号后调用，确保下次 usePreferences 拉取新用户偏好
 */
export function invalidatePreferenceCache(): void {
  preferenceCache.clear()
  inflightRequests.clear()
  // 同时清理所有防抖定时器：切换账号后旧用户的待写入应该取消
  for (const timer of writeTimers.values()) {
    clearTimeout(timer)
  }
  writeTimers.clear()
}

/**
 * 批量预加载偏好：在 MainLayout 挂载时调用，提前拉取多个 key 减少首屏闪烁
 */
export async function prefetchPreferences(keys: string[]): Promise<void> {
  const missing = keys.filter((k) => !preferenceCache.has(k) && !inflightRequests.has(k))
  if (missing.length === 0) return
  try {
    const all = await preferencesApi.getAll()
    for (const k of missing) {
      if (k in all) {
        preferenceCache.set(k, all[k])
      }
    }
  } catch {
    // 预加载失败：忽略，各 hook 会自行重试
  }
}
