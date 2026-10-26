// AI 总开关关闭时的危险操作文案（规范见 docs/standards/危险操作文案规范.md，T02726）。
//
// 这里写下的每条后果都对应后端真实代码，不是沿用页面旧文案的推测：
// - api_ai.py::_ai_enabled() 在 ai_enabled=false 时让 parse-task / evaluate-condition /
//   deep-analyze 跳过 LLM、直接走已有的规则回落分支（响应里 source="rule"）——
//   这是 T02947 的裁决 A，不是「直接失败」，也不是「什么都不返回」。
// - test-connection 仍走 _check_ai_enabled() 硬 403：测一个已经关掉的开关没有意义，
//   返回规则结果只会把「连不上」伪装成「连通但降级」。
// - seller-template-check 全程是词频统计，压根不调 LLM，所以不受本开关约束。
// - worker.py 的自动评估与深度分析用 settings.ai_enabled 作前置条件，关闭时跳过 AI、
//   保留规则评估结果——与上面三个推理端点同一条口径。
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

/** 关闭后退回规则解析的推理入口，逐条来自后端 `_ai_enabled()` 的判断点 */
export const AI_GATE_AFFECTED = [
  '任务页 AI 建任务（/api/ai/parse-task → 规则解析）',
  '评估页 AI 成色评估与批量评估（/api/ai/evaluate-condition → 规则模拟）',
  '评估页 AI 深度分析（/api/ai/deep-analyze → 规则模拟）',
] as const

/** 仍然硬失败的入口：它没有「规则形态」，关闭时只能报错（T02947 裁决 A 明确保留） */
export const AI_GATE_HARD_FAIL = [
  '本页「测试连接」（/api/ai/test-connection，仍返回 403）',
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

/**
 * 窄屏卡片用的一句话提示。刻意由上面的常量派生：
 * 「关闭后所有 AI 功能停用」这句话在本项目里是假的（后端开关不覆盖 AI_GATE_EXCLUDED），
 * 桌面端 T02726 已经删掉过它，别让移动端再手写一份。
 */
export const GATE_HINT = `关闭后 AI 建任务与 AI 评估退回规则解析（结果非 AI）；不含${joinNames([...AI_GATE_EXCLUDED])}`

export interface DisableAICopyOptions {
  /** 移动端总开关只改本页表单，要点「保存」才落库。不写清这一步，
   * 「热更新生效」会被读成开关一切就生效（T02892）。 */
  deferredSave?: boolean
}

/**
 * @param countsUnknown 配置或用量接口没取到时传 true：
 *   此时 config.model / today 都是兜底空值，写进「数量」会说成「0 个模型、今日 0 次」，
 *   等于把接口故障冒充成统计结果（T02700 与 T02726 的交叉点），故留 null 走 COUNT_UNKNOWN。
 */
export function buildDisableAICopy(
  config: AIModelFields,
  today: AITodayUsage,
  countsUnknown = false,
  opts: DisableAICopyOptions = {},
): DangerCopy {
  const calls = today?.total_calls ?? 0
  const tokens = today?.total_tokens ?? 0
  const action = opts.deferredSave
    ? '先把「启用 AI 服务」开关切到关闭，再点本页「保存」才会写入' +
      '（settings.ai_enabled = false，热更新生效，无需重启）'
    : '把 AI 功能总开关切到关闭（settings.ai_enabled = false，热更新生效，无需重启）'
  return {
    title: '确认关闭 AI 功能总开关？',
    action,
    scope:
      `受影响：${joinNames([...AI_GATE_AFFECTED])}——后端在调用 LLM 前先检查开关，` +
      '关闭时这些操作不再请求模型，而是退回规则引擎给出结果（仍可点、仍可保存，但来源标记为「规则」而非 AI）；' +
      `${joinNames([...AI_GATE_HARD_FAIL])}；` +
      '后台任务的自动评估/深度分析同样跳过 AI，沿用规则评估结果。' +
      `不包含：${joinNames([...AI_GATE_EXCLUDED])}（后端无此开关判断），` +
      '以及 API Key、模型配置与历史评估结果。' +
      (opts.deferredSave ? '取消本确认框则本页表单不变；只切开关而不点保存，后端配置也不会变。' : ''),
    count: countsUnknown
      ? null
      : `${countConfiguredModels(config)} · 今日已调用 ${calls} 次、${tokens} tokens`,
    recovery: opts.deferredSave
      ? '再点一次开关并保存即恢复，配置与历史结果不受影响；关闭期间不会新增 token 消耗，' +
        '但已经消耗的 token 不可退。'
      : '再点一次开关即恢复，配置与历史结果不受影响；关闭期间不会新增 token 消耗，' +
        '但已经消耗的 token 不可退。',
  }
}
