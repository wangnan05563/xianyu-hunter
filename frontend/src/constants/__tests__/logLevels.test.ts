/**
 * 日志级别归一化单测（T02569 读侧 → T02683 归一后）
 *
 * events.level 自 T02683 起统一为小写全词，别名表已删除；
 * 前端只做大小写归一，展示与配色仍用大写键。
 */
import { describe, it, expect } from 'vitest'
import { countLevels, levelColor, normalizeLevel } from '../logLevels'

describe('normalizeLevel', () => {
  it('规范小写全词归一到大写键', () => {
    expect(normalizeLevel('error')).toBe('ERROR')
    expect(normalizeLevel('warning')).toBe('WARNING')
    expect(normalizeLevel('info')).toBe('INFO')
    expect(normalizeLevel('debug')).toBe('DEBUG')
    expect(normalizeLevel('trace')).toBe('TRACE')
    expect(normalizeLevel('ERROR')).toBe('ERROR')
  })

  it('大小写与首尾空格不影响结果，空值返回空串', () => {
    expect(normalizeLevel('  Error ')).toBe('ERROR')
    expect(normalizeLevel('InFo')).toBe('INFO')
    expect(normalizeLevel(undefined)).toBe('')
    expect(normalizeLevel(null)).toBe('')
    expect(normalizeLevel('')).toBe('')
  })

  it('未知字面值原样大写返回，不吞掉也不误并', () => {
    expect(normalizeLevel('critical')).toBe('CRITICAL')
  })

  it('旧缩写不再被合并（T02683 后库里不会再有）', () => {
    expect(normalizeLevel('err')).toBe('ERR')
    expect(normalizeLevel('warn')).toBe('WARN')
  })
})

describe('levelColor', () => {
  it('规范级别取到对应颜色', () => {
    expect(levelColor('error')).toBe('red')
    expect(levelColor('warning')).toBe('orange')
    expect(levelColor('info')).toBe('blue')
    expect(levelColor('debug')).toBe('default')
  })

  it('未知级别与空值回退 default（灰色），不再依赖调用方兜底', () => {
    expect(levelColor('critical')).toBe('default')
    expect(levelColor(undefined)).toBe('default')
  })
})

describe('countLevels', () => {
  it('按规范级别累加', () => {
    const dist = countLevels([
      { level: 'error' },
      { level: 'warning' },
      { level: 'info' },
      { level: 'warning' },
    ])
    expect(dist.ERROR).toBe(1)
    expect(dist.WARNING).toBe(2)
    expect(dist.INFO).toBe(1)
  })

  it('四个主级别即使没有数据也保持 0 占位，口径与旧版一致', () => {
    const dist = countLevels([{ level: 'error' }])
    expect(Object.keys(dist).slice(0, 4)).toEqual(['ERROR', 'WARNING', 'INFO', 'DEBUG'])
    expect(dist.WARNING).toBe(0)
    expect(dist.DEBUG).toBe(0)
  })

  it('出现过的其他级别补在尾部，不静默丢数', () => {
    const dist = countLevels([{ level: 'trace' }, { level: 'critical' }])
    expect(dist.TRACE).toBe(1)
    expect(dist.CRITICAL).toBe(1)
  })

  it('空级别/缺失级别的行不计入任何桶', () => {
    const dist = countLevels([{ level: '' }, { level: undefined }, {}])
    expect(Object.values(dist).every((n) => n === 0)).toBe(true)
  })
})
