// @vitest-environment node
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

// T02963 裁决：新建任务的默认模式与后端 API 契约统一为 notify（不自动下单）；
// 编辑回填是另一条语义（沿用任务自身的 mode），两者不能合并成一个兜底。
const SRC = readFileSync(resolve(__dirname, '../TaskEditor.tsx'), 'utf8')

describe('新建任务默认模式（T02963）', () => {
  it('新建初值回落到 NOTIFY，不再与 API 默认值分叉', () => {
    expect(SRC).toContain(
      'const initialMode = isTaskMode(prefillMode) ? prefillMode : TASK_MODE.NOTIFY',
    )
    expect(SRC).not.toContain('isTaskMode(prefillMode) ? prefillMode : TASK_MODE.CONFIRM')
  })

  it('编辑回填仍保留 CONFIRM 兜底，不被新建默认值顺手改掉', () => {
    expect(SRC).toContain('mode: task.mode || TASK_MODE.CONFIRM')
  })
})
