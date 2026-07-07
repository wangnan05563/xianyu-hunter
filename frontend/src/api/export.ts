// 数据导出 API 客户端
// 对应后端 /api/export 端点，支持 items/evaluations/orders/events 4 个数据集
//
// 设计要点：
// - 使用 URL 直跳而非 axios 下载：浏览器原生处理 CSV 流式响应更稳定，避免大文件 blob 内存占用
// - 携带 xh_token cookie（同源请求，credentials 默认包含）
import client from './client'

export type ExportDataset = 'items' | 'evaluations' | 'orders' | 'events'

export interface ExportDatasetInfo {
  key: ExportDataset
  columns: string[]
  description: string
}

export interface ExportParams {
  /** 按任务 ID 过滤（items/orders/events 支持） */
  task_id?: string
  /** 起始时间 ISO 格式（如 2026-06-01T00:00:00） */
  start?: string
  /** 截止时间 ISO 格式 */
  end?: string
  /** 订单状态过滤（仅 orders） */
  status?: string
  /** 事件等级过滤（仅 events） */
  level?: string
  /** 最大导出行数（默认 5000，上限 50000） */
  limit?: number
}

export const exportApi = {
  /** 列出可导出的数据集及列定义 */
  listDatasets: (): Promise<{ datasets: ExportDatasetInfo[] }> =>
    client.get('/api/export').then((r) => r.data),

  /**
   * 构造导出 URL（浏览器直跳下载）
   *
   * 为什么用 URL 直跳而非 axios blob 下载：
   * 1. CSV 流式响应由浏览器原生处理，避免大文件 blob 占用 JS 堆内存
   * 2. 自动触发浏览器下载 UI，无需手写 saveAs 逻辑
   * 3. 同源请求会自动携带 xh_token cookie，无需额外 header
   */
  buildUrl: (dataset: ExportDataset, params: ExportParams = {}): string => {
    const search = new URLSearchParams()
    if (params.task_id) search.set('task_id', params.task_id)
    if (params.start) search.set('start', params.start)
    if (params.end) search.set('end', params.end)
    if (params.status) search.set('status', params.status)
    if (params.level) search.set('level', params.level)
    if (params.limit) search.set('limit', String(params.limit))
    const qs = search.toString()
    // S4624：避免嵌套模板字面量，提取为独立变量
    const querySuffix = qs ? `?${qs}` : ''
    return `/api/export/${dataset}${querySuffix}`
  },

  /** 触发浏览器下载（同源直跳，cookie 自动携带） */
  download: (dataset: ExportDataset, params: ExportParams = {}): void => {
    globalThis.location.href = exportApi.buildUrl(dataset, params)
  },
}
