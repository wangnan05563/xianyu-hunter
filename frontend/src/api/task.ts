import client from './client'
import type { Task, TaskCreateBody, TaskRun, TaskDep, TaskLink, FieldMap } from './types'

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
  stage: 'checking_cache' | 'checking_cookies' | 'acquiring_lock' | 'searching' | 'refreshing_token' | 'searching_retry' | 'filtering' | 'writing_db' | 'done' | 'error'
  detail?: string
  status?: number
  count?: number
  // done 阶段携带的完整结果
  ok?: boolean
  items?: TaskLink[]
  sellers?: TaskLink[]
  session_expired?: boolean
  field_map?: FieldMap
}

// 任务关联（商品列表）API：管理任务下挂载的商品/卖家链接
export const taskLinkApi = {
  list: (
    taskId: string,
    params: { type?: string; limit?: number; offset?: number; keyword?: string; region?: string },
  ) =>
    client
      .get<{ items: TaskLink[]; total: number; total_for_type: number }>(`/api/tasks/${taskId}/links`, { params })
      .then((r) => r.data),

  count: (taskId: string) =>
    client.get<{ item: number; seller: number; total: number }>(`/api/tasks/${taskId}/links/count`).then((r) => r.data),

  // SSE 流式实时搜索：通过 fetch + ReadableStream 接收进度事件
  // onProgress 回调接收每个阶段的进度（checking_cache / searching / writing_db / done / error）
  // 返回最终 done 阶段的完整数据（与旧接口格式兼容）
  live: (
    taskId: string,
    onProgress?: (data: LiveProgress) => void,
  ): Promise<{ items: TaskLink[]; session_expired?: boolean; field_map?: FieldMap }> => {
    const token = localStorage.getItem('xh_token')
    return fetch(`/api/tasks/${taskId}/links/live`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    }).then(async (response) => {
      // 前置检查失败（HTTP 错误码），按 axios 兼容格式抛出
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: response.statusText }))
        throw { response: { status: response.status, data: errorData } }
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
          const line = evt.trim()
          if (!line.startsWith('data: ')) continue
          try {
            const data = JSON.parse(line.slice(6)) as LiveProgress
            if (data.stage === 'done') {
              finalData = data
            } else if (data.stage === 'error') {
              // SSE 错误事件：按 axios 兼容格式抛出，触发 401 拦截器
              throw { response: { status: data.status || 502, data: { detail: data.detail } } }
            }
            onProgress?.(data)
          } catch (e) {
            // 传播已构造的 axios 兼容错误
            if (e && typeof e === 'object' && 'response' in e) throw e
          }
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
