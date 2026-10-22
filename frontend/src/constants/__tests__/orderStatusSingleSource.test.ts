import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import {
  ORDER_STATUS,
  ORDER_STATUS_CONFIG,
  ORDER_STATUS_LABELS,
  ORDER_STATUS_USER_CHOICES,
  orderStatusOptions,
} from '../orderStatus'
import {
  FOREIGN_VOCAB,
  codeLines,
  exists,
  scanStatusLiteralPositions,
  srcOf,
  vocabFor,
} from './statusLiteralScan'

// T02693：T02585 把订单状态收敛到后端 OrderStatus 之后，散落的裸串又长回来了一次
// （trend / stats_today / business_kpi / buyer / repo_orders 各自写死 'succeeded'/'failed'/
// 'dry_run'，前端 Timeline 与告警深链同样裸写）。裸串不报错，只静默命中 0 行，
// 所以这里把「前端常量表 ↔ 后端枚举」钉死，并对已清理的文件禁止再出现裸状态字面串。
// 跨语言源码断言写法同 T02619 的 notificationCategorySingleSource。

const BACKEND_ORDER_DOMAIN = resolve(
  __dirname,
  '../../../../backend/xianyu_hunter/domain/order.py',
)

/** 本轮已收口的订单域前端文件：只允许通过 ORDER_STATUS 常量引用状态 */
const CLEANED_FILES = [
  resolve(__dirname, '../../pages/Timeline/index.tsx'),
  resolve(__dirname, '../../pages/Timeline/components/TimelineList.tsx'),
  // T02716：移动端订单页 + 桌面订单页 + 评估页的订单状态判断
  resolve(__dirname, '../../pages/Orders/Orders.tsx'),
  resolve(__dirname, '../../mobile/pages/Orders/index.tsx'),
  resolve(__dirname, '../../mobile/pages/Orders/OrderDetail.tsx'),
  resolve(__dirname, '../../pages/Evaluations/utils.ts'),
]

/** 从后端 OrderStatus 抽取成员名 → 字面值（与 domain/order.py 的 `X = "y"` 行一一对应） */
function parseBackendOrderStatus(): Record<string, string> {
  const src = readFileSync(BACKEND_ORDER_DOMAIN, 'utf-8')
  const start = src.indexOf('class OrderStatus')
  expect(start, '后端 domain/order.py 未找到 OrderStatus 定义').toBeGreaterThanOrEqual(0)
  // 枚举体是缩进行，到第一条顶格行为止（下一条是 PENDING_STATUSES 段的注释）
  const after = src.slice(start)
  const rest = after.slice(after.indexOf('\n') + 1)
  const body = rest.slice(0, rest.search(/^\S.*$/m))
  const out: Record<string, string> = {}
  for (const m of body.matchAll(/^\s{4}([A-Z_]+)\s*=\s*"([a-z_]+)"/gm)) {
    out[m[1]] = m[2]
  }
  expect(Object.keys(out).length, 'OrderStatus 解析结果为空，多半是枚举写法改了').toBeGreaterThan(0)
  return out
}

describe('订单状态单一事实源（T02693）', () => {
  it('ORDER_STATUS 的取值逐字等于后端 OrderStatus', () => {
    const backend = parseBackendOrderStatus()
    expect(ORDER_STATUS).toEqual(backend)
  })

  it('ORDER_STATUS_CONFIG 的键集合与枚举一致（不多不少）', () => {
    const backendValues = Object.values(parseBackendOrderStatus())
    expect(Object.keys(ORDER_STATUS_CONFIG).sort()).toEqual([...backendValues].sort())
    expect(Object.values(ORDER_STATUS).sort()).toEqual([...backendValues].sort())
  })

  it('历史死值（pending / paid / submitting / paying）不再出现在任何状态表里', () => {
    for (const dead of ['pending', 'paid', 'submitting', 'paying', 'confirmed', 'takeover']) {
      expect(Object.keys(ORDER_STATUS_CONFIG), `配置表又长回了死值 ${dead}`).not.toContain(dead)
      expect(Object.values(ORDER_STATUS), `常量表又长回了死值 ${dead}`).not.toContain(dead)
    }
  })

  it('标签表覆盖每个枚举值，可选项取自同一张表（T02716）', () => {
    const backendValues = Object.values(parseBackendOrderStatus())
    // Record<OrderStatusValue, string> 让 TS 保证覆盖，这里再对运行时值核一遍
    expect(Object.keys(ORDER_STATUS_LABELS).sort()).toEqual([...backendValues].sort())
    for (const value of ORDER_STATUS_USER_CHOICES) {
      expect(ORDER_STATUS_LABELS[value], `可选项 ${value} 没有对应标签`).toBeTruthy()
    }
    // 可选项与标签必须来自同一份映射：value 就是枚举值、label 就是标签表里的同一个值
    const options = orderStatusOptions(ORDER_STATUS_USER_CHOICES)
    expect(options.map((o) => o.value)).toEqual([...ORDER_STATUS_USER_CHOICES])
    expect(options.map((o) => o.label)).toEqual(
      ORDER_STATUS_USER_CHOICES.map((v) => ORDER_STATUS_LABELS[v]),
    )
  })

  it('已清理文件里禁止裸写状态字面串（防止再次漂移）', () => {
    for (const path of CLEANED_FILES) {
      // 注释不计，判据与任务守卫共用（statusLiteralScan.codeLines）
      const lines = codeLines(readFileSync(path, 'utf-8'))
      for (const value of Object.values(ORDER_STATUS)) {
        const offender = lines.find((line) => new RegExp(`['"\`]${value}['"\`]`).test(line))
        expect(offender, `${path} 裸写了 '${value}'，应改用 ORDER_STATUS 常量`).toBeUndefined()
      }
    }
  })

  it('告警深链兜底值走常量表（与后端告警查询口径同源）', () => {
    const src = readFileSync(resolve(__dirname, '../../utils/alertDeepLink.ts'), 'utf-8')
    expect(src).toMatch(/import\s*\{[^}]*ORDER_STATUS[^}]*\}\s*from\s*'\.\.\/constants\/orderStatus'/)
  })
})

