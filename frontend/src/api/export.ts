// 数据导出 API 客户端
// 对应后端 /api/export 端点，支持 items/evaluations/orders/events 4 个数据集
//
// 设计要点（FR-C-2 导出失败态可见）：
// - 下载走 axios blob + 隐藏 <a download>，不再用 location.href 直跳：
//   直跳时 HTTP 4xx/5xx 会整页跳走且错误不可见，用户只看到「页面没了」
// - 后端在 X-Export-Rows 回带行数，前端据此区分「0 行」与「有数据」
import client from './client'
import { filenameFromHeaders, readExportError, rowsFromHeaders, triggerBlobDownload } from '../utils/exportFeedback'

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

export interface ExportResult {
  /** 后端 X-Export-Rows 回带的行数；老后端未回带时为 null（此时不宣称具体行数） */
  rows: number | null
  filename: string
}

/** 后端没回带文件名时按同一命名规则兜底 */
function defaultFilename(dataset: ExportDataset): string {
  const ts = new Date().toISOString().slice(0, 19).replaceAll(/[-:]/g, '').replace('T', '-')
  return `xh-${dataset}-${ts}.csv`
}

export const exportApi = {
  /** 列出可导出的数据集及列定义 */
  listDatasets: (): Promise<{ datasets: ExportDatasetInfo[] }> =>
    client.get('/api/export').then((r) => r.data),

  /**
   * 下载数据集为 CSV：axios 取 blob → 隐藏 <a download> 触发保存。
   * 失败时抛出可读错误（HTTP 状态/后端 detail/网络不可达），页面不跳走。
   */
  downloadFile: async (dataset: ExportDataset, params: ExportParams = {}): Promise<ExportResult> => {
    let resp
    try {
      resp = await client.get<Blob>(`/api/export/${dataset}`, {
        params,
        responseType: 'blob',
        // 导出可能几万行，30s 默认超时偏短
        timeout: 120000,
      })
    } catch (err) {
      throw await readExportError(err, dataset)
    }
    const rows = rowsFromHeaders(resp.headers)
    const filename = filenameFromHeaders(resp.headers, defaultFilename(dataset))
    triggerBlobDownload(resp.data, filename)
    return { rows, filename }
  },
}
