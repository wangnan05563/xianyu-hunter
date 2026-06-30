/**
 * 从 axios 错误中提取后端返回的可读错误信息
 *
 * 后端错误响应格式（由 exception_handler.py 统一）：
 * - 400 校验失败：{ detail: { message, errors } }
 * - 401 未授权：{ detail: "Unauthorized" }
 * - 500 内部错误：{ detail: "内部服务器错误" }
 *
 * 不在每个页面重复解析逻辑，统一在此提取人类可读信息。
 */
export function extractApiError(e: unknown): string {
  if (typeof e === 'object' && e !== null) {
    const resp = (e as { response?: { data?: unknown; status?: number } }).response
    if (resp) {
      const detail = (resp.data as Record<string, unknown>)?.detail
      if (typeof detail === 'string') return detail
      if (typeof detail === 'object' && detail !== null) {
        const msg = (detail as Record<string, unknown>).message
        const errors = (detail as Record<string, unknown>).errors
        if (typeof msg === 'string') {
          if (Array.isArray(errors) && errors.length > 0) {
            return `${msg}：${errors.join('; ')}`
          }
          return msg
        }
      }
      if (resp.status === 401) return '认证已过期，请重新登录'
      if (resp.status === 500) return '服务器内部错误，请稍后重试'
    }
  }
  return e instanceof Error ? e.message : '操作失败'
}
