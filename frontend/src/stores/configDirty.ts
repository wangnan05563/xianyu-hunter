import type { AppConfig } from '../api'

/** 每个配置页可写的顶层配置段（点号键）。新增配置页必须在此登记。 */
export const SCOPE_PRICE = ['price_strategy', 'bargain_price'] as const
export const SCOPE_EVAL = ['eval'] as const
/**
 * 通知页除了 notifier 段，还直接写 13 个顶层凭据键（ChannelCard 的 fields[].key
 * 经 updateChannelField 原样作为 update() 的顶层键）。这份清单由
 * configScopeCoversWrites.test.ts 与 NotifierChannels/constants.ts 对锁，
 * 漏登记不会静默丢数据——页段提交只发登记过的段。
 */
export const SCOPE_NOTIFIER = [
  'notifier',
  'serverchan_send_key',
  'pushplus_token',
  'bark_server',
  'bark_key',
  'telegram_bot_token',
  'telegram_chat_id',
  'wecom_webhook',
  'dingtalk_webhook',
  'dingtalk_secret',
  'webhook_url',
  'ntfy_server',
  'ntfy_topic',
  'ntfy_token',
] as const
export const SCOPE_SEARCH = ['antidetect', 'search', 'task_scheduler', 'waf'] as const
/**
 * 抢单页除 buyer 外还写 eval.auto_buy_score / eval.pass_score 与 account_rotator
 * （分数阈值、轮转冷却都在这一页）。eval 与「评估规则」页重叠是共享 config
 * 的既成事实：两边任一页的 eval 草稿都会被另一页的保存带上盘。
 */
export const SCOPE_BUYER = ['buyer', 'eval', 'account_rotator'] as const

/** 路由 -> 配置段：关闭确认与未保存黄条按这个边界判断"这一页脏不脏" */
export const CONFIG_SCOPE_BY_ROUTE: Readonly<Record<string, readonly string[]>> = {
  '/config/price': SCOPE_PRICE,
  '/config/eval': SCOPE_EVAL,
  '/config/notifier': SCOPE_NOTIFIER,
  '/config/search': SCOPE_SEARCH,
  '/config/buyer': SCOPE_BUYER,
}

export function scopeForPath(path: string): readonly string[] | null {
  return CONFIG_SCOPE_BY_ROUTE[path] ?? null
}

/** path 是否属于 scope：按点号边界比较，search_extra 不算 search 的改动 */
export function pathInScope(path: string, scope: readonly string[]): boolean {
  return scope.some((key) => path === key || path.startsWith(`${key}.`))
}

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return v !== null && typeof v === 'object' && !Array.isArray(v)
}

/** 收集 a->b 的所有变更路径；数组整体记一条（拆下标会让 revertField 无法回写） */
export function collectChangedPaths(
  a: unknown,
  b: unknown,
  prefix = '',
  out: string[] = [],
): string[] {
  if (Array.isArray(a) || Array.isArray(b)) {
    if (JSON.stringify(a) !== JSON.stringify(b)) out.push(prefix)
    return out
  }
  if (isPlainObject(a) && isPlainObject(b)) {
    const keys = new Set([...Object.keys(a), ...Object.keys(b)])
    for (const key of keys) {
      collectChangedPaths(a[key], b[key], prefix ? `${prefix}.${key}` : key, out)
    }
    return out
  }
  if (a !== b) out.push(prefix)
  return out
}

export function filterChangedPaths(paths: readonly string[], scope: readonly string[]): string[] {
  return paths.filter((p) => pathInScope(p, scope))
}

function getAtPath(root: unknown, path: string): unknown {
  let cur: unknown = root
  for (const key of path.split('.')) {
    if (cur == null || typeof cur !== 'object') return undefined
    cur = (cur as Record<string, unknown>)[key]
  }
  return cur
}

function setAtPath(root: Record<string, unknown>, path: string, value: unknown): void {
  const keys = path.split('.')
  let cur: Record<string, unknown> = root
  for (let i = 0; i < keys.length - 1; i++) {
    const step = cur[keys[i]]
    if (step == null || typeof step !== 'object') return
    cur = step as Record<string, unknown>
  }
  const last = keys[keys.length - 1]
  if (value === undefined) delete cur[last]
  else cur[last] = value
}

/**
 * 载入服务端配置后，把所有未保存草稿写回去（本页与别页一视同仁）。
 * load() 会因为切页 mount、TaskEditor 打开而无处不在地触发；只保留"别页"草稿的话，
 * 切回来那一页的草稿会被自己这次 load 抹掉，和"切换标签页会保留草稿"的说法相悖。
 * 未改动的字段仍取服务端新值，改动过的字段以草稿为准。
 */
export function applyDrafts(
  fresh: AppConfig,
  draft: AppConfig,
  original: AppConfig,
): AppConfig {
  const next = structuredClone(fresh) as unknown as Record<string, unknown>
  for (const path of collectChangedPaths(draft, original)) {
    setAtPath(next, path, getAtPath(draft, path))
  }
  return next as unknown as AppConfig
}

/** 以 base 为底，把 scope 里的每个顶层段换成 src 的值（src 没有该段则删掉） */
function withSegments(
  base: AppConfig,
  src: AppConfig,
  scope: readonly string[],
): Record<string, unknown> {
  const next = structuredClone(base) as unknown as Record<string, unknown>
  for (const seg of scope) {
    setAtPath(next, seg, getAtPath(src, seg))
  }
  return next
}

/**
 * 按页段构造提交体：只带「这一页写过、且确实和 original 不同」的顶层段。
 * 后端 `POST /api/config/save` 是 deepcopy(current) + 深合并，部分载荷即可，
 * 所以未提交的其他页草稿只留在浏览器内存里，不会被这一页的保存顺带写盘。
 * 已知落差：删掉某个键/段在这里和整份提交时都落不了地（深合并只写出现的键），
 * 需要删除语义时走配置导入或版本回滚。
 */
export function scopedSubmitPayload(
  config: AppConfig,
  original: AppConfig,
  scope: readonly string[],
): Partial<AppConfig> {
  const payload: Record<string, unknown> = {}
  for (const seg of scope) {
    if (JSON.stringify(getAtPath(config, seg)) !== JSON.stringify(getAtPath(original, seg))) {
      payload[seg] = structuredClone(getAtPath(config, seg))
    }
  }
  return payload as unknown as Partial<AppConfig>
}

/** 保存成功后刷新 original：本页段认草稿，别页草稿继续按脏算 */
export function markScopeSaved(
  original: AppConfig,
  config: AppConfig,
  scope: readonly string[],
): AppConfig {
  return withSegments(original, config, scope) as unknown as AppConfig
}

/** 只回滚本页段，别页草稿不动（T02571 页段化的「重置」） */
export function revertScope(
  config: AppConfig,
  original: AppConfig,
  scope: readonly string[],
): AppConfig {
  return withSegments(config, original, scope) as unknown as AppConfig
}
