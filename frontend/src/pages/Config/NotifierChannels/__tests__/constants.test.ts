import { describe, it, expect } from 'vitest'
import { eventTypes } from '../constants'
import { ENUM_TO_DOT } from '../../../../constants/eventTypes'

describe('NotifierChannels eventTypes ↔ ENUM_TO_DOT 对齐', () => {
  it('eventTypes 数量为 22，与设计文档和 ENUM_TO_DOT 对齐', () => {
    expect(eventTypes).toHaveLength(22)
    expect(Object.keys(ENUM_TO_DOT)).toHaveLength(22)
  })

  it('eventTypes key 集合 = ENUM_TO_DOT key 集合（双向覆盖）', () => {
    const notifierKeys = new Set(eventTypes.map(e => e.key))
    const dotKeys = new Set(Object.keys(ENUM_TO_DOT))
    for (const k of dotKeys) expect(notifierKeys.has(k), `eventTypes 缺少 ${k}`).toBe(true)
    for (const k of notifierKeys) expect(dotKeys.has(k), `ENUM_TO_DOT 缺少 ${k}`).toBe(true)
  })

  it('severity 取值合法（info / important / critical）', () => {
    const valid = new Set(['info', 'important', 'critical'])
    for (const e of eventTypes) {
      expect(valid.has(e.severity), `${e.key} 的 severity ${e.severity} 非法`).toBe(true)
    }
  })

  it('eventTypes key 唯一', () => {
    const seen = new Set<string>()
    for (const e of eventTypes) {
      expect(seen.has(e.key), `eventTypes 重复 key: ${e.key}`).toBe(false)
      seen.add(e.key)
    }
  })

  it('默认订阅项 EVAL_PASSED 与 BUY_SUCCEEDED 存在', () => {
    const defaults = eventTypes.filter(e => e.defaultNotify).map(e => e.key)
    expect(defaults).toContain('EVAL_PASSED')
    expect(defaults).toContain('BUY_SUCCEEDED')
  })
})
