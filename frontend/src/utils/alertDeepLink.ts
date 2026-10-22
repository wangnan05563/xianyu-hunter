import { ORDER_STATUS, ORDER_STATUS_CONFIG } from '../constants/orderStatus'

/**
 * 告警深链（T02620）：抽屉/雷达的跳转从「页面级」升级为「页面 + 查询」
 *
 * 背景：告警抽屉以前只能跳到 `/orders`、`/evaluations`，落到目标页后看不出
 * 具体是哪一条异常——因为两个页面都不读 URL 查询参数（本轮补齐读取侧）。
 *
 * 为什么把构造函数放这里而不是 useNotificationModel：
 * - useNotificationModel 依赖 api/React，本模块必须是纯函数，才能被
 *   Orders / Evaluations / MainLayout 三处共用，也能被 vitest 直接单测；
 * - `AlertKind` 用 `import type` 引入（编译期擦除），不会与 hook 模块形成运行时循环依赖。
 *
 * 查询参数命名与两端读取口径一一对应（改一边必须改另一边，静态守卫测试会红）：
 * - `/orders?status=<OrderStatus>&ref=<order id>`：status 驱动状态筛选，ref 驱动行定位
 *   （ref 是评审 2.1-4 既有能力，此处只负责拼进去）；
 * - `/evaluations?item_id=<id>&score_max=<0-100>`：item_id 驱动商品筛选，
 *   score_max 是「评估分」口径（0–100 整数，与后端 /api/evaluations 的 max_score 同域），
 *   而告警里的 `score_value` 是 0–1 归一分，故必须 ×100 换算。
 */

/** 告警类 → 落地页基础路径（原 useNotificationModel.ALERT_JUMP_TARGETS 迁来，值不变） */
export const ALERT_JUMP_TARGETS = {
  failed: '/orders',
  timeout: '/orders',
  low_eval: '/evaluations',
} as const

export type AlertKind = keyof typeof ALERT_JUMP_TARGETS

/**
 * 告警条目里深链用得上的字段。
 *
 * ⚠ 刻意全部可选：`/api/stats/today` 返回的是 `repo.list_orders` / EventRow 的原始
 * dict，字段以数据库列名为准（`item_id`、`score_value`），前端历史上按自造契约
 * 声明过 `score`，所以这里只声明「深链真正需要的列名口径字段」，取值一律做兜底。
 */
export type AlertJumpItem = {
  readonly id?: string | number | null
  readonly item_id?: string | null
  readonly score_value?: number | null
  readonly status?: string | null
}

/** 订单 id / 商品 id 只放行安全字符：脏数据降级为「不带该参数」，而不是拼出坏链接 */
const SAFE_ID_PATTERN = /^[A-Za-z0-9_:.-]{1,64}$/

function safeId(value: string | number | null | undefined): string {
  const raw = value == null ? '' : String(value)
  return SAFE_ID_PATTERN.test(raw) ? raw : ''
}

/** 0–1 归一分 → 评估分口径（0–100 整数）；非法值返回空串表示不带该参数 */
export function evalScoreMaxFromAlert(scoreValue: number | null | undefined): string {
  if (typeof scoreValue !== 'number' || !Number.isFinite(scoreValue)) return ''
  const pct = Math.round(scoreValue * 100)
  if (pct < 0 || pct > 100) return ''
  return String(pct)
}

/**
 * 取该告警条目真正落在筛选上的状态值。
 *
 * 优先用条目自带的 `status`（它就是后端写进 orders 表的那个字面值），
 * 只有拿不到/不在白名单时才退回兜底值。
 * ⚠ 兜底值必须与后端告警查询的 WHERE 同源，否则筛出来是空列表：
 * 「待支付超时」来自 `stats_today._query_timeout_pending`，其口径是
 * `domain/order.py::PENDING_STATUSES = (pending_pay,)`（不是 takeover_pending）。
 */
function statusForAlert(item: AlertJumpItem | undefined, fallback: string): string {
  return parseOrderStatusParam(item?.status) ?? fallback
}

/**
 * 组装某条告警的落地链接。
 *
 * 每条告警都先带「页面级筛选」再带「条目定位」：即使定位参数因为分页失效
 * （订单在第 2 页之后，见 T02641），用户落到的也是已经筛好的异常子集，
 * 而不是整张全量列表——这正是本单要消掉的「跳到页面却看不出异常」。
 */
export function buildAlertJumpTarget(kind: AlertKind, item?: AlertJumpItem): string {
  const base = ALERT_JUMP_TARGETS[kind]
  const params = new URLSearchParams()
  if (kind === 'failed' || kind === 'timeout') {
    params.set('status', statusForAlert(item, kind === 'failed' ? ORDER_STATUS.FAILED : ORDER_STATUS.PENDING_PAY))
    const ref = safeId(item?.id)
    if (ref) params.set('ref', ref)
  } else {
    const itemId = safeId(item?.item_id)
    if (itemId) params.set('item_id', itemId)
    const scoreMax = evalScoreMaxFromAlert(item?.score_value)
    if (scoreMax) params.set('score_max', scoreMax)
  }
  const query = params.toString()
  return query ? `${base}?${query}` : base
}

/**
 * 抢单记录页读取的 status 参数：只接受与 OrderStatus 同源（ORDER_STATUS_CONFIG 键集）
 * 的字面值。非法值返回 undefined＝不筛选，脏链接静默降级而非把垃圾塞进 WHERE。
 */
export function parseOrderStatusParam(raw: string | null | undefined): string | undefined {
  if (!raw) return undefined
  return Object.prototype.hasOwnProperty.call(ORDER_STATUS_CONFIG, raw) ? raw : undefined
}

/** 评估明细页读取的深链参数 */
export type EvalDeepLink = {
  readonly itemId?: string
  readonly scoreMax?: number
}

function parseScoreMax(raw: string | null): number | undefined {
  if (!raw) return undefined
  const n = Number(raw)
  if (!Number.isFinite(n)) return undefined
  // 与后端 `max_score: int = Query(None, ge=0, le=100)` 同域，越界视为脏参数
  if (n < 0 || n > 100) return undefined
  return n
}

export function parseEvalDeepLink(sp: Pick<URLSearchParams, 'get'>): EvalDeepLink {
  const out: { itemId?: string; scoreMax?: number } = {}
  const itemId = safeId(sp.get('item_id'))
  if (itemId) out.itemId = itemId
  const scoreMax = parseScoreMax(sp.get('score_max'))
  if (scoreMax !== undefined) out.scoreMax = scoreMax
  return out
}

/**
 * 深链参数是否仍然是「当前筛选」的真实描述（T02831）。
 * 落地之后用户手动改过商品ID 或评分区间，链接里的那两个值就不再代表页面上的筛选态，
 * 提示条继续写「已按告警定位到…」就是替一个已不存在的条件背书。
 * 链接里没带的那一项按「不构成矛盾」处理：只带 score_max 的链接不该因为商品ID 是空的
 * 就判成不一致。
 */
export function evalDeepLinkMatchesFilters(
  dl: EvalDeepLink,
  cur: { itemId: string; scoreRange: [number, number] },
): boolean {
  if (dl.itemId && cur.itemId !== dl.itemId) return false
  if (dl.scoreMax != null && (cur.scoreRange[0] !== 0 || cur.scoreRange[1] !== dl.scoreMax)) return false
  return true
}
