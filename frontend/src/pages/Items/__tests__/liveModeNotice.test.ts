// frontend/src/pages/Items/__tests__/liveModeNotice.test.ts
// T02659（评审 2.3-6）：进实时模式后分页器消失、删除置灰，页面上没有任何说明，
// 用户第一反应是「功能坏了」；地区/品牌候选的口径也随之变化（本次结果提取 vs DB 全量 DISTINCT）同样无文案。
// 本单的原则是「只补说明，不静默改行为」，所以除了文案本身，
// 还要钉住两件事：既有行为（`!liveMode` 的两处门）一字未动，以及文案不许说谎。
//
// 文案为什么单独成模块并能被测：建议稿原文写的是「需持久化请改用刷新写库」，
// 而 `handleRefresh` 在实时模式下是 `if (liveMode) { loadLive(); return }`——
// 「刷新」在实时模式里只做又一次实时搜索，根本不写库。照抄建议就会给用户一条做不到的指令。
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  EXIT_LIVE_MODE_LABEL,
  EXIT_LIVE_MODE_TIP,
  LIVE_MODE_NOTICE,
  deleteTip,
  facetTip,
} from '../liveModeCopy'

const stripComments = (s: string) =>
  s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')

const page = stripComments(readFileSync(resolve(__dirname, '../ItemList.tsx'), 'utf-8'))

describe('实时模式说明条的文案口径', () => {
  it('讲清三件反常：不分页、不能删、结果未入库', () => {
    expect(LIVE_MODE_NOTICE).toContain('未入库')
    expect(LIVE_MODE_NOTICE).toContain('不分页')
    expect(LIVE_MODE_NOTICE).toContain('单条删除不可用')
  })

  it('顺带说明候选口径也变了（与 facetTip 同源，不留第二套说法）', () => {
    expect(LIVE_MODE_NOTICE).toContain('地区/品牌候选也取自本次搜索结果')
  })

  it('不承诺实时模式做不到的事：实时模式下的「刷新」并不写库', () => {
    expect(LIVE_MODE_NOTICE).not.toMatch(/刷新[^。]*写库/)
    expect(LIVE_MODE_NOTICE).not.toContain('持久化请改用刷新')
    // 事实核对：源码里实时模式的刷新分支确实只是再搜一次
    expect(page).toMatch(/if \(liveMode\) \{\s*\n\s*loadLive\(\)\s*\n\s*return\s*\n\s*\}/)
  })

  it('出口按钮说的是「退回数据库模式」，不是又一次搜索', () => {
    expect(EXIT_LIVE_MODE_LABEL).toBe('退出实时模式')
    expect(EXIT_LIVE_MODE_TIP).toContain('恢复分页与删除')
    expect(EXIT_LIVE_MODE_TIP).toContain('已入库')
  })
})

describe('地区/品牌候选的 tooltip 与实际取数一致', () => {
  it('实时模式：候选来自本次搜索结果，明说没入库的那批不在其中', () => {
    expect(facetTip(true, 'region')).toContain('本次搜索结果的地区')
    expect(facetTip(true, 'brand')).toContain('本次搜索结果的品牌')
    expect(facetTip(true, 'region')).not.toContain('全量')
  })

  it('数据库模式：候选来自 facets 全量去重，不只当前页', () => {
    expect(facetTip(false, 'region')).toContain('后端 facets 的全量去重')
    expect(facetTip(false, 'brand')).toContain('不只当前页')
  })
})

describe('删除按钮的禁用原因分档（两种禁用各有各的说法）', () => {
  it('实时模式优先：结果是未入库的搜索结果，没有可删的关联行', () => {
    expect(deleteTip({ liveMode: true, hasLinkId: true })).toContain('未入库')
    expect(deleteTip({ liveMode: true, hasLinkId: true })).toContain('退出实时模式后才能删')
  })

  it('非实时但缺 link_id：还没有关联记录，而不是「不可恢复」', () => {
    expect(deleteTip({ liveMode: false, hasLinkId: false })).toContain('还没有关联记录')
  })

  it('可删时才说「不可恢复」', () => {
    expect(deleteTip({ liveMode: false, hasLinkId: true })).toBe('删除此商品关联（不可恢复）')
  })
})

describe('说明条的接线（源码口径，防只改文案不落地）', () => {
  it('只在实时模式且本次未关闭时出现', () => {
    expect(page).toMatch(/\{liveMode && !liveNoticeDismissed && \(/)
    expect(page).toMatch(/onClose=\{\(\) => setLiveNoticeDismissed\(true\)\}/)
  })

  it('退出实时模式后复位关闭标记：下一次进入还会解释一次，不是永久静音', () => {
    expect(page).toMatch(/if \(!liveMode\) setLiveNoticeDismissed\(false\)/)
  })

  it('出口动作是真的退出实时模式，不掺别的副作用', () => {
    expect(page).toMatch(/onClick=\{\(\) => setLiveMode\(false\)\}/)
  })

  it('既有行为一字未动：两处分页仍由 !liveMode 挡着，删除仍按原条件禁用', () => {
    // 表格视图 + 卡片视图各一处；本单只加说明，不碰这两处的门
    expect(page.match(/\{!liveMode && \(/g)).toHaveLength(2)
    expect(page.match(/marginTop: 16, textAlign: 'right'/g)).toHaveLength(2)
    expect(page).toMatch(/disabled=\{!record\.link_id \|\| liveMode\}/)
  })

  it('两个下拉各自挂上口径 tooltip，且把 liveMode 传了进去', () => {
    expect(page).toMatch(/<Tooltip title=\{facetTip\(liveMode, 'region'\)\}>/)
    expect(page).toMatch(/<Tooltip title=\{facetTip\(liveMode, 'brand'\)\}>/)
  })
})
