import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// T02564 现场取证后固化下来的三条契约，防止回归：
// 1) 异常雷达跳转走 sheet 通道（裸 <a href> 在 basename=/xianyu 下会 404 并整页刷新）
// 2) 抢单记录页必须真的读 ?ref=，且 id 门槛放行字符串主键
// 3) 统计卡的 sparkline 各自取对应指标的序列，不能四张卡共用 events

// 注释里保留了「原为裸 <a href>」这类历史说明，断言前先剥掉注释
const stripComments = (s: string) =>
  s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')

const radar = stripComments(readFileSync(resolve(__dirname, '../components/AlertRadar.tsx'), 'utf-8'))
const orders = stripComments(readFileSync(resolve(__dirname, '../../Orders/Orders.tsx'), 'utf-8'))
const statCards = stripComments(readFileSync(resolve(__dirname, '../components/StatCardsSection.tsx'), 'utf-8'))

describe('异常雷达 → 抢单记录定位链接', () => {
  it('雷达用 openSheetWithNotification 跳转并带 ref，不留裸 a 标签', () => {
    expect(radar).toContain('openSheetWithNotification')
    expect(radar).not.toMatch(/<a\s+href=["'`]\/orders/)
  })

  // T02828：抽屉的参数口径（utils/alertDeepLink.ts）是唯一来源，雷达不能自己拼链接。
  // 原先雷达写死 `/orders?ref=${o.id}`，落地是全量列表，用户还得自己找那一条。
  it('雷达三类条目都走 buildAlertJumpTarget，不再手拼查询串', () => {
    expect(radar).toContain("import { buildAlertJumpTarget }")
    for (const kind of ['failed', 'timeout', 'low_eval']) {
      expect(radar, `雷达的 ${kind} 栏没有接入统一深链口径`).toContain(`jump('${kind}'`)
    }
    expect(radar).not.toContain('`/orders?ref=')
    expect(radar).not.toContain('`/evaluations?')
  })

  it('订单页消费 ?ref=，门槛放行字符串 id（订单主键是 string，不是纯数字）', () => {
    expect(orders).toContain("searchParams.get('ref')")
    expect(orders).toMatch(/refId\s*=\s*\/\^\[A-Za-z0-9/)
    expect(orders).not.toMatch(/refId\s*=\s*\/\^\\d\+\$/)
    expect(orders).toContain('xh-row-highlight')
  })
})

describe('统计卡 sparkline 口径', () => {
  it('四张卡分别取自己的趋势指标，而不是共用 events', () => {
    for (const metric of ['orders_pending', 'orders_succeeded', 'orders_failed']) {
      expect(statCards).toContain(metric)
    }
    expect(statCards).toMatch(/series:\s*sparklines\.events/)
  })
})
