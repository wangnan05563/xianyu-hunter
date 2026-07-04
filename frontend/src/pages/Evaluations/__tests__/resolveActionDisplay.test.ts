import { describe, it, expect } from 'vitest'
import { resolveActionDisplay } from '../utils'
import type { EvalItem } from '../../../api'

// 构造最小可用的 EvalItem 测试数据
function makeItem(overrides: Partial<EvalItem['payload']> = {}): EvalItem {
  return {
    item_id: 'i1',
    task_id: 't1',
    created_at: '2026-07-01T00:00:00Z',
    payload: {
      score: 85,
      risk_level: 'low',
      ...overrides,
    },
  }
}

const AUTO_BUY_SCORE = 80

describe('resolveActionDisplay', () => {
  describe('占位类型判定', () => {
    it('无订单且评分达标时返回 null（渲染抢单按钮）', () => {
      const r = makeItem({ score: 85 })
      expect(resolveActionDisplay(r, AUTO_BUY_SCORE)).toBeNull()
    })

    it('评分等于阈值时返回 null（边界 inclusive）', () => {
      const r = makeItem({ score: 80 })
      expect(resolveActionDisplay(r, AUTO_BUY_SCORE)).toBeNull()
    })

    it('评分低于阈值时返回 below_threshold', () => {
      const r = makeItem({ score: 79 })
      expect(resolveActionDisplay(r, AUTO_BUY_SCORE)).toBe('below_threshold')
    })

    it('score 缺失时按 0 处理，返回 below_threshold', () => {
      // 防御 score=null 场景：后端可能返回 null（数据不足）
      const r = makeItem({ score: null as unknown as number })
      expect(resolveActionDisplay(r, AUTO_BUY_SCORE)).toBe('below_threshold')
    })

    it('is_sold=true 且评分达标时返回 sold', () => {
      const r = makeItem({ score: 95, is_sold: true })
      expect(resolveActionDisplay(r, AUTO_BUY_SCORE)).toBe('sold')
    })

    it('is_sold=false 时不影响判定，返回 null', () => {
      const r = makeItem({ score: 85, is_sold: false })
      expect(resolveActionDisplay(r, AUTO_BUY_SCORE)).toBeNull()
    })
  })

  describe('订单状态判定', () => {
    it('order_status=pending_pay 返回 ordered', () => {
      const r = makeItem({ score: 85, order_status: 'pending_pay' })
      expect(resolveActionDisplay(r, AUTO_BUY_SCORE)).toBe('ordered')
    })

    it('order_status=succeeded 返回 ordered', () => {
      const r = makeItem({ score: 85, order_status: 'succeeded' })
      expect(resolveActionDisplay(r, AUTO_BUY_SCORE)).toBe('ordered')
    })

    it('order_status=paid 返回 ordered', () => {
      const r = makeItem({ score: 85, order_status: 'paid' })
      expect(resolveActionDisplay(r, AUTO_BUY_SCORE)).toBe('ordered')
    })

    it('order_status=takeover_pending 返回 ordered', () => {
      const r = makeItem({ score: 85, order_status: 'takeover_pending' })
      expect(resolveActionDisplay(r, AUTO_BUY_SCORE)).toBe('ordered')
    })

    it('order_status=failed 不视为已下单（允许重试）', () => {
      const r = makeItem({ score: 85, order_status: 'failed' })
      expect(resolveActionDisplay(r, AUTO_BUY_SCORE)).toBeNull()
    })

    it('order_status=cancelled 不视为已下单（允许重试）', () => {
      const r = makeItem({ score: 85, order_status: 'cancelled' })
      expect(resolveActionDisplay(r, AUTO_BUY_SCORE)).toBeNull()
    })
  })

  describe('优先级顺序：ordered > sold > below_threshold', () => {
    it('已下单 + 已售：ordered 优先', () => {
      // 场景：抢单成功后商品被标记为已售，应显示"已下单"而非"已售"
      const r = makeItem({
        score: 95,
        order_status: 'succeeded',
        is_sold: true,
      })
      expect(resolveActionDisplay(r, AUTO_BUY_SCORE)).toBe('ordered')
    })

    it('订单失败 + 已售：sold 优先于按钮', () => {
      // 场景：下单失败后商品被他人购得，无法再抢，应显示"已售"
      const r = makeItem({
        score: 95,
        order_status: 'failed',
        is_sold: true,
      })
      expect(resolveActionDisplay(r, AUTO_BUY_SCORE)).toBe('sold')
    })

    it('订单取消 + 已售：sold 优先于按钮', () => {
      const r = makeItem({
        score: 95,
        order_status: 'cancelled',
        is_sold: true,
      })
      expect(resolveActionDisplay(r, AUTO_BUY_SCORE)).toBe('sold')
    })

    it('订单失败 + 已售 + 低分：sold 优先于 below_threshold', () => {
      // 场景：商品已售且评分低，应显示"已售"而非"未达阈值"
      // 原因：用户更需要知道商品已售（不可抢），而非评分信息
      const r = makeItem({
        score: 50,
        order_status: 'failed',
        is_sold: true,
      })
      expect(resolveActionDisplay(r, AUTO_BUY_SCORE)).toBe('sold')
    })

    it('已下单 + 低分：ordered 优先于 below_threshold', () => {
      const r = makeItem({
        score: 50,
        order_status: 'succeeded',
      })
      expect(resolveActionDisplay(r, AUTO_BUY_SCORE)).toBe('ordered')
    })
  })

  describe('边界场景', () => {
    it('is_sold 缺失（undefined）时按未售处理', () => {
      // 后端 _enrich_eval_with_item 可能未注入 is_sold（旧评估数据）
      const r = makeItem({ score: 85 })
      expect(resolveActionDisplay(r, AUTO_BUY_SCORE)).toBeNull()
    })

    it('order_status 为空字符串时按无订单处理', () => {
      // 防御后端返回空字符串而非 undefined
      const r = makeItem({ score: 85, order_status: '' })
      expect(resolveActionDisplay(r, AUTO_BUY_SCORE)).toBeNull()
    })

    it('autoBuyScore=0 时 score=0 也可抢', () => {
      // 极端配置：用户关闭评分门槛
      const r = makeItem({ score: 0 })
      expect(resolveActionDisplay(r, 0)).toBeNull()
    })
  })
})
