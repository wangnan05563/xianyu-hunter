// T02726：AI 总开关关闭是全站最后一处原生 globalThis.confirm。
// 换成 confirmDanger 后，四要素文案必须与后端真实行为对齐——
// 「关闭后所有 AI 功能降级到规则模式」这句话在本项目里是假的：
// 四个推理接口在规则回落之前就被 _check_ai_enabled() 拦成 403，
// 只有 worker 的自动评估路径才是真降级；chatbot/Embedding 根本没有这个开关。
// 文案会随代码漂移，所以这里用后端源码当事实源做双向断言，而不是断言一句漂亮话。
import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { missingDangerFields } from '@/components/DangerSummary'
import {
  AI_GATE_AFFECTED,
  AI_GATE_EXCLUDED,
  GATE_HINT,
  buildDisableAICopy,
  countConfiguredModels,
} from '../dangerCopy'

const REPO_ROOT = resolve(__dirname, '../../../../../../')
const BACKEND = join(REPO_ROOT, 'backend/xianyu_hunter')

function read(rel: string): string {
  const p = join(BACKEND, rel)
  expect(existsSync(p), `后端事实源缺失：${rel}`).toBe(true)
  return readFileSync(p, 'utf-8')
}

const aiRoutes = () => read('web/routes/api_ai.py')
const deepRoutes = () => read('web/routes/api_ai_deep.py')
const worker = () => read('modules/worker.py')

const CONFIG = { model: 'gpt-4o', vision_model: 'qwen-vl-max' }
const TODAY = { total_calls: 37, total_tokens: 12800 }

describe('关闭 AI 开关的四要素文案', () => {
  const copy = buildDisableAICopy(CONFIG, TODAY)

  it('动作/影响范围/恢复成本缺一不可', () => {
    expect(missingDangerFields(copy)).toEqual([])
  })

  it('动作写明真实开关字段', () => {
    expect(copy.action).toContain('关闭')
    expect(copy.action).toContain('ai_enabled')
  })

  it('影响范围点名每一个被拦住的调用点', () => {
    for (const site of AI_GATE_AFFECTED) {
      expect(copy.scope, `${site} 未在影响范围里说明`).toContain(site)
    }
  })

  it('显式写「不包含」，不把没受开关控制的能力算进来', () => {
    for (const excluded of AI_GATE_EXCLUDED) {
      expect(copy.scope).toContain(excluded)
    }
    expect(copy.scope).toContain('不包含')
  })

  it('数量只由页面真实字段拼出', () => {
    expect(copy.count).toContain('受影响的模型 2 个')
    expect(copy.count).toContain('文本 gpt-4o')
    expect(copy.count).toContain('视觉 qwen-vl-max')
    expect(copy.count).toContain('37 次')
    expect(copy.count).toContain('12800 tokens')
  })

  it('恢复成本给出可执行的恢复动作与不可退的部分', () => {
    expect(copy.recovery).toContain('再点一次开关')
    expect(copy.recovery).toContain('不可退')
  })
})

describe('未配置模型时数量不得伪装成完整', () => {
  it('模型字段为空 → 0 个而不是省略该行', () => {
    expect(countConfiguredModels({ model: '', vision_model: '' })).toContain('0 个')
    const copy = buildDisableAICopy({ model: '', vision_model: '' }, { total_calls: 0, total_tokens: 0 })
    expect(copy.count).toContain('受影响的模型 0 个')
    expect(missingDangerFields(copy)).toEqual([])
  })

  it('用量字段缺失（旧接口）时按 0 显示，不渲染 undefined', () => {
    const copy = buildDisableAICopy(CONFIG, {})
    expect(copy.count).not.toContain('undefined')
    expect(copy.count).toContain('今日已调用 0 次')
  })

  // T02700 交叉缺陷：配置或用量请求失败时，页面里躺着的是内置默认值，
  // 此时「0 个模型 / 今日 0 次」是把「没取到」说成「没有」，确认框必须改口
  it('countsUnknown=true 时数量留空，交给「未能预先统计」而不是 0', () => {
    const copy = buildDisableAICopy(CONFIG, TODAY, true)
    expect(copy.count).toBeNull()
    expect(missingDangerFields(copy)).toEqual([])
    // 取到数据时仍要给出具体数量，别把 countsUnknown 当成默认状态
    expect(buildDisableAICopy(CONFIG, TODAY).count).toContain('受影响的模型 2 个')
  })
})

