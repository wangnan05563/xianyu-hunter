import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from 'react'
import { storage } from '../utils/storage'

/**
 * 持久化状态 Hook —— useState 的持久化版本
 *
 * 为什么需要这个 Hook：
 * 1. 各页面 UI 偏好（分页大小、视图模式、筛选条件等）需要跨会话保留，
 *    之前各组件自己管理 localStorage，逻辑重复且错误处理不一致
 * 2. API 与 useState 完全兼容，替换时只需改函数名和加 key，无侵入
 * 3. 统一的防抖写入、数据验证、错误处理和回退机制
 *
 * 使用示例：
 *   const [pageSize, setPageSize] = usePersistentState('xh.items.pageSize', 20, {
 *     validator: (v): v is number => typeof v === 'number' && v > 0
 *   })
 *
 * @param key localStorage 存储键
 * @param defaultValue 默认值（读取失败或验证不通过时使用）
 * @param options.validator 数据验证函数，防止脏数据导致 UI 异常
 * @param options.debounce 写入防抖（ms），避免快速交互时频繁写入，默认 300
 */
export function usePersistentState<T>(
  key: string,
  defaultValue: T,
  options?: {
    validator?: (value: unknown) => value is T
    debounce?: number
  },
): [T, Dispatch<SetStateAction<T>>, { remove: () => void; isPersistent: boolean }] {
  const validator = options?.validator
  const debounceMs = options?.debounce ?? 300

  // 初始化：从 localStorage 读取，验证通过则使用存储值，否则用默认值
  // 为什么用 lazy initializer：避免每次渲染都读 localStorage
  const [state, setState] = useState<T>(() => storage.get(key, defaultValue, validator))

  // 追踪是否真正持久化（localStorage 不可用时为 false）
  const [isPersistent, setIsPersistent] = useState<boolean>(() => storage.isAvailable())

  // 防抖写入：用 ref 保存定时器，避免每次渲染重建
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    // 防抖写入：快速交互（如连续切换视图模式）时只写最后一次
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => {
      const ok = storage.set(key, state)
      // localStorage 状态变化时更新标识（如用户中途清除存储）
      if (ok !== isPersistent) setIsPersistent(ok)
    }, debounceMs)

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [key, state, debounceMs, isPersistent])

  // 清除存储并重置为默认值
  const remove = useCallback(() => {
    storage.remove(key)
    setState(defaultValue)
  }, [key, defaultValue])

  return [state, setState, { remove, isPersistent }]
}
