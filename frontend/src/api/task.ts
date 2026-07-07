import client from './client'
import type { Task, TaskCreateBody, TaskRun, TaskDep, TaskLink, FieldMap, TaskPrecheckResult } from './types'

// 任务 API：负责任务的 CRUD 与运行控制
// start/pause/resume/stop 统一委托 control 端点，避免后端多次实现相似逻辑
export const taskApi = {
  list: (params?: { status?: string; limit?: number; offset?: number }) =>
    client.get<{ items: Task[]; count: number; total: number; limit: number; offset: number }>(
      '/api/tasks',
      { params },
    ).then((r) => r.data),

  get: (id: string) => client.get<Task>(`/api/tasks/${id}`).then((r) => r.data),

  create: (body: TaskCreateBody) => client.post('/api/tasks', body).then((r) => r.data),

  update: (id: string, body: Partial<TaskCreateBody>) =>
    client.patch(`/api/tasks/${id}`, body).then((r) => r.data),

  delete: (id: string) => client.delete(`/api/tasks/${id}`).then((r) => r.data),

  // 后端统一控制端点：action=pause|resume|stop|restart
  control: (id: string, action: 'pause' | 'resume' | 'stop' | 'restart') =>
    client.post(`/api/tasks/${id}/control`, null, { params: { action } }).then((r) => r.data),

  // 恢复前置校验：前端"启动/恢复"按钮点击前调用，判断 root_cause 是否消除
  // 返回 resume_blocked=true 时前端必须弹 Modal 阻断，避免"恢复→失效→暂停"无效循环
  precheck: (id: string) =>
    client.get<TaskPrecheckResult>(`/api/tasks/${id}/precheck`).then((r) => r.data),

  start: (id: string) => taskApi.control(id, 'restart'),
  pause: (id: string) => taskApi.control(id, 'pause'),
  resume: (id: string) => taskApi.control(id, 'resume'),
  stop: (id: string) => taskApi.control(id, 'stop'),

  // 批量操作：对多个任务同时执行 pause/resume/stop/restart/delete
  batchControl: (taskIds: string[], action: 'pause' | 'resume' | 'stop' | 'restart' | 'delete') =>
    client.post('/api/tasks/batch-control', { task_ids: taskIds, action }).then((r) => r.data),
}

// Cron 校验 API：独立于任务 CRUD，专用于表达式校验与下次触发预览
export const cronApi = {
  validate: (cron: string) =>
    client.post<{ valid: boolean; cron: string; next_runs: string[]; error?: string }>(
      '/api/cron/validate',
      { cron },
    ).then((r) => r.data),
}

// 任务详情扩展 API：提供运行历史与依赖关系查询，与基础 CRUD 解耦
export const taskDetailApi = {
  runs: (taskId: string, rangeHours = 24) =>
    client
      .get<{ runs: TaskRun[]; idle_gaps: Array<{ from: string; to: string; duration_s: number }> }>(
        `/api/tasks/${taskId}/runs`,
        { params: { range_hours: rangeHours } },
      )
      .then((r) => r.data),

  deps: (taskId: string) =>
    client.get<{ task_id: string; deps: TaskDep[] }>(`/api/tasks/${taskId}/deps`).then((r) => r.data.deps),

  dependents: (taskId: string) =>
    client.get<{ task_id: string; dependents: TaskDep[] }>(`/api/tasks/${taskId}/dependents`).then((r) => r.data.dependents),

  addDep: (taskId: string, dependsOn: string) =>
    client.post(`/api/tasks/${taskId}/deps`, { depends_on: dependsOn }).then((r) => r.data),

  removeDep: (taskId: string, dependsOn: string) =>
    client.delete(`/api/tasks/${taskId}/deps`, { data: { depends_on: dependsOn } }).then((r) => r.data),
}

// SSE 实时搜索进度事件类型
export interface LiveProgress {
  // waiting_inflight: 已有搜索在进行中，等待复用结果（避免并发竞争 browser_lock）
  // waiting_lock: 后台 Worker 正在执行搜索任务，实时查询等待浏览器锁（每 1.5s 推一次）
  stage: 'checking_cache' | 'checking_cookies' | 'waiting_inflight' | 'acquiring_lock' | 'waiting_lock' | 'searching' | 'refreshing_token' | 'searching_retry' | 'filtering' | 'writing_db' | 'done' | 'error'
  detail?: string
  status?: number
  count?: number
  // waiting_lock 阶段携带已等待秒数，前端用于拼接文案
  elapsed_sec?: number
  // done 阶段携带的完整结果
  ok?: boolean
  items?: TaskLink[]
  sellers?: TaskLink[]
  session_expired?: boolean
  field_map?: FieldMap
  // done 阶段携带的过滤汇总信息
  // 为什么需要：final_total=0 时让用户看到 raw/keyword_skipped/price_skipped 的分布，
  // 从而判断是搜索不到内容还是被过滤条件筛掉，并提供"显示被过滤结果"入口
  filter_summary?: LiveFilterSummary
}

// 实时搜索过滤汇总：后端返回的 raw_results → 过滤后 final_total 链路统计
export interface LiveFilterSummary {
  raw: number
  formatted: number
  keyword_skipped: number
  price_skipped: number
  publish_days_skipped: number
  final_total: number
  final_items: number
  final_sellers: number
  // 被过滤的商品列表（限制 50 条，避免响应过大）
  filtered_out: LiveFilteredItem[]
}

