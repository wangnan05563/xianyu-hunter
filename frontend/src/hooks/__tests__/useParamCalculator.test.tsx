import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'

// Mock API 模块：避免实际网络请求，允许断言调用参数与控制返回值
const validateTaskMock = vi.fn()
const validateConfigMock = vi.fn()

vi.mock('../../api', () => ({
  paramCalculatorApi: {
    validateTask: (...args: unknown[]) => validateTaskMock(...args),
    validateConfig: (...args: unknown[]) => validateConfigMock(...args),
  },
}))

import { useParamCalculator } from '../useParamCalculator'
import type { ValidationReport } from '../../api'

// 构造一个最小的合法校验报告
function makeReport(overrides: Partial<ValidationReport> = {}): ValidationReport {
  return {
    scenario: 'task_create',
    ok: true,
    has_blocking: false,
    warning_count: 0,
    info_count: 0,
    elapsed_ms: 12,
    suggestions: [],
    ...overrides,
  }
}

beforeEach(() => {
  vi.useFakeTimers()
  validateTaskMock.mockReset()
  validateConfigMock.mockReset()
})

afterEach(() => {
  // 清除遗留计时器：防止前一个测试的防抖计时器在下一个测试中触发，导致 mock 参数串扰
  vi.clearAllTimers()
  vi.useRealTimers()
})

