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

describe('地区/品牌候选项来源', () => {
  it('调用后端 facets 接口取全量 DISTINCT', () => {
    expect(page).toMatch(/taskLinkApi\.facets\(selectedTask\)/)
    expect(api).toMatch(/`\/api\/tasks\/\$\{taskId\}\/links\/facets`/)
  })
  it('DB 模式优先用 facets，空则回落当前页提取（旧后端可用）', () => {
    expect(page).toMatch(/facets\.regions\.length \? facets\.regions : fromPage/)
    expect(page).toMatch(/facets\.brands\.length \? facets\.brands : fromPage/)
  })
})
