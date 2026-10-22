import type { ExportResult } from '@/api/export'

/** antd 的 message 实例（静态方法或 App.useApp() 返回的都兼容） */
export interface MessageLike {
  success: (content: string) => unknown
  warning: (content: string) => unknown
  error: (content: string) => unknown
}

type ExportHeaders =
  | { 'content-disposition'?: string; 'x-export-rows'?: string | number; [k: string]: unknown }
  | undefined

/** 从 Content-Disposition 取文件名，取不到时用调用方兜底名 */
export function filenameFromHeaders(headers: ExportHeaders, fallback: string): string {
  const m = /filename="?([^";]+)"?/.exec(String(headers?.['content-disposition'] ?? ''))
  return m?.[1] ?? fallback
}

/** 从 X-Export-Rows 取真实导出行数；缺失或非法时返回 null，不猜数字 */
export function rowsFromHeaders(headers: ExportHeaders): number | null {
  const raw = headers?.['x-export-rows']
  if (raw == null || raw === '') return null
  const n = Number(raw)
  return Number.isFinite(n) && n >= 0 ? n : null
}

/**
 * 把 axios 导出错误翻成人话（T02587 / T02707）。
 * responseType:'blob' 时后端错误体也是 Blob，必须异步读出才能拿到 detail，
 * 否则用户只会看到「Request failed with status code 500」。
 */
export async function readExportError(err: unknown, subject: string): Promise<Error> {
  const e = err as { response?: { status?: number; data?: unknown }; message?: string }
  const status = e?.response?.status
  if (!status) return new Error(`导出失败（${subject}）：网络不可达或服务未响应`)
  const data = e.response?.data
  if (typeof Blob !== 'undefined' && data instanceof Blob) {
    try {
      const parsed = JSON.parse(await data.text()) as { detail?: unknown }
      if (typeof parsed.detail === 'string' && parsed.detail) {
        return new Error(`导出失败（${subject}）：${parsed.detail}`)
      }
    } catch { /* 错误体不是 JSON，落到状态码提示 */ }
  }
  if (status === 401 || status === 403) {
    return new Error(`导出失败（${subject}）：登录态已失效或无权限，请重新登录`)
  }
  return new Error(`导出失败（${subject}）：服务端返回 ${status}`)
}

/**
 * blob 触发浏览器下载。
 * 必须延时 revoke：同步（或下一帧）释放会让部分浏览器在下载真正开始前拿到空文件（T02707）。
 */
export function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  try {
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.style.display = 'none'
    document.body.appendChild(a)
    a.click()
    a.remove()
  } finally {
    setTimeout(() => URL.revokeObjectURL(url), 10000)
  }
}

/**
 * 导出结果的统一口径提示（T02587 / FR-C-2）。
 *
 * 为什么必须区分 0 行：三处导出入口原先一律 `message.success('正在导出…')`，
 * 筛选条件写错导致 0 行时同样弹「正在导出」，用户以为拿到了数据。
 */
export function notifyExportResult(
  msg: MessageLike,
  res: ExportResult,
  title: string,
): void {
  if (res.rows === 0) {
    msg.warning(`${title}：筛选结果为 0 行，文件 ${res.filename} 只有表头`)
    return
  }
  if (res.rows == null) {
    // 老后端没回带行数：只说已保存，不谎报具体条数
    msg.success(`${title}已保存为 ${res.filename}`)
    return
  }
  msg.success(`${title}已导出 ${res.rows} 行，保存为 ${res.filename}`)
}
