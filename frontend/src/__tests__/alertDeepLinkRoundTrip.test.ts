// frontend/src/__tests__/alertDeepLinkRoundTrip.test.ts
// T02831：告警深链的「URL → 筛选」读端已经由 T02620 落地，本文件守的是反方向——
// 手动改筛选必须回写 URL，且回写不得把同一条链接里的其它参数擦掉。
// 只做渲染级用例的话，「回写时顺手 new 一个空的 URLSearchParams」这种丢参数的写法
// 照样能绿（当前可见筛选态与链接不一致，只有刷新才暴露），所以这里按写法逐个钉。
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'

const SRC_ROOT = resolve(__dirname, '..')

function read(rel: string): string {
  return readFileSync(join(SRC_ROOT, rel), 'utf-8')
}

function codeOf(src: string): string {
  return src
    .split(/\r?\n/)
    .filter((l) => !/^\s*(\/\/|\*|\/\*)/.test(l))
    .join('\n')
}

// 读端与写端成对：页面里用 parse*Param(searchParams.get(KEY)) 读过的键，
// 必须同时存在 set(KEY…) 与 delete(KEY…) —— 只 set 不 delete 的话，
// 「清空筛选」这个动作永远写不回 URL，刷新还是被筛回来。
const ROUND_TRIP: { rel: string; key: string; reader: string }[] = [
  { rel: 'pages/Orders/Orders.tsx', key: 'status', reader: "searchParams.get('status')" },
]

describe('深链筛选参数读写成对（T02831）', () => {
  ROUND_TRIP.forEach(({ rel, key, reader }) => {
    it(`${rel} 的 ${key} 既读也写`, () => {
      const src = read(rel)
      expect(src, `${rel} 不再读 ?${key}=，读端一丢本页就不再是告警落地页`).toContain(reader)
      expect(src, `${rel} 的 ${key} 没有回写入口（手动筛选与链接会各说各话）`)
        .toContain(`setSearchParams`)
      expect(src, `${rel} 选中值时没写 ${key}`).toContain(`set('${key}'`)
      expect(src, `${rel} 清空筛选时没删 ${key} 键，清空后刷新仍被筛回来`)
        .toContain(`delete('${key}')`)
    })
  })

  it('Orders 的每次 URL 改写都基于当前参数快照，不整串替换', () => {
    const code = codeOf(read('pages/Orders/Orders.tsx'))
    const writes = (code.match(/setSearchParams\(/g) ?? []).length
    const clones = (code.match(/new URLSearchParams\(searchParams\)/g) ?? []).length
    expect(writes, 'setSearchParams 调用点数量变了，核对后更新本条').toBe(2)
    expect(clones, '有一处 URL 改写没从当前 searchParams 克隆，会把 ref/status 擦了').toBe(writes)
  })

  it('Orders 状态筛选只有一个写入口，绕开它的写法即漏写', () => {
    const code = codeOf(read('pages/Orders/Orders.tsx'))
    const setters = (code.match(/setStatusFilter\(/g) ?? []).length
    // 挂载后只有两处：URL 效果里以链接为准 + onStatusChange 里跟随用户动作
    expect(setters, '状态筛选的写入口多了：新增那处必须同样回写 URL').toBe(2)
    // 两处里只有 onStatusChange 负责用户动作，另一处以链接为准
    expect(code).toContain('const onStatusChange')
  })

  it('评估页的定位提示按「参数是否仍等于当前筛选」分文案', () => {
    const src = read('pages/Evaluations/index.tsx')
    expect(src, '提示条又变回无条件宣称「已按告警定位」').toContain('deepLinkMatchesFilters')
    // 判定本身在 utils/alertDeepLink 里（那边每个分支都能单元测试），
    // 本文件只钉「页面真的把两个筛选值都喂进去了」这条接线
    const wire = src.slice(
      src.indexOf('const deepLinkMatchesFilters'),
      src.indexOf('const columns = useEvalColumns'),
    )
    expect(wire.length, 'deepLinkMatchesFilters 接线解析为空').toBeGreaterThan(0)
    expect(wire).toContain('evalDeepLinkMatchesFilters(deepLink, {')
    expect(wire).toContain('itemId: filters.itemId')
    expect(wire).toContain('scoreRange: filters.scoreRange')
    expect(src, '不一致时没有降级文案').toContain('已被手动筛选覆盖')
    // 首帧筛选还没套用就出提示条会把「马上要套用」闪成「已被覆盖」
    expect(src).toContain('deepLinkApplied.current')
  })
})
