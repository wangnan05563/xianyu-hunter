import { create } from 'zustand'
import { paramCalculatorApi } from '../api'
import type { RuleMeta, Suggestion, ValidationReport } from '../api'

// 参数计算器全局 Store
//
// 设计说明：
// - 独立于 configStore：校验结果是配置变更的"派生视图"，不应耦合
// - 提供 manual validate 方法供非 Hook 场景使用（如提交前最终校验）
// - Hook 内部维护防抖与实时校验，Store 用于跨页面共享与提交前校验

interface ParamCalculatorState {
  suggestions: Suggestion[]
  hasBlocking: boolean
  lastReport: ValidationReport | null
  rules: RuleMeta[]
  isValidating: boolean
  error: string | null

  // 手动校验任务参数（提交前最终校验，无防抖）
  validateTask: (fields: Record<string, unknown>, scenario?: 'task_create' | 'task_edit') => Promise<ValidationReport>
  // 手动校验系统配置（提交前最终校验，无防抖）
  validateConfig: (fields: Record<string, unknown>) => Promise<ValidationReport>
  // 加载规则列表（用于配置界面展示阈值说明）
  loadRules: () => Promise<void>
  // 重新加载规则（管理员修改 param_rules.yaml 后）
  reload: () => Promise<void>
  // 清空当前建议
  clear: () => void
}

export const useParamCalculatorStore = create<ParamCalculatorState>((set) => ({
  suggestions: [],
  hasBlocking: false,
  lastReport: null,
  rules: [],
  isValidating: false,
  error: null,

  validateTask: async (fields, scenario = 'task_create') => {
    set({ isValidating: true, error: null })
    try {
      const report = await paramCalculatorApi.validateTask(fields, scenario)
      set({
        suggestions: report.suggestions,
        hasBlocking: report.has_blocking,
        lastReport: report,
        isValidating: false,
      })
      return report
    } catch (e) {
      const msg = e instanceof Error ? e.message : '校验失败'
      set({ isValidating: false, error: msg })
      // 返回空报告避免阻断提交：校验服务不可用时不阻塞主流程
      return {
        scenario,
        ok: true,
        has_blocking: false,
        warning_count: 0,
        info_count: 0,
        elapsed_ms: 0,
        suggestions: [],
      }
    }
  },

  validateConfig: async (fields) => {
    set({ isValidating: true, error: null })
    try {
      const report = await paramCalculatorApi.validateConfig(fields)
      set({
        suggestions: report.suggestions,
        hasBlocking: report.has_blocking,
        lastReport: report,
        isValidating: false,
      })
      return report
    } catch (e) {
      const msg = e instanceof Error ? e.message : '校验失败'
      set({ isValidating: false, error: msg })
      return {
        scenario: 'config_update' as const,
        ok: true,
        has_blocking: false,
        warning_count: 0,
        info_count: 0,
        elapsed_ms: 0,
        suggestions: [],
      }
    }
  },

  loadRules: async () => {
    try {
      const { rules } = await paramCalculatorApi.listRules()
      set({ rules })
    } catch {
      // 规则加载失败不阻断：规则列表仅用于文档展示
    }
  },

  reload: async () => {
    try {
      await paramCalculatorApi.reload()
      // 重新加载后刷新规则列表
      const { rules } = await paramCalculatorApi.listRules()
      set({ rules })
    } catch {
      // 重新加载失败不阻断：下次校验仍使用旧规则
    }
  },

  clear: () => {
    set({
      suggestions: [],
      hasBlocking: false,
      lastReport: null,
      error: null,
    })
  },
}))
