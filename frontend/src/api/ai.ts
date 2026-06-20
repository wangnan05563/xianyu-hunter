import client from './client'
import type {
  AIConfig,
  AIUsage,
  AITestConnectionResult,
  AIBudgetBody,
  AIParseTaskResult,
  AIConditionResult,
} from './types'

// AI 服务 API：管理模型配置、用量预算与条件评估等智能能力
export const aiApi = {
  getConfig: () => client.get<AIConfig>('/api/ai/config').then((r) => r.data),

  putConfig: (config: Partial<AIConfig>) =>
    client.put('/api/ai/config', config).then((r) => r.data),

  testConnection: () =>
    client.post<AITestConnectionResult>('/api/ai/test-connection').then((r) => r.data),

  getUsage: () => client.get<AIUsage>('/api/ai/usage').then((r) => r.data),

  putBudget: (budget: AIBudgetBody) =>
    client.put('/api/ai/budget', budget).then((r) => r.data),

  parseTask: (text: string) =>
    client.post<AIParseTaskResult>('/api/ai/parse-task', { text }).then((r) => r.data),

  // 条件评估为 LLM 调用，单次耗时较长，超时设为 60s
  evaluateCondition: (itemId: string) =>
    client
      .post<AIConditionResult>('/api/ai/evaluate-condition', { item_id: itemId }, { timeout: 60000 })
      .then((r) => r.data),
}
