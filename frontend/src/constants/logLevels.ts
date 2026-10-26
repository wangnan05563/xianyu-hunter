// 日志级别归一化与配色（单点口径）
//
// events.level 自 T02683 起统一为小写全词（info / warning / error / debug / trace），
// 后端启动迁移会把历史 warn / err / 大写行改写干净。前端展示与配色仍用大写键，
// 所以这里只做大小写归一，不再维护缩写别名表。
// 所有取色与计数一律走本文件的 normalizeLevel / levelColor / countLevels，不要再直接索引颜色表。

/** 规范级别 → Tag 配色 */
export const LEVEL_COLOR: Record<string, string> = {
  ERROR: 'red',
  WARNING: 'orange',
  INFO: 'blue',
  DEBUG: 'default',
  TRACE: 'default',
}

/** 规范级别取值（小写全词，与后端 events.level 同源）；筛选项一律引用这里，别写字面值 */
export const LOG_LEVEL = {
  ERROR: 'error',
  WARNING: 'warning',
  INFO: 'info',
  DEBUG: 'debug',
  TRACE: 'trace',
} as const

/** 原始级别字面值 → 规范大写键；未知字面值原样大写返回（配色自然回退 default） */
export function normalizeLevel(raw?: string | null): string {
  return (raw ?? '').trim().toUpperCase()
}

/** 级别 Tag 配色 */
export function levelColor(raw?: string | null): string {
  return LEVEL_COLOR[normalizeLevel(raw)] ?? 'default'
}

/** 级别分布计数：按规范键累加。四个主级别恒先占位（0 也展示，口径与旧版一致），
 *  出现过的其他级别（如 trace）补在尾部，避免静默丢数 */
export function countLevels(items: Array<{ level?: string | null }>): Record<string, number> {
  const dist: Record<string, number> = { ERROR: 0, WARNING: 0, INFO: 0, DEBUG: 0 }
  items.forEach((item) => {
    const level = normalizeLevel(item.level)
    if (!level) return
    dist[level] = (dist[level] ?? 0) + 1
  })
  return dist
}
