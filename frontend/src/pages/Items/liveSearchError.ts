/**
 * 实时搜索错误分类（T02660）
 *
 * 后端新版返回结构化 code（cookie_expired / browser_unavailable 等），
 * 旧版只有中文 detail。这里优先按 code 分支，code 缺失时保留原有中文子串
 * 匹配作为升级窗口期的兼容回落，避免旧后端行为回退。
 */

export type LiveSearchErrorKind =
  | 'session_expired'
  | 'browser_unavailable'
  | 'browser_lock'
  | 'timeout'
  | 'unknown'

export interface LiveSearchErrorInfo {
  kind: LiveSearchErrorKind
  detail: string
  code?: string
}

// 登录态类错误码：需要「重新登录」入口（含登录态 Cookie 同步失败）
const SESSION_EXPIRED_CODES = new Set([
  'cookie_expired',
  'cookie_stale',
  'cookie_missing',
  'cookie_sync_failed',
])

// 浏览器/调度器类错误码：只需提示，不引导重新登录
const BROWSER_UNAVAILABLE_CODES = new Set(['browser_unavailable', 'scheduler_off'])

// 旧后端的中文 detail 标识（仅兼容回落使用，新后端不再依赖）
const SESSION_EXPIRED_MARKERS = ['已过期', '不完整', '未刷新到实时搜索浏览器', '重新登录']

const readErrorBody = (err: unknown): { detail?: unknown; code?: unknown } => {
  const data = (err as { response?: { data?: unknown } })?.response?.data
  return typeof data === 'object' && data !== null ? (data as { detail?: unknown; code?: unknown }) : {}
}

const readDetail = (err: unknown, detail: unknown): string =>
  typeof detail === 'string' && detail ? detail : String(err)

export function classifyLiveSearchError(err: unknown): LiveSearchErrorInfo {
  const { detail: rawDetail, code: rawCode } = readErrorBody(err)
  const detail = readDetail(err, rawDetail)
  const code = typeof rawCode === 'string' && rawCode ? rawCode : undefined
  const status = (err as { response?: { status?: number } })?.response?.status
  const axiosCode = (err as { code?: string })?.code

  if (code && SESSION_EXPIRED_CODES.has(code)) return { kind: 'session_expired', detail, code }
  if (code && BROWSER_UNAVAILABLE_CODES.has(code)) return { kind: 'browser_unavailable', detail, code }
  // 未识别的 code 仍走旧口径，避免后端新增码后前端静默丢掉提示
  if (status === 440 || status === 403 || SESSION_EXPIRED_MARKERS.some((m) => detail.includes(m))) {
    return { kind: 'session_expired', detail, code }
  }
  if (status === 503 || detail.includes('浏览器不可用')) return { kind: 'browser_unavailable', detail, code }
  if (detail.includes('系统正在执行后台搜索任务')) return { kind: 'browser_lock', detail, code }
  if (axiosCode === 'ECONNABORTED' || detail.includes('timeout')) return { kind: 'timeout', detail, code }
  return { kind: 'unknown', detail, code }
}
