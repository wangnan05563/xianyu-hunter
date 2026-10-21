// T02884：formatDuration 的紧凑单位只是换字形，不能换算法。
// 移动端 AntiCrawl 原先自养一份 `Xh Ym`，与共享实现边界不同（60 秒它写 `1m 0s`、
// 0 秒它写 `0s`），两份实现会在同一个数字上给出两种答案。这里钉住两级单位与边界值一致。
import { describe, it, expect } from 'vitest'
import { formatDateTime, formatDuration } from '../timeFormat'

describe('formatDuration 中文/紧凑两种单位同源（T02884）', () => {
  it.each([
    // [秒数, 中文, 紧凑]
    [4270, '1 小时 11 分', '1h 11m'],
    [3600, '1 小时', '1h'],
    [3599, '59 分 59 秒', '59m 59s'],
    [60, '1 分', '1m'],
    [59, '59 秒', '59s'],
    [0, '不足 1 秒', '0s'],
  ] as const)('%i 秒', (sec, zh, compact) => {
    expect(formatDuration(sec)).toBe(zh)
    expect(formatDuration(sec, { compact: true })).toBe(compact)
  })

  it('小时级不带秒，两种单位一致（避免出现第三种长相）', () => {
    expect(formatDuration(7325)).toBe('2 小时 2 分')
    expect(formatDuration(7325, { compact: true })).toBe('2h 2m')
  })

  it('取不到时长说「—」，不说 0 秒', () => {
    for (const v of [null, undefined, Number.NaN, -1]) {
      expect(formatDuration(v)).toBe('—')
      expect(formatDuration(v, { compact: true })).toBe('—')
    }
  })

  it('formatDateTime 对空值给「—」，对脏值原样回显而不是 1970', () => {
    expect(formatDateTime(null)).toBe('—')
    expect(formatDateTime('not-a-date')).toBe('not-a-date')
    expect(formatDateTime('2026-10-19T05:40:07.728251')).toMatch(/^2026\/10\/19/)
  })
})
