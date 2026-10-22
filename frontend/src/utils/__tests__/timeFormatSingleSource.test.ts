import { describe, it, expect } from 'vitest'
import { readFileSync, readdirSync, existsSync } from 'node:fs'
import { join, resolve } from 'node:path'

// T02695：同一份今日告警载荷（TodayAlert）在两个入口曾有三种时间长相——
// 抽屉裸 ISO、抽屉裸秒、雷达「N 分钟前」。收口到 utils/timeFormat 一份 helper 之后，
// 这里禁止这两个文件再把手工格式化写回去（同 T02693/T02716 的裸字面串钉法）。
// T02884 把同一形状的位点继续往上加（棘轮只增不减）。

const SRC_ROOT = resolve(__dirname, '../..')
// 告警口径相关的文件（T02695 + T02884）：age_sec / 「分钟前」这类时长口径只在这些文件里冲突，
// 商品列表等页面用「3 分钟前」的相对时间是有意为之，不在本规则射程内
const ALERT_FILES = [
  'components/layout/MainLayout.tsx',
  'pages/Dashboard/components/AlertRadar.tsx',
  // T02884 A 类：裸 ISO 直接给用户看
  'mobile/pages/Orders/index.tsx',
  'mobile/pages/Orders/OrderDetail.tsx',
  'mobile/pages/Tasks/TaskDetail.tsx',
  'pages/Maintenance/VectorAdmin.tsx',
  'pages/Chatbot/Config.tsx',
  // T02884 B 类：裸秒 / 手工折算时长
  'pages/AntiCrawl/index.tsx',
  'mobile/pages/AntiCrawl/index.tsx',
]
const CLEANED_FILES = [
  ...ALERT_FILES,
  'components/layout/MainLayout.tsx',
  'pages/Dashboard/components/AlertRadar.tsx',
  // T02884 A 类：裸 ISO 直接给用户看
  'mobile/pages/Orders/index.tsx',
  'mobile/pages/Orders/OrderDetail.tsx',
  'mobile/pages/Tasks/TaskDetail.tsx',
  'pages/Maintenance/VectorAdmin.tsx',
  'pages/Chatbot/Config.tsx',
  // T02884 B 类：裸秒 / 手工折算时长
  'pages/AntiCrawl/index.tsx',
  'mobile/pages/AntiCrawl/index.tsx',
  // T02901 第一波：内联 new Date(x).toLocaleString('zh-CN') 与异名本地 helper
  'components/editors/CronEditor.tsx',
  'mobile/pages/BatchRefresh/index.tsx',
  'mobile/pages/ErrorLogs/index.tsx',
  'mobile/pages/Evaluations/index.tsx',
  'mobile/pages/Items/index.tsx',
  'mobile/pages/Logs/index.tsx',
  'mobile/pages/Notifications/index.tsx',
  'mobile/pages/Timeline/index.tsx',
  'mobile/pages/VersionManager/index.tsx',
  'pages/Chatbot/components/VectorAdminPanel.tsx',
  'pages/Config/VersionManager.tsx',
  'pages/Dashboard/components/EventStreamSection.tsx',
  'pages/Evaluations/components/CollectResultModal.tsx',
  'pages/Evaluations/hooks/useEvalColumns.tsx',
  'pages/Items/ItemList.tsx',
  'pages/Logs/ErrorLogs.tsx',
  'pages/Logs/Logs.tsx',
  'pages/Maintenance/BatchRefresh.tsx',
  'pages/Maintenance/DatabaseAdmin.tsx',
  'pages/Notifications/index.tsx',
  'pages/Orders/Orders.tsx',
  'pages/Tasks/TaskDetail.tsx',
]

function read(rel: string): string {
  return readFileSync(resolve(SRC_ROOT, rel), 'utf-8')
}

function walk(dir: string): string[] {
  const out: string[] = []
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (entry.name === '__tests__') continue
      out.push(...walk(join(dir, entry.name)))
    } else if (/\.tsx?$/.test(entry.name)) {
      out.push(join(dir, entry.name))
    }
  }
  return out
}

