import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * T02566 §2.3 商品列表三项修复的契约测试（源码断言，锁死口径防回归）
 * 注释先剥掉，避免"把旧写法写在注释里"被误判为仍存在
 */
const stripComments = (s: string) =>
  s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')

const page = stripComments(readFileSync(resolve(__dirname, '../ItemList.tsx'), 'utf-8'))
const api = stripComments(readFileSync(resolve(__dirname, '../../../api/task.ts'), 'utf-8'))

describe('商品列表登录失效跳转', () => {
  it('「重新登录」跳 /login?redirect=（与 MainLayout/UserMenu 全局惯例一致）', () => {
    expect(page).toMatch(/navigate\(`\/login\?redirect=/)
  })
  it('不再跳 `/?redirect=`（那条路径落到仪表盘且 redirect 被忽略）', () => {
    expect(page).not.toMatch(/navigate\(`\/\?redirect=/)
  })
})

describe('商品列表 React key', () => {
  it('卡片视图不再用 item.link_id 作 key（实时结果 link_id 恒为 0 会撞 key）', () => {
    expect(page).not.toMatch(/key=\{item\.link_id\}/)
    expect(page).toMatch(/key=\{rowKeyOf\(item\)\}/)
  })
  it('表格 rowKey 与高亮口径一致（都用 link_key）', () => {
    expect(page).not.toMatch(/rowKey="link_id"/)
    expect(page).toMatch(/rowKey=\{rowKeyOf\}/)
    expect(page).toMatch(/const rowKeyOf = \(i: TaskLink\) => i\.link_key \|\| String\(i\.link_id\)/)
  })
})

describe('实时搜索错误分支（T02660）', () => {
  it('按结构化 code 的分类结果分支，不再直接匹配中文子串', () => {
    expect(page).toMatch(/classifyLiveSearchError\(err\)/)
    expect(page).not.toMatch(/detail\.includes\('已过期'\)/)
  })
  it('SSE 错误事件透传 code', () => {
    expect(api).toMatch(/makeHttpError\(data\.status \|\| 502, \{ detail: data\.detail, code: data\.code \}\)/)
  })
})

describe('地区/品牌候选项来源', () => {
  it('调后端 facets，并把当前关键词/销售状态一起传过去（T02661 裁决「方案1」）', () => {
    expect(page).toMatch(
      /taskLinkApi\.facets\(selectedTask, \{\s*\n\s*keyword: search \|\| undefined,\s*\n\s*sold_filter: soldFilter === 'all' \? undefined : soldFilter,\s*\n\s*\}\)/,
    )
    expect(api).toMatch(/`\/api\/tasks\/\$\{taskId\}\/links\/facets`, \{ params \}/)
  })
  it('region/brand 不得进 facets 请求：候选不能被自己收缩掉（T02566 的自锁死）', () => {
    const at = page.indexOf('taskLinkApi.facets(')
    const call = page.slice(at, at + 400)
    expect(call).not.toMatch(/region:/)
    expect(call).not.toMatch(/brand:/)
    // 收缩条件变了就得重取，否则候选停留在旧筛选下（选了必空）；region/brand 不进依赖
    expect(page).toMatch(/\}, \[selectedTask, liveMode, search, soldFilter\]\)/)
  })
  it('DB 模式优先用 facets，空则回落当前页提取（旧后端可用）', () => {
    expect(page).toMatch(/facets\.regions\.length \? facets\.regions : fromPage/)
    expect(page).toMatch(/facets\.brands\.length \? facets\.brands : fromPage/)
  })
})

// T02658（评审 2.3-5）：标题列原来是一个去样式 button，点一下同时「真实采集 + 新开原帖」，
// 两个副作用都不可发现。现在标题只开原帖，采集移到独立按钮。
describe('商品标题与采集职责拆分（T02658）', () => {
  const linkCase = page.slice(page.indexOf("case 'link':"), page.indexOf("case 'price':"))

  it('表格标题是纯链接（Typography.Link + href），不再挂采集 handler', () => {
    expect(linkCase).toContain('<Typography.Link href={d.url}')
    expect(linkCase).not.toContain('handleRefreshItem')
    expect(linkCase).not.toContain('<button')
  })

  it('采集是操作列独立按钮，handler 不再打开新窗口', () => {
    expect(page).toContain('tip="采集更新商品信息（不打开原帖）"')
    expect(page).toMatch(/handleRefreshItem\(record\.link_key/)
    const fn = page.slice(
      page.indexOf('const handleRefreshItem'),
      page.indexOf('}, [selectedTask, applyRefreshToLiveItem, loadItems])'),
    )
    expect(fn).not.toContain('globalThis.open')
    expect(page).not.toContain('globalThis.open')
  })

  it('卡片视图同样拆成「打开原帖」链接与独立采集按钮', () => {
    expect(page).toContain('aria-label={`打开原帖：')
    expect(page).toContain('title="采集更新商品信息（不打开原帖）"')
    expect(page).not.toContain('采集更新并打开原帖')
  })
})
