import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import {
  ALERT_JUMP_TARGETS,
  buildAlertJumpTarget,
  evalScoreMaxFromAlert,
  parseEvalDeepLink,
  parseOrderStatusParam,
} from '../alertDeepLink'

// 告警深链守卫（T02620）：抽屉/雷达的跳转必须带上「本条告警」的查询参数，
// 且落地页要真的读取这些参数——写侧与读侧的参数名口径由本文件钉住。
const LAYOUT_SOURCE = readFileSync(resolve(__dirname, '../../components/layout/MainLayout.tsx'), 'utf-8')
const ORDERS_SOURCE = readFileSync(resolve(__dirname, '../../pages/Orders/Orders.tsx'), 'utf-8')
const EVALS_SOURCE = readFileSync(resolve(__dirname, '../../pages/Evaluations/index.tsx'), 'utf-8')

describe('buildAlertJumpTarget：写侧（抽屉/雷达跳转）', () => {
  it('失败订单：带 status=failed 与 ref=<订单 id>', () => {
    expect(buildAlertJumpTarget('failed', { id: 'ORD-1', status: 'failed' }))
      .toBe('/orders?status=failed&ref=ORD-1')
  })

  it('待支付超时：状态兜底用 pending_pay（后端超时口径），不是 takeover_pending', () => {
    // 依据：stats_today._query_timeout_pending 的 WHERE 是 domain/order.PENDING_STATUSES
    // ＝ ('pending_pay',)。写成 takeover_pending 会让落地页筛出空列表，比不筛更糟。
    expect(buildAlertJumpTarget('timeout', { id: 'ORD-2', status: 'pending_pay' }))
      .toBe('/orders?status=pending_pay&ref=ORD-2')
    expect(buildAlertJumpTarget('timeout', { id: 'ORD-2' })).toBe('/orders?status=pending_pay&ref=ORD-2')
  })

  it('条目自带合法 status 时以条目为准（告警口径变化时不写死）', () => {
    expect(buildAlertJumpTarget('failed', { id: 'X', status: 'cancelled' }))
      .toBe('/orders?status=cancelled&ref=X')
  })

  it('脏 id / 脏 status 一律降级：宁可少带参数，也不拼出坏链接', () => {
    expect(buildAlertJumpTarget('failed', { id: '"><script>' })).toBe('/orders?status=failed')
    expect(buildAlertJumpTarget('failed', { id: 'ok1', status: 'not_a_status' }))
      .toBe('/orders?status=failed&ref=ok1')
    expect(buildAlertJumpTarget('failed', undefined)).toBe('/orders?status=failed')
  })

  it('低分评估：带 item_id 定位，并把 0-1 归一分换算成评估分口径的 score_max', () => {
    expect(buildAlertJumpTarget('low_eval', { item_id: 'ITEM-9', score_value: 0.42 }))
      .toBe('/evaluations?item_id=ITEM-9&score_max=42')
  })

  it('低分评估缺 item_id / score_value 时逐层降级，最终回到裸页面（与改动前等价）', () => {
    expect(buildAlertJumpTarget('low_eval', { item_id: 'ITEM-9' })).toBe('/evaluations?item_id=ITEM-9')
    expect(buildAlertJumpTarget('low_eval', { score_value: 0.1 })).toBe('/evaluations?score_max=10')
    expect(buildAlertJumpTarget('low_eval', {})).toBe(ALERT_JUMP_TARGETS.low_eval)
    expect(buildAlertJumpTarget('low_eval')).toBe('/evaluations')
  })

  it('基础路径未漂移：/orders 与 /evaluations 仍是唯一落地页', () => {
    expect(ALERT_JUMP_TARGETS.failed).toBe('/orders')
    expect(ALERT_JUMP_TARGETS.timeout).toBe('/orders')
    expect(ALERT_JUMP_TARGETS.low_eval).toBe('/evaluations')
  })
})

