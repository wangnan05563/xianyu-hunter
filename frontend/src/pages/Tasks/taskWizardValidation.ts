// 任务向导各步校验（T02653）
//
// 为什么需要：Steps 支持点选跳步后，用户可以直接跳到第 6 步提交，
// 前面填错的参数（价格倒置、调度越界）会一次性被后端拒绝，用户不知道错在哪一步。
// 这里把校验规则收敛成纯函数，供「下一步」「跳步」「提交」三处复用。

export const STEP_TITLES = [
  '基础信息',
  '价格与过滤',
  '搜索参数',
  'AI 评估',
  '反检测',
  '调度与确认',
] as const

export interface WizardValues {
  keyword: string
  min_price: number | null
  max_price: number | null
  max_publish_days: number | null
  eval_threshold: number | null
  ai_prompt: string | null
  useCron: boolean
  cron: string
  intervalSeconds: number
}

export interface StepError {
  step: number
  field: string
  message: string
}

/** 字段 → 页面锚点 id（跳步被拦截时滚动到第一个错误字段） */
export const FIELD_ANCHORS: Record<string, string> = {
  keyword: 'wizard-field-keyword',
  min_price: 'wizard-field-price',
  max_publish_days: 'wizard-field-max-publish-days',
  eval_threshold: 'wizard-field-eval-threshold',
  ai_prompt: 'wizard-field-ai-prompt',
  cron: 'wizard-field-cron',
  interval_seconds: 'wizard-field-interval',
}

export const KEYWORD_MAX_LENGTH = 80
export const AI_PROMPT_MAX_LENGTH = 500
export const INTERVAL_MIN = 30
export const INTERVAL_MAX = 3600

const err = (step: number, field: string, message: string): StepError => ({ step, field, message })

/** 校验单步，返回该步全部错误（空数组表示通过） */
export function validateStep(step: number, v: WizardValues): StepError[] {
  switch (step) {
    case 0: {
      const keyword = v.keyword.trim()
      if (!keyword) return [err(0, 'keyword', '请输入关键词')]
      if (keyword.length > KEYWORD_MAX_LENGTH) {
        return [err(0, 'keyword', `关键词最多 ${KEYWORD_MAX_LENGTH} 个字符`)]
      }
      return []
    }
    case 1: {
      const errors: StepError[] = []
      if (v.min_price != null && v.max_price != null && v.min_price > v.max_price) {
        errors.push(err(1, 'min_price', '最低价不能高于最高价'))
      }
      if (v.max_publish_days != null && (v.max_publish_days < 1 || v.max_publish_days > 30)) {
        errors.push(err(1, 'max_publish_days', '发布天数需在 1–30 天之间'))
      }
      return errors
    }
    case 3: {
      const errors: StepError[] = []
      if (v.eval_threshold != null && (v.eval_threshold < 0 || v.eval_threshold > 100)) {
        errors.push(err(3, 'eval_threshold', '评估阈值需在 0–100 之间'))
      }
      if ((v.ai_prompt ?? '').length > AI_PROMPT_MAX_LENGTH) {
        errors.push(err(3, 'ai_prompt', `提示词最多 ${AI_PROMPT_MAX_LENGTH} 个字符`))
      }
      return errors
    }
    case 5: {
      if (v.useCron) {
        const cron = v.cron.trim()
        if (!cron || cron.split(/\s+/).length !== 5) {
          return [err(5, 'cron', 'Cron 表达式需为 5 段（分 时 日 月 周）')]
        }
        return []
      }
      if (v.intervalSeconds < INTERVAL_MIN || v.intervalSeconds > INTERVAL_MAX) {
        return [err(5, 'interval_seconds', `执行间隔需在 ${INTERVAL_MIN}–${INTERVAL_MAX} 秒之间`)]
      }
      return []
    }
    default:
      return []
  }
}

/** 校验 [fromInclusive, toExclusive) 区间内的所有步（跳步/提交用） */
export function validateStepsBetween(
  fromInclusive: number,
  toExclusive: number,
  v: WizardValues,
): StepError[] {
  const errors: StepError[] = []
  for (let step = fromInclusive; step < toExclusive; step += 1) {
    errors.push(...validateStep(step, v))
  }
  return errors
}
