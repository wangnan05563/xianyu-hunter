// T02726：AI 总开关关闭是全站最后一处原生 globalThis.confirm。
// 换成 confirmDanger 后，四要素文案必须与后端真实行为对齐——
// 「关闭后所有 AI 功能降级到规则模式」这句话在本项目里是假的：
// T02947 裁决 A 之后，三个推理接口在开关关闭时确实退回规则解析，
// 但只有那三个；chatbot/Embedding/价格解读根本没有这个开关，test-connection 仍硬失败。
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
  /** 从 @router 装饰器切到下一个端点/分节头为止（不能按 `def ` 切，
   *  紧跟着的那行就是本端点自己的 def） */
  const endpointBody = (src: string, marker: string) => {
    const start = src.indexOf(marker)
    expect(start, `接口已不存在：${marker}`).toBeGreaterThan(-1)
    const rest = src.slice(start + marker.length)
    const end = rest.search(/\n(?=@router\.|# =)/)
    return end === -1 ? rest : rest.slice(0, end)
  }

  it('推理端点改用 _ai_enabled() 分支，硬门禁只剩 test-connection（T02947 裁决 A）', () => {
    const src = aiRoutes()
    const deep = deepRoutes()
    expect(deep).toContain('@router.post("/deep-analyze")')
    // raise 型门禁只允许 test-connection 一处；deep 文件里一处都不该留
    expect((src.match(/^\s+_check_ai_enabled\(\)$/gm) ?? [])).toHaveLength(1)
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
