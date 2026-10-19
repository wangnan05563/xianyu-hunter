/**
 * 日志级别归一化单测（T02569 / REQ-037 / 评审 2.7-1、2.7-2）
 *
 * 回归点：后端 events.level 存小写缩写（实测库内 info / err / warning 并存，另有代码路径写 error），
 * 前端原先直接 `level.toUpperCase()` 后查大写键表 —— `err` 变成 `ERR`，既不在颜色表键内
 * （级别 Tag 恒灰），也不在分布桶内（有错误日志时 ERROR 恒显示 0）。
 * 按要求必须同时覆盖 err 与 error 两种写法。
 */
import { describe, it, expect } from 'vitest'
import { countLevels, levelColor, normalizeLevel } from '../logLevels'

describe('normalizeLevel', () => {
  it('缩写与全称两种写法归一到同一规范键', () => {
    expect(normalizeLevel('err')).toBe('ERROR')
    expect(normalizeLevel('error')).toBe('ERROR')
    expect(normalizeLevel('ERROR')).toBe('ERROR')
    expect(normalizeLevel('warn')).toBe('WARNING')
    expect(normalizeLevel('warning')).toBe('WARNING')
    expect(normalizeLevel('info')).toBe('INFO')
    expect(normalizeLevel('debug')).toBe('DEBUG')
    expect(normalizeLevel('trace')).toBe('TRACE')
  })

  it('大小写与首尾空格不影响结果，空值返回空串', () => {
    expect(normalizeLevel('  Err ')).toBe('ERROR')
    expect(normalizeLevel('InFo')).toBe('INFO')
    expect(normalizeLevel(undefined)).toBe('')
    expect(normalizeLevel(null)).toBe('')
    expect(normalizeLevel('')).toBe('')
  })

  it('未知字面值原样大写返回，不吞掉也不误并', () => {
    expect(normalizeLevel('critical')).toBe('CRITICAL')
  })
})

describe('levelColor', () => {
  it('小写缩写取到与全称相同的颜色', () => {
    expect(levelColor('err')).toBe('red')
    expect(levelColor('error')).toBe('red')
    expect(levelColor('warn')).toBe('orange')
    expect(levelColor('warning')).toBe('orange')
    expect(levelColor('info')).toBe('blue')
  })

  it('未知级别与空值回退 default（灰色），不再依赖调用方兜底', () => {
    expect(levelColor('critical')).toBe('default')
    expect(levelColor(undefined)).toBe('default')
  })
})

describe('countLevels', () => {
  it('err 与 error 合并计入 ERROR，warn 与 warning 合并计入 WARNING', () => {
    const dist = countLevels([
      { level: 'err' },
      { level: 'error' },
      { level: 'warning' },
      { level: 'warn' },
      { level: 'info' },
    ])
    expect(dist.ERROR).toBe(2)
    expect(dist.WARNING).toBe(2)
    expect(dist.INFO).toBe(1)
  })

  it('四个主级别即使没有数据也保持 0 占位，口径与旧版一致', () => {
    const dist = countLevels([{ level: 'err' }])
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
