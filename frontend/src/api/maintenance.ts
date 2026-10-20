import client from './client'
import type { StorageStatus, CleanupResult, CleanupBody } from './types'

// 系统维护 API：查询存储占用并按对象类型执行清理
//
// 超时口径必须单独放宽（T02575）：client.ts 的默认 timeout 是 30s，而缓存统计/预览
// 要真实遍历浏览器 profile 与源码目录（本机实测 2073 个文件 / 426 MB 的 profile
// 在磁盘争用下单次请求跑到 449s）。沿用默认值会让「预览」几乎必然在前端被 abort，
// 用户看到的是请求失败，而后台其实还在扫描——比不给预览更糟。
// 正解是把大目录扫描移出请求路径（进度/增量统计），已按 T02575 派生单跟进；
// 这里先把超时对齐真实耗时，保证功能可用。
const STATUS_TIMEOUT_MS = 300000
const CLEANUP_TIMEOUT_MS = 900000

export const maintenanceApi = {
  getStorageStatus: () =>
    client
      .get<StorageStatus>('/api/maintenance/status', { timeout: STATUS_TIMEOUT_MS })
      .then((r) => r.data),

  // target 区分三类清理对象：缓存 / 数据库 / 日志
  cleanup: (target: 'cache' | 'database' | 'logs', body: CleanupBody) =>
    client
      .post<CleanupResult>(`/api/maintenance/${target}`, body, { timeout: CLEANUP_TIMEOUT_MS })
      .then((r) => r.data),
}
