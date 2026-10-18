import { describe, it, expect } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useOpenKeysOnDeepLink } from '../useOpenKeysOnDeepLink'

// T02559 / 2.4 深链定位：菜单是 GET /api/menu 异步拉回的，
// 首帧 autoOpenKeys 恒为空，若只靠 useState 初值，深链打开分组内页面时侧栏不展开。
describe('useOpenKeysOnDeepLink', () => {
  it('菜单异步到达后，首屏展开当前路由所属分组', () => {
    const { result, rerender } = renderHook(
      ({ keys, ready }: { keys: string[]; ready: boolean }) =>
        useOpenKeysOnDeepLink(keys, ready),
      { initialProps: { keys: [], ready: false } },
    )
    expect(result.current.openKeys).toEqual([])

    rerender({ keys: ['system'], ready: true })
    expect(result.current.openKeys).toEqual(['system'])
  })

  it('挂载时菜单已就绪则直接展开，无需等 effect', () => {
    const { result } = renderHook(() => useOpenKeysOnDeepLink(['data'], true))
    expect(result.current.openKeys).toEqual(['data'])
  })

  it('用户手动开合后，路由变化不再联动', () => {
    const { result, rerender } = renderHook(
      ({ keys, ready }: { keys: string[]; ready: boolean }) =>
        useOpenKeysOnDeepLink(keys, ready),
      { initialProps: { keys: [], ready: false } },
    )
    act(() => result.current.setOpenKeys(['tasks']))
    rerender({ keys: ['system'], ready: true })
    expect(result.current.openKeys).toEqual(['tasks'])
  })

  it('初始展开后不再被后续 autoOpenKeys 变化覆盖', () => {
    const { result, rerender } = renderHook(
      ({ keys }: { keys: string[] }) => useOpenKeysOnDeepLink(keys, true),
      { initialProps: { keys: ['data'] } },
    )
    rerender({ keys: ['system'] })
    expect(result.current.openKeys).toEqual(['data'])
  })

  it('菜单未就绪时即使有 keys 也不提前展开', () => {
    const { result } = renderHook(() => useOpenKeysOnDeepLink([], false))
    expect(result.current.openKeys).toEqual([])
  })
})
