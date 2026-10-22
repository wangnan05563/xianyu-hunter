import { createElement, type ReactNode } from 'react'
import {
  ApiOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  DatabaseOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined,
  ShoppingOutlined,
  ThunderboltOutlined,
  ToolOutlined,
} from '@ant-design/icons'

// ===== 事件类型：单一事实源（T02842）=====
// events.type 落库形态只有一种：点分格式（domain/events.py::EventType 的 value，
// 以及 save_event() 直接写字面串的 task.search_done / db_admin.<action> 等）。
// 原先这里并排站着三张表——Dashboard 的下划线表（buy_succeeded）、Dashboard 的点分幽灵表
// （task.runner.* / collector.* / buyer.*）、时间线的点分表——前两张与 DB 实际值零交集，
// 所以仪表盘上的事件标签全部退化成末段英文（evTypeLabel 的兜底成了常态）。
// 现在只剩 EVENT_TYPE_META 一张表，标签/颜色/图标都由它出，两套中文命名不再各写各的。

export interface EventTypeMeta {
  readonly label: string
  readonly color: string
  readonly icon?: ReactNode
}

export const EVENT_TYPE_META: Record<string, EventTypeMeta> = {
  // 任务生命周期
  'task.started': { label: '任务启动', color: 'blue', icon: createElement(CheckCircleOutlined) },
  'task.stopped': { label: '任务停止', color: 'default', icon: createElement(CloseCircleOutlined) },
  'task.paused': { label: '任务暂停', color: 'orange', icon: createElement(ExclamationCircleOutlined) },
  'task.error': { label: '任务异常', color: 'red', icon: createElement(CloseCircleOutlined) },
  // T02883：依赖链激活原先 type=NULL，时间线标签只能兜底成通用「事件」
  'task.dep_triggered': { label: '依赖链激活', color: 'blue', icon: createElement(ThunderboltOutlined) },
  // worker.py 写死字面串，不在 EventType 枚举里（两张库里 16314 + 219 行的主力类型）
  'task.search_done': { label: '搜索完成', color: 'blue', icon: createElement(InfoCircleOutlined) },
  'task.buy_dry_run': { label: '演练下单', color: 'purple', icon: createElement(ShoppingOutlined) },
  // 商品与评估
  'item.discovered': { label: '发现商品', color: 'cyan', icon: createElement(ApiOutlined) },
  'item.found': { label: '发现商品', color: 'cyan', icon: createElement(ApiOutlined) },
  'eval.passed': { label: '通过筛选', color: 'green', icon: createElement(CheckCircleOutlined) },
  'eval.rejected': { label: '已过滤', color: 'default', icon: createElement(CloseCircleOutlined) },
  'eval.scored': { label: '商品评分', color: 'cyan', icon: createElement(InfoCircleOutlined) },
  // 购买链路（文案与 EVENT_TYPE_OPTIONS 的订阅过滤项同源，见下方派生）
  'buy.requested': { label: '请求购买', color: 'orange', icon: createElement(ShoppingOutlined) },
  'buy.succeeded': { label: '购买成功', color: 'green', icon: createElement(CheckCircleOutlined) },
  'buy.failed': { label: '购买失败', color: 'red', icon: createElement(CloseCircleOutlined) },
  'price.dropped': { label: '商品降价', color: 'gold', icon: createElement(ThunderboltOutlined) },
  // 通知与隧道
  'notify.sent': { label: '通知已发送', color: 'blue', icon: createElement(ApiOutlined) },
  'tunnel.started': { label: '隧道启动', color: 'green', icon: createElement(ApiOutlined) },
  // web/startup.py:778 写死字面串，不在 EventType 枚举里
  'tunnel.autostart_failed': { label: '隧道自启失败', color: 'red', icon: createElement(CloseCircleOutlined) },
  // 安全
  'waf.triggered': { label: '风控触发', color: 'red', icon: createElement(ExclamationCircleOutlined) },
  'waf.blocked': { label: '风控拦截', color: 'red', icon: createElement(CloseCircleOutlined) },
  // 认证
  'login.expired': { label: '登录过期', color: 'red', icon: createElement(ExclamationCircleOutlined) },
  'auth.expired': { label: '会话过期', color: 'red', icon: createElement(ExclamationCircleOutlined) },
  'auth.cookie_self_heal': { label: '登录态自愈', color: 'green', icon: createElement(ToolOutlined) },
  // 系统
  'system.error': { label: '系统错误', color: 'red', icon: createElement(CloseCircleOutlined) },
  // 维护（api_maintenance._log_cleanup_action 写 f"maintenance.{category}"）
  'maintenance.database': { label: '数据库维护', color: 'default', icon: createElement(ToolOutlined) },
  'maintenance.logs': { label: '日志清理', color: 'default', icon: createElement(ToolOutlined) },
  'maintenance.cache': { label: '缓存清理', color: 'default', icon: createElement(ToolOutlined) },
}

