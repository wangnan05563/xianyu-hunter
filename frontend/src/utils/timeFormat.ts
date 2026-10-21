// 时间/时长展示的统一口径（T02695）
// 站内原本三套写法并存：告警抽屉渲染裸 ISO（`2026-10-19T05:40:07.728251`）、
// 同一抽屉的超时行渲染裸秒（`超时 4270s`，用户要心算才知道是 71 分钟）、
// 仪表盘告警雷达又折算成「N 分钟前」。同一条订单在两个入口三种长相。
// 格式化交给宿主 Intl（与订单表格列、移动端时间线一致），不引入 dayjs 增大 bundle。

/** ISO 时间 → 本地可读时间；与 pages/Orders 表格列同一口径，空值给「—」而不是 1970 年 */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString('zh-CN')
}

/**
 * 秒数 → 中文时长（最多两级单位，长任务不写「3600 秒」）
 * 用于「超时多久 / 已等待多久」这类相对时间，绝对时间请用 formatDateTime
 */
export function formatDuration(sec: number | null | undefined): string {
  if (sec === null || sec === undefined || !Number.isFinite(sec) || sec < 0) return '—'
  const total = Math.floor(sec)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  if (h > 0) return m > 0 ? `${h} 小时 ${m} 分` : `${h} 小时`
  if (m > 0) return s > 0 ? `${m} 分 ${s} 秒` : `${m} 分`
  return s > 0 ? `${s} 秒` : '不足 1 秒'
}
