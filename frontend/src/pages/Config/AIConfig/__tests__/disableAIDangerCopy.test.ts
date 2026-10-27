// T02726：AI 总开关关闭是全站最后一处原生 globalThis.confirm。
// 换成 confirmDanger 后，四要素文案必须与后端真实行为对齐——
// T02947 裁决 A 之后，三个推理接口在开关关闭时确实退回规则解析；
// T02891 裁决 A（全量纳管）之后，chatbot/RAG/Agent/远程 Embedding/价格解读也各自判开关，
// 「不包含」清单只剩真正不产生 token 费用的本地能力。
// 文案会随代码漂移，所以这里用后端源码当事实源做双向断言，而不是断言一句漂亮话。
import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { missingDangerFields } from '@/components/DangerSummary'
import {
  AI_GATE_AFFECTED,
  AI_GATE_EXCLUDED,
  AI_GATE_HARD_FAIL,
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

  it('硬失败清单只有两处，且不含对话入口（AC-18 要的是降级，不是死路）', () => {
    const copy = buildDisableAICopy(CONFIG, TODAY)
    expect(AI_GATE_HARD_FAIL).toHaveLength(2)
    expect(AI_GATE_HARD_FAIL.join(' ')).not.toContain('对话')
    for (const hard of AI_GATE_HARD_FAIL) {
      expect(copy.scope, `${hard} 未在「仍会直接报错」里说明`).toContain(hard)
    }
    // 对话的关闭态必须说成「降级」，窄屏卡片与桌面端四要素同口径
    expect(GATE_HINT).toContain('对话退成常见问题与检索片段')
    expect(copy.scope).toContain('推理入口退回规则引擎')
  })
})

describe('文案与后端源码逐条对齐（新增漂移会被拒）', () => {
  /** 从 @router 装饰器切到下一个端点/分节头为止（不能按 `def ` 切，
   *  紧跟着的那行就是本端点自己的 def） */
  const endpointBody = (src: string, marker: string) => {
    const start = src.indexOf(marker)
    expect(start, `接口已不存在：${marker}`).toBeGreaterThan(-1)
    const rest = src.slice(start + marker.length)
    const end = rest.search(/\n(?=@router\.|# =)/)
    return end === -1 ? rest : rest.slice(0, end)
  }

  it('推理端点改用 _ai_enabled() 分支，raise 型门禁只剩 test-connection 与远程 test-embedding', () => {
    const src = aiRoutes()
    const deep = deepRoutes()
    expect(deep).toContain('@router.post("/deep-analyze")')
    // test-connection 一直是 raise 型；test-embedding 由 T02891 裁决 A 补上（只在远程配置下触发）
    // → raise 点固定为 2 处，deep 文件里一处都不该留
    expect((src.match(/^\s+_check_ai_enabled\(\)$/gm) ?? [])).toHaveLength(2)
    expect((deep.match(/^\s+_check_ai_enabled\(\)$/gm) ?? [])).toHaveLength(0)
    // 三个推理端点各自判开关，漏一个就是「关着还在烧 token」
    expect(endpointBody(src, '@router.post("/parse-task")')).toContain('_ai_enabled()')
    expect(endpointBody(src, '@router.post("/evaluate-condition")')).toContain('_ai_enabled()')
    expect(endpointBody(deep, '@router.post("/deep-analyze")')).toContain('_ai_enabled()')
    // seller-template-check 全程零 LLM，门禁必须摘掉（T02891 孤儿端点同一条证据）
    expect(endpointBody(deep, '@router.post("/seller-template-check")')).not.toContain('_ai_enabled()')
  })

  it('开关关闭时 parse-task 走得到 _rule_parse，test-connection 仍硬失败', () => {
    const src = aiRoutes()
    const parse = endpointBody(src, '@router.post("/parse-task")')
    expect(parse).not.toContain('_check_ai_enabled()')
    expect(parse).toContain('_rule_parse(')
    // 唯一保留 403 的端点：测一个已关掉的开关没有意义
    expect(endpointBody(src, '@router.post("/test-connection")')).toContain('_check_ai_enabled()')
  })

  it('worker 的自动评估/深度分析确实是「跳过 AI」的真降级', () => {
    const src = worker()
    expect(src).toContain('settings.ai_enabled and eval_cfg.ai_auto_eval')
    expect(src).toContain('settings.ai_enabled and eval_cfg.ai_auto_deep_analyze')
  })

  it('T02891 裁决 A 后：原先不受控的调用点必须逐个判开关', () => {
    // 模块层用统一判据 config.is_ai_disabled()（每次重读，开关是热更新的）；
    // 路由层直接读 settings.ai_enabled 再抛带 code 的 403
    const gated: Array<[string, string]> = [
      ['modules/chatbot/agent.py', 'is_ai_disabled()'],
      ['modules/chatbot/rag_engine.py', 'is_ai_disabled()'],
      ['modules/chatbot/embedding_service.py', 'is_ai_disabled()'],
      ['modules/chatbot/intent_classifier.py', 'is_ai_disabled()'],
      ['web/routes/api_kb.py', 'ai_enabled'],
      ['web/routes/price_histogram.py', 'ai_enabled'],
    ]
    for (const [rel, marker] of gated) {
      expect(read(rel), `${rel} 缺 AI 总开关判断（应包含 ${marker}）`).toContain(marker)
    }
  })

  it('对话入口不设门禁：AC-18 要的是降级，不是死路', () => {
    // 智能客服需求 AC-18「关闭 AI 开关后，对话降级为 FAQ + 检索片段」——
    // 在 /api/chatbot/chat 上加 403 会让这条验收标准失效，付费出口已在各调用点判开关闭合。
    expect(read('web/routes/api_chatbot.py')).not.toContain('ai_enabled')
    expect(read('modules/chatbot/orchestrator.py')).toContain('_fallback_after_llm_failure')
  })

  it('判据只有一个出处：模块不得各自读 settings.ai_enabled', () => {
    for (const rel of [
      'modules/chatbot/agent.py',
      'modules/chatbot/rag_engine.py',
      'modules/chatbot/embedding_service.py',
      'modules/chatbot/intent_classifier.py',
    ]) {
      const src = read(rel)
      expect(src, `${rel} 应改走 config.is_ai_disabled()`).toContain('is_ai_disabled')
      expect(src, `${rel} 不应自己拼开关条件`).not.toContain('settings.ai_enabled')
    }
    expect(read('config.py')).toContain('def is_ai_disabled()')
  })

  it('向量库维护端点不调模型，没有开关判断才是正确状态', () => {
    expect(read('web/routes/api_vector_admin.py')).not.toContain('ai_enabled')
  })
})
