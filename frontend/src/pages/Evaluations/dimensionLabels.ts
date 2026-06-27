/**
 * 评估维度与拒绝原因的中文翻译
 *
 * 为什么在前端翻译而非后端：
 * 1. 后端写入的英文 key 是稳定的协议契约，前端展示层独立于后端实现
 * 2. 后续增加语言（如 i18n 英文版）只需扩展映射，无需修改后端
 * 3. 调试时后端原始 key 仍可在 payload 中查看，便于定位问题
 *
 * 字段来源：
 * - dimension_scores 的 key：evaluator.py 中写入的英文标识（professional/credit/dispute/price/popularity）
 * - reject_reasons 的 token：evaluator.py 中 reasons.append 的英文标识
 */

// === 评估维度（dimension_scores 的 key）===
// 与后端 evaluator._eval_* 方法写入的 key 保持一致
export const DIMENSION_LABELS: Record<string, string> = {
  professional: '职业卖家',
  credit: '信用',
  dispute: '纠纷',
  price: '价格',
  popularity: '热度',
}

// === 拒绝原因（reject_reasons 的 token）===
// 与后端 evaluator.py 中 reasons.append 的字符串保持一致
// 模式匹配：优先精确匹配，未匹配时再尝试前缀匹配（如 professional_keyword:xxx）
const REJECT_REASON_LABELS: Array<[RegExp, string]> = [
  // === 一票否决类 ===
  [/^platform_blacklist$/, '平台黑名单'],
  [/^credit_score (\d+(?:\.\d+)?) < min (\d+)$/, '信用分$1低于阈值$2'],
  [/^insufficient_seller_data$/, '卖家信息不足'],

  // === 职业卖家 ===
  [/^professional_keyword:/, '含职业关键词'],
  [/^on_sale_count (\d+(?:\.\d+)?) < min (\d+)$/, '在售数$1低于阈值$2'],
  [/^post_count_30d (\d+(?:\.\d+)?) < min (\d+)$/, '30天发布数$1低于阈值$2'],
  [/^top_category_ratio/, '商品集中度过高'],

  // === 信用 ===
  [/^credit_score_unknown$/, '信用分未知'],
  [/^credit_score (\d+(?:\.\d+)?) moderate$/, '信用分$1中等'],
  [/^low_register_days/, '注册时间过短'],
  [/^bad_review (\d+(?:\.\d+)?)$/, '差评数$1过多'],
  [/^low_sold_count (\d+(?:\.\d+)?)$/, '已售数$1过低'],

  // === 价格 ===
  [/^price_suspicious_low$/, '价格疑似过低'],
  [/^price_abnormal_low\(\$?[\d.]+\)$/, '价格异常低'],
  [/^price_bait:/, '价格诱饵词'],
  [/^shipping_trap:/, '运费陷阱'],

  // === 成色与热度 ===
  [/^no_image_for_condition$/, '缺少成色参考图'],
  [/^zero_want_count$/, '无人想要'],
  [/^low_want_count\(/, '想要人数偏低'],
  [/^high_want_count\(/, '想要人数偏高'],

  // === AI 评估结果 ===
  [/^ai_reject\(/, 'AI 成色评估拒绝'],
  [/^ai_caution\(/, 'AI 成色评估谨慎'],
  [/^ai_low_condition\(/, 'AI 评估成色较低'],
]

/**
 * 翻译单个评估维度 key
 * @param key 后端返回的英文 key
 * @returns 中文标签；未匹配时返回原 key
 */
export function translateDimension(key: string): string {
  return DIMENSION_LABELS[key] ?? key
}

/**
 * 翻译单个拒绝原因 token
 * @param reason 后端返回的英文原因
 * @returns 中文描述；未匹配时返回原 token
 */
export function translateRejectReason(reason: string): string {
  for (const [pattern, label] of REJECT_REASON_LABELS) {
    if (pattern.test(reason)) return label
  }
  return reason
}

/**
 * 批量翻译拒绝原因数组
 */
export function translateRejectReasons(reasons: string[] | undefined | null): string[] {
  if (!reasons) return []
  return reasons.map(translateRejectReason)
}