describe('告警抽屉与雷达的时间展示同源（T02695）', () => {
  it('两个消费方都从 utils/timeFormat 取时间格式', () => {
    for (const rel of CLEANED_FILES) {
      expect(read(rel), `${rel} 没用共享 helper`).toMatch(/from '.*utils\/timeFormat'/)
    }
  })

  it('禁止裸插值 created_at（必须走 formatDateTime）', () => {
    const offenders: string[] = []
    for (const rel of CLEANED_FILES) {
      for (const line of read(rel).split(/\r?\n/)) {
        // key={`${id}-${item.created_at}`} 是 React 列表键拼接，不是给用户看的时间
        if (/key=|rowKey=/.test(line)) continue
        // 模板串里的 `${o.created_at}` 与 JSX 里的 `{o.created_at}` 是同一个病，两种写法都要拦
        for (const m of line.matchAll(/\$\{[\w.]+\.created_at\}/g)) offenders.push(`${rel}: ${m[0]}`)
        // 负向后视：不再从 `${...}` 里重复摘出内层花括号，同一处只报一遍
        for (const m of line.matchAll(/(?<!\$)\{\s*[\w.]+\.created_at\s*\}/g)) {
          offenders.push(`${rel}: ${m[0]}`)
        }
      }
    }
    expect(offenders, `裸 ISO 会露出 T 和微秒，与订单表格列两套口径：\n${offenders.join('\n')}`).toEqual([])
  })

  it('禁止手工切 ISO 字符串当时间显示（坐标轴缩写除外）', () => {
    const offenders: string[] = []
    for (const rel of CLEANED_FILES) {
      for (const line of read(rel).split(/\r?\n/)) {
        if (!/\.slice\(\s*5\s*,\s*16\s*\)/.test(line)) continue
        // 唯一的豁免：图表 x 轴标签。它是「缩写」不是「完整时间」，
        // 且必须先经共享 helper（或 Intl）落地再切位（TaskDetail 的 runs 轴），
        // 不能直接切库里的 ISO 串
        if (/toLocaleString|formatDateTime/.test(line)) continue
        offenders.push(`${rel}: ${line.trim()}`)
      }
    }
    expect(offenders, `直接切 ISO 是第四套口径（雷达低分曾这么干）：\n${offenders.join('\n')}`).toEqual([])
  })

  it('禁止裸秒数与「分钟前」两种时长写法（必须走 formatDuration）', () => {
    const offenders: string[] = []
    for (const rel of ALERT_FILES) {
      const src = read(rel)
      // `[^}]*` 而不是 `[\w.() |]*`：`${Math.floor(session.token_age_sec)}s` 这种带括号的写法
      // 也要拦住，AntiCrawl 的 token 年龄与告警的 age_sec 是同一个病
      for (const m of src.matchAll(/\$\{[^}]*age_sec[^}]*\}s/g)) offenders.push(`${rel}: ${m[0]}`)
      for (const m of src.matchAll(/age_sec[^)]*\/\s*60/g)) offenders.push(`${rel}: 手工折算 ${m[0]}`)
      if (/分钟前/.test(src)) offenders.push(`${rel}: 「分钟前」是第三种口径`)
    }
    expect(
      offenders,
      `同一个 age_sec 在两个入口不能有多种算法：\n${offenders.join('\n')}`,
    ).toEqual([])
  })

  it('超时行统一念「超时 X」，抽屉与雷达一致', () => {
    expect(read(CLEANED_FILES[0])).toMatch(/超时 \$\{formatDuration\(o\.age_sec\)\}/)
    expect(read(CLEANED_FILES[1])).toMatch(/超时 \{formatDuration\(o\.age_sec\)\}/)
  })
})

describe('时长 helper 只有一份实现（T02884）', () => {
  // 被禁的写法在运行时拼出来，免得本文件里的正则字面量自匹配
  const defineNeedles = ['formatDur', 'ation'].join('').split('')
  const definePrefixes = ['function ', 'const ']
  const sharedFile = resolve(SRC_ROOT, 'utils', 'timeFormat.ts')

  it('除 utils/timeFormat.ts 外，全站不得再定义 formatDuration', () => {
    const name = defineNeedles.join('')
    const offenders: string[] = []
    for (const p of walk(SRC_ROOT)) {
      if (p === sharedFile) continue
      readFileSync(p, 'utf-8').split(/\r?\n/).forEach((line, i) => {
        for (const prefix of definePrefixes) {
          if (new RegExp(`^\\s*(export\\s+)?${prefix}${name}\\b`).test(line)) {
            offenders.push(`${p.replace(SRC_ROOT, '')}:${i + 1}: ${line.trim()}`)
          }
        }
      })
    }
    expect(
      offenders,
      `第二份 formatDuration 会在 60 秒边界上与共享实现分叉，请改 utils/timeFormat：\n${offenders.join('\n')}`,
    ).toEqual([])
  })

  it('共享实现支持紧凑单位，移动端 AntiCrawl 接的是它而不是本地副本', () => {
    expect(readFileSync(sharedFile, 'utf-8')).toContain('compact')
    const mobile = read('mobile/pages/AntiCrawl/index.tsx')
    expect(mobile).toContain("from '../../../utils/timeFormat'")
    expect(mobile).not.toMatch(/h\}h \$\{m\}m/)
    // 逐个调用点核对，不用「文件里出现过一次就算过」：
    // 只有一处带 compact 也能满足存在性断言，另一处会静默退回中文长单位
    const calls = (mobile.match(/formatDuration\(/g) ?? []).length
    const compactCalls = (mobile.match(/\{ compact: true \}/g) ?? []).length
    expect(calls, '移动端 AntiCrawl 应当没有 formatDuration 调用').toBeGreaterThan(0)
    expect(compactCalls, `移动端有 ${calls - compactCalls} 处调用没带 compact`).toBe(calls)
  })

  it('CLEANED_FILES 里每个文件都真实存在且引了 timeFormat', () => {
    for (const rel of CLEANED_FILES) {
      expect(existsSync(resolve(SRC_ROOT, rel)), `${rel} 已不在仓库里，请核对清单`).toBe(true)
      expect(read(rel), `${rel} 没用共享 helper`).toMatch(/utils\/timeFormat/)
    }
  })
})

