// API 统一出口：re-export 所有子模块，保持 `import { xxx } from '../api'` 的历史路径兼容
// 拆分后各业务域独立维护，新增 API 时优先归入对应子模块而非在此处扩展

// 共享类型
export * from './types'

// 业务域 API
export { configApi } from './config'
export { taskApi, cronApi, taskDetailApi, taskLinkApi } from './task'
export type { LiveProgress, LiveFilterSummary, LiveFilteredItem } from './task'
export { statsApi } from './stats'
export { aiApi } from './ai'
export { priceApi } from './price'
export { authApi } from './auth'
export { anticrawlApi } from './anticrawl'
export type {
  StrategyEvaluation,
  InitializeResult,
  SessionStatus,
  FingerprintInfo,
  FreqStats,
  CookieLayersResult,
  HealthReport,
  OperationResult,
} from './anticrawl'
export { maintenanceApi } from './maintenance'
export { dbAdminApi } from './dbAdmin'
export { orderApi } from './order'
export type { OrderListParams } from './order'
export { evalApi } from './evaluation'
export type { OfficialCollectResult, BatchCollectResult } from './evaluation'
export { timelineApi, logApi } from './event'
export { errorLogApi } from './errorLogs'
export { itemApi } from './item'
export { templateApi } from './template'
export type { TaskTemplate, TemplateCreateBody } from './template'
