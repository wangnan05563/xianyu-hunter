// @vitest-environment node
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

// T02571 / D-6：DiffPreviewModal 不得再直连 configStore，config 一律由调用方注入。
// 只读源码、不 mount 组件：jsdom + render 要整套 antd 环境，这里断言的是「组件的依赖形状」。
const modal = readFileSync(resolve(__dirname, '../DiffPreviewModal.tsx'), 'utf-8')
const callers = [
  '../../pages/Config/BuyerStrategy.tsx',
  '../../pages/Config/EvalRules.tsx',
  '../../pages/Config/NotifierChannels/index.tsx',
  '../../pages/Config/PriceStrategy.tsx',
  '../../pages/Config/SearchConfig.tsx',
]

describe('DiffPreviewModal 与 configStore 解耦（D-6）', () => {
  it('组件不再 import / 调用 useConfigStore', () => {
    expect(modal).not.toMatch(/useConfigStore/)
  })

  it('config 走 props 声明与解构', () => {
    expect(modal).toMatch(/readonly config: AppConfig \| null/)
    expect(modal).toMatch(/\r?\n  config,\r?\n/)
  })

  it.each(callers)('%s 在 DiffPreviewModal 上注入 config', (rel) => {
    const src = readFileSync(resolve(__dirname, rel), 'utf-8')
    // 紧邻断言：props 少传一项时 tsc 会报错，这里守的是「确实传了 store 里的那份 config」
    expect(src, `${rel} 未把 config 传给 DiffPreviewModal`).toMatch(
      /diffChanges=\{diffChanges\}\r?\n\s*config=\{config\}/,
    )
  })
})
