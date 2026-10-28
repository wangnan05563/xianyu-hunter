import type { AppConfig } from '../api'

/** 每个配置页可写的顶层配置段（点号键）。新增配置页必须在此登记。 */
export const SCOPE_PRICE = ['price_strategy', 'bargain_price'] as const
export const SCOPE_EVAL = ['eval'] as const
export const SCOPE_NOTIFIER = ['notifier'] as const
export const SCOPE_SEARCH = ['antidetect', 'search', 'task_scheduler', 'waf'] as const
export const SCOPE_BUYER = ['buyer'] as const

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
