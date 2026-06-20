import client from './client'
import type { Task, TaskCreateBody, TaskRun, TaskDep, TaskLink } from './types'

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
    client.put(`/api/tasks/${id}`, body).then((r) => r.data),

  delete: (id: string) => client.delete(`/api/tasks/${id}`).then((r) => r.data),

  // 后端统一控制端点：action=pause|resume|stop|restart
  control: (id: string, action: 'pause' | 'resume' | 'stop' | 'restart') =>
    client.post(`/api/tasks/${id}/control`, null, { params: { action } }).then((r) => r.data),

  start: (id: string) => taskApi.control(id, 'restart'),
  pause: (id: string) => taskApi.control(id, 'pause'),
  resume: (id: string) => taskApi.control(id, 'restart'),
  stop: (id: string) => taskApi.control(id, 'stop'),
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

  deps: (taskId: string) => client.get<TaskDep[]>(`/api/tasks/${taskId}/deps`).then((r) => r.data),

  dependents: (taskId: string) =>
    client.get<TaskDep[]>(`/api/tasks/${taskId}/dependents`).then((r) => r.data),
}

// 任务关联（商品列表）API：管理任务下挂载的商品/卖家链接
export const taskLinkApi = {
  list: (taskId: string, params: { type?: string; limit?: number; offset?: number }) =>
    client
      .get<{ items: TaskLink[]; total: number; total_for_type: number }>(`/api/tasks/${taskId}/links`, { params })
      .then((r) => r.data),

  count: (taskId: string) =>
    client.get<{ item: number; seller: number; total: number }>(`/api/tasks/${taskId}/links/count`).then((r) => r.data),

  // 长轮询实时拉取，超时放宽到 120s（闲鱼搜索+DOM解析耗时较长）
  live: (taskId: string) =>
    client.get<{ items: TaskLink[]; session_expired?: boolean }>(`/api/tasks/${taskId}/links/live`, { timeout: 120000 }).then((r) => r.data),

  remove: (taskId: string, linkId: number) =>
    client.delete(`/api/tasks/${taskId}/links/${linkId}`).then((r) => r.data),
}
