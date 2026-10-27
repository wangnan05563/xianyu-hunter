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
  // 只到日期或只到时间的内联 Intl：缩写形状曾经的三条旁路（EvalRules/ItemList/移动端关于页）
  const LOCALE_DATE_CALL = ['toLocale', "Date", "String('"].join('')
  const LOCALE_TIME_CALL = ['toLocale', "Time", "String('"].join('')
  const sharedFile = resolve(SRC_ROOT, 'utils', 'timeFormat.ts')

  it('除共享 helper 外，不得再内联 Intl 格式化（空值/脏值护栏会跟着丢）', () => {
    // T02905 起去掉 `.slice(` 豁免：那条豁免原本是给图表轴的（先落地再切位），
    // 缩写档位进 helper 之后轴标签也有正规写法了，留着它等于允许「切 ISO 位」这套第四口径回潮
    const needles = [LOCALE_CALL, LOCALE_CALL_H12, LOCALE_DATE_CALL, LOCALE_TIME_CALL]
    const offenders: string[] = []
    for (const p of walk(SRC_ROOT)) {
      if (p === sharedFile) continue
      readFileSync(p, 'utf-8').split(/\r?\n/).forEach((line, i) => {
        if (needles.some((n) => line.includes(n))) {
          offenders.push(`${p.replace(SRC_ROOT, '')}:${i + 1}: ${line.trim()}`)
        }
      })
    }
    expect(
      offenders,
      `内联 Intl 与 formatDateTime 会在空值上分叉（Intl 遇到 Invalid Date 直接抛 RangeError），请改 utils/timeFormat：\n${offenders.join('\n')}`,
    ).toEqual([])
  })

  it('带字段选项的 Intl 只允许出现在共享 helper 里（T02905 把清单清空）', () => {
    // T02901 留的 ALLOWED 清单（4 个文件）把当时的现状钉住了，但没有收口：
    // 缩写形状此后又各自长出了 `toLocaleTimeString`（EvalRules/ItemList）、
    // `toLocaleDateString`（移动端关于页）、`padStart` 手工拼串（SheetTabs/BrandCard）三种写法，
    // 都不在旧清单的字面量射程里。本单起清单为空，缩写只能来自 utils/timeFormat。
    const ALLOWED: string[] = []
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
    expect(hits, `缩写档位要加进 utils/timeFormat 的 SHORT_FORMATS，别在页面里自己写：\n${hits.join('\n')}`).toEqual([])
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

  it('不得对共享 helper 的结果再切字符位（那是第四套口径的来源）', () => {
    // TaskDetail 的 runs 轴原本写 formatDateTime(r.start).slice(5, 16)：
    // 位切依赖 locale 数据的字面形状，宿主 ICU 一变（2026/10/19 vs 2026-10-19）就切歪
    const callName = ['format', '(?:Short)?DateTime'].join('')
    const sliceRe = new RegExp(`${callName}\\([^)\\n]*\\)\\s*\\.slice\\(`, 'g')
    const offenders: string[] = []
    for (const p of walk(SRC_ROOT)) {
      // 注释行不参与扫描：helper 自己的文档就在引用这行旧写法，算命中等于把守卫写成「不许解释 bug」
      const code = readFileSync(p, 'utf-8')
        .split(/\r?\n/)
        .filter((l) => !/^\s*(\/\/|\*|\/\*)/.test(l))
        .join('\n')
      for (const m of code.matchAll(sliceRe)) {
        offenders.push(`${p.replace(SRC_ROOT, '')}: ${m[0]}`)
      }
    }
    expect(offenders, `缩写请用 formatShortDateTime 的档位：\n${offenders.join('\n')}`).toEqual([])
  })
})

