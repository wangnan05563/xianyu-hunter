// T02732：单日抢单上限的口径必须写清「所有账号合计」。
// 护栏本身是全局的：buyer.py 调 count_real_orders_since(today_start) 时不传 user_id，
// orders 里所有账号的真实落单都吃同一份额度。但前端只写「按 UTC 自然日计数」，
// 多账号用户会以为每个账号各有 N 次。文案会随代码漂移，所以用后端源码做事实源。
import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join, resolve } from 'node:path'

const REPO_ROOT = resolve(__dirname, '../../../../../')

function read(rel: string): string {
  const p = join(REPO_ROOT, rel)
  expect(existsSync(p), `事实源缺失：${rel}`).toBe(true)
  return readFileSync(p, 'utf-8')
}

const page = () => read('frontend/src/pages/Config/BuyerStrategy.tsx')
const buyer = () => read('backend/xianyu_hunter/modules/buyer.py')
const yamlConfig = () => read('backend/xianyu_hunter/infra/yaml_config.py')

describe('单日上限文案与后端全局口径对齐（T02732）', () => {
  it('护栏计数不按账号过滤：count_real_orders_since 只传日期', () => {
    const src = buyer()
    const calls = src.match(/count_real_orders_since\([^)]*\)/g) ?? []
    expect(calls).toHaveLength(1)
    expect(calls[0]).toBe('count_real_orders_since(today_start)')
    expect(calls[0]).not.toContain('user_id')
  })

  it('计数只算真实落单，演练不占额度', () => {
    expect(buyer()).toContain('if not dry_run:')
    const repo = read('backend/xianyu_hunter/infra/repo_orders.py')
    expect(repo).toMatch(/type\s*==\s*["']real["']/)
  })

  it('页面两处文案都点明「所有账号合计」', () => {
    const src = page()
    const hits = src.match(/所有账号合计/g) ?? []
    expect(hits.length, '输入说明与状态卡各需要一处').toBe(2)
    expect(src).toContain('按 UTC 自然日计数、所有账号合计，与仪表盘「今日订单」同一口径')
    expect(src).toContain('（UTC 自然日，所有账号合计，仅计真实落单）')
  })

  it('配置字段描述与页面口径一致', () => {
    expect(yamlConfig()).toContain('UTC 自然日内所有账号合计的最多真实落单次数')
    expect(read('backend/xianyu_hunter/modules/buyer_config.py')).toContain(
      'max_orders_per_day: UTC 自然日内所有账号合计的最多真实落单次数',
    )
  })

  it('不得残留「每账号额度」的相反说法', () => {
    const src = page()
    expect(src).not.toContain('每个账号')
    expect(src).not.toContain('单账号')
  })
})
