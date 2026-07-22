import client from './client'

// 批量采集调度器 API
// 对应后端 src/xianyu_hunter/web/routes/api_batch_refresh.py

// 变更日志单条记录：商品字段变更详情
export interface BatchRefreshChangeLogEntry {
  item_id: string
  changed_fields: string[]
  timestamp: string
}

// 进度信息（运行中才有，空闲时为 null）
export interface BatchRefreshProgress {
  task_id: number
  current: number
  total: number
  current_item_id: string | null
  started_at: string
  elapsed_ms?: number
}

// GET /api/batch-refresh/status 返回结构
// status: idle=空闲 | running=执行中 | paused=已暂停 | stopping=停止中 | unavailable=调度器未启动
export interface BatchRefreshStatus {
  status: 'idle' | 'running' | 'paused' | 'stopping' | 'unavailable'
  last_run_at: string | null
  last_result: { success: number; failed: number; skipped: number; stopped?: boolean } | null
  change_log: BatchRefreshChangeLogEntry[]
  enabled: boolean
  interval_minutes: number
  // 批次参数：前端配置入口回显当前值
  batch_size: number
  max_items_per_run: number
  history_retention_days: number
  progress: BatchRefreshProgress | null
  control_available: boolean
}

// PATCH /api/batch-refresh/config 请求体（所有字段可选）
export interface BatchRefreshConfigPatch {
  interval_minutes?: number
  enabled?: boolean
  batch_size?: number
  max_items_per_run?: number
  history_retention_days?: number
}

// PATCH /api/batch-refresh/config 返回结构
export interface BatchRefreshConfigResult {
  ok: boolean
  enabled: boolean
  interval_minutes: number
  batch_size: number
  max_items_per_run: number
  history_retention_days: number
}

// POST /api/batch-refresh/trigger 返回结构
export interface BatchRefreshTriggerResult {
  ok: boolean
  task_id: number
}

// POST /api/batch-refresh/pause|resume|stop 返回结构
export interface BatchRefreshControlResult {
  ok: boolean
  status: string
}

// ============== 执行历史相关类型 ==============

// 历史记录状态：与后端 batch_refresh_history.status 对齐
// running=执行中 / completed=正常完成 / cancelled=用户停止 / failed=连续失败熔断
export type BatchRefreshHistoryStatus =
  | 'running'
  | 'completed'
  | 'cancelled'
  | 'failed'

// 触发来源：manual=用户手动 / scheduler=APScheduler 定时
export type BatchRefreshTriggerSource = 'manual' | 'scheduler'

// 单条错误消息（error_messages JSON 数组元素）
export interface BatchRefreshErrorMessage {
  item_id: string
  error: string
  timestamp: string
}

// 历史记录单条结构
export interface BatchRefreshHistoryItem {
  id: number
  task_id: number
  trigger_source: BatchRefreshTriggerSource
  started_at: string
  completed_at: string | null
  total: number
  success: number
  failed: number
  skipped: number
  status: BatchRefreshHistoryStatus
  error_messages: BatchRefreshErrorMessage[]
  consecutive_failures: number
  duration_ms: number | null
  created_at: string
}

// GET /api/batch-refresh/history 查询参数
export interface BatchRefreshHistoryQuery {
  task_id?: number
  status?: BatchRefreshHistoryStatus
  trigger_source?: BatchRefreshTriggerSource
  start?: string  // ISO8601
  end?: string    // ISO8601
  order_by?: 'started_at' | 'task_id' | 'status' | 'duration_ms'
  order_dir?: 'asc' | 'desc'
  limit?: number
  offset?: number
}

// GET /api/batch-refresh/history 返回结构
export interface BatchRefreshHistoryListResult {
  items: BatchRefreshHistoryItem[]
  total: number
  limit: number
  offset: number
  status_counts: Record<string, number>
}

// GET /api/batch-refresh/history/stats 单条聚合
export interface BatchRefreshHistoryStat {
  task_id: number
  run_count: number
  last_run_at: string | null
  total_success: number
  total_failed: number
}

// GET /api/batch-refresh/history/stats 返回结构
export interface BatchRefreshHistoryStatsResult {
  items: BatchRefreshHistoryStat[]
  count: number
}

// DELETE /api/batch-refresh/history 返回结构
export interface BatchRefreshHistoryCleanupResult {
  ok: boolean
  deleted: number
}

export const batchRefreshApi = {
  // 查询当前状态、上次执行结果和最近变更日志
  getStatus: () =>
    client.get<BatchRefreshStatus>('/api/batch-refresh/status').then((r) => r.data),

  // 手动触发一次批量采集，返回任务 ID
  // 调度器未启动返回 503，已有批次在运行返回 409
  trigger: () =>
    client.post<BatchRefreshTriggerResult>('/api/batch-refresh/trigger').then((r) => r.data),

  // 运行时热更新配置：interval_minutes 修改后立即 reschedule
  patchConfig: (body: BatchRefreshConfigPatch) =>
    client.patch<BatchRefreshConfigResult>('/api/batch-refresh/config', body).then((r) => r.data),

  // 暂停当前批次（仅 running 态可暂停，立即返回 <500ms）
  pause: () =>
    client.post<BatchRefreshControlResult>('/api/batch-refresh/pause').then((r) => r.data),

  // 继续执行已暂停的批次（仅 paused 态可继续）
  resume: () =>
    client.post<BatchRefreshControlResult>('/api/batch-refresh/resume').then((r) => r.data),

  // 停止当前批次（running/paused 态可停止，未处理的 items 持久化以便续传）
  stop: () =>
    client.post<BatchRefreshControlResult>('/api/batch-refresh/stop').then((r) => r.data),

  // ============== 执行历史 ==============

  // 分页查询执行历史（支持按 task_id/status/trigger_source/时间范围筛选+排序）
  listHistory: (query: BatchRefreshHistoryQuery = {}) =>
    client
      .get<BatchRefreshHistoryListResult>('/api/batch-refresh/history', { params: query })
      .then((r) => r.data),

  // 按 task_id 聚合统计执行次数（用于检查某 task_id 执行过几次）
  getHistoryStats: () =>
    client
      .get<BatchRefreshHistoryStatsResult>('/api/batch-refresh/history/stats')
      .then((r) => r.data),

  // 查询单条历史详情（含完整错误消息列表）
  getHistoryDetail: (historyId: number) =>
    client
      .get<BatchRefreshHistoryItem>(`/api/batch-refresh/history/${historyId}`)
      .then((r) => r.data),

  // 删除单条历史记录
  deleteHistory: (historyId: number) =>
    client
      .delete<{ ok: boolean }>(`/api/batch-refresh/history/${historyId}`)
      .then((r) => r.data),

  // 按天数清理过期历史（days=0 清空全部）
  cleanupHistory: (days: number) =>
    client
      .delete<BatchRefreshHistoryCleanupResult>('/api/batch-refresh/history', {
        params: { days },
      })
      .then((r) => r.data),
}
