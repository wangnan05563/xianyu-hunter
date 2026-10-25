import client from './client'
import type { StorageStatus, CleanupResult, CleanupBody, CacheScan } from './types'

// 系统维护 API：查询存储占用并按对象类型执行清理
//
// 超时口径（T02575 / T02738）：client.ts 的默认 timeout 是 30s，而清理真实删除
// 可能涉及大量文件，必须单独放宽。统计类请求不再需要超长等待——浏览器 profile
// 的大目录遍历已改成后台分批推进（CacheScanService），/status 与预览都在秒级
// 返回「统计中」，由 /cache-scan 轮询续跑。只有真实删除仍按长耗时计。
const STATUS_TIMEOUT_MS = 300000
const CLEANUP_TIMEOUT_MS = 900000
// 单次轮询在服务端有 2s 预算上限，客户端给 60s 足以覆盖磁盘争用，又不会挂死界面
const SCAN_POLL_TIMEOUT_MS = 60000

export const maintenanceApi = {
  getStorageStatus: () =>
    client
      .get<StorageStatus>('/api/maintenance/status', { timeout: STATUS_TIMEOUT_MS })
      .then((r) => r.data),

  // 推进并读取浏览器数据目录的增量统计；服务端按预算走一小片，前端轮询到 done（T02738）
  getCacheScan: () =>
    client
      .get<CacheScan>('/api/maintenance/cache-scan', { timeout: SCAN_POLL_TIMEOUT_MS })
      .then((r) => r.data),

  // target 区分三类清理对象：缓存 / 数据库 / 日志
  cleanup: (target: 'cache' | 'database' | 'logs', body: CleanupBody) =>
    client
      .post<CleanupResult>(`/api/maintenance/${target}`, body, { timeout: CLEANUP_TIMEOUT_MS })
      .then((r) => r.data),
}
