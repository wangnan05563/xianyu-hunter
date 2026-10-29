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

/**
 * 找出 offset 所在的最近一层「组件内顶层声明」：缩进 ≤ 2 的 `const foo = …` / `function foo(…)`
 * / `useEffect(…)`。缩进 ≥ 4 的 `const next = …` 是函数体内局部变量，不能当边界
 * （否则 onStatusChange 会被从中间切断）。
 */
function enclosingFunctionLabel(code: string, offset: number): string | null {
  const lines = code.split('\n')
  const starts: { label: string; pos: number }[] = []
  let pos = 0
  for (const line of lines) {
    const named = line.match(/^ {0,2}(?:export\s+)?(?:const|function)\s+([A-Za-z0-9_]+)/)
    if (named) starts.push({ label: named[1], pos })
    else if (/^ {2}useEffect\(/.test(line)) starts.push({ label: 'useEffect', pos })
    pos += line.length + 1
  }
  let found: string | null = null
  for (let i = 0; i < starts.length; i++) {
    const end = i + 1 < starts.length ? starts[i + 1].pos : code.length
    if (offset >= starts[i].pos && offset < end) found = starts[i].label
  }
  return found
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
    // 4 处 = 状态筛选 / 清除定位 / 清除筛选保留 ref / 日期窗口（T02829）；新增写入口时同步本条
    expect(writes, 'setSearchParams 调用点数量变了，核对后更新本条').toBe(4)
    expect(clones, '有一处 URL 改写没从当前 searchParams 克隆，会把 ref/status 擦了').toBe(writes)
  })

  it('Orders 状态筛选只有一个写入口，绕开它的写法即漏写', () => {
    const code = codeOf(read('pages/Orders/Orders.tsx'))
    // 不能数 setStatusFilter( 的出现次数：T02673 的「演练单」是同一个下拉的第二分支，
    // 一次用户动作会连写 type 与 status 两个 state（两端互斥），出现次数随分支增加而涨。
    // 真正的不变量是「落点所在的函数」只有两个：
    //   · useEffect（URL → 状态，以链接为准，不回写，否则会自己写自己）；
    //   · onStatusChange（用户动作 → 状态 + 回写 URL）。
    // 新增第三个函数里写 status 即视为绕开写入口。
    const owners = new Set<string | null>()
    for (const m of code.matchAll(/setStatusFilter\(/g)) {
      owners.add(enclosingFunctionLabel(code, m.index ?? 0))
    }
    expect([...owners].sort(), '状态筛选的写入口变了：新增落点必须同样回写 URL').toEqual([
      'onStatusChange',
      'useEffect',
    ])

    // onStatusChange 是唯一的用户动作写入口：它必须同时把 type/status 两套参数写回 URL，
    // 两个分支共用同一个 setSearchParams 快照（dry_run 分支删 status、普通分支删 type）
    const start = code.indexOf('const onStatusChange')
    const end = code.indexOf('const handleDelete', start)
    const writer = code.slice(start, end)
    expect(writer.length, 'onStatusChange 解析为空').toBeGreaterThan(0)
    expect(writer).toContain('setSearchParams(next, { replace: true })')
    expect(writer, '演练单分支没删 status').toContain("next.delete('status')")
    expect(writer, '普通分支没写 status').toContain("next.set('status', v)")
    expect(writer, '普通分支没删 type，切回真实单后仍被演练单筛住').toContain("next.delete('type')")
    // 字面量必须取自 ORDER_STATUS（T02585 单一来源），不得硬写 'dry_run'
    expect(writer, '演练单分支没写 type').toContain("next.set('type', ORDER_STATUS.DRY_RUN)")
    // 这里不再数 setStatusFilter 的次数：一个用户动作可能写多个互斥 state（T02673 的演练单），
    // 次数随分支增加而涨。落点归属由上面的 owners 断言守，函数内只守 URL 写回。
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
