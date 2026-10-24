/**
 * 任务「沉默」判定（T02652）：按最近一次采集命中时间，而不是 updated_at。
 *
 * 背景：编辑任务也会刷新 updated_at，原实现因此把「长期零命中、刚被编辑过」的任务
 * 显示成「活跃」，语义正好反了。
 *
 * 数据口径：
 * - 后端 `/api/tasks` 的每项已带 `last_seen_at`（list_tasks_with_last_seen 用
 *   max(items.last_seen) 聚合，即该任务最近一次真正抓到商品的时间）；
 * - 没有命中记录时退回 `created_at`：新建但还没跑过的任务不该被判「沉默」；
 * - 无持久化的「最近执行时间」列，事件表的时间窗查询不适合塞进列表请求，
 *   故不为此单新增 schema。
 */

const DAY_MS = 24 * 60 * 60 * 1000

export type TaskSilenceLevel = 'active' | 'silent7' | 'silent30' | 'unknown'

export type TaskSilence = {
  readonly level: TaskSilenceLevel
  /** 距基准时间的天数；基准时间不可解析时为 null */
  readonly days: number | null
  /** 判定依据：命中记录 / 创建时间 / 不可用 */
  readonly basis: 'hit' | 'created' | 'unknown'
}

/**
 * 后端 SQLite 里存的是 UTC naive datetime，FastAPI 序列化后通常不带时区后缀；
 * JS 会把这种串按本地时间解析，东八区会整体偏移 8 小时，卡在 7d/30d 边界上会误判。
 * 这里对「没有显式时区」的时间串补 Z，明确按 UTC 解析。
 */
export function parseBackendTime(raw: string | null | undefined): number {
  if (!raw) return Number.NaN
  const hasZone = /([zZ]|[+-]\d{2}:?\d{2})$/.test(raw)
  return Date.parse(hasZone ? raw : `${raw}Z`)
}

export function taskSilence(
  task: { readonly created_at?: string | null; readonly last_seen_at?: string | null },
  now: number = Date.now(),
): TaskSilence {
  const hit = parseBackendTime(task.last_seen_at)
  const hasHit = Number.isFinite(hit)
  const base = hasHit ? hit : parseBackendTime(task.created_at)
  if (!Number.isFinite(base)) return { level: 'unknown', days: null, basis: 'unknown' }

  // 未来时间（时钟漂移）按 0 天处理，避免出现负数天
  const days = Math.max(0, (now - base) / DAY_MS)
  const level: TaskSilenceLevel = days > 30 ? 'silent30' : days > 7 ? 'silent7' : 'active'
  return { level, days, basis: hasHit ? 'hit' : 'created' }
}
