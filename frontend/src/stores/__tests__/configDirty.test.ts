import { describe, expect, it } from 'vitest'
import type { AppConfig } from '../../api'
import {
  SCOPE_EVAL,
  SCOPE_PRICE,
  SCOPE_SEARCH,
  applyDrafts,
  collectChangedPaths,
  filterChangedPaths,
  pathInScope,
  scopeForPath,
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
})
