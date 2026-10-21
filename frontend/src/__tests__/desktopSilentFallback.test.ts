// frontend/src/__tests__/desktopSilentFallback.test.ts
// T02700 桌面端假回执清零：把已改造文件钉成棘轮。
// 静默兜底（catch 成 null/[]/{}）把「没取到」压成「取到 0 条」，窄屏/宽屏都是同一个病根，
// 移动端归零见 mobile/__tests__/mobileSilentFallback.test.ts（T02701），本文件管桌面端。
//
// 口径与 T02586 一致：Promise.all([ 换 allSettled、失败保留上一次数据但显式声明、
// 数字用 — 而非 0、空态与错误态分开。
// 注意：ban 的是「把请求结果替换成空值」的兜底，fetchHealth().catch(() => undefined)
// 这种「函数本身不会 reject、只用于抑制 floating promise」的写法不在禁用范围。
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'

const SRC_ROOT = resolve(__dirname, '..')

function read(rel: string): string {
  return readFileSync(join(SRC_ROOT, rel), 'utf-8')
}

/** 运行时拼出被禁用的写法，避免本文件里的字面量自匹配 */
const silentFallbackNeedles = [
  ['catch(() => ', 'null)'],
  ['catch(() => ', '[])'],
  ['catch(() => ', '({})'],
  ['catch(() => ', '{})'],
  ['Promise.', 'all(['],
].map((parts) => parts.join(''))

const CLEANED = [
  'pages/Tasks/TaskDetail.tsx',
  'pages/Tasks/TaskList.tsx',
  'pages/Chatbot/Config.tsx',
  'pages/Config/AIConfig/index.tsx',
  'components/layout/UserMenu.tsx',
]

describe('桌面端静默兜底归零（T02700）', () => {
  CLEANED.forEach((rel) => {
    it(`${rel} 不再把请求失败压成空值，也不再整批 Promise.all`, () => {
      const lines = read(rel).split(/\r?\n/)
      const offenders: string[] = []
      lines.forEach((line, i) => {
        for (const needle of silentFallbackNeedles) {
          if (line.includes(needle)) offenders.push(`${rel}:${i + 1}: ${line.trim()}`)
        }
      })
      expect(
        offenders,
        `接口失败被写成空态，请用 useFailedSources 记账 + FetchFailedHint/DataBlock：\n${offenders.join('\n')}`,
      ).toEqual([])
    })
  })

  // 只记了账不接失败态 = 改了个寂寞：声明的每个数据源都必须有对应的错误展示位
  const withSourceLedger = [
    'pages/Tasks/TaskDetail.tsx',
    'pages/Chatbot/Config.tsx',
    'pages/Config/AIConfig/index.tsx',
    'components/layout/UserMenu.tsx',
  ]

  withSourceLedger.forEach((rel) => {
    it(`${rel} 声明的每个数据源都有失败态接住`, () => {
      const src = read(rel)
      expect(src, `${rel} 应使用共用的 useFailedSources`).toContain('useFailedSources')
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

  it('三态组件与共用失败账各一份，不再各页自造', () => {
    expect(read('components/DataBlock.tsx')).toContain('FetchFailedHint')
    const hook = read('hooks/useFailedSources.ts')
    expect(hook).toContain('settle')
    expect(hook).toContain('track')
    // TaskDetail 原先自带 settled()，与 hook 并存会出现两套口径
    expect(read('pages/Tasks/TaskDetail.tsx')).not.toContain('function settled')
  })

  it('批量恢复预检：部分预检请求失败时不能当作「全部可恢复」直接执行', () => {
    const src = read('pages/Tasks/TaskList.tsx')
    // 预检改 allSettled 后，取到的条数与选中条数必须对齐，缺口要显式问用户
    expect(src).toContain('unchecked')
    expect(src).toContain('预检未完成')
  })

  it('AI 开关确认框在数据没取到时不谎报受影响数量', () => {
    const page = read('pages/Config/AIConfig/index.tsx')
    expect(page).toContain('!!failed.config || !!failed.usage')
    expect(page).toContain('disabled={!!failed.config}')
  })
})
