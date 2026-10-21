import { describe, it, expect } from 'vitest'
import { readFileSync, readdirSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { EVENT_TYPE_LABELS, EVENT_TYPE_OPTIONS } from '../eventTypes'

// T02693：时间线事件类型表注册过 order.created / order.paid / order.failed 三个键，
// 但后端 domain/events.py 从未定义过 order.* 事件，两张库（18363 + 232 行事件）里也是
// 0 行；而真正落库的 buy.requested / buy.succeeded / buy.failed（notifier hub 写
// event.type.value）反而没注册，抢单事件在时间线上退化成灰色英文标签。
// 幽灵注册不报错，只是永远匹配不到——和裸状态字面串是同一个失效形状，所以一起钉。

const SRC_ROOT = resolve(__dirname, '../..')
const BACKEND_ROOT = resolve(__dirname, '../../../../backend/xianyu_hunter')

function walk(dir: string, suffixes: string[]): string[] {
  const out: string[] = []
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, entry.name)
    if (entry.isDirectory()) out.push(...walk(p, suffixes))
    else if (suffixes.some((s) => entry.name.endsWith(s))) out.push(p)
  }
  return out
}

/** 后端全部 .py 源码拼成一坨：事件类型字面值必须在这里出现过 */
function backendSource(): string {
  return walk(BACKEND_ROOT, ['.py']).map((p) => readFileSync(p, 'utf-8')).join('\n')
}

describe('事件类型注册表不含幽灵键（T02693）', () => {
  it('前端任何地方都不再出现 order.* 事件类型', () => {
    const offenders: string[] = []
    for (const p of walk(SRC_ROOT, ['.ts', '.tsx'])) {
      const src = readFileSync(p, 'utf-8')
      for (const m of src.matchAll(/['"`](order\.[a-z_]+)['"`]/g)) {
        offenders.push(`${p.replace(SRC_ROOT, '')}: ${m[1]}`)
      }
    }
    expect(offenders, `后端从未发出过 order.* 事件：\n${offenders.join('\n')}`).toEqual([])
  })

  it('购买链路三个类型已注册，标签与订阅过滤项逐字一致', () => {
    const optionLabel = new Map(EVENT_TYPE_OPTIONS.map((o) => [o.value, o.label]))
    for (const [key, expected] of [
      ['buy.requested', '请求购买'],
      ['buy.succeeded', '购买成功'],
      ['buy.failed', '购买失败'],
    ] as const) {
      expect(EVENT_TYPE_LABELS[key], `${key} 未注册，时间线上会退化成灰色英文标签`).toBeTruthy()
      expect(EVENT_TYPE_LABELS[key].label).toBe(expected)
      // 两处文案不一致时，用户在过滤下拉与时间线上看到的是两个名字
      expect(optionLabel.get(key), `${key} 的过滤项文案与标签表漂移`).toBe(expected)
    }
  })

  it('cleanup.database 幽灵键已摘除', () => {
    expect(EVENT_TYPE_LABELS['cleanup.database']).toBeUndefined()
  })

  it('标签表每个键都能在后端源码里找到（新增幽灵键会被拒）', () => {
    const backend = backendSource()
    const dead = Object.keys(EVENT_TYPE_LABELS).filter((k) => !backend.includes(k))
    expect(dead, `以下事件类型后端源码里根本没有，属幽灵注册：${dead.join(', ')}`).toEqual([])
  })
})
