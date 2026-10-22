import { describe, it, expect } from 'vitest'
import { readFileSync, readdirSync } from 'node:fs'
import { join, resolve } from 'node:path'
import {
  EVENT_TYPE_META, EVENT_TYPE_OPTIONS, ENUM_TO_DOT, DB_ADMIN_ACTION_LABELS,
  eventTypeMeta, eventTypeColor, eventTypeLabel,
} from '../eventTypes'

// T02693：时间线事件类型表注册过 order.created / order.paid / order.failed 三个键，
// 但后端 domain/events.py 从未定义过 order.* 事件，两张库（18363 + 232 行事件）里也是
// 0 行；而真正落库的 buy.requested / buy.succeeded / buy.failed（notifier hub 写
// event.type.value）反而没注册，抢单事件在时间线上退化成灰色英文标签。
// 幽灵注册不报错，只是永远匹配不到——和裸状态字面串是同一个失效形状，所以一起钉。
//
// T02842 把这个钉法推到全表：Dashboard 侧曾另有两张表（下划线格式 + 21 个 task.runner.*
// / collector.* / buyer.* 点分幽灵键），与 DB 实际 type 零交集，evTypeLabel 的英文末段
// 兜底成了常态。现在三张表合成 EVENT_TYPE_META 一张，断言双向：
//   后端发出的每个事件类型都必须在这张表里（漏注册）
//   这张表里的每个键都必须在后端源码里出现过（幽灵注册）

const SRC_ROOT = resolve(__dirname, '../..')
const BACKEND_ROOT = resolve(__dirname, '../../../../backend/xianyu_hunter')

function walk(dir: string, suffixes: string[]): string[] {
  const out: string[] = []
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, entry.name)
    if (entry.isDirectory()) out.push(...walk(p, suffixes))
    else if (suffixes.some((s) => entry.name.endsWith(s))) out.push(p)
  }
  return out
}

/** 后端全部 .py 源码拼成一坨：事件类型字面值必须在这里出现过 */
function backendSource(): string {
  return walk(BACKEND_ROOT, ['.py']).map((p) => readFileSync(p, 'utf-8')).join('\n')
}

/**
 * 切 domain/events.py::EventType 的枚举体，返回 {成员名: 字面值}
 * 到第一个顶格行为止（枚举体后面紧跟注释 + EVENT_SEVERITY，不能越界）
 */
function parseBackendEventTypeEnum(): Record<string, string> {
  const src = readFileSync(join(BACKEND_ROOT, 'domain/events.py'), 'utf-8')
  const start = src.indexOf('class EventType')
  expect(start, '后端 domain/events.py 里找不到 class EventType').toBeGreaterThanOrEqual(0)
  const body = src.slice(start).split('\nclass ')[0]
  const out: Record<string, string> = {}
  for (const m of body.matchAll(/^\s{4}([A-Z_]+)\s*=\s*"([^"]+)"/gm)) {
    out[m[1]] = m[2]
  }
  return out
}

