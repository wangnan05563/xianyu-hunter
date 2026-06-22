import client from './client'

// 模板市场类型定义
export interface TaskTemplate {
  id: string
  name: string
  keyword: string
  min_price: number | null
  max_price: number | null
  mode: string
  icon: string
  category: string
  is_preset: boolean
  created_at?: string
}

export interface TemplateCreateBody {
  name: string
  keyword: string
  min_price?: number | null
  max_price?: number | null
  mode?: string
  icon?: string
  category?: string
}

// 模板市场 API：预置模板只读，私有模板可增删
export const templateApi = {
  list: (category?: string) =>
    client.get<{ items: TaskTemplate[]; total: number }>(
      '/api/templates',
      { params: category && category !== '全部' ? { category } : undefined },
    ).then((r) => r.data),

  create: (body: TemplateCreateBody) =>
    client.post<{ ok: boolean; id: string; template: TaskTemplate }>('/api/templates', body).then((r) => r.data),

  delete: (id: string) =>
    client.delete<{ ok: boolean }>(`/api/templates/${id}`).then((r) => r.data),
}