describe('缩写档位只有一份表（T02905）', () => {
  const sharedFile = resolve(SRC_ROOT, 'utils', 'timeFormat.ts')
  const helper = readFileSync(sharedFile, 'utf-8')

  /** 每个位点期望的档位与次数（逐个调用点核对，不用「文件里出现过一次就算过」） */
  const EXPECTED: Record<string, Record<string, number>> = {
    // 图数据与 tooltip coord 必须同形，否则 markPoint 落不到点上
    'components/PriceTrendChart.tsx': { 'month-day-time': 2 },
    'pages/Tasks/TaskDetail.tsx': { 'month-day-time': 1, time: 1 },
    'pages/Timeline/components/TimelineList.tsx': { 'month-day-time': 1 },
    'pages/Timeline/utils.ts': { 'month-day-time': 1 },
    'components/SheetWorkspace/SheetTabs.tsx': { 'date-time': 1 },
    'pages/About/BrandCard.tsx': { date: 1 },
    'mobile/pages/About/index.tsx': { date: 1 },
    'pages/Config/EvalRules.tsx': { time: 2 },
    'pages/Items/ItemList.tsx': { time: 1 },
    // 一个调用点按区间选档位，两个档位各出现一次
    'pages/Dashboard/components/TrendModal.tsx': { 'month-day': 1, time: 1 },
  }

  it('每个位点的档位与调用数逐条核对', () => {
    for (const [rel, scopes] of Object.entries(EXPECTED)) {
      const src = read(rel)
      expect(src, `${rel} 没引共享 helper`).toMatch(/utils\/timeFormat/)
      for (const [scope, count] of Object.entries(scopes)) {
        const hits = (src.match(new RegExp(`'${scope}'`, 'g')) ?? []).length
        expect(hits, `${rel} 的 '${scope}' 档位出现 ${hits} 次，期望 ${count} 次`).toBe(count)
      }
    }
  })

  it('每个缩写调用点都带档位（漏档位会静默走错形状）', () => {
    const scopes = Object.keys(EXPECTED).flatMap((rel) => Object.keys(EXPECTED[rel]))
    const callName = ['formatShort', 'DateTime('].join('')
    const offenders: string[] = []
    for (const p of walk(SRC_ROOT)) {
      if (p === sharedFile) continue
      const src = readFileSync(p, 'utf-8')
      let at = -1
      while ((at = src.indexOf(callName, at + 1)) >= 0) {
        const after = src.slice(at, at + 200)
        if (!scopes.some((s) => after.includes(`'${s}'`))) {
          offenders.push(`${p.replace(SRC_ROOT, '')}: ${after.split(/\r?\n/)[0].trim()}`)
        }
      }
    }
    expect(offenders, `调用点缺档位：\n${offenders.join('\n')}`).toEqual([])
  })

  it('档位表与调用点双向闭合（没有死档位，也没有表外档位）', () => {
    const table = helper.slice(helper.indexOf('const SHORT_FORMATS'))
    const declared = [...table.matchAll(/^\s{2}'?([a-z-]+)'?:\s*\{/gm)].map((m) => m[1])
    expect(declared.length, '档位表解析为空，多半是写法改了').toBeGreaterThan(0)
    const used = new Set(Object.keys(EXPECTED).flatMap((rel) => Object.keys(EXPECTED[rel])))
    for (const d of declared) {
      expect(used.has(d), `档位 ${d} 没有任何调用点，是死档位`).toBe(true)
    }
    for (const u of used) {
      expect(declared, `调用点用了档位表里没有的档位 ${u}`).toContain(u)
    }
  })

  it('共享 helper 里整时间戳与缩写各只有一个 Intl 出口', () => {
    expect((helper.match(/toLocaleString/g) ?? []).length).toBe(1)
    expect((helper.match(/new Intl\.DateTimeFormat\(/g) ?? []).length).toBe(1)
  })

  // 手工拼日期串（getFullYear/padStart）的豁免落成可校验数据，
  // 写法沿用 T02850 的外来词表：登记词消失即红
  const FOREIGN_VOCAB: Record<string, { readonly why: string; readonly words: readonly string[] }> = {
    'pages/About/index.tsx': {
      why: '页脚版权年份，不是某个事件的时间戳',
      words: ['getFullYear()'],
    },
    'pages/Chatbot/components/ChatbotOnboarding.tsx': {
      why: '按时段挑问候语，产出的是档位不是时间',
      words: ['getHours()'],
    },
  }
  const HANDMADE = ['getFullYear()', 'getMonth()', 'getHours()', ['padStart', "(2, '0')"].join('')]

  it('手工拼日期串只允许出现在登记过的外来词位点', () => {
    const offenders: string[] = []
    for (const p of walk(SRC_ROOT)) {
      if (p === sharedFile) continue
      const rel = p.replace(SRC_ROOT, '').replace(/\\/g, '/').slice(1)
      const src = readFileSync(p, 'utf-8')
      const allowed = FOREIGN_VOCAB[rel]?.words ?? []
      for (const w of HANDMADE) {
        if (src.includes(w) && !allowed.includes(w)) offenders.push(`${rel}: ${w}`)
      }
    }
    expect(
      offenders,
      `拼串绕开 Intl，空值/脏值护栏与 locale 口径都会分叉；请走 formatShortDateTime：\n${offenders.join('\n')}`,
    ).toEqual([])
  })

  it('登记的外来词仍然真实存在（豁免清单不许只增不减地腐烂）', () => {
    for (const [rel, vocab] of Object.entries(FOREIGN_VOCAB)) {
      expect(existsSync(resolve(SRC_ROOT, rel)), `${rel} 已不在仓库里，请核对清单`).toBe(true)
      for (const w of vocab.words) {
        expect(read(rel), `${rel} 里的 '${w}' 已消失（${vocab.why}），把它从豁免表删掉`).toContain(w)
      }
    }
  })

  it('趋势弹窗不再把后端 ISO 串直接端给用户（T02884 A 类同族）', () => {
    const src = read('pages/Dashboard/components/TrendModal.tsx')
    expect(src, 'tooltip 又回到裸 ISO').not.toMatch(/\$\{s\.ts\}/)
    expect(src).toContain('${formatDateTime(s.ts)}')
    expect(src, '轴标签又在切 ISO').not.toMatch(/split\('T'\)/)
  })
})

// T02911：dayjs 是时间展示来源里的第三个库（在 Intl 家族与手工拼串之外）。
// 上面的 needle 全是 Intl / 拼串形状，`.format('YYYY-MM-DD HH:mm:ss')` 一条都不匹配，
// 所以这一族从来没进过射程。守卫按「写法」扫带日期 token 的字面量格式串，
// 并把合法用途（提交给后端的参数、落库的配置值）落成 文件 → 格式串 → 次数 的可校验数据：
// 多一处（新位点没登记）红，少一处（登记词已消失）也红。
describe('dayjs 的字面量格式串不许出现在展示位（T02911）', () => {
  const TOKEN_RE = /\.format\('([YMDHms:\-T ]+)'\)/g

  const PARAM_USE: Record<string, { readonly why: string; readonly tokens: Record<string, number> }> = {
    'pages/Evaluations/hooks/useEvalList.ts': {
      why: 'start_time / end_time 是查询参数，不是给用户看的时间',
      tokens: { 'YYYY-MM-DD': 2 },
    },
    'pages/Export/index.tsx': {
      why: '导出请求体的时间边界，由后端解析',
      tokens: { 'YYYY-MM-DDTHH:mm:ss': 2 },
    },
    'pages/Config/NotifierChannels/index.tsx': {
      why: '免打扰时段的配置值，落库给后端读',
      tokens: { 'HH:mm': 2 },
    },
  }

  // walk() 已排除 __tests__，这里的字面量不会自伤；注释行再挡一道
  function scan(): Record<string, Record<string, number>> {
    const found: Record<string, Record<string, number>> = {}
    for (const p of walk(SRC_ROOT)) {
      const rel = p.replace(SRC_ROOT, '').replace(/\\/g, '/').slice(1)
      for (const line of readFileSync(p, 'utf-8').split(/\r?\n/)) {
        if (/^\s*(\/\/|\*|\/\*)/.test(line)) continue
        for (const m of line.matchAll(TOKEN_RE)) {
          const tokens = found[rel] ?? (found[rel] = {})
          tokens[m[1]] = (tokens[m[1]] ?? 0) + 1
        }
      }
    }
    return found
  }

  it('带日期格式串的 .format() 只出现在登记过的参数位点', () => {
    const offenders: string[] = []
    for (const [rel, tokens] of Object.entries(scan())) {
      const allowed = PARAM_USE[rel]?.tokens
      for (const [tok, n] of Object.entries(tokens)) {
        if (!allowed || allowed[tok] !== n) {
          offenders.push(`${rel}: .format('${tok}') × ${n}${allowed ? `（登记为 ${allowed[tok] ?? 0}）` : '（未登记）'}`)
        }
      }
    }
    expect(
      offenders,
      `dayjs 的字面量格式串把展示绑到库自己的固定形状，与站内其它时间点（按宿主 Intl 出）在浏览器 ICU 下会分叉；` +
        `展示请走 formatDateTime / formatShortDateTime，确属参数或配置则登记进 PARAM_USE：\n${offenders.join('\n')}`,
    ).toEqual([])
  })

  it('登记的参数位点仍然真实存在（豁免表不许只增不减地腐烂）', () => {
    const found = scan()
    for (const [rel, entry] of Object.entries(PARAM_USE)) {
      for (const [tok, n] of Object.entries(entry.tokens)) {
        expect(found[rel]?.[tok], `${rel} 里的 '${tok}' 数量对不上（${entry.why}），核对后更新豁免表`).toBe(n)
      }
    }
  })

  it('商品列表 updated_at 的绝对时间走 helper，相对时间保持有意豁免', () => {
    const src = read('pages/Items/ItemList.tsx')
    expect(src, 'updated_at 列的 tooltip 又回到 dayjs 的字面量格式串').not.toMatch(TOKEN_RE)
    expect(src).toContain('formatDateTime(record.updated_at)')
    // fromNow()（「3 分钟前」）是本列的定位，T02695 起就在射程外；钉住它别被同源清扫顺手删掉
    expect(src, 'updated_at 列的相对时间被顺手删掉了').toContain('{t.fromNow()}')
  })
})
