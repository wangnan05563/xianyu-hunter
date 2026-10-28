import { describe, expect, it } from 'vitest'
import type { AppConfig } from '../../api'
import {
  SCOPE_BUYER,
  SCOPE_EVAL,
  SCOPE_NOTIFIER,
  SCOPE_PRICE,
  SCOPE_SEARCH,
  applyDrafts,
  collectChangedPaths,
  filterChangedPaths,
  markScopeSaved,
  pathInScope,
  revertScope,
  scopeForPath,
  scopedSubmitPayload,
} from '../configDirty'

const base = () =>
  ({
    eval: { pass_score: 60, thresholds: { on_sale_count: 3 } },
    search: { page_size: 20, regions: ['a'] },
    antidetect: { qps: 3 },
    price_strategy: { max_price: 100 },
    bargain_price: { percentile: 0.1 },
  }) as unknown as AppConfig

describe('configDirty（T02572 脏归属）', () => {
  it('叶子改动精确到字段', () => {
    const a = base()
    const b = structuredClone(a)
    b.eval.pass_score = 70
    expect(collectChangedPaths(a, b)).toEqual(['eval.pass_score'])
  })

  it('新增键与删除键都被记下', () => {
    const a = base()
    const b = structuredClone(a) as unknown as Record<string, unknown>
    ;(b as { eval: Record<string, unknown> }).eval.new_flag = true
    delete (b.bargain_price as unknown)
    expect(collectChangedPaths(a, b).sort()).toEqual(['bargain_price', 'eval.new_flag'])
  })

  it('数组整体记一条，不拆下标', () => {
    const a = base()
    const b = structuredClone(a)
    b.search.regions = ['a', 'b']
    expect(collectChangedPaths(a, b)).toEqual(['search.regions'])
  })

  it('无改动返回空', () => {
    const a = base()
    expect(collectChangedPaths(a, structuredClone(a))).toEqual([])
  })

  it('点号边界：search_extra 不算 search 的改动', () => {
    expect(pathInScope('search_extra.x', SCOPE_SEARCH)).toBe(false)
    expect(pathInScope('search.page_size', SCOPE_SEARCH)).toBe(true)
  })

  it('scope 过滤只留本页段', () => {
    const a = base()
    const b = structuredClone(a)
    b.eval.pass_score = 70
    b.price_strategy.max_price = 200
    expect(filterChangedPaths(collectChangedPaths(a, b), SCOPE_PRICE)).toEqual([
      'price_strategy.max_price',
    ])
    expect(filterChangedPaths(collectChangedPaths(a, b), SCOPE_EVAL)).toEqual(['eval.pass_score'])
  })

  it('载入保留所有未保存草稿（本页与别页一视同仁）', () => {
    const original = base()
    const draft = structuredClone(original)
    draft.eval.pass_score = 70
    draft.search.page_size = 50
    const fresh = structuredClone(original)
    fresh.search.page_size = 30 // 服务端在此期间被别处改了
    fresh.eval.pass_score = 65
    const next = applyDrafts(fresh, draft, original)
    expect(next.eval.pass_score).toBe(70)
    expect(next.search.page_size).toBe(50)
  })

  it('未改动的字段取服务端新值', () => {
    const original = base()
    const draft = structuredClone(original)
    draft.eval.pass_score = 70
    const fresh = structuredClone(original)
    fresh.eval.thresholds.on_sale_count = 5
    const next = applyDrafts(fresh, draft, original)
    expect(next.eval.pass_score).toBe(70)
    expect(next.eval.thresholds.on_sale_count).toBe(5)
  })

  it('保留草稿时被删掉的键真的删掉，而不是写成 undefined', () => {
    const original = base()
    const draft = structuredClone(original) as unknown as Record<string, unknown>
    delete draft.bargain_price
    const next = applyDrafts(
      structuredClone(original),
      draft as unknown as AppConfig,
      original,
    )
    expect('bargain_price' in (next as unknown as Record<string, unknown>)).toBe(false)
  })

  it('5 个配置页都有归属，非配置路由与未迁移的 /config/ai 没有', () => {
    for (const p of [
      '/config/price',
      '/config/eval',
      '/config/notifier',
      '/config/search',
      '/config/buyer',
    ]) {
      expect(scopeForPath(p)).not.toBeNull()
    }
    expect(scopeForPath('/tasks')).toBeNull()
    expect(scopeForPath('/config/ai')).toBeNull()
  })

  it('通知页的凭据键都登记在 SCOPE_NOTIFIER 里（新增渠道漏登记会丢保存）', async () => {
    const { defaultChannels } = await import('../../pages/Config/NotifierChannels/constants')
    const fieldKeys = defaultChannels.flatMap((ch) => ch.fields.map((f) => f.key))
    expect(fieldKeys.length).toBeGreaterThan(0)
    const notifierScope: readonly string[] = SCOPE_NOTIFIER
    for (const key of fieldKeys) {
      expect(notifierScope, `notify 页会写顶层键 ${key}，但它不在 SCOPE_NOTIFIER`).toContain(key)
    }
  })

  it('抢单页写到的 eval / account_rotator 也在 SCOPE_BUYER 内', () => {
    // 分数阈值（eval.auto_buy_score / eval.pass_score）与轮转参数都在这页编辑
    const buyerScope: readonly string[] = SCOPE_BUYER
    for (const key of ['buyer', 'eval', 'account_rotator']) {
      expect(buyerScope).toContain(key)
    }
  })
})

describe('按页段提交（T02571）', () => {
  it('只把变化过的顶层段放进载荷', () => {
    const original = base()
    const draft = structuredClone(original)
    draft.price_strategy.max_price = 200
    expect(Object.keys(scopedSubmitPayload(draft, original, SCOPE_PRICE))).toEqual([
      'price_strategy',
    ])
    // 本段没变化 => 载荷为空，调用方据此跳过请求
    expect(scopedSubmitPayload(draft, original, SCOPE_EVAL)).toEqual({})
  })

  it('载荷取的是草稿值，且与 config 不共享引用', () => {
    const original = base()
    const draft = structuredClone(original)
    draft.search.page_size = 50
    const payload = scopedSubmitPayload(draft, original, SCOPE_SEARCH) as {
      search: { page_size: number }
    }
    expect(payload.search.page_size).toBe(50)
    payload.search.page_size = 999
    expect(draft.search.page_size).toBe(50)
  })

  it('保存后只认本页段，别页草稿继续算脏', () => {
    const original = base()
    const draft = structuredClone(original)
    draft.price_strategy.max_price = 200
    draft.eval.pass_score = 70
    const nextOriginal = markScopeSaved(original, draft, SCOPE_PRICE)
    expect(nextOriginal.price_strategy.max_price).toBe(200)
    expect(collectChangedPaths(draft, nextOriginal)).toEqual(['eval.pass_score'])
  })

  it('重置只回滚本页段，别页草稿不动', () => {
    const original = base()
    const draft = structuredClone(original)
    draft.price_strategy.max_price = 200
    draft.eval.pass_score = 70
    const next = revertScope(draft, original, SCOPE_PRICE)
    expect(next.price_strategy.max_price).toBe(100)
    expect(next.eval.pass_score).toBe(70)
  })
})
