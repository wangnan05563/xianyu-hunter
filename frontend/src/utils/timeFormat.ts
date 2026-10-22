// 时间/时长展示的统一口径（T02695）
// 站内原本三套写法并存：告警抽屉渲染裸 ISO（`2026-10-19T05:40:07.728251`）、
// 同一抽屉的超时行渲染裸秒（`超时 4270s`，用户要心算才知道是 71 分钟）、
// 仪表盘告警雷达又折算成「N 分钟前」。同一条订单在两个入口三种长相。
// 格式化交给宿主 Intl（与订单表格列、移动端时间线一致），不引入 dayjs 增大 bundle。

/**
 * ISO 时间 → 本地可读时间；空值与解不出的值都给 null，调用方据此隐藏整行。
 * 移动端有四处各自写过这份「先判空、再判 Invalid Date、否则本地化」的逻辑
 * （Evaluations/Items 的 formatLocalTime、评估明细列的 formatPublishTime），
 * 判空口径一致、只是没处可放，收到这里；要「空值显示占位符」请用 formatDateTime
 */
export function tryFormatDateTime(value: TimeInput | Date): string | null {
  const d = parseTime(value)
  return d === null ? null : d.toLocaleString('zh-CN')
}

/** ISO 时间 → 本地可读时间；与 pages/Orders 表格列同一口径，空值给「—」而不是 1970 年 */
export function formatDateTime(value: TimeInput | Date): string {
  const text = tryFormatDateTime(value)
  if (text) return text
  return isBlank(value) ? '—' : String(value)
}

/**
 * 缩写档位（T02901 第三波 / T02905）：窄展示位（图表轴、时间线行、页签标题）放不下整时间戳，
 * 但缩写同样需要空值与 Invalid Date 护栏——`Intl.DateTimeFormat().format(NaN)` 是直接抛
 * RangeError 的，各处自己写 Intl 时没人兜这一层。
 *
 * 站内原本有五种缩写长相各自实现：
 * `10-19 05:40`（图上）、`05:40`（任务趋势轴）、`2026-10-19 05:40`（页签，手工 pad）、
 * `2026-10-19`（关于页发布日，手工 pad）、以及 `formatDateTime(x).slice(5, 16)`
 * （先落地整时间戳再按字符位切，locale 数据一改就切歪）。这里收到一份预设表，
 * 分隔符与位数交给宿主 Intl，与 formatDateTime 保持同一个 locale 来源。
 */
const SHORT_FORMATS = {
  date: { year: 'numeric', month: '2-digit', day: '2-digit' },
  /** 图表轴上跨天展示：只有月日 */
  'month-day': { month: '2-digit', day: '2-digit' },
  'month-day-time': { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' },
  'date-time': {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  },
  time: { hour: '2-digit', minute: '2-digit' },
} as const

export type ShortTimeScope = keyof typeof SHORT_FORMATS

// 每个档位一个 formatter：Intl.DateTimeFormat 构造成本不低，图表每帧都新建会抖
const shortFormatters = new Map<ShortTimeScope, Intl.DateTimeFormat>()

function shortFormatter(scope: ShortTimeScope): Intl.DateTimeFormat {
  let f = shortFormatters.get(scope)
  if (!f) {
    f = new Intl.DateTimeFormat('zh-CN', SHORT_FORMATS[scope])
    shortFormatters.set(scope, f)
  }
  return f
}

/** 缩写版：解不出或空值给 null（调用方据此隐藏整行，与 tryFormatDateTime 同口径） */
export function tryFormatShortDateTime(
  value: TimeInput | Date,
  scope: ShortTimeScope,
): string | null {
  const d = parseTime(value)
  return d === null ? null : shortFormatter(scope).format(d)
}

/** 缩写版：空值给「—」，脏值原样回显（与 formatDateTime 同一取舍） */
export function formatShortDateTime(value: TimeInput | Date, scope: ShortTimeScope): string {
  const text = tryFormatShortDateTime(value, scope)
  if (text) return text
  return isBlank(value) ? '—' : String(value)
}

type TimeInput = string | number | null | undefined

function isBlank(value: TimeInput | Date): boolean {
  return value === null || value === undefined || value === ''
}

/** 唯一的判空/判 Invalid Date 入口：两种形状共用，避免「整时间戳有护栏、缩写没有」 */
function parseTime(value: TimeInput | Date): Date | null {
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value
  if (isBlank(value)) return null
  const d = new Date(value as string | number)
  return Number.isNaN(d.getTime()) ? null : d
}

/**
 * 秒数 → 时长（最多两级单位，长任务不写「3600 秒」）
 * 用于「超时多久 / 已等待多久」这类相对时间，绝对时间请用 formatDateTime。
 *
 * `compact: true` 只是把单位换成 `1h 11m` 这种窄屏写法，算法与中文分支同源；
 * 移动端 AntiCrawl 原先自己有一份 `formatDuration`（T02884 收掉），
 * 两份实现会在 60 秒边界上给出不同答案。
 *
 * `withSeconds: true` 是给**正在倒数的计时器**用的：秒始终念出来，包括整分与整点。
 * 默认分支在 s=0 或跨过一小时后就不念秒了，静态统计值无所谓，
 * 倒计时会在整分那一秒看着像卡住（订单接管、登录已用时）。
 */
export function formatDuration(
  sec: number | null | undefined,
  opts?: { readonly compact?: boolean; readonly withSeconds?: boolean },
): string {
  if (sec === null || sec === undefined || !Number.isFinite(sec) || sec < 0) return '—'
  const total = Math.floor(sec)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const keepSec = opts?.withSeconds === true
  if (opts?.compact) return compactParts(h, m, s, keepSec)
  if (h > 0) {
    if (keepSec) return `${h} 小时 ${m} 分 ${s} 秒`
    return m > 0 ? `${h} 小时 ${m} 分` : `${h} 小时`
  }
  if (m > 0) return s > 0 || keepSec ? `${m} 分 ${s} 秒` : `${m} 分`
  return s > 0 ? `${s} 秒` : '不足 1 秒'
}

// 紧凑单位同样「最多两级」：不带秒时省略零头，与中文分支保持同一个取舍
function compactParts(h: number, m: number, s: number, withSeconds: boolean): string {
  if (h > 0) {
    if (withSeconds) return `${h}h ${m}m ${s}s`
    return m > 0 ? `${h}h ${m}m` : `${h}h`
  }
  if (m > 0) return s > 0 || withSeconds ? `${m}m ${s}s` : `${m}m`
  return s > 0 ? `${s}s` : '0s'
}
