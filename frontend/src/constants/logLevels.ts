// 日志级别归一化与配色（单点口径）
//
// 为什么要归一：后端 events.level 存小写缩写，实测库里就有 info / err / warning 三种字面值；
// 而前端筛选下拉与展示用全称大写。直接 `level.toUpperCase()` 后 `err` 变成 `ERR`，
// 既不在颜色表键内（级别 Tag 恒灰），也不在分布桶内（有错误日志时 ERROR 恒显示 0）。
// 所有取色与计数一律走本文件的 normalizeLevel / levelColor / countLevels，不要再直接索引颜色表。

/** 规范级别 → Tag 配色 */
export const LEVEL_COLOR: Record<string, string> = {
  ERROR: 'red',
  WARNING: 'orange',
  INFO: 'blue',
  DEBUG: 'default',
  TRACE: 'default',
}

/** 后端/历史写入的各种写法 → 规范大写键 */
const LEVEL_ALIASES: Record<string, string> = {
  ERR: 'ERROR',
  ERROR: 'ERROR',
  WARN: 'WARNING',
  WARNING: 'WARNING',
  INFO: 'INFO',
  DEBUG: 'DEBUG',
  TRACE: 'TRACE',
}

/** 原始级别字面值 → 规范大写键；未知字面值原样大写返回（配色自然回退 default） */
export function normalizeLevel(raw?: string | null): string {
  const upper = (raw ?? '').trim().toUpperCase()
  return LEVEL_ALIASES[upper] ?? upper
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