describe('deferredSave：移动端开关只改本页表单（T02892）', () => {
  it('动作与恢复成本必须写明「再点保存才生效」，桌面端措辞不受污染', () => {
    const copy = buildDisableAICopy(CONFIG, TODAY, false, { deferredSave: true })
    expect(copy.action).toContain('保存')
    expect(copy.scope).toContain('不点保存')
    expect(copy.recovery).toContain('并保存')
    expect(missingDangerFields(copy)).toEqual([])
    // 桌面端切换即生效，不能带上只对移动端成立的话
    const desktop = buildDisableAICopy(CONFIG, TODAY)
    expect(desktop.action).not.toContain('保存')
    expect(desktop.scope).not.toContain('不点保存')
  })

  it('窄屏卡片提示由「不包含」清单派生，不再承诺「所有 AI 功能」', () => {
    for (const excluded of AI_GATE_EXCLUDED) {
      expect(GATE_HINT, `${excluded} 应出现在卡片提示里`).toContain(excluded)
    }
    expect(GATE_HINT).not.toContain('所有 AI')
  })
})

describe('文案与后端源码逐条对齐（新增漂移会被拒）', () => {
  it('每个「受影响」调用点都能找到 _check_ai_enabled() 拦在规则回落之前', () => {
    const src = aiRoutes()
    const deep = deepRoutes()
    // parse-task / evaluate-condition / test-connection 在 api_ai.py，
    // deep-analyze 在 api_ai_deep.py；四者各有一次门禁调用
    for (const marker of ['@router.post("/parse-task")', '@router.post("/evaluate-condition")', '@router.post("/test-connection")']) {
      expect(src, `接口已不存在：${marker}`).toContain(marker)
    }
    expect(deep).toContain('@router.post("/deep-analyze")')
    const callSites = (s: string) => s.match(/^\s+_check_ai_enabled\(\)$/gm) ?? []
    expect(callSites(src)).toHaveLength(3)
    expect(callSites(deep)).toHaveLength(2)
  })

  it('门禁在规则回落之前抛错，所以受影响接口是「失败」而非「降级」', () => {
    const src = aiRoutes()
    const gateStart = src.indexOf('def _check_ai_enabled')
    expect(gateStart, '_check_ai_enabled 定义找不到').toBeGreaterThan(-1)
    const gateEnd = src.indexOf('\ndef ', gateStart + 1)
    const gate = src.slice(gateStart, gateEnd === -1 ? undefined : gateEnd)
    expect(gate).toContain('403')

    const parseStart = src.indexOf('@router.post("/parse-task")')
    expect(parseStart, 'parse-task 已不存在').toBeGreaterThan(-1)
    const gateAt = src.indexOf('_check_ai_enabled()', parseStart)
    const ruleAt = src.indexOf('_rule_parse(', gateAt)
    // 检查点在规则回落之前 → 关闭时根本走不到 _rule_parse
    expect(gateAt).toBeGreaterThan(parseStart)
    expect(ruleAt).toBeGreaterThan(gateAt)
  })

  it('worker 的自动评估/深度分析确实是「跳过 AI」的真降级', () => {
    const src = worker()
    expect(src).toContain('settings.ai_enabled and eval_cfg.ai_auto_eval')
    expect(src).toContain('settings.ai_enabled and eval_cfg.ai_auto_deep_analyze')
  })

  it('「不包含」列出的能力里没有任何 ai_enabled 判断', () => {
    const ungated = [
      'modules/chatbot/agent.py',
      'modules/chatbot/rag_engine.py',
      'modules/chatbot/embedding_service.py',
      'web/routes/api_chatbot.py',
      'web/routes/api_vector_admin.py',
      'web/routes/price_histogram.py',
    ]
    for (const rel of ungated) {
      expect(read(rel), `${rel} 现在受 ai_enabled 影响，文案需同步`).not.toContain('ai_enabled')
    }
  })
})
