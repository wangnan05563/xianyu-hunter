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
// - T02891 裁决 A（全量纳管）之后，chatbot / RAG / Agent / 远程 Embedding /
//   价格趋势解读也各自判开关，判据统一走 config.is_ai_disabled()。门禁落在付费出口本身：
//   对话入口 /api/chatbot/chat 不拦——智能客服需求 AC-18 要求「关闭 AI 开关后对话降级为
//   FAQ + 检索片段」，orchestrator 的降级链已能零成本兑现它，端点 403 反而把降级变成死路。
// - 仍然不受约束的只有「不产生 token 费用」的那两类：本地 Embedding 后端与本地
//   ChromaDB 检索（见 AI_GATE_EXCLUDED）。把它们一起关掉省不到钱，只会让检索静默变空。
import type { DangerCopy } from '@/components/DangerSummary'

export interface AIModelFields {
  readonly model?: string | null
  readonly vision_model?: string | null
}

export interface AITodayUsage {
  readonly total_calls?: number | null
  readonly total_tokens?: number | null
}

/** 受开关约束的调用点，逐条来自后端真实的判开关位置 */
export const AI_GATE_AFFECTED = [
  '任务页 AI 建任务（/api/ai/parse-task → 规则解析）',
  '评估页 AI 成色评估与批量评估（/api/ai/evaluate-condition → 规则模拟）',
  '评估页 AI 深度分析（/api/ai/deep-analyze → 规则模拟）',
  '对话助手意图分类（LLM 兜底 → 规则预筛后保守放行）',
  '对话助手回答生成与推荐追问（不打 LLM；入口仍可发消息，命中常见问题按 FAQ 答，否则退成「只列检索片段」或提示转人工）',
  '对话助手工具决策（Agent 调 LLM 前判断；意图不再建议 agent 时本就不会触发）',
  '远程 Embedding 向量化（含批量重建的逐条向量化）',
  '价格趋势 AI 解读（/api/prices/analyze；直方图本体是纯 SQL，不受影响）',
] as const

/** 仍然硬失败的入口：它没有「规则形态」，关闭时只能报错（T02947 裁决 A 保留，T02891 裁决 A 扩充） */
export const AI_GATE_HARD_FAIL = [
  '本页「测试连接」（/api/ai/test-connection，仍返回 403）',
  '本页「测试 Embedding 连接」与知识库重建（远程 embedding 配置下返回 403）',
] as const

/** 明确「不包含」：这些能力不产生 token 费用，关掉开关也照跑 */
export const AI_GATE_EXCLUDED = [
  '本地 Embedding 后端（不产生 token 费用）',
  '本地向量库检索与知识库读写（ChromaDB 本地，不调 LLM）',
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
 * 「关闭后所有 AI 功能停用」这句话在 T02891 落地之前是假的（开关不覆盖 chatbot/Embedding），
 * 落地之后也不能反过来写成「对话助手会被拦下」——它是降级成 FAQ/检索片段，不是不可用。
 * 桌面端 T02726 已经删掉过那句承诺，别让移动端再手写一份。
 */
export const GATE_HINT = `关闭后 AI 建任务与 AI 评估退回规则解析（结果非 AI），对话退成常见问题与检索片段，远程向量化会被直接拦下；不含${joinNames([...AI_GATE_EXCLUDED])}`

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
      `受影响：${joinNames([...AI_GATE_AFFECTED])}——后端在发起调用前先检查开关，` +
      '关闭时这些操作不再请求模型：推理入口退回规则引擎给出结果（仍可点、仍可保存，但来源标记为「规则」而非 AI）。' +
      `其中仍会直接报错的：${joinNames([...AI_GATE_HARD_FAIL])}；` +
      '后台任务的自动评估/深度分析同样跳过 AI，沿用规则评估结果。' +
      `不包含：${joinNames([...AI_GATE_EXCLUDED])}（不产生 token 费用，关掉开关照跑），` +
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