// T02850：后端增删一个 OrderStatus 取值时的期望行为：
//   · 常量表/配置表/标签表 → 前三条断言直接红，必须一起补；
//   · 已清理文件（CLEANED_FILES）→ 不随取值增减而红（它们引用常量）；
//   · 外来词表文件（FOREIGN_VOCAB）→ 不随订单域新增取值而红，除非有人在那个文件的状态位置上
//     真写了新订单取值（第 2 条规则拦这个），登记里的词若已消失则第 3 条红；
//   · 下面这三处**故意**不在扫描位置上：`key: 'succeeded'`（统计卡 id）、`defaultActiveKey={['failed', …]}`
//     （告警抽屉页签）、`jump('failed', o)`（雷达跳转 kind）。它们是各自域的标识符，
//     与订单状态比较无关；扫描只认 status/state/mode 位置与选项 value，所以不会误伤，
//     也不给它们登记（登记了反而变成「以后可以裸写」的通行证）。
describe('订单域字面值的全站扫描与外来词表登记（T02850）', () => {
  const ORDER_VALUES: readonly string[] = Object.values(ORDER_STATUS)

  it('全站把订单取值写在状态/模式位置上的，必须已被收口或已登记词表', () => {
    const cleanedRel = new Set(
      CLEANED_FILES.map((p) => p.slice(resolve(__dirname, '../..').length + 1).replace(/\\/g, '/')),
    )
    const unregistered = scanStatusLiteralPositions(ORDER_VALUES).filter((h) => {
      if (cleanedRel.has(h.file)) return false
      return vocabFor(h.file)?.values.includes(h.value) !== true
    })
    expect(
      unregistered,
      `新出现的裸写（既不在 CLEANED_FILES 也不在外来词表登记里）：\n${unregistered
        .map((h) => `${h.file}:${h.line}: ${h.text}`).join('\n')}`,
    ).toEqual([])
  })

  it('订单域的外来词表点确实存在且各自属于别的域（不是把守卫关掉）', () => {
    const relevant = ['pages/Maintenance/Tunnel.tsx', 'pages/Chatbot/index.tsx',
      'components/layout/UserMenu.tsx', 'pages/Maintenance/BatchRefresh.tsx']
    for (const rel of relevant) {
      const v = FOREIGN_VOCAB.find((f) => f.file === rel)
      expect(v, `${rel} 的外来词表登记丢失`).toBeTruthy()
      expect(exists(rel), `${rel} 已不在仓库里，登记要删`).toBe(true)
      expect(v!.domain, `${rel} 的登记没写清属于哪个域`).toMatch(/隧道|消息|昵称|批量刷新/)
      // 登记里的每个词都要还能在那个文件里找到，否则登记过期（该词已经不再裸写）
      for (const value of v!.values) {
        expect(srcOf(rel), `${rel} 已不再出现 '${value}'，登记应删除`).toContain(`'${value}'`)
      }
    }
  })

  it('统计卡与告警页签的 id 不在扫描位置上，别把它们误登记成外来词表', () => {
    for (const rel of ['pages/Dashboard/components/StatCardsSection.tsx',
      'components/layout/MainLayout.tsx',
      'pages/Dashboard/components/AlertRadar.tsx']) {
      expect(FOREIGN_VOCAB.some((f) => f.file === rel), `${rel} 不该出现在外来词表登记里`).toBe(false)
    }
  })
})
