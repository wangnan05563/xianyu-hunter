import type { TimelineEntry } from '../../api'

// 解析 payload 为可读信息
// payload 可能是字符串（旧数据）或对象，统一规整为 Record<string, unknown>
export function parsePayload(item: TimelineEntry) {
  let payload = item.payload
  if (typeof payload === 'string') {
    try { payload = JSON.parse(payload) } catch { return null }
  }
  if (typeof payload !== 'object' || payload === null) return null
  return payload as Record<string, unknown>
}

// 格式化相对时间：1 分钟内显示"刚刚"，之后按粒度递增
// 后端返回的 _ts 带 'Z' 后缀（UTC），new Date() 会自动转为本地时间
// 兼容旧数据（无 Z 后缀的空格分隔格式）：replace 后仍能被 Date 解析
export function formatRelativeTime(ts: string): string {
  const d = new Date(ts.replace(' ', 'T'))
  if (Number.isNaN(d.getTime())) return ts.slice(0, 19)
  const now = Date.now()
  const diff = now - d.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
  if (diff < 604800000) return `${Math.floor(diff / 86400000)} 天前`
  return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
