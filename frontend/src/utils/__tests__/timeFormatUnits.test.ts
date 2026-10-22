// T02884：formatDuration 的紧凑单位只是换字形，不能换算法。
// 移动端 AntiCrawl 原先自养一份 `Xh Ym`，与共享实现边界不同（60 秒它写 `1m 0s`、
// 0 秒它写 `0s`），两份实现会在同一个数字上给出两种答案。这里钉住两级单位与边界值一致。
import { describe, it, expect } from 'vitest'
import { formatDateTime, formatDuration, tryFormatDateTime } from '../timeFormat'

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

// T02901：withSeconds 是给正在倒数的计时器用的。默认分支跨过一小时就不念秒，
// 静态统计值无所谓，倒计时会看着像卡住（订单接管、登录已用时）。
describe('formatDuration withSeconds（T02901 倒计时）', () => {
  it.each([
    [4270, '1 小时 11 分 10 秒', '1h 11m 10s'],
    [3600, '1 小时 0 分 0 秒', '1h 0m 0s'],
    [600, '10 分 0 秒', '10m 0s'],
    [65, '1 分 5 秒', '1m 5s'],
    [59, '59 秒', '59s'],
    [0, '不足 1 秒', '0s'],
  ] as const)('%i 秒带秒计数', (sec, zh, compact) => {
    expect(formatDuration(sec, { withSeconds: true })).toBe(zh)
    expect(formatDuration(sec, { compact: true, withSeconds: true })).toBe(compact)
  })

  it('不带 withSeconds 时省略秒零头（静态统计保持两级）', () => {
    expect(formatDuration(4270)).toBe('1 小时 11 分')
    expect(formatDuration(4270, { compact: true })).toBe('1h 11m')
    // 倒计时经过整分那一秒若也这样显示，看起来就像停了
    expect(formatDuration(600)).toBe('10 分')
    expect(formatDuration(600, { compact: true })).toBe('10m')
  })
})

// T02901：移动端与评估明细有四处「解不出就返回 null，整行不显示」的私有实现，
// 判空口径一致、只是没处可放，收到共享 helper 里；这里钉住它与 formatDateTime 的分工
describe('tryFormatDateTime（T02901 可空口径）', () => {
  it('空值与脏值给 null，不给 Invalid Date 也不给占位符', () => {
    for (const v of [null, undefined, '', 'not-a-date']) {
      expect(tryFormatDateTime(v)).toBeNull()
    }
  })

  it('数字时间戳也接得住（Sheet 页签用毫秒）', () => {
    expect(tryFormatDateTime(1760000000000)).toMatch(/2025/)
  })

  it('formatDateTime 与它同源：同一个空值分别得到占位符与 null', () => {
    expect(tryFormatDateTime('')).toBeNull()
    expect(formatDateTime('')).toBe('—')
  })
})