/** api_db_admin 里 f"db_admin.{action}" 的 action 字面串集合 */
function backendDbAdminActions(): string[] {
  const src = readFileSync(join(BACKEND_ROOT, 'web/routes/api_db_admin.py'), 'utf-8')
  const actions = new Set<string>()
  for (const m of src.matchAll(/_log_audit\(\s*container,\s*"([a-z_]+)"/g)) {
    actions.add(m[1])
  }
  return [...actions].sort()
}

// 智能客服事件只发进程内 event_bus，不进 events 表（两张库 18363 + 232 行里 0 条 chatbot.*），
// 由客服自己的页面展示，所以时间线表不覆盖它们。这个豁免必须是"恰好这 13 个"，
// 后端新增/改名 chatbot 事件时下面的用例要失败，逼下一轮重新确认口径。
const CHATBOT_PREFIX = 'chatbot.'

describe('事件类型注册表不含幽灵键（T02693）', () => {
  it('前端任何地方都不再出现 order.* 事件类型', () => {
    const offenders: string[] = []
    for (const p of walk(SRC_ROOT, ['.ts', '.tsx'])) {
      const src = readFileSync(p, 'utf-8')
      for (const m of src.matchAll(/['"`](order\.[a-z_]+)['"`]/g)) {
        offenders.push(`${p.replace(SRC_ROOT, '')}: ${m[1]}`)
      }
    }
    expect(offenders, `后端从未发出过 order.* 事件：\n${offenders.join('\n')}`).toEqual([])
  })

  it('购买链路三个类型已注册，标签与订阅过滤项逐字一致', () => {
    const optionLabel = new Map(EVENT_TYPE_OPTIONS.map((o) => [o.value, o.label]))
    for (const [key, expected] of [
      ['buy.requested', '请求购买'],
      ['buy.succeeded', '购买成功'],
      ['buy.failed', '购买失败'],
    ] as const) {
      expect(EVENT_TYPE_META[key], `${key} 未注册，时间线上会退化成灰色英文标签`).toBeTruthy()
      expect(EVENT_TYPE_META[key].label).toBe(expected)
      // 两处文案不一致时，用户在过滤下拉与时间线上看到的是两个名字
      expect(optionLabel.get(key), `${key} 的过滤项文案与标签表漂移`).toBe(expected)
    }
  })

  it('cleanup.database 幽灵键已摘除', () => {
    expect(eventTypeMeta('cleanup.database')).toBeUndefined()
  })

  it('标签表每个键都能在后端源码里找到（新增幽灵键会被拒）', () => {
    const backend = backendSource()
    const dead = Object.keys(EVENT_TYPE_META).filter((k) => !backend.includes(k))
    expect(dead, `以下事件类型后端源码里根本没有，属幽灵注册：${dead.join(', ')}`).toEqual([])
  })
})

describe('Dashboard 幽灵表已并入单一事实源（T02842）', () => {
  it('旧点分幽灵键全部不存在（task.runner.* / collector.* / evaluator.* / buyer.* / auth.*）', () => {
    const ghosts = [
      'task.runner.started', 'task.runner.stopped', 'task.runner.finished', 'task.runner.error',
      'collector.page_loaded', 'collector.search_done', 'collector.item_found', 'collector.rate_limited',
      'evaluator.item_scored', 'evaluator.item_passed', 'evaluator.item_rejected',
      'buyer.order_placed', 'buyer.order_failed', 'buyer.payment_done', 'buyer.timeout',
      'auth.login_success', 'auth.login_failed', 'auth.session_expired',
      'system.startup', 'system.shutdown', 'system.warning',
    ]
    for (const g of ghosts) {
      expect(EVENT_TYPE_META[g], `${g} 是后端从未发出过的幽灵键，不应回到表里`).toBeUndefined()
    }
  })

  it('dep_triggered 仍不是事件类型，但 task.dep_triggered 必须注册（T02883）', () => {
    // 原先 scheduler.py:390 / api_orders.py:375 / cookie_status.py:595 三处 save_event
    // 只写 stage、type 留 NULL（nullable 不报错），时间线标签退化成通用「事件」。
    // T02883 补上 type 后，裸 stage 词依然不接受：它是 stage 不是类型，注册进来就又是幽灵键。
    expect(EVENT_TYPE_META['dep_triggered']).toBeUndefined()
    expect(eventTypeMeta('dep_triggered')).toBeUndefined()
    expect(EVENT_TYPE_META['task.dep_triggered'], '依赖链激活没注册，标签会退化').toBeTruthy()
    expect(eventTypeMeta('auth.cookie_self_heal'), '登录态自愈没注册').toBeTruthy()
    // 中文名逐字钉住：文案在别处再写一份就是 T02842 收掉的老病
    expect(eventTypeLabel('task.dep_triggered')).toBe('依赖链激活')
    expect(eventTypeLabel('auth.cookie_self_heal')).toBe('登录态自愈')
  })

  it('两个新类型可订阅、订阅设置的大写枚举名也能映射过来（T02883）', () => {
    // 补 type 的意义在于「用户能筛到它」。这三个位置（后端枚举值 / 前端订阅项 / 大写枚举名映射）
    // 任一处漏了都不报错：前者让本用例红，后两处只有运行时才看得出来，所以逐名配对钉死。
    const backendEnum = parseBackendEventTypeEnum()
    const optionLabel = new Map(EVENT_TYPE_OPTIONS.map((o) => [o.value, o.label]))
    for (const [enumName, dot, label] of [
      ['TASK_DEP_TRIGGERED', 'task.dep_triggered', '依赖链激活'],
      ['AUTH_COOKIE_SELF_HEAL', 'auth.cookie_self_heal', '登录态自愈'],
    ] as const) {
      expect(backendEnum[enumName], `后端 EventType.${enumName} 不在了或改了字面值`).toBe(dot)
      expect(ENUM_TO_DOT[enumName], `${enumName} 没有点分映射，通知订阅会静默丢掉这个类型`).toBe(dot)
      expect(optionLabel.get(dot), `${dot} 不在订阅过滤项里，用户筛不到这类事件`).toBe(label)
    }
  })

  it('下划线格式键一律不接受（DB 里 type 只有点分形态）', () => {
    const underscoreKeys = Object.keys(EVENT_TYPE_META).filter((k) => !k.includes('.'))
    expect(underscoreKeys, `事件类型必须用后端落库的点分格式：${underscoreKeys.join(', ')}`).toEqual([])
  })

  it('移动端用的 eventTypeLabel 也读同一张表（未注册才回落原始 type）', () => {
    expect(eventTypeLabel('task.search_done')).toBe('搜索完成')
    expect(eventTypeLabel('db_admin.update')).toBe('数据表更新')
    // 移动端卡片标题的兜底是原始 type（保留可排查性），不是裁末段
    expect(eventTypeLabel('never.emitted')).toBe('never.emitted')
    expect(eventTypeLabel('')).toBe('事件')
  })

  it('工单点名的真实类型都能查到中文标签与颜色', () => {
    // 颜色按事件语义给定：维护/清理类本就是中性色（default），不能拿"非 default"当覆盖率指标
    const expectedColor: Record<string, string> = {
      'task.search_done': 'blue',
      'eval.scored': 'cyan',
      'eval.passed': 'green',
      'tunnel.started': 'green',
      'tunnel.autostart_failed': 'red',
      'maintenance.database': 'default',
      'maintenance.logs': 'default',
      'maintenance.cache': 'default',
    }
    for (const t of Object.keys(expectedColor)) {
      const meta = eventTypeMeta(t)
      expect(meta, `${t} 未注册，仪表盘会显示英文末段`).toBeTruthy()
      expect(meta!.label, `${t} 标签不是中文`).toMatch(/[\u4e00-\u9fa5]/)
      expect(eventTypeColor(t), `${t} 颜色与注册表漂移`).toBe(expectedColor[t])
    }
  })
})

describe('单一事实源双向覆盖后端 EventType（T02842）', () => {
  const backendEnum = parseBackendEventTypeEnum()
  const mainValues = Object.entries(backendEnum)
    .map(([, v]) => v)
    .filter((v) => !v.startsWith(CHATBOT_PREFIX))
  const chatbotValues = Object.values(backendEnum).filter((v) => v.startsWith(CHATBOT_PREFIX))

  it('后端主系统事件类型全部注册（漏一个就是仪表盘的一处英文末段）', () => {
    const missing = mainValues.filter((v) => !eventTypeMeta(v))
    expect(
      missing,
      `以下 EventType 值在前端 EVENT_TYPE_META 里没有注册：${missing.join(', ')}`,
    ).toEqual([])
  })

  it('chatbot.* 是唯一豁免集合，且与后端枚举里的 chatbot 事件一一对应', () => {
    expect(chatbotValues).toHaveLength(13)
    // 反向确认：主系统值里不含 chatbot，豁免清单没被悄悄扩大
    expect(mainValues.some((v) => v.startsWith(CHATBOT_PREFIX))).toBe(false)
  })

  it('订阅过滤项的文案取自同一张表，不存在第二套中文命名', () => {
    for (const opt of EVENT_TYPE_OPTIONS) {
      expect(EVENT_TYPE_META[opt.value], `${opt.value} 可订阅但未注册标签`).toBeTruthy()
      expect(opt.label, `${opt.value} 过滤项文案与标签表漂移`).toBe(EVENT_TYPE_META[opt.value].label)
    }
  })

  it('通知订阅的大写枚举名映射到的类型都有标签', () => {
    for (const [enumName, dot] of Object.entries(ENUM_TO_DOT)) {
      expect(eventTypeMeta(dot), `ENUM_TO_DOT.${enumName} 指向未注册类型 ${dot}`).toBeTruthy()
    }
  })
})

describe('db_admin.<action> 家族规则与后端动作词同源（T02842）', () => {
  const actions = backendDbAdminActions()

  it('后端 _log_audit 用到的每个动作，前端都能解析成中文（*_failed 统一后缀）', () => {
    expect(actions.length).toBeGreaterThan(0)
    for (const action of actions) {
      const meta = eventTypeMeta(`db_admin.${action}`)
      expect(meta, `db_admin.${action} 解析不到标签，会退化成 ${action}`).toBeTruthy()
      expect(meta!.label, `db_admin.${action} 标签不是中文`).toMatch(/[\u4e00-\u9fa5]/)
    }
  })

  it('动作词表没有多余项（后端删掉某动作后，前端不该继续挂着）', () => {
    const backendBases = new Set(
      actions.map((a) => (a.endsWith('_failed') ? a.slice(0, -'_failed'.length) : a)),
    )
    const extra = Object.keys(DB_ADMIN_ACTION_LABELS).filter((k) => !backendBases.has(k))
    expect(extra, `以下 db_admin 动作后端源码里已不存在：${extra.join(', ')}`).toEqual([])
  })

  it('失败动作标签带「失败」且标红，成功动作不带', () => {
    expect(eventTypeMeta('db_admin.delete')?.label).toBe('数据表删除')
    expect(eventTypeMeta('db_admin.delete_failed')?.label).toBe('数据表删除失败')
    expect(eventTypeMeta('db_admin.delete_failed')?.color).toBe('red')
    expect(eventTypeMeta('db_admin.batch_delete_failed')?.label).toBe('数据表批量删除失败')
  })
})