describe('evalScoreMaxFromAlert：换算与边界', () => {
  it('四舍五入到整数百分比', () => {
    expect(evalScoreMaxFromAlert(0.5)).toBe('50')
    expect(evalScoreMaxFromAlert(0.333)).toBe('33')
  })

  it('非法值一律返回空串（表示不带该参数）', () => {
    expect(evalScoreMaxFromAlert(null)).toBe('')
    expect(evalScoreMaxFromAlert(undefined)).toBe('')
    expect(evalScoreMaxFromAlert(Number.NaN)).toBe('')
    expect(evalScoreMaxFromAlert(1.5)).toBe('')
    expect(evalScoreMaxFromAlert(-0.1)).toBe('')
  })
})

describe('parseOrderStatusParam：读侧白名单', () => {
  it('只接受与 OrderStatus 同源的字面值', () => {
    expect(parseOrderStatusParam('failed')).toBe('failed')
    expect(parseOrderStatusParam('pending_pay')).toBe('pending_pay')
    expect(parseOrderStatusParam('takeover_pending')).toBe('takeover_pending')
  })

  it('未知值/空值返回 undefined＝不筛选（脏链接静默降级）', () => {
    expect(parseOrderStatusParam('paid')).toBeUndefined()
    expect(parseOrderStatusParam('')).toBeUndefined()
    expect(parseOrderStatusParam(null)).toBeUndefined()
    expect(parseOrderStatusParam(undefined)).toBeUndefined()
  })
})

describe('parseEvalDeepLink：读侧参数校验', () => {
  const sp = (q: string) => new URLSearchParams(q)

  it('item_id 与 score_max 同时可用', () => {
    expect(parseEvalDeepLink(sp('item_id=ITEM-9&score_max=42'))).toEqual({ itemId: 'ITEM-9', scoreMax: 42 })
  })

  it('越界或非数字的 score_max 被丢弃（与后端 Query(ge=0, le=100) 同域）', () => {
    expect(parseEvalDeepLink(sp('score_max=101'))).toEqual({})
    expect(parseEvalDeepLink(sp('score_max=-1'))).toEqual({})
    expect(parseEvalDeepLink(sp('score_max=abc'))).toEqual({})
  })

  it('脏 item_id 被丢弃，不进入 LIKE 条件', () => {
    expect(parseEvalDeepLink(sp('item_id=%22%3E%3Cscript%3E'))).toEqual({})
  })

  it('无参数时返回空对象', () => {
    expect(parseEvalDeepLink(sp(''))).toEqual({})
  })
})

describe('写侧与读侧必须同口径（静态守卫）', () => {
  it('抽屉项改走 buildAlertJumpTarget，不再用裸路径常量', () => {
    expect(LAYOUT_SOURCE).toContain('buildAlertJumpTarget(kind, item)')
    expect(LAYOUT_SOURCE).not.toContain('openSheetWithNotification(ALERT_JUMP_TARGETS[kind])')
    // 三个面板都把条目本身传进 alertItem，否则条目级参数无从取得
    for (const kind of ['failed', 'timeout', 'low_eval']) {
      expect(LAYOUT_SOURCE).toContain(`alertItem('${kind}', `)
    }
  })

  it('抢单记录页真的读 ?status=（否则链接被静默忽略）', () => {
    expect(ORDERS_SOURCE).toContain("parseOrderStatusParam(searchParams.get('status'))")
    expect(ORDERS_SOURCE).toContain('useState<string | undefined>(urlStatus)')
  })

  it('评估明细页真的读 ?item_id / ?score_max，并给出可清除的定位提示', () => {
    expect(EVALS_SOURCE).toContain('parseEvalDeepLink(searchParams)')
    expect(EVALS_SOURCE).toContain('filters.setItemId(deepLink.itemId)')
    expect(EVALS_SOURCE).toContain('filters.setScoreRange([0, deepLink.scoreMax])')
    expect(EVALS_SOURCE).toContain('clearDeepLink')
    // 套用/清除都必须走「渲染追平后再 reload」这条通道，否则 load() 拿到旧筛选快照
    expect(EVALS_SOURCE).toContain('setReloadToken((t) => t + 1)')
  })

  it('告警条目字段口径用后端列名（score_value/item_id），不再自造 score', () => {
    const TYPES_SOURCE = readFileSync(resolve(__dirname, '../../api/types.ts'), 'utf-8')
    expect(TYPES_SOURCE).toContain('score_value?: number | null')
    expect(TYPES_SOURCE).not.toContain('created_at: string; score: number }>')
  })
})
