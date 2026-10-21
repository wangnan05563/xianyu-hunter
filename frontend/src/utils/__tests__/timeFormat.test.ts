import { describe, it, expect } from 'vitest'
import { formatDateTime, formatDuration } from '../timeFormat'

// T02695：告警抽屉的裸 ISO（2026-10-19T05:40:07.728251）、裸秒（超时 4270s）与雷达的
// 「N 分钟前」是同一份数据的三种长相。helper 只有一份，这里钉它的口径。

describe('formatDateTime', () => {
  it('后端带微秒的裸 ISO 渲染成本地可读时间，不再露出 T/微秒', () => {
    const out = formatDateTime('2026-10-19T05:40:07.728251')
    expect(out).not.toContain('T')
    expect(out).not.toMatch(/\.\d/)
    expect(out).toMatch(/2026/)
    expect(out).toMatch(/10/)
  })

  it('空值给占位符而不是 Invalid Date / 1970', () => {
    expect(formatDateTime(null)).toBe('—')
    expect(formatDateTime(undefined)).toBe('—')
    expect(formatDateTime('')).toBe('—')
  })

  it('解析不了的字符串原样返回，不伪装成时间', () => {
    expect(formatDateTime('not-a-date')).toBe('not-a-date')
  })
})

describe('formatDuration', () => {
  it('4270 秒说成「1 小时 11 分」，用户不用心算', () => {
    expect(formatDuration(4270)).toBe('1 小时 11 分')
  })

  it('按时段选单位，最多两级', () => {
    expect(formatDuration(3600)).toBe('1 小时')
    expect(formatDuration(3661)).toBe('1 小时 1 分')
    expect(formatDuration(60)).toBe('1 分')
    expect(formatDuration(90)).toBe('1 分 30 秒')
    expect(formatDuration(59)).toBe('59 秒')
    expect(formatDuration(0)).toBe('不足 1 秒')
  })

  it('缺失/负数/NaN 给占位符，不显示「-3 秒」这种脏值', () => {
    expect(formatDuration(null)).toBe('—')
    expect(formatDuration(undefined)).toBe('—')
    expect(formatDuration(-5)).toBe('—')
    expect(formatDuration(Number.NaN)).toBe('—')
  })
})