// 被过滤的单条商品记录，供前端 Modal 展示
export interface LiveFilteredItem {
  link_type: string
  link_key: string
  display?: Partial<TaskLink['display']> & Record<string, any>
  filter_reason: 'keyword' | 'price' | 'publish_days'
  filter_detail: string
}

// 构造 axios 兼容错误对象：让上层 catch 能识别 HTTP 状态码与响应体
// 为什么需要：fetch 抛出的原生 Error 没有 response 字段，401 拦截器等需要 .response.status
const makeHttpError = (status: number, data: unknown): Error & { response: { status: number; data: unknown } } =>
  Object.assign(new Error(`HTTP ${status}`), { response: { status, data } })

// 解析单条 SSE 事件文本为 LiveProgress 对象
// 为什么独立：JSON.parse 失败时返回 null 让调用方统一处理，避免主循环嵌套 try/catch
const parseSSEEvent = (line: string): LiveProgress | null => {
  const trimmed = line.trim()
  if (!trimmed.startsWith('data: ')) return null
  try {
    return JSON.parse(trimmed.slice(6)) as LiveProgress
  } catch {
    return null
  }
}

// 分发单条 SSE 事件：done 写入 finalData、error 抛出兼容错误、其他仅回调 onProgress
// 返回 { finalData, shouldThrow }，调用方按返回值推进状态机，保持原有 throw 语义
// 为什么返回值而非直接 throw：把分发逻辑提纯后主循环不再需要 try/catch，降低认知复杂度
const dispatchSSEEvent = (
  data: LiveProgress,
  onProgress?: (data: LiveProgress) => void,
): { finalData: LiveProgress | null; shouldThrow: Error & { response: unknown } | null } => {
  // done 阶段：先记录终态数据，再回调 onProgress（保持与原 if/else 后统一 onProgress 的顺序）
  if (data.stage === 'done') {
    onProgress?.(data)
    return { finalData: data, shouldThrow: null }
  }
  // error 阶段：构造兼容错误抛出，不回调 onProgress（原实现用 throw 跳过 onProgress）
  if (data.stage === 'error') {
    return {
      finalData: null,
      shouldThrow: makeHttpError(data.status || 502, { detail: data.detail }),
    }
  }
  // 其他阶段：仅回调 onProgress 推送进度
  onProgress?.(data)
  return { finalData: null, shouldThrow: null }
}

// 任务关联（商品列表）API：管理任务下挂载的商品/卖家链接
export const taskLinkApi = {
  list: (
    taskId: string,
    params: { type?: string; limit?: number; offset?: number; keyword?: string; region?: string; brand?: string; sold_filter?: 'all' | 'onsale' | 'sold' },
  ) =>
    client
      .get<{ items: TaskLink[]; total: number; total_for_type: number }>(`/api/tasks/${taskId}/links`, { params })
      .then((r) => r.data),

  count: (taskId: string) =>
    client.get<{ item: number; seller: number; total: number }>(`/api/tasks/${taskId}/links/count`).then((r) => r.data),

  // SSE 流式实时搜索：通过 fetch + ReadableStream 接收进度事件
  // onProgress 回调接收每个阶段的进度（checking_cache / searching / writing_db / done / error）
  // 返回最终 done 阶段的完整数据（与旧接口格式兼容）
  // 为什么包含 filter_summary：done 阶段后端会返回过滤统计，前端用于判断是否被过滤条件筛掉
  live: (
    taskId: string,
    onProgress?: (data: LiveProgress) => void,
  ): Promise<{ items: TaskLink[]; session_expired?: boolean; field_map?: FieldMap; filter_summary?: LiveFilterSummary }> => {
    const token = localStorage.getItem('xh_token')
    return fetch(`/api/tasks/${taskId}/links/live`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    }).then(async (response) => {
      // 前置检查失败（HTTP 错误码），按 axios 兼容格式抛出
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: response.statusText }))
        throw makeHttpError(response.status, errorData)
      }
      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let finalData: any = null
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        // SSE 事件以 \n\n 分隔
        const events = buffer.split('\n\n')
        buffer = events.pop() || ''
        for (const evt of events) {
          // 解析 + 分发拆为纯函数，避免主循环嵌套 try/catch 与多层 if
          const parsed = parseSSEEvent(evt)
          if (!parsed) continue
          const result = dispatchSSEEvent(parsed, onProgress)
          // error 阶段抛出兼容错误，触发 401 拦截器等上层处理
          if (result.shouldThrow) throw result.shouldThrow
          if (result.finalData) finalData = result.finalData
        }
      }
      return finalData
    })
  },

  // 实时搜索并写入 DB，返回写入统计（刷新数据源用）
  refresh: (taskId: string) =>
    client.post<{ ok: boolean; found: number; saved: number; counts: Record<string, number> }>(`/api/tasks/${taskId}/links/refresh`, {}, { timeout: 120000 }).then((r) => r.data),

  remove: (taskId: string, linkId: number) =>
    client.delete(`/api/tasks/${taskId}/links/${linkId}`).then((r) => r.data),

  // 手动添加关联（商品 ID / 卖家 ID）
  create: (taskId: string, body: { link_type: string; link_key: string; note?: string }) =>
    client.post(`/api/tasks/${taskId}/links`, body).then((r) => r.data),
}
