// @vitest-environment node
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * T02571「保存按页段提交」：5 个配置页必须把本页 scope 交给 previewSave/confirmSave/reset。
 * 少了这个实参就退化成整份提交——别的页的未保存草稿会被这一次保存顺带写盘。
 */
const PAGES: ReadonlyArray<{ file: string; scope: string }> = [
  { file: '../../pages/Config/PriceStrategy.tsx', scope: 'SCOPE_PRICE' },
  { file: '../../pages/Config/EvalRules.tsx', scope: 'SCOPE_EVAL' },
  { file: '../../pages/Config/NotifierChannels/index.tsx', scope: 'SCOPE_NOTIFIER' },
  { file: '../../pages/Config/SearchConfig.tsx', scope: 'SCOPE_SEARCH' },
  { file: '../../pages/Config/BuyerStrategy.tsx', scope: 'SCOPE_BUYER' },
]

describe('配置页按页段提交（T02571）', () => {
  it.each(PAGES.map((p) => [p.file, p.scope] as const))('%s 用 %s 提交并重置', (file, scope) => {
    const src = readFileSync(resolve(__dirname, file), 'utf-8')
    expect(src, `${file} 未 import ${scope}`).toMatch(
      new RegExp(`import \\{ ${scope} \\} from '[^']*stores/configDirty'`),
    )
    expect(src).toContain(`previewSave(${scope})`)
    expect(src).toContain(`confirmSave(${scope})`)
    // onClick={reset} 会把 MouseEvent 当成 scope 传进去，必须显式包一层
    expect(src).toContain(`reset(${scope})`)
    expect(src, `${file} 仍在用整份 hasChanges() 控制重置按钮`).not.toMatch(/disabled=\{!hasChanges\(\)\}/)
  })

  it('TaskEditor 的全局配置面板保持整份提交，且不会把点击事件当成 scope', () => {
    const src = readFileSync(resolve(__dirname, '../../pages/Tasks/TaskEditor.tsx'), 'utf-8')
    expect(src).not.toMatch(/previewSave\(SCOPE_|confirmSave\(SCOPE_|reset\(SCOPE_/)
    // reset 现在带可选 scope，直接绑 onClick 会把 MouseEvent 当成段名
    expect(src, 'onClick={reset} 会把点击事件当成 scope 传给 reset').not.toMatch(/onClick=\{reset\}/)
  })
})
