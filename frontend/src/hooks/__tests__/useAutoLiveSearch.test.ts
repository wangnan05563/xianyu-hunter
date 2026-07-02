import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useAutoLiveSearch } from '../useAutoLiveSearch'

// Mock taskLinkApi.live：返回 Promise<{ items: [] }>
vi.mock('../../api', () => ({
  taskLinkApi: {
    live: vi.fn().mockResolvedValue({ items: [] }),
  },
}))

// Mock Task 类型最小子集
interface MockTask {
  id: string
  status: 'running' | 'paused' | 'stopped'
  interval_seconds: number
}

beforeEach(() => {
  vi.useFakeTimers()
  // 默认页面可见
  Object.defineProperty(document, 'hidden', { value: false, configurable: true, writable: true })
})

afterEach(() => {
  vi.useRealTimers()
  vi.clearAllMocks()
})

describe('useAutoLiveSearch', () => {
  it('enabled=false 时 remainMap 为空', () => {
    const tasks: MockTask[] = [{ id: 't1', status: 'running', interval_seconds: 60 }]
    const { result } = renderHook(() => useAutoLiveSearch({ tasks: tasks as any, enabled: false }))
    expect(result.current.remainMap).toEqual({})
    expect(result.current.searchingIds.size).toBe(0)
  })

  it('enabled=true 时初始化 running 任务的倒计时为 interval_seconds', () => {
    const tasks: MockTask[] = [
      { id: 't1', status: 'running', interval_seconds: 30 },
      { id: 't2', status: 'paused', interval_seconds: 60 },
    ]
    const { result } = renderHook(() => useAutoLiveSearch({ tasks: tasks as any, enabled: true }))
    expect(result.current.remainMap).toEqual({ t1: 30 })
  })

  it('每秒 tick 倒计时递减 1', () => {
    const tasks: MockTask[] = [{ id: 't1', status: 'running', interval_seconds: 60 }]
    const { result } = renderHook(() => useAutoLiveSearch({ tasks: tasks as any, enabled: true }))
    expect(result.current.remainMap.t1).toBe(60)
    act(() => { vi.advanceTimersByTime(1000) })
    expect(result.current.remainMap.t1).toBe(59)
    act(() => { vi.advanceTimersByTime(1000) })
    expect(result.current.remainMap.t1).toBe(58)
  })

  it('document.hidden=true 时 tick 不递减', () => {
    Object.defineProperty(document, 'hidden', { value: true, configurable: true })
    const tasks: MockTask[] = [{ id: 't1', status: 'running', interval_seconds: 60 }]
    const { result } = renderHook(() => useAutoLiveSearch({ tasks: tasks as any, enabled: true }))
    expect(result.current.remainMap.t1).toBe(60)
    act(() => { vi.advanceTimersByTime(5000) })
    expect(result.current.remainMap.t1).toBe(60)
  })

  it('任务状态从 running 变为 paused 时从 remainMap 移除', () => {
    const initial: MockTask[] = [{ id: 't1', status: 'running', interval_seconds: 60 }]
    const { result, rerender } = renderHook(({ tasks }) => useAutoLiveSearch({ tasks: tasks as any, enabled: true }), {
      initialProps: { tasks: initial },
    })
    expect(result.current.remainMap.t1).toBe(60)
    rerender({ tasks: [{ id: 't1', status: 'paused', interval_seconds: 60 }] })
    expect(result.current.remainMap.t1).toBeUndefined()
  })

  it('搜索完成后倒计时重置为 interval_seconds', async () => {
    const { taskLinkApi } = await import('../../api')
    ;(taskLinkApi.live as any).mockResolvedValue({ items: [{ id: 1 }, { id: 2 }] })

    const tasks: MockTask[] = [{ id: 't1', status: 'running', interval_seconds: 30 }]
    const { result } = renderHook(() => useAutoLiveSearch({ tasks: tasks as any, enabled: true }))
    // 快进 30 秒，触发搜索入队
    act(() => { vi.advanceTimersByTime(30 * 1000) })
    expect(result.current.remainMap.t1).toBe(0)
    // 推进 1 秒让 Promise 微任务 flush
    // 为什么不用 runAllTimersAsync：Hook 内有 setInterval，会导致无限循环
    await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
    expect(result.current.remainMap.t1).toBe(30)
  })

  it('搜索失败时倒计时仍重置', async () => {
    const { taskLinkApi } = await import('../../api')
    ;(taskLinkApi.live as any).mockRejectedValue(new Error('network'))

    const tasks: MockTask[] = [{ id: 't1', status: 'running', interval_seconds: 45 }]
    const { result } = renderHook(() => useAutoLiveSearch({ tasks: tasks as any, enabled: true }))
    act(() => { vi.advanceTimersByTime(45 * 1000) })
    await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
    expect(result.current.remainMap.t1).toBe(45)
  })

  it('pauseAll 清空 remainMap 与队列', () => {
    const tasks: MockTask[] = [{ id: 't1', status: 'running', interval_seconds: 60 }]
    const { result } = renderHook(() => useAutoLiveSearch({ tasks: tasks as any, enabled: true }))
    expect(result.current.remainMap.t1).toBe(60)
    act(() => { result.current.pauseAll() })
    expect(result.current.remainMap).toEqual({})
  })

  it('搜索中倒计时保持不递减（避免显示负数）', async () => {
    const { taskLinkApi } = await import('../../api')
    // 用可控 Promise 阻塞搜索完成，确保搜索中状态持续
    let resolveSearch!: (v: { items: any[] }) => void
    ;(taskLinkApi.live as any).mockImplementation(
      () => new Promise((resolve) => { resolveSearch = resolve }),
    )

    const tasks: MockTask[] = [{ id: 't1', status: 'running', interval_seconds: 5 }]
    const { result } = renderHook(() => useAutoLiveSearch({ tasks: tasks as any, enabled: true }))
    // 快进 5 秒，倒计时到 0 触发搜索入队
    act(() => { vi.advanceTimersByTime(5 * 1000) })
    expect(result.current.remainMap.t1).toBe(0)
    expect(result.current.searchingIds.has('t1')).toBe(true)

    // 搜索未完成期间再 tick 3 秒，倒计时应保持 0 不递减为负
    act(() => { vi.advanceTimersByTime(3 * 1000) })
    expect(result.current.remainMap.t1).toBe(0)

    // 释放搜索 Promise 让 finally 重置倒计时
    await act(async () => {
      resolveSearch({ items: [] })
      await vi.advanceTimersByTimeAsync(1000)
    })
    expect(result.current.remainMap.t1).toBe(5)
  })

  it('resumeAll 重置所有 running 任务的倒计时', () => {
    const tasks: MockTask[] = [{ id: 't1', status: 'running', interval_seconds: 60 }]
    const { result } = renderHook(() => useAutoLiveSearch({ tasks: tasks as any, enabled: true }))
    // 倒计时递减到 50
    act(() => { vi.advanceTimersByTime(10 * 1000) })
    expect(result.current.remainMap.t1).toBe(50)
    // pauseAll 清空
    act(() => { result.current.pauseAll() })
    expect(result.current.remainMap).toEqual({})
    // resumeAll 重置为 interval_seconds
    act(() => { result.current.resumeAll() })
    expect(result.current.remainMap.t1).toBe(60)
  })

  it('选项 B：页面隐藏后恢复可见时保留剩余值并继续递减', () => {
    const tasks: MockTask[] = [{ id: 't1', status: 'running', interval_seconds: 60 }]
    const { result } = renderHook(() => useAutoLiveSearch({ tasks: tasks as any, enabled: true }))
    // 递减到 55
    act(() => { vi.advanceTimersByTime(5 * 1000) })
    expect(result.current.remainMap.t1).toBe(55)

    // 页面隐藏：tick 不递减，remainMap 保持 55（不重置为 60）
    // 直接修改 document.hidden 不会触发 visibilitychange 事件，需手动派发
    // 否则 visibleRef 仍是 true，tick 会继续递减
    Object.defineProperty(document, 'hidden', { value: true, configurable: true })
    act(() => { document.dispatchEvent(new Event('visibilitychange')) })
    act(() => { vi.advanceTimersByTime(10 * 1000) })
    expect(result.current.remainMap.t1).toBe(55)

    // 页面恢复可见：从 55 继续递减（选项 B：保留剩余值）
    Object.defineProperty(document, 'hidden', { value: false, configurable: true })
    act(() => { document.dispatchEvent(new Event('visibilitychange')) })
    act(() => { vi.advanceTimersByTime(5 * 1000) })
    expect(result.current.remainMap.t1).toBe(50)
  })
})
