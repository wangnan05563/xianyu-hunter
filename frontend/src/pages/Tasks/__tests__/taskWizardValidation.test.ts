// @vitest-environment node
/**
 * 任务向导各步校验（T02653）
 *
 * 钉住：跳步/下一步/提交前必须能拦住价格倒置、调度越界这类非法参数，
 * 且错误要带 step 序号与字段名，界面才能跳回对应步骤并高亮字段。
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import {
  validateStep,
  validateStepsBetween,
  type WizardValues,
} from '../taskWizardValidation'

function values(patch: Partial<WizardValues> = {}): WizardValues {
  return {
    keyword: '索尼 A7M4',
    min_price: null,
    max_price: null,
    max_publish_days: 7,
    eval_threshold: null,
    ai_prompt: null,
    useCron: false,
    cron: '*/5 * * * *',
    intervalSeconds: 60,
    ...patch,
  }
}

describe('validateStep', () => {
  it('Step 1：空关键词 / 纯空格 / 超长都拦截', () => {
    expect(validateStep(0, values({ keyword: '' }))).toEqual([
      { step: 0, field: 'keyword', message: '请输入关键词' },
    ])
    expect(validateStep(0, values({ keyword: '   ' }))).toHaveLength(1)
    expect(validateStep(0, values({ keyword: 'x'.repeat(81) }))[0].message).toContain('80')
    expect(validateStep(0, values({ keyword: 'x'.repeat(80) }))).toEqual([])
  })

  it('Step 2：价格倒置必须拦截；区间相等/单边为 null 放行', () => {
    expect(validateStep(1, values({ min_price: 5000, max_price: 3000 }))).toEqual([
      { step: 1, field: 'min_price', message: '最低价不能高于最高价' },
    ])
    expect(validateStep(1, values({ min_price: 3000, max_price: 3000 }))).toEqual([])
    expect(validateStep(1, values({ min_price: 5000, max_price: null }))).toEqual([])
    expect(validateStep(1, values({ max_publish_days: 0 }))[0].field).toBe('max_publish_days')
  })

  it('Step 4：AI 阈值越界与提示词超长', () => {
    expect(validateStep(3, values({ eval_threshold: 101 }))[0]).toMatchObject({
      step: 3,
      field: 'eval_threshold',
    })
    expect(validateStep(3, values({ eval_threshold: -1 }))).toHaveLength(1)
    expect(validateStep(3, values({ eval_threshold: 0 }))).toEqual([])
    expect(validateStep(3, values({ ai_prompt: 'x'.repeat(501) }))[0].field).toBe('ai_prompt')
    expect(validateStep(3, values({ ai_prompt: 'x'.repeat(500) }))).toEqual([])
  })

  it('Step 6：固定间隔 30–3600；Cron 必须 5 段', () => {
    expect(validateStep(5, values({ intervalSeconds: 29 }))[0].message).toContain('30–3600')
    expect(validateStep(5, values({ intervalSeconds: 3601 }))).toHaveLength(1)
    expect(validateStep(5, values({ intervalSeconds: 30 }))).toEqual([])
    expect(validateStep(5, values({ useCron: true, cron: '*/5 * * *' }))[0].field).toBe('cron')
    expect(validateStep(5, values({ useCron: true, cron: '  ' }))).toHaveLength(1)
    expect(validateStep(5, values({ useCron: true, cron: '0 9 * * 1' }))).toEqual([])
    // Cron 模式下不再校验固定间隔
    expect(validateStep(5, values({ useCron: true, cron: '0 9 * * 1', intervalSeconds: 1 }))).toEqual([])
  })

  it('无输入的步骤（搜索/反检测）恒通过', () => {
    expect(validateStep(2, values())).toEqual([])
    expect(validateStep(4, values())).toEqual([])
  })
})

describe('validateStepsBetween', () => {
  it('跳步时汇总目标步之前的所有错误，并带正确 step 序号', () => {
    const errs = validateStepsBetween(0, 6, values({
      keyword: '',
      min_price: 5000,
      max_price: 100,
      intervalSeconds: 5,
    }))
    expect(errs.map((e) => e.field)).toEqual(['keyword', 'min_price', 'interval_seconds'])
    expect(errs[2].step).toBe(5)
  })

  it('区间为空时不校验（向后跳步不应被拦）', () => {
    expect(validateStepsBetween(3, 3, values({ keyword: '' }))).toEqual([])
  })
})

// 纯函数只有被 TaskEditor 真正接上才算落地：这里钉住三处接线
const editor = readFileSync(resolve(__dirname, '../TaskEditor.tsx'), 'utf-8')
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .replace(/^\s*\/\/.*$/gm, '')

describe('TaskEditor 接线（T02653）', () => {
  it('「下一步」先校验当前步，通过才前进', () => {
    expect(editor).toMatch(/const handleNext = \(\) => \{[\s\S]*?validateStep\(current, wizardValues\)[\s\S]*?setCurrent\(current \+ 1\)/)
  })

  it('点选跳步校验目标步之前的所有步', () => {
    expect(editor).toMatch(/onChange=\{handleStepJump\}/)
    expect(editor).toContain('validateStepsBetween(current, target, wizardValues)')
  })

  it('最终提交前再全量校验一次；错误会切回出错步骤', () => {
    expect(editor).toMatch(/validateStepsBetween\(0, steps\.length, wizardValues\)/)
    expect(editor).toContain('setCurrent(first.step)')
  })

  it('「直接创建」快捷通道不做逐步校验', () => {
    expect(editor).toContain('onClick={() => handleSubmit(false)}')
  })
})