describe('全站时间口径同源（T02901）', () => {
  // 被禁写法在运行时拼出来，免得本文件里的正则字面量自匹配
  const LOCALE_CALL = ['toLocale', "String('zh-", "CN')"].join('')
  // 只带 hour12 的写法与不带选项完全等价（zh-CN 默认就是 24 小时制），
  // 它绕过了上一条 needle 的字面量匹配，实际是一个整时间戳
  const LOCALE_CALL_H12 = [LOCALE_CALL.slice(0, LOCALE_CALL.length - 1), ", { hour12: false })"].join('')
  const sharedFile = resolve(SRC_ROOT, 'utils', 'timeFormat.ts')

  it('除共享 helper 外，不得再内联 Intl 格式化（空值/脏值护栏会跟着丢）', () => {
    const offenders: string[] = []
    for (const p of walk(SRC_ROOT)) {
      if (p === sharedFile) continue
      readFileSync(p, 'utf-8').split(/\r?\n/).forEach((line, i) => {
        // 图表 x 轴要在 Intl 结果上切位缩写，那是唯一允许的下游用法
        if (line.includes(LOCALE_CALL) && !/\.slice\(/.test(line)) {
          offenders.push(`${p.replace(SRC_ROOT, '')}:${i + 1}: ${line.trim()}`)
        }
        if (line.includes(LOCALE_CALL_H12)) offenders.push(`${p.replace(SRC_ROOT, '')}:${i + 1}: ${line.trim()}`)
      })
    }
    expect(
      offenders,
      `内联 Intl 与 formatDateTime 会在空值上分叉（Invalid Date vs 「—」），请改 utils/timeFormat：\n${offenders.join('\n')}`,
    ).toEqual([])
  })

  it('带字段选项的 Intl 是有意缩写（坐标轴/时间线），只能出现在清单里这几处', () => {
    // 缩写形状（月日时分）与整时间戳是两种需求，本单只统一后者；
    // 前者要不要收进共享 helper（formatShort 之类）属第三波，先钉住现状不许扩散
    const ALLOWED = [
      'components/PriceTrendChart.tsx',
      'pages/Tasks/TaskDetail.tsx',
      'pages/Timeline/components/TimelineList.tsx',
      // 相对时间 helper 超过一周后退回的「MM-DD HH:mm」绝对兜底
      'pages/Timeline/utils.ts',
    ]
    const hits: string[] = []
    for (const p of walk(SRC_ROOT)) {
      if (p === sharedFile) continue
      const rel = p.replace(SRC_ROOT, '').replace(/\\/g, '/').slice(1)
      if (ALLOWED.includes(rel)) continue
      readFileSync(p, 'utf-8').split(/\r?\n/).forEach((line, i) => {
        if (/(month|day|hour|minute): '2-digit'/.test(line)) {
          hits.push(`${rel}:${i + 1}: ${line.trim()}`)
        }
      })
    }
    expect(hits, `新的缩写形状要先进清单再落地，否则会出现第四套时间长相：\n${hits.join('\n')}`).toEqual([])
  })

  it('不得再出现行内秒→分/时折算（倒计时与统计值都要走 formatDuration）', () => {
    const offenders: string[] = []
    for (const p of walk(SRC_ROOT)) {
      if (p === sharedFile) continue
      readFileSync(p, 'utf-8').split(/\r?\n/).forEach((line, i) => {
        if (/\/\s*60\)?\s*(分钟|分|秒)/.test(line) || /%\s*60\)?\}?\s*秒/.test(line)) {
          offenders.push(`${p.replace(SRC_ROOT, '')}:${i + 1}: ${line.trim()}`)
        }
      })
    }
    expect(
      offenders,
      `自己折算的时长没有小时级，超过 1 小时会写成「71分10秒」：\n${offenders.join('\n')}`,
    ).toEqual([])
  })

  it('共享 helper 里 Intl 只调用一次，两个入口不会分叉', () => {
    const src = readFileSync(sharedFile, 'utf-8')
    expect((src.match(/toLocaleString/g) ?? []).length).toBe(1)
  })

  it('倒计时代码带秒，静态统计不带秒（withSeconds 的分工）', () => {
    // 逐个调用点核对，不用「文件里出现过一次就算过」
    const withSeconds = walk(SRC_ROOT).filter((p) =>
      readFileSync(p, 'utf-8').includes('withSeconds: true'))
    const files = withSeconds.map((p) => p.replace(SRC_ROOT, '').replace(/\\/g, '/'))
    for (const rel of ['pages/Orders/Orders.tsx', 'pages/Login/index.tsx',
      'mobile/components/TakeoverCountdown.tsx', 'pages/Maintenance/BatchRefresh.tsx']) {
      expect(files, `${rel} 是倒计时/耗时展示，应当带 withSeconds`).toContain('/' + rel)
    }
  })
})
