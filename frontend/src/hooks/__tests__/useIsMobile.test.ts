import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useIsMobile } from '../useIsMobile'

// matchMedia mock：用对象保存当前查询结果，便于测试动态切换
let currentMatches = false
const listeners = new Set<(e: MediaQueryListEvent) => void>()

beforeEach(() => {
  currentMatches = false
  listeners.clear()
  // matchMedia 必须返回带 addEventListener/removeEventListener 的 MediaQueryList
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: currentMatches,
      media: query,
      onchange: null,
      addEventListener: (_: string, l: (e: MediaQueryListEvent) => void) => listeners.add(l),
      removeEventListener: (_: string, l: (e: MediaQueryListEvent) => void) => listeners.delete(l),
      dispatchEvent: () => false,
    })),
  })
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useIsMobile', () => {
  it('桌面端（>=768px）返回 false', () => {
    currentMatches = false
    const { result } = renderHook(() => useIsMobile())
    expect(result.current).toBe(false)
  })

  it('移动端（<768px）返回 true', () => {
    currentMatches = true
    const { result } = renderHook(() => useIsMobile())
    expect(result.current).toBe(true)
  })

  it('断点变化时同步更新', () => {
    currentMatches = false
    const { result } = renderHook(() => useIsMobile())
    expect(result.current).toBe(false)

    // 模拟断点切换到移动端
    currentMatches = true
    act(() => {
      listeners.forEach((l) => l({ matches: true, media: '(max-width: 767px)' } as MediaQueryListEvent))
    })
    expect(result.current).toBe(true)
  })

  it('查询的是 (max-width: 767px) 断点', () => {
    renderHook(() => useIsMobile())
    expect(window.matchMedia).toHaveBeenCalledWith('(max-width: 767px)')
  })
})
