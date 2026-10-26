// useDebouncedAction 单测（T02669）：筛选「改完就查」的计时语义
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { FILTER_AUTO_DELAY_MS, useDebouncedAction } from '../useDebouncedAction'

describe('useDebouncedAction', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('连续改多次只查一次，且要等满 300ms 才查', () => {
    const action = vi.fn()
    const { result } = renderHook(() => useDebouncedAction(action))
    result.current.schedule()
    result.current.schedule()
    result.current.schedule()
    expect(action).not.toHaveBeenCalled()
    // 这里故意写死毫秒数而不是引用常量：常量若被改成 0，等价于「改一下就发请求」，
    // 本单要的正是那段等待，只有钉死数字才能发现退化
    act(() => vi.advanceTimersByTime(100))
    expect(action).not.toHaveBeenCalled()
    act(() => vi.advanceTimersByTime(200))
    expect(action).toHaveBeenCalledTimes(1)
  })

  it('flush 是立即执行：取消尚未到点的自动查询，只查这一次', () => {
    const action = vi.fn()
    const { result } = renderHook(() => useDebouncedAction(action))
    result.current.schedule()
    act(() => vi.advanceTimersByTime(100))
    result.current.flush()
    expect(action).toHaveBeenCalledTimes(1)
    act(() => vi.advanceTimersByTime(FILTER_AUTO_DELAY_MS))
    expect(action).toHaveBeenCalledTimes(1)
  })

  it('到点执行的是最新那次 action，不是挂载时的旧闭包', () => {
    const first = vi.fn()
    const second = vi.fn()
    const { result, rerender } = renderHook(
      ({ action }: { action: () => void }) => useDebouncedAction(action),
      { initialProps: { action: first } },
    )
    result.current.schedule()
    rerender({ action: second })
    act(() => vi.advanceTimersByTime(FILTER_AUTO_DELAY_MS))
    expect(first).not.toHaveBeenCalled()
    expect(second).toHaveBeenCalledTimes(1)
  })

  it('卸载后不再补发查询', () => {
    const action = vi.fn()
    const { result, unmount } = renderHook(() => useDebouncedAction(action))
    result.current.schedule()
    unmount()
    act(() => vi.advanceTimersByTime(FILTER_AUTO_DELAY_MS * 2))
    expect(action).not.toHaveBeenCalled()
  })
})
