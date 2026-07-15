import client from './client'
import type {
  AIConfig,
  AIUsage,
  AITestConnectionResult,
  AITestEmbeddingResult,
  AIBudgetBody,
  AIParseTaskResult,
  AIConditionResult,
  DeepAnalyzeResult,
  SellerTemplateCheckResult,
} from './types'

// AI 服务 API:管理模型配置、用量预算与条件评估等智能能力
export const aiApi = {
  getConfig: () => client.get<AIConfig>('/api/ai/config').then((r) => r.data),

  putConfig: (config: Partial<AIConfig>) =>
    client.put<AIConfig>('/api/ai/config', config).then((r) => r.data),

  testConnection: () =>
    client.post<AITestConnectionResult>('/api/ai/test-connection').then((r) => r.data),

  // Embedding 连接测试：独立于 LLM 测试，验证向量端点可用性
  // 本地模式首次调用需下载 ~95MB 模型权重，180s 超时覆盖慢网络场景
  testEmbedding: () =>
    client
      .post<AITestEmbeddingResult>('/api/ai/test-embedding', undefined, { timeout: 180000 })
      .then((r) => r.data),

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

  // O-13-26 深度多模态分析：Vision 推理较慢，超时 90s 对齐后端
  // checks 可选：stolen_image / damage / consistency / template
  deepAnalyze: (itemId: string, checks?: string[]) =>
    client
      .post<DeepAnalyzeResult>(
        '/api/ai/deep-analyze',
        { item_id: itemId, checks: checks ?? ['stolen_image', 'damage', 'consistency', 'template'] },
        { timeout: 90000 },
      )
      .then((r) => r.data),

  // O-13-26 卖家文案模板化检测：纯规则，响应快
  sellerTemplateCheck: (sellerId: string, sampleSize?: number) =>
    client
      .post<SellerTemplateCheckResult>(
        '/api/ai/seller-template-check',
        { seller_id: sellerId, sample_size: sampleSize ?? 20 },
        { timeout: 30000 },
      )
      .then((r) => r.data),
}
