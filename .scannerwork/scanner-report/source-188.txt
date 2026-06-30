import client from './client'
import type { StorageStatus, CleanupResult, CleanupBody } from './types'

// 系统维护 API：查询存储占用并按对象类型执行清理
export const maintenanceApi = {
  getStorageStatus: () =>
    client.get<StorageStatus>('/api/maintenance/status').then((r) => r.data),

  // target 区分三类清理对象：缓存 / 数据库 / 日志
  cleanup: (target: 'cache' | 'database' | 'logs', body: CleanupBody) =>
    client.post<CleanupResult>(`/api/maintenance/${target}`, body).then((r) => r.data),
}
