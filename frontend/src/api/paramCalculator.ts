import client from './client'

// 参数计算器 API：负责参数校验请求与规则查询

// ===== 类型定义 =====

export type ParamScenario = 'task_create' | 'task_edit' | 'config_update'

export type Severity = 'error' | 'warning' | 'info'

export type RuleCategory = 'accuracy' | 'stability' | 'efficiency'

export interface Suggestion {
  code: string
  severity: Severity
  category: RuleCategory
  message: string
  fix_hint: string
  affected_fields: string[]
}

export interface ValidationReport {
  scenario: ParamScenario
  ok: boolean
  has_blocking: boolean
  warning_count: number
  info_count: number
  elapsed_ms: number
  suggestions: Suggestion[]
}

export interface RuleMeta {
  code: string
  name: string
  category: RuleCategory
  scenarios: ParamScenario[]
  priority: number
  enabled: boolean
  description: string
}

// ===== API 实现 =====

export const paramCalculatorApi = {
  validateTask: (fields: Record<string, unknown>, scenario: ParamScenario = 'task_create') =>
    client
      .post<ValidationReport>('/api/param-calculator/validate-task', { fields, scenario })
      .then((r) => r.data),

  validateConfig: (fields: Record<string, unknown>) =>
    client
      .post<ValidationReport>('/api/param-calculator/validate-config', { fields })
      .then((r) => r.data),

  listRules: () =>
    client
      .get<{ rules: RuleMeta[] }>('/api/param-calculator/rules')
      .then((r) => r.data),

  reload: () =>
    client
      .post<{ ok: boolean; message: string }>('/api/param-calculator/reload')
      .then((r) => r.data),
}
