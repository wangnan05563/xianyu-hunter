import type { ExportResult } from '@/api/export'

/** antd 的 message 实例（静态方法或 App.useApp() 返回的都兼容） */
export interface MessageLike {
  success: (content: string) => unknown
  warning: (content: string) => unknown
  error: (content: string) => unknown
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