// ===== db_admin.<action>：类型名由后端拼装，逐条注册没意义 =====
// api_db_admin._log_audit 用 f"db_admin.{action}" 写事件，action 是路由里的字面串。
// 动作词表与后端一一对应，失败动作统一加「失败」后缀，避免给 9 个动作各写一遍。
export const DB_ADMIN_ACTION_LABELS: Record<string, string> = {
  create: '数据表新增',
  update: '数据表更新',
  delete: '数据表删除',
  batch_delete: '数据表批量删除',
  import: '数据表导入',
}
const DB_ADMIN_FAILED_SUFFIX = '_failed'

function dbAdminMeta(type: string): EventTypeMeta | undefined {
  if (!type.startsWith('db_admin.')) return undefined
  const action = type.slice('db_admin.'.length)
  const failed = action.endsWith(DB_ADMIN_FAILED_SUFFIX)
  const base = failed ? action.slice(0, -DB_ADMIN_FAILED_SUFFIX.length) : action
  const label = DB_ADMIN_ACTION_LABELS[base]
  if (!label) return undefined
  return {
    label: failed ? `${label}失败` : label,
    color: failed ? 'red' : 'default',
    icon: createElement(DatabaseOutlined),
  }
}

/** 查事件类型展示元信息；未注册返回 undefined（由调用方决定兜底文案） */
export function eventTypeMeta(type: string | undefined | null): EventTypeMeta | undefined {
  if (!type) return undefined
  return EVENT_TYPE_META[type] ?? dbAdminMeta(type)
}

/** 事件类型颜色，未注册回落 antd 的 default（灰色） */
export function eventTypeColor(type: string | undefined | null): string {
  return eventTypeMeta(type)?.color || 'default'
}

/** 事件类型中文名；未注册回落原始 type（移动端卡片标题这类只要兜底、不要裁末段的场景） */
export function eventTypeLabel(type: string | undefined | null): string {
  if (!type) return '事件'
  return eventTypeMeta(type)?.label || type
}

// ===== Timeline：事件类型过滤选项 =====
// label 一律取自 EVENT_TYPE_META（T02842 前这里另写一份中文，两处会漂移：
// 用户在过滤下拉里叫「评估通过」、时间线上叫「通过筛选」）。
// 只剩 severity 是订阅/降噪用的独立维度，与后端 EVENT_SEVERITY 对齐。
type SubscribableEventType = { value: string; severity: string }

const SUBSCRIBABLE_EVENTS: readonly SubscribableEventType[] = [
  // 业务结果类（与 domain/events.py EventType 对齐）
  { value: 'item.discovered', severity: 'info' },
  { value: 'item.found', severity: 'info' },
  { value: 'eval.passed', severity: 'important' },
  { value: 'eval.rejected', severity: 'info' },
  { value: 'eval.scored', severity: 'info' },
  { value: 'buy.requested', severity: 'info' },
  { value: 'buy.succeeded', severity: 'critical' },
  { value: 'buy.failed', severity: 'important' },
  { value: 'notify.sent', severity: 'info' },
  { value: 'waf.triggered', severity: 'critical' },
  { value: 'waf.blocked', severity: 'critical' },
  { value: 'login.expired', severity: 'critical' },
  { value: 'auth.expired', severity: 'critical' },
  // T02883：补上 type 之后这两路才谈得上订阅过滤（NULL 行会被按 type 的过滤整体筛掉）
  { value: 'auth.cookie_self_heal', severity: 'important' },
  { value: 'task.dep_triggered', severity: 'info' },
  { value: 'task.started', severity: 'info' },
  { value: 'task.stopped', severity: 'info' },
  { value: 'task.paused', severity: 'info' },
  { value: 'task.error', severity: 'critical' },
  { value: 'system.error', severity: 'critical' },
  // DB 实际存储的操作动作类
  { value: 'task.search_done', severity: 'info' },
  { value: 'maintenance.database', severity: 'info' },
  { value: 'maintenance.logs', severity: 'info' },
  { value: 'maintenance.cache', severity: 'info' },
]

