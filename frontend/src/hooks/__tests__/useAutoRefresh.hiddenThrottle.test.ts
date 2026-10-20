import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useAutoRefresh } from '../useAutoRefresh'

/**
 * N13（T02562 / 6.2 复测项）：桌面端兜底轮询必须随 document.hidden 降频。
 *
 * 原症状：只有移动端在页面隐藏时停轮询，桌面端照旧 30s 一次，
 * 后台标签页越开越多、请求量线性上涨，两端行为还不一致。
 * 现在的口径是「降频 3 倍」（BACKGROUND_SLOWDOWN=3），不是彻底停：
 * SSE 仍是主通道，兜底轮询要在后台保留一个更慢的保底。
 *
 * 为什么用假计时器：这条断言的本质是「下一次刷新被排到 3 倍之后」，
 * 真计时器要等 90 秒，且受调度抖动影响；假计时器把 10s/30s 变成确定量。
 */
const INTERVAL_SEC = 10
const SLOWDOWN = 3

function setHidden(value: boolean) {
  Object.defineProperty(document, 'visibilityState', {
    configurable: true,
    get: () => (value ? 'hidden' : 'visible'),
  })
  Object.defineProperty(document, 'hidden', { configurable: true, get: () => value })
}

/** 切可见性并派发事件；包在 act 里，保证 hook 的重新排期落到 result.current 上 */
async function flipHidden(value: boolean) {
  await act(async () => {
    setHidden(value)
    document.dispatchEvent(new Event('visibilitychange'))
  })
}

/** 推进假计时器并 flush 刷新回调里的微任务链 */
async function tick(ms: number) {
  await act(async () => {
    vi.advanceTimersByTime(ms)
  })
}

/** 下次兜底轮询距今的秒数（nextRefreshAt 为空表示未调度） */
function remainingSec(nextRefreshAt: number | null): number | null {
  if (nextRefreshAt === null) return null
  return Math.round((nextRefreshAt - Date.now()) / 1000)
}

describe('useAutoRefresh 页面隐藏降频（N13）', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    setHidden(false)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('可见时按 intervalSec 排期，隐藏后同一档被推后到 3 倍', async () => {
    const refresh = vi.fn().mockResolvedValue(undefined)
    const { result } = renderHook(() =>
      useAutoRefresh({ enabled: true, intervalSec: INTERVAL_SEC, refresh }),
    )

    // 可见：首帧只排期不刷新，下一次落在 intervalSec
    expect(remainingSec(result.current.nextRefreshAt)).toBe(INTERVAL_SEC)
    await tick(INTERVAL_SEC * 1000)
    expect(refresh).toHaveBeenCalledTimes(1)
    // 刷新完成后重新排期，仍是 10s
    expect(remainingSec(result.current.nextRefreshAt)).toBe(INTERVAL_SEC)

    await flipHidden(true)
    expect(remainingSec(result.current.nextRefreshAt)).toBe(INTERVAL_SEC * SLOWDOWN)

    await tick(INTERVAL_SEC * 1000 * SLOWDOWN - 1)
    expect(refresh).toHaveBeenCalledTimes(1) // 后台 10s/20s 这两档都不该发
    await tick(2)
    expect(refresh).toHaveBeenCalledTimes(2) // 到 3 倍间隔才补发
  })

  it('恢复可见后回到正常间隔', async () => {
    const refresh = vi.fn().mockResolvedValue(undefined)
    const { result } = renderHook(() =>
      useAutoRefresh({ enabled: true, intervalSec: INTERVAL_SEC, refresh }),
    )
    await tick(INTERVAL_SEC * 1000)
    expect(refresh).toHaveBeenCalledTimes(1)

    await flipHidden(true)
    expect(remainingSec(result.current.nextRefreshAt)).toBe(INTERVAL_SEC * SLOWDOWN)
    await tick(INTERVAL_SEC * 1000)
    expect(refresh).toHaveBeenCalledTimes(1)

    await flipHidden(false)
    // 恢复可见时不重置倒计时（避免切标签页造成请求风暴），但也不会继续吃 3 倍剩余
    expect(remainingSec(result.current.nextRefreshAt)).toBe(INTERVAL_SEC * SLOWDOWN - INTERVAL_SEC)
    await tick(INTERVAL_SEC * 1000 * (SLOWDOWN - 1))
    expect(refresh).toHaveBeenCalledTimes(2)
    // 补发之后重新排期：间隔回到 intervalSec，与可见态一致
    expect(remainingSec(result.current.nextRefreshAt)).toBe(INTERVAL_SEC)
  })
})
