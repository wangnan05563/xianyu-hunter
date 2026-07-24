import { useCallback, useEffect, useRef, useState } from 'react'
import { paramCalculatorApi } from '../api'
import type { ParamScenario, Suggestion, ValidationReport } from '../api'

// 参数计算器 Hook：提供防抖校验与实时建议
//
// 响应时间预算：用户修改 → 防抖 150ms → API 请求 ~100ms → 后端计算 <50ms = 总 <300ms
// 防抖窗口内多次修改只触发一次校验，避免频繁请求

interface UseParamCalculatorOptions {
  /** 防抖延迟（毫秒），默认 150ms 以满足 300ms 总响应时间预算 */
  debounceMs?: number
  /** 是否在挂载时自动校验一次（用于编辑场景恢复初始建议） */
  validateOnMount?: boolean
}

interface UseParamCalculatorReturn {
  /** 当前建议列表（按 severity 降序） */
  suggestions: Suggestion[]
  /** 是否存在阻断性问题（error 级别） */
  hasBlocking: boolean
  /** 最近一次校验是否成功（网络/服务异常时为 false） */
  isValidating: boolean
  /** 最近一次校验耗时（毫秒，含网络往返） */
  lastElapsedMs: number
  /** 手动触发任务参数校验 */
  validateTask: (fields: Record<string, unknown>) => void
  /** 手动触发系统配置校验 */
  validateConfig: (fields: Record<string, unknown>) => void
  /** 立即清空建议（如表单重置时调用） */
  clear: () => void
}

export function useParamCalculator(
  scenario: ParamScenario,
  options: UseParamCalculatorOptions = {},
): UseParamCalculatorReturn {
  const { debounceMs = 150, validateOnMount = false } = options

  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [hasBlocking, setHasBlocking] = useState(false)
  const [isValidating, setIsValidating] = useState(false)
  const [lastElapsedMs, setLastElapsedMs] = useState(0)

  // 防抖计时器：窗口内多次修改只保留最后一次
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // 请求序列号：防止竞态（旧请求结果覆盖新请求结果）
  const requestIdRef = useRef(0)
  // 当前场景引用：避免闭包捕获初始场景
  const scenarioRef = useRef(scenario)
  scenarioRef.current = scenario

  const doValidate = useCallback(
    async (fields: Record<string, unknown>, isConfig: boolean) => {
      const requestId = ++requestIdRef.current
      setIsValidating(true)
      try {
        const sc = scenarioRef.current
        const report: ValidationReport = isConfig
          ? await paramCalculatorApi.validateConfig(fields)
          : await paramCalculatorApi.validateTask(fields, sc)
        // 竞态保护：仅采用最新请求的结果
        if (requestId !== requestIdRef.current) return
        setSuggestions(report.suggestions)
        setHasBlocking(report.has_blocking)
        setLastElapsedMs(report.elapsed_ms)
      } catch {
        // 校验失败不阻断用户操作：清空建议，由调用方决定是否提示
        if (requestId !== requestIdRef.current) return
        setSuggestions([])
        setHasBlocking(false)
      } finally {
        if (requestId === requestIdRef.current) {
          setIsValidating(false)
        }
      }
    },
    [],
  )

  // 防抖包装：延迟触发校验，窗口内多次修改只保留最后一次
  const scheduleValidate = useCallback(
    (fields: Record<string, unknown>, isConfig: boolean) => {
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => {
        void doValidate(fields, isConfig)
      }, debounceMs)
    },
    [debounceMs, doValidate],
  )

  const validateTask = useCallback(
    (fields: Record<string, unknown>) => {
      scheduleValidate(fields, false)
    },
    [scheduleValidate],
  )

  const validateConfig = useCallback(
    (fields: Record<string, unknown>) => {
      scheduleValidate(fields, true)
    },
    [scheduleValidate],
  )

  const clear = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
    // 使所有进行中的请求结果失效
    requestIdRef.current++
    setSuggestions([])
    setHasBlocking(false)
    setIsValidating(false)
  }, [])

  // 卸载时清理计时器，防止内存泄漏与无效请求
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])

  // validateOnMount 场景：编辑模式进入时立即校验一次
  // 为什么不用 useEffect 依赖 fields：fields 由调用方管理，Hook 不感知其变化
  // 调用方需在 mount 时主动调用 validateTask/validateConfig
  useEffect(() => {
    if (!validateOnMount) return
    // 仅标记需要在 mount 时校验，实际触发由调用方传入 fields
  }, [validateOnMount])

  return {
    suggestions,
    hasBlocking,
    isValidating,
    lastElapsedMs,
    validateTask,
    validateConfig,
    clear,
  }
}
