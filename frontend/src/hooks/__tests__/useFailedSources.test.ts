import { renderHook, act } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { useFailedSources } from '../useFailedSources'

type Source = 'a' | 'b'

const rejected = Promise.reject(new Error('boom')) as unknown as Promise<never>
// 顶层未处理拒绝会让 vitest 直接算失败，这里先挂一个空 catch 兜住
void rejected.catch(() => undefined)

describe('useFailedSources 失败账（T02700/T02701 共用实现）', () => {
  it('初始状态没有任何数据源失败', () => {
    const { result } = renderHook(() => useFailedSources<Source>())
    expect(result.current.failed).toEqual({})
    expect(result.current.isFailed('a')).toBe(false)
  })

  it('mark(false) 记上账，mark(true) 销账', () => {
    const { result } = renderHook(() => useFailedSources<Source>())
    act(() => result.current.mark('a', false))
    expect(result.current.isFailed('a')).toBe(true)
    act(() => result.current.mark('a', true))
    expect(result.current.isFailed('a')).toBe(false)
    expect(result.current.failed).toEqual({})
  })

  it('键之间互不影响：只销自己那一笔', () => {
    const { result } = renderHook(() => useFailedSources<Source>())
    act(() => {
      result.current.mark('a', false)
      result.current.mark('b', false)
    })
    act(() => result.current.mark('a', true))
    expect(result.current.isFailed('a')).toBe(false)
    expect(result.current.isFailed('b')).toBe(true)
  })

  it('重复标记同一种结果不产生新 state（避免无谓重渲染）', () => {
    const { result } = renderHook(() => useFailedSources<Source>())
    act(() => result.current.mark('a', false))
    const first = result.current.failed
    act(() => result.current.mark('a', false))
    expect(result.current.failed).toBe(first)
    // 未失败时销账同样应保持引用稳定
    const stable = result.current.failed
    act(() => result.current.mark('b', true))
    expect(result.current.failed).toBe(stable)
  })

  it('settle：成功返回数据并销账，失败返回 null 并记账', () => {
    const { result } = renderHook(() => useFailedSources<Source>())
    let value: unknown = 'unset'
    act(() => {
      value = result.current.settle({ status: 'fulfilled', value: 42 }, 'a')
    })
    expect(value).toBe(42)
    expect(result.current.isFailed('a')).toBe(false)

    act(() => {
      value = result.current.settle(
        { status: 'rejected', reason: new Error('e') } as PromiseSettledResult<number>,
        'a',
      )
    })
    expect(value).toBeNull()
    expect(result.current.isFailed('a')).toBe(true)
  })

  it('track：成功返回数据，失败返回 null 而不是把异常抛给调用方', async () => {
    const { result } = renderHook(() => useFailedSources<Source>())
    await act(async () => {
      expect(await result.current.track('a', Promise.resolve('ok'))).toBe('ok')
    })
    expect(result.current.isFailed('a')).toBe(false)

    await act(async () => {
      expect(await result.current.track('a', rejected)).toBeNull()
    })
    expect(result.current.isFailed('a')).toBe(true)

    await act(async () => {
      expect(await result.current.track('a', Promise.resolve('retry ok'))).toBe('retry ok')
    })
    expect(result.current.isFailed('a')).toBe(false)
  })
})
