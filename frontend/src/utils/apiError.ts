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

// 从 detail 字段提取可读消息：字符串直返，对象尝试拼接 message + errors
// 为什么单独提取：detail 可能是 string 也可能是 {message, errors}，主函数多层嵌套判断
const extractDetailMessage = (detail: unknown): string | null => {
  if (typeof detail === 'string') return detail
  if (typeof detail === 'object' && detail !== null) {
    const msg = (detail as Record<string, unknown>).message
    const errors = (detail as Record<string, unknown>).errors
    if (typeof msg === 'string') {
      // 校验失败时拼接字段错误，便于定位具体哪个参数不合法
      if (Array.isArray(errors) && errors.length > 0) {
        return `${msg}：${errors.join('; ')}`
      }
      return msg
    }
  }
  return null
}

// HTTP 状态码到用户友好提示的映射，仅处理与用户操作相关的状态
const getStatusMessage = (status: number | undefined): string | null => {
  if (status === 401) return '认证已过期，请重新登录'
  if (status === 500) return '服务器内部错误，请稍后重试'
  return null
}

export function extractApiError(e: unknown, fallback = '操作失败'): string {
  if (typeof e === 'object' && e !== null) {
    const resp = (e as { response?: { data?: unknown; status?: number } }).response
    if (resp) {
      // 优先用后端返回的 detail 文案，其次按状态码兜底
      const detailMsg = extractDetailMessage((resp.data as Record<string, unknown>)?.detail)
      if (detailMsg) return detailMsg
      const statusMsg = getStatusMessage(resp.status)
      if (statusMsg) return statusMsg
    }
  }
  // 优先用 Error.message，避免丢失原生 JS 错误信息；无 message 时用调用方 fallback
  if (e instanceof Error && e.message) return e.message
  return fallback
}
