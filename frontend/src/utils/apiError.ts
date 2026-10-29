/**
 * 从 axios 错误中提取后端返回的可读错误信息
 *
 * 后端错误响应格式（由 exception_handler.py 统一）：
 * - 400 校验失败：{ detail: { message, errors } }
 * - 401 未授权：{ detail: "Unauthorized" }
 * - 403 AI 总开关关闭：{ detail: "AI 功能已关闭…", code: "ai_disabled" }（CodedHTTPException）
 * - 500 内部错误：{ detail: "内部服务器错误" }
 *
 * 不在每个页面重复解析逻辑，统一在此提取人类可读信息；
 * 「这是不是 AI 开关被关闭」的判定也只在 isAiDisabledError 这一处。
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

/** AI 总开关关闭的机器码，与后端 api_ai.py::AI_DISABLED_CODE 同源 */
export const AI_DISABLED_CODE = 'ai_disabled'

// 兼容旧后端（未带 code 的版本）：按 detail 前缀识别。文案一旦改此标记即失效，故仅作兜底
const AI_DISABLED_DETAIL_MARKER = 'AI 功能已关闭'

/** 后端 detail 缺失时的兜底文案；刻意不给「稍后重试」——重试不会把开关打开 */
export const AI_DISABLED_FALLBACK = 'AI 功能已关闭，请到「配置-AI 服务」页面开启后重试'

/**
 * 是否「AI 总开关已关闭」这一种 403。
 *
 * 为什么集中在这里：各页面原先各自 `status === 403` 就断言 AI 未开启，
 * 把权限类 403 也说成「AI 功能未开启」，且开关关着时根本还会继续发请求。
 * 判定只此一处，页面用它做分支，不再 grep 中文文案。
 */
export function isAiDisabledError(e: unknown): boolean {
  const resp = (e as { response?: { status?: number; data?: unknown } } | undefined)?.response
  if (resp?.status !== 403) return false
  const data = resp.data
  if (typeof data !== 'object' || data === null) return false
  const body = data as Record<string, unknown>
  if (body.code === AI_DISABLED_CODE) return true
  return typeof body.detail === 'string' && body.detail.includes(AI_DISABLED_DETAIL_MARKER)
}

export function extractApiError(e: unknown, fallback = '操作失败'): string {
  if (typeof e === 'object' && e !== null) {
    const resp = (e as { response?: { data?: unknown; status?: number } }).response
    if (resp) {
      // 优先用后端返回的 detail 文案，其次按状态码兜底
      const detailMsg = extractDetailMessage((resp.data as Record<string, unknown>)?.detail)
      if (detailMsg) return detailMsg
      // AI 关闭时后端没给 detail（异常少见），给一句指向开关的诚实文案
      if (isAiDisabledError(e)) return AI_DISABLED_FALLBACK
      const statusMsg = getStatusMessage(resp.status)
      if (statusMsg) return statusMsg
    }
  }
  // 优先用 Error.message，避免丢失原生 JS 错误信息；无 message 时用调用方 fallback
  if (e instanceof Error && e.message) return e.message
  return fallback
}