describe('useParamCalculator', () => {
  describe('初始状态', () => {
    it('返回空建议且不处于校验中状态', () => {
      const { result } = renderHook(() => useParamCalculator('task_create'))
      expect(result.current.suggestions).toEqual([])
      expect(result.current.hasBlocking).toBe(false)
      expect(result.current.isValidating).toBe(false)
      expect(result.current.lastElapsedMs).toBe(0)
    })
  })

  describe('防抖', () => {
    it('validateTask 在防抖窗口内不发起请求', () => {
      const { result } = renderHook(() => useParamCalculator('task_create'))
      act(() => {
        result.current.validateTask({ keyword: 'iphone' })
      })
      // 防抖窗口内尚未调用 API
      expect(validateTaskMock).not.toHaveBeenCalled()
      expect(result.current.isValidating).toBe(false)
    })

    it('防抖结束后发起请求并更新状态', async () => {
      const report = makeReport({
        has_blocking: true,
        elapsed_ms: 42,
        suggestions: [
          {
            code: 'PRICE_RANGE_INVALID',
            severity: 'error',
            category: 'accuracy',
            message: '价格区间无效',
            fix_hint: '检查 min_price <= max_price',
            affected_fields: ['min_price', 'max_price'],
          },
        ],
      })
      validateTaskMock.mockResolvedValue(report)

      const { result } = renderHook(() => useParamCalculator('task_create'))
      act(() => {
        result.current.validateTask({ min_price: 100, max_price: 50 })
      })

      // 推进防抖计时器
      await act(async () => {
        vi.advanceTimersByTime(150)
      })
      await act(async () => {
        // 让微任务队列消费 Promise
      })

      expect(validateTaskMock).toHaveBeenCalledTimes(1)
      expect(validateTaskMock).toHaveBeenCalledWith(
        { min_price: 100, max_price: 50 },
        'task_create',
      )
      expect(result.current.suggestions).toHaveLength(1)
      expect(result.current.hasBlocking).toBe(true)
      expect(result.current.lastElapsedMs).toBe(42)
      expect(result.current.isValidating).toBe(false)
    })

    it('防抖窗口内多次调用只保留最后一次', async () => {
      validateTaskMock.mockResolvedValue(makeReport())
      const { result } = renderHook(() => useParamCalculator('task_create'))

      act(() => {
        result.current.validateTask({ keyword: 'a' })
      })
      act(() => {
        result.current.validateTask({ keyword: 'b' })
      })
      act(() => {
        result.current.validateTask({ keyword: 'c' })
      })

      // 还未到防抖结束，API 不应被调用
      expect(validateTaskMock).not.toHaveBeenCalled()

      // advanceTimersByTimeAsync 会同步推进计时器并 flush 中间的微任务，
      // 避免 Promise resolve 被推迟到下一个测试导致参数串扰
      await act(async () => {
        await vi.advanceTimersByTimeAsync(150)
      })

      // 三次修改合并为一次请求，且采用最后一次参数
      expect(validateTaskMock).toHaveBeenCalledTimes(1)
      expect(validateTaskMock).toHaveBeenCalledWith(
        { keyword: 'c' },
        'task_create',
      )
    })
  })

  describe('场景分发', () => {
    it('task_edit 场景使用 task API 且传入对应 scenario', async () => {
      validateTaskMock.mockResolvedValue(makeReport({ scenario: 'task_edit' }))
      const { result } = renderHook(() => useParamCalculator('task_edit'))

      act(() => {
        result.current.validateTask({ keyword: 'x' })
      })
      await act(async () => {
        vi.advanceTimersByTime(150)
      })
      await act(async () => {})

      expect(validateTaskMock).toHaveBeenCalledWith({ keyword: 'x' }, 'task_edit')
    })

    it('config_update 场景调用 validateConfig 而非 validateTask', async () => {
      validateConfigMock.mockResolvedValue(makeReport({ scenario: 'config_update' }))
      const { result } = renderHook(() => useParamCalculator('config_update'))

      act(() => {
        result.current.validateConfig({ live_search_ttl: 5 })
      })
      await act(async () => {
        vi.advanceTimersByTime(150)
      })
      await act(async () => {})

      expect(validateConfigMock).toHaveBeenCalledTimes(1)
      expect(validateConfigMock).toHaveBeenCalledWith({ live_search_ttl: 5 })
      expect(validateTaskMock).not.toHaveBeenCalled()
    })
  })

  describe('竞态保护', () => {
    it('旧请求晚返回时不会覆盖新请求的结果', async () => {
      // 第一次请求返回阻断性错误，第二次请求返回通过
      let resolveFirst: (v: ValidationReport) => void = () => {}
      let resolveSecond: (v: ValidationReport) => void = () => {}
      validateTaskMock.mockImplementationOnce(
        () => new Promise((res) => { resolveFirst = res }),
      )
      validateTaskMock.mockImplementationOnce(
        () => new Promise((res) => { resolveSecond = res }),
      )

      const { result } = renderHook(() => useParamCalculator('task_create'))

      // 第一次触发
      act(() => {
        result.current.validateTask({ keyword: 'old' })
      })
      await act(async () => {
        vi.advanceTimersByTime(150)
      })
      // 此时第一次请求已发出但未解决

      // 第二次触发：覆盖第一次
      act(() => {
        result.current.validateTask({ keyword: 'new' })
      })
      await act(async () => {
        vi.advanceTimersByTime(150)
      })

      // 让第二次先返回（通过）
      await act(async () => {
        resolveSecond(makeReport({ suggestions: [] }))
        await Promise.resolve()
      })
      expect(result.current.hasBlocking).toBe(false)

      // 第一次晚返回（阻断性错误）应被丢弃
      await act(async () => {
        resolveFirst(makeReport({
          has_blocking: true,
          suggestions: [{
            code: 'OLD',
            severity: 'error',
            category: 'accuracy',
            message: 'should be discarded',
            fix_hint: '',
            affected_fields: [],
          }],
        }))
        await Promise.resolve()
      })
      // 仍是第二次的结果
      expect(result.current.hasBlocking).toBe(false)
      expect(result.current.suggestions).toHaveLength(0)
    })
  })

  describe('错误处理', () => {
    it('API 抛错时清空建议且不阻断用户操作', async () => {
      validateTaskMock.mockRejectedValue(new Error('network down'))
      const { result } = renderHook(() => useParamCalculator('task_create'))

      act(() => {
        result.current.validateTask({ keyword: 'x' })
      })
      await act(async () => {
        vi.advanceTimersByTime(150)
      })
      await act(async () => {})

      expect(result.current.suggestions).toEqual([])
      expect(result.current.hasBlocking).toBe(false)
      expect(result.current.isValidating).toBe(false)
    })
  })

  describe('clear', () => {
    it('立即清空建议并取消待执行的防抖计时器', async () => {
      validateTaskMock.mockResolvedValue(makeReport())
      const { result } = renderHook(() => useParamCalculator('task_create'))

      act(() => {
        result.current.validateTask({ keyword: 'pending' })
      })
      // 防抖未结束就 clear
      act(() => {
        result.current.clear()
      })

      // 推进防抖时间，不应再发起请求
      await act(async () => {
        vi.advanceTimersByTime(200)
      })
      expect(validateTaskMock).not.toHaveBeenCalled()
      expect(result.current.suggestions).toEqual([])
      expect(result.current.isValidating).toBe(false)
    })

    it('clear 使进行中的请求结果失效', async () => {
      let resolveReq: (v: ValidationReport) => void = () => {}
      validateTaskMock.mockImplementationOnce(
        () => new Promise((res) => { resolveReq = res }),
      )

      const { result } = renderHook(() => useParamCalculator('task_create'))
      act(() => {
        result.current.validateTask({ keyword: 'x' })
      })
      await act(async () => {
        vi.advanceTimersByTime(150)
      })

      // 请求已发出但未返回，此时 clear
      act(() => {
        result.current.clear()
      })

      // 请求晚返回阻断性结果，不应被采纳
      await act(async () => {
        resolveReq(makeReport({
          has_blocking: true,
          suggestions: [{
            code: 'STALE',
            severity: 'error',
            category: 'accuracy',
            message: 'stale result',
            fix_hint: '',
            affected_fields: [],
          }],
        }))
        await Promise.resolve()
      })

      expect(result.current.hasBlocking).toBe(false)
      expect(result.current.suggestions).toHaveLength(0)
    })
  })

  describe('卸载清理', () => {
    it('组件卸载后防抖计时器不触发 API 调用', async () => {
      validateTaskMock.mockResolvedValue(makeReport())
      const { result, unmount } = renderHook(() => useParamCalculator('task_create'))

      act(() => {
        result.current.validateTask({ keyword: 'will-unmount' })
      })
      unmount()

      await act(async () => {
        vi.advanceTimersByTime(200)
      })
      expect(validateTaskMock).not.toHaveBeenCalled()
    })
  })
})