// 可订阅值必须都在 EVENT_TYPE_META 里。
// T02925：原先这里直接 throw，而本函数被下面的 EVENT_TYPE_OPTIONS 在模块顶层调用 ——
// 也就是 throw 发生在 **import 期**：一个标签漏注册会让整条 eventTypes import 链崩掉，
// 时间线、日志、通知订阅设置、移动端卡片标题一起白屏（守卫有效，但失败面是全站）。
// 响度改由用例承担（eventTypeSingleSource「订阅过滤项的文案取自同一张表」会红），
// 运行时回落成原始 type —— 与 eventTypeLabel() 对未注册类型的既有口径一致。
// 导出只为让「降级路径」可被用例覆盖：这条分支在两张表对齐时走不到，
// 不导出的话把它改坏（回落成空串）也没有用例会红（T02925 探针 P4）。
export function subscribableLabel(value: string): string {
  const meta = EVENT_TYPE_META[value]
  if (meta) return meta.label
  console.warn(`[eventTypes] 可订阅事件类型 ${value} 未在 EVENT_TYPE_META 注册标签`)
  return value
}

export const EVENT_TYPE_OPTIONS: { value: string; label: string; severity: string }[] =
  SUBSCRIBABLE_EVENTS.map((e) => ({ ...e, label: subscribableLabel(e.value) }))

// 全部合法 value 集合：O(1) 查找，用于校验 mapped 是否为"有效过滤项"
export const EVENT_TYPE_VALUES = new Set(EVENT_TYPE_OPTIONS.map((o) => o.value))

// ===== Timeline：大写枚举名 → 小写点分格式映射（用于同步通知订阅规则）=====
// value 必须落在 EVENT_TYPE_VALUES 内，否则 syncFromNotifier 同步后会过滤掉所有事件。
// 之前缺失 TASK_STOPPED / TASK_SEARCH_DONE / ITEM_FOUND / AUTH_EXPIRED / WAF_BLOCKED /
// SYSTEM_ERROR 这 6 个映射，导致 config.yaml 中的订阅项被静默丢弃。
export const ENUM_TO_DOT: Record<string, string> = {
  ITEM_DISCOVERED: 'item.discovered',
  ITEM_FOUND: 'item.found',
  EVAL_PASSED: 'eval.passed',
  EVAL_REJECTED: 'eval.rejected',
  EVAL_SCORED: 'eval.scored',
  BUY_REQUESTED: 'buy.requested',
  BUY_SUCCEEDED: 'buy.succeeded',
  BUY_FAILED: 'buy.failed',
  NOTIFY_SENT: 'notify.sent',
  WAF_TRIGGERED: 'waf.triggered',
  WAF_BLOCKED: 'waf.blocked',
  LOGIN_EXPIRED: 'login.expired',
  AUTH_EXPIRED: 'auth.expired',
  TASK_STARTED: 'task.started',
  TASK_STOPPED: 'task.stopped',
  TASK_PAUSED: 'task.paused',
  TASK_ERROR: 'task.error',
  TASK_SEARCH_DONE: 'task.search_done',
  SYSTEM_ERROR: 'system.error',
  MAINTENANCE_DATABASE: 'maintenance.database',
  MAINTENANCE_LOGS: 'maintenance.logs',
  MAINTENANCE_CACHE: 'maintenance.cache',
}

// ===== Timeline：日志严重度配置（含颜色与图标）=====
export const SEVERITY_CONFIG: Record<string, { color: string; icon: ReactNode }> = {
  error: { color: 'red', icon: createElement(CloseCircleOutlined) },
  err: { color: 'red', icon: createElement(CloseCircleOutlined) },
  warning: { color: 'orange', icon: createElement(ExclamationCircleOutlined) },
  warn: { color: 'orange', icon: createElement(ExclamationCircleOutlined) },
  info: { color: 'blue', icon: createElement(InfoCircleOutlined) },
}
