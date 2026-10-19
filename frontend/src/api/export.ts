// 数据导出 API 客户端
// 对应后端 /api/export 端点，支持 items/evaluations/orders/events 4 个数据集
//
// 设计要点（FR-C-2 导出失败态可见）：
// - 下载走 axios blob + 隐藏 <a download>，不再用 location.href 直跳：
//   直跳时 HTTP 4xx/5xx 会整页跳走且错误不可见，用户只看到「页面没了」
// - 后端在 X-Export-Rows 回带行数，前端据此区分「0 行」与「有数据」
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

export interface ExportResult {
  /** 后端 X-Export-Rows 回带的行数；老后端未回带时为 null（此时不宣称具体行数） */
  rows: number | null
  filename: string
}

/** 从 Content-Disposition 取文件名，取不到时按同一命名规则兜底 */
function parseFilename(disposition: string | undefined, dataset: ExportDataset): string {
  const m = /filename="?([^";]+)"?/.exec(disposition ?? '')
  if (m?.[1]) return m[1]
  const ts = new Date().toISOString().slice(0, 19).replace(/[-:]/g, '').replace('T', '-')
  return `xh-${dataset}-${ts}.csv`
}

/**
 * 把 axios 错误翻成人话。
 * responseType: 'blob' 时后端返回的错误体也是 Blob，必须异步读出才能拿到 detail，
 * 否则用户只会看到「Request failed with status code 500」这种无信息量提示。
 */
async function toReadableError(err: unknown, dataset: ExportDataset): Promise<Error> {
  const e = err as { response?: { status?: number; data?: unknown; headers?: Record<string, string> }; message?: string }
  const status = e?.response?.status
  if (!status) return new Error('导出请求失败：网络不可达或服务未响应')
  const data = e.response?.data
  if (data instanceof Blob) {
    try {
      const parsed = JSON.parse(await data.text()) as { detail?: string }
      if (parsed.detail) return new Error(`导出失败（${dataset}）：${parsed.detail}`)
    } catch { /* 错误体不是 JSON，落到状态码提示 */ }
  }
  if (status === 401 || status === 403) return new Error(`导出失败（${dataset}）：登录态已失效或无权限，请重新登录`)
  return new Error(`导出失败（${dataset}）：服务端返回 ${status}`)
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
      throw await toReadableError(err, dataset)
    }
    const rowsHeader = resp.headers?.['x-export-rows']
    const parsedRows = rowsHeader == null ? NaN : Number(rowsHeader)
    const filename = parseFilename(resp.headers?.['content-disposition'], dataset)
    const url = URL.createObjectURL(resp.data)
    try {
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.style.display = 'none'
      document.body.appendChild(a)
      a.click()
      a.remove()
    } finally {
      // 交给浏览器接管下载后再释放，同步 revoke 会让部分浏览器拿到空文件
      setTimeout(() => URL.revokeObjectURL(url), 10000)
    }
    return { rows: Number.isNaN(parsedRows) ? null : parsedRows, filename }
  },
}
