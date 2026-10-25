// frontend/src/mobile/__tests__/mobileSilentFallback.test.ts
// T02701 移动端假回执清零：静默兜底（catch 成 null/[]/{}）在 mobile 目录归零，
// 并钉成棘轮 —— 失败要么上账要么显式提示，不允许再用「空态」冒充「取到了 0 条」。
// 桌面端同类改造见 T02586（Dashboard）与 T02700（useFailedSources 抽取）。
import { describe, expect, it } from 'vitest'
import { readFileSync, readdirSync, existsSync } from 'node:fs'
import { join, resolve } from 'node:path'

const MOBILE_ROOT = resolve(__dirname, '..')
const SRC_ROOT = resolve(MOBILE_ROOT, '..')

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

// 被禁用的写法在运行时拼出来，免得本文件里的正则字面量自匹配
const silentFallbackPatterns = [
  ['catch(() => ', 'null)'],
  ['catch(() => ', '[])'],
  ['catch(() => ', '({})'],
  ['catch(() => ', '{})'],
  ['catch(() => ', 'undefined)'],
].map((parts) => parts.join(''))

describe('移动端静默兜底归零（T02701）', () => {
  it('mobile 目录下不再有 catch 成 null/[]/{}/undefined 的静默兜底', () => {
    const offenders: string[] = []
    for (const p of walk(MOBILE_ROOT)) {
      const lines = readFileSync(p, 'utf-8').split(/\r?\n/)
      lines.forEach((line, i) => {
        for (const needle of silentFallbackPatterns) {
          if (line.includes(needle)) {
            offenders.push(`${p.replace(SRC_ROOT, '')}:${i + 1}: ${line.trim()}`)
          }
        }
      })
    }
    expect(offenders, `接口失败被写成空态，请用 useFailedSources 记账 + LoadFailedBar：\n${offenders.join('\n')}`).toEqual([])
  })

  const converted = [
    'pages/Market/index.tsx',
    'pages/Export/index.tsx',
    'pages/ChatbotConfig/index.tsx',
    'pages/Chatbot/index.tsx',
    'pages/Logs/index.tsx',
    // T02718：列表/状态页接入显式失败态（config 表单页另立单）
    'pages/Items/index.tsx',
    'pages/Evaluations/index.tsx',
    'pages/Timeline/index.tsx',
    'pages/AntiCrawl/index.tsx',
    'pages/Notifications/index.tsx',
    'pages/ErrorLogs/index.tsx',
    'pages/DatabaseAdmin/index.tsx',
    'pages/VersionManager/index.tsx',
    'pages/Cleanup/index.tsx',
    'pages/BatchRefresh/index.tsx',
    // T02978：配置/表单页三态（加载中 / 失败可重试 / 成功），不再永久 Spin
    'pages/PriceStrategy/index.tsx',
    'pages/BuyConfig/index.tsx',
    'pages/SearchConfig/index.tsx',
    'pages/AIConfig/index.tsx',
    'pages/EvalRules/index.tsx',
    'pages/NotifierChannels/index.tsx',
    'pages/About/index.tsx',
  ]

  converted.forEach((rel) => {
    it(`${rel} 用共用的失败账 + 窄屏失败条`, () => {
      const src = readFileSync(join(MOBILE_ROOT, rel), 'utf-8')
      // 只断言出现名字会被 import 行蒙混过关：必须落到调用点与 JSX 上
      expect(src, `${rel} 应调用 useFailedSources 记账（仅 import 不算）`).toMatch(/useFailedSources[<(]/)
      expect(src, `${rel} 应渲染 <LoadFailedBar />（仅 import 不算）`).toContain('<LoadFailedBar')
    })

    it(`${rel} 声明的每个数据源都有对应的失败态`, () => {
      const src = readFileSync(join(MOBILE_ROOT, rel), 'utf-8')
      const typeLine = src.match(/type\s+\w*Source\s*=\s*([^;\n]+)/)
      expect(typeLine, `${rel} 缺少 \`type XxxSource = 'a' | 'b'\` 数据源声明`).not.toBeNull()
      const keys = [...typeLine![1].matchAll(/'([^']+)'/g)].map((m) => m[1])
      expect(keys.length, `${rel} 数据源声明解析为空`).toBeGreaterThan(0)
      keys.forEach((key) => {
        expect(src, `${rel} 的 ${key} 没有中文名映射`).toContain(`${key}:`)
        expect(
          src,
          `${rel} 的 ${key} 只记了账却没接失败态（用户仍会看到空态冒充成功）`,
        ).toContain(`SOURCE_LABELS.${key}`)
      })
    })
  })

  it('失败账只有一份实现：Dashboard 也走 useFailedSources，不留本地副本', () => {
    const dash = readFileSync(join(SRC_ROOT, 'pages/Dashboard/index.tsx'), 'utf-8')
    expect(dash).toContain('useFailedSources')
    // 原先的模块级 settled() / 本地 setFailedSources 已删掉，两套逻辑不能并存
    expect(dash).not.toContain('setFailedSources')
    expect(dash).not.toContain('function settled')
  })

  it('窄屏失败条与桌面端 Alert 变体各就各位', () => {
    expect(existsSync(join(MOBILE_ROOT, 'components/LoadFailedBar.tsx'))).toBe(true)
    expect(existsSync(join(SRC_ROOT, 'components/FetchFailedHint.tsx'))).toBe(true)
    const bar = readFileSync(join(MOBILE_ROOT, 'components/LoadFailedBar.tsx'), 'utf-8')
    // 移动端屏幕窄：单行 role=alert + 重试，不用桌面端那种 message + description 两行组件
    expect(bar).toContain('role="alert"')
    expect(bar).toContain('加载失败')
  })
})
