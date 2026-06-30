import client from './client'
import type { ErrorLog } from './types'

export const errorLogApi = {
  list: (params?: {
    status?: string
    error_type?: string
    request_path?: string
    start?: string
    end?: string
    limit?: number
    offset?: number
  }) =>
    client
      .get<{ items: ErrorLog[]; count: number; status_counts: Record<string, number> }>(
        '/api/error-logs',
        { params },
      )
      .then((r) => r.data),

  get: (id: number) =>
    client.get<ErrorLog>(`/api/error-logs/${id}`).then((r) => r.data),

  getAiContext: (id: number, format: 'json' | 'markdown') =>
    client
      .get<string>(`/api/error-logs/${id}/ai-context`, {
        params: { format },
        responseType: 'text',
        transformResponse: [(data) => data],
      })
      .then((r) => r.data as string),

  updateStatus: (id: number, status: string) =>
    client
      .patch<{ status: string }>(`/api/error-logs/${id}/status`, null, { params: { status } })
      .then((r) => r.data),

  delete: (id: number) =>
    client.delete<{ status: string }>(`/api/error-logs/${id}`).then((r) => r.data),

  batch: (ids: number[], action: 'delete' | 'resolve' | 'ignore' | 'new') =>
    client
      .post<{ affected: number; status: string }>('/api/error-logs/batch', { ids, action })
      .then((r) => r.data),

  cleanup: (days: number = 30) =>
    client
      .post<{ deleted: number; status: string }>('/api/error-logs/cleanup', null, {
        params: { days },
      })
      .then((r) => r.data),
}
