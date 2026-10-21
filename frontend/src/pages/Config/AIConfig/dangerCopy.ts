// AI 总开关关闭时的危险操作文案（规范见 docs/standards/危险操作文案规范.md，T02726）。
//
// 这里写下的每条后果都对应后端真实代码，不是沿用页面旧文案的推测：
// - api_ai.py::_check_ai_enabled() 在 ai_enabled=false 时抛 403，调用点在规则回落之前，
//   所以 parse-task / evaluate-condition / test-connection / deep-analyze / seller-template-check
//   是「直接失败」，不是「降级到规则模式」。
// - worker.py 的自动评估与深度分析用 settings.ai_enabled 作前置条件，关闭时跳过 AI、
//   保留规则评估结果——只有这条是真降级。
// - chatbot / RAG / Embedding / 价格趋势 AI 解读 全仓没有 ai_enabled 判断，不受本开关影响。
import type { DangerCopy } from '@/components/DangerSummary'

export interface AIModelFields {
  readonly model?: string | null
  readonly vision_model?: string | null
}

export interface AITodayUsage {
  readonly total_calls?: number | null
  readonly total_tokens?: number | null
}

/** 受本开关影响的调用点，逐条来自后端 _check_ai_enabled() 的位置 */
export const AI_GATE_AFFECTED = [
  '任务页 AI 建任务（/api/ai/parse-task）',
  '评估页 AI 成色评估与批量评估（/api/ai/evaluate-condition）',
  '评估页 AI 深度分析（/api/ai/deep-analyze）',
  '本页「测试连接」（/api/ai/test-connection）',
] as const

/** 明确「不包含」：这些 AI 能力不走这个开关 */
export const AI_GATE_EXCLUDED = [
  'AI 对话助手与知识库检索',
  'Embedding 向量服务',
  '价格趋势 AI 解读',
] as const

function joinNames(names: string[]): string {
  return names.length ? names.join('、') : '无'
}

/** 数量只允许来自页面已加载的真实字段：配置里的模型名 + 今日用量 */
export function countConfiguredModels(config: AIModelFields): string {
  const named: string[] = []
  if (config.model) named.push(`文本 ${config.model}`)
  if (config.vision_model) named.push(`视觉 ${config.vision_model}`)
  return `受影响的模型 ${named.length} 个（${joinNames(named)}）`
}

export function buildDisableAICopy(config: AIModelFields, today: AITodayUsage): DangerCopy {
  const calls = today?.total_calls ?? 0
  const tokens = today?.total_tokens ?? 0
  return {
    title: '确认关闭 AI 功能总开关？',
    action: '把 AI 功能总开关切到关闭（settings.ai_enabled = false，热更新生效，无需重启）',
    scope:
      `受影响：${joinNames([...AI_GATE_AFFECTED])}——后端在调用 LLM 前先检查开关，` +
      '这些操作会直接返回「AI 功能已关闭」的 403 错误，不会自动改用规则模式；' +
      '后台任务的自动评估/深度分析则跳过 AI，沿用规则评估结果。' +
      `不包含：${joinNames([...AI_GATE_EXCLUDED])}（后端无此开关判断），` +
      '以及 API Key、模型配置与历史评估结果。',
    count: `${countConfiguredModels(config)} · 今日已调用 ${calls} 次、${tokens} tokens`,
    recovery:
      '再点一次开关即恢复，配置与历史结果不受影响；关闭期间不会新增 token 消耗，' +
      '但已经消耗的 token 不可退。',
  }
}
