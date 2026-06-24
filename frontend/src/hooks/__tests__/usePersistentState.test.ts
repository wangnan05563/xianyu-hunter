import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { usePersistentState } from '../usePersistentState'

// Mock localStorage
const store = new Map<string, string>()
const localStorageMock = {
  getItem: vi.fn((key: string) => store.get(key) ?? null),
  setItem: vi.fn((key: string, value: string) => { store.set(key, value) }),
  removeItem: vi.fn((key: string) => { store.delete(key) }),
  clear: vi.fn(() => { store.clear() }),
}

beforeEach(() => {
  store.clear()
  vi.clearAllMocks()
  vi.useFakeTimers()
  Object.defineProperty(globalThis, 'localStorage', {
    value: localStorageMock,
    writable: true,
    configurable: true,
  })
})

afterEach(() => {
  vi.useRealTimers()
})

describe('usePersistentState', () => {
  it('初始化时从 localStorage 读取已存储的值', () => {
    // 预先写入数据
    store.set('xh.test.init', JSON.stringify({ __v: 1, data: 42 }))

    const { result } = renderHook(() => usePersistentState('xh.test.init', 0))
    expect(result.current[0]).toBe(42)
  })

  it('localStorage 无数据时使用默认值', () => {
    const { result } = renderHook(() => usePersistentState('xh.test.default', 'fallback'))
    expect(result.current[0]).toBe('fallback')
  })

  it('状态变化后自动保存到 localStorage（防抖）', () => {
    const { result } = renderHook(() =>
      usePersistentState('xh.test.save', 'initial', { debounce: 300 }),
    )

    act(() => {
      result.current[1]('updated')
    })

    // 防抖期间不应写入
    expect(localStorageMock.setItem).not.toHaveBeenCalled()

    // 防抖结束后写入
    act(() => {
      vi.advanceTimersByTime(300)
    })

    expect(localStorageMock.setItem).toHaveBeenCalledWith(
      'xh.test.save',
      expect.stringContaining('"data":"updated"'),
    )
  })

  it('支持函数式更新', () => {
    store.set('xh.test.func', JSON.stringify({ __v: 1, data: 10 }))

    const { result } = renderHook(() => usePersistentState('xh.test.func', 0))

    act(() => {
      result.current[1]((prev) => prev + 5)
    })

    expect(result.current[0]).toBe(15)

    act(() => {
      vi.advanceTimersByTime(300)
    })

    // 验证写入的值是更新后的值
    const written = JSON.parse(localStorageMock.setItem.mock.calls[0][1])
    expect(written.data).toBe(15)
  })

  it('validator 验证失败时返回默认值', () => {
    // 写入类型不匹配的脏数据
    store.set('xh.test.dirty', JSON.stringify({ __v: 1, data: 'not-a-number' }))

    const { result } = renderHook(() =>
      usePersistentState('xh.test.dirty', 0, {
        validator: (v): v is number => typeof v === 'number',
      }),
    )

    expect(result.current[0]).toBe(0)
  })

  it('remove 方法清除存储并重置为默认值', () => {
    store.set('xh.test.rm', JSON.stringify({ __v: 1, data: 'stored' }))

    const { result } = renderHook(() => usePersistentState('xh.test.rm', 'default'))

    expect(result.current[0]).toBe('stored')

    act(() => {
      result.current[2].remove()
    })

    expect(result.current[0]).toBe('default')
    expect(localStorageMock.removeItem).toHaveBeenCalledWith('xh.test.rm')
  })

  it('isPersistent 标识在 localStorage 可用时为 true', () => {
    const { result } = renderHook(() => usePersistentState('xh.test.persist', 'val'))
    expect(result.current[2].isPersistent).toBe(true)
  })

  it('快速连续更新只写入最后一次（防抖合并）', () => {
    const { result } = renderHook(() =>
      usePersistentState('xh.test.debounce', 0, { debounce: 300 }),
    )

    // 连续更新 3 次
    act(() => { result.current[1](1) })
    act(() => { result.current[1](2) })
    act(() => { result.current[1](3) })

    act(() => {
      vi.advanceTimersByTime(300)
    })

    // 只写入一次，值为最后一次更新
    expect(localStorageMock.setItem).toHaveBeenCalledTimes(1)
    const written = JSON.parse(localStorageMock.setItem.mock.calls[0][1])
    expect(written.data).toBe(3)
  })

  it('对象类型数据正确序列化和反序列化', () => {
    const defaultValue = { name: '', count: 0 }
    store.set(
      'xh.test.obj',
      JSON.stringify({ __v: 1, data: { name: '张三', count: 5 } }),
    )

    const { result } = renderHook(() =>
      usePersistentState('xh.test.obj', defaultValue, {
        validator: (v): v is { name: string; count: number } =>
          v !== null && typeof v === 'object' && 'name' in v && 'count' in v,
      }),
    )

    expect(result.current[0]).toEqual({ name: '张三', count: 5 })

    act(() => {
      result.current[1]({ name: '李四', count: 10 })
    })

    act(() => {
      vi.advanceTimersByTime(300)
    })

    const written = JSON.parse(localStorageMock.setItem.mock.calls[0][1])
    expect(written.data).toEqual({ name: '李四', count: 10 })
  })
})
