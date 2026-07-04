import client from './client'

// 偏好值类型：允许任意 JSON 可序列化值
// 为什么用 unknown 而非 any：保留类型安全，调用方需显式断言或类型守卫
export type PreferenceValue = string | number | boolean | null | object | unknown[]

// 偏好映射：key → value
// 后端 user_preferences 表的 pref_value 是 JSON 字符串，前端直接读写对象
export type PreferenceMap = Record<string, PreferenceValue>

// 用户偏好 API：管理用户级偏好配置（列配置、分页大小、视图模式等）
// 与后端 api_preferences.py 契约对齐：GET/PUT /api/preferences
// user_id 由中间件从 session_token 注入，前端无需传递
export const preferencesApi = {
  // 获取当前用户全部偏好
  getAll: () =>
    client.get<PreferenceMap>('/api/preferences').then((r) => r.data),

  // 批量更新偏好（合并写入，不删除其他字段）
  update: (prefs: PreferenceMap) =>
    client.put<{ ok: boolean }>('/api/preferences', prefs).then((r) => r.data),

  // 获取单个偏好字段
  get: (key: string) =>
    client.get<{ value: PreferenceValue }>(`/api/preferences/${encodeURIComponent(key)}`).then((r) => r.data.value),

  // 设置单个偏好字段
  set: (key: string, value: PreferenceValue) =>
    client.put<{ ok: boolean }>(`/api/preferences/${encodeURIComponent(key)}`, { value }).then((r) => r.data),

  // 删除单个偏好字段
  remove: (key: string) =>
    client.delete<{ ok: boolean }>(`/api/preferences/${encodeURIComponent(key)}`).then((r) => r.data),
}
