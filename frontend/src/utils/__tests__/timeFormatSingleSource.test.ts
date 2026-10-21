import { describe, it, expect } from 'vitest'
import { readFileSync, readdirSync, existsSync } from 'node:fs'
import { join, resolve } from 'node:path'

// T02695：同一份今日告警载荷（TodayAlert）在两个入口曾有三种时间长相——
// 抽屉裸 ISO、抽屉裸秒、雷达「N 分钟前」。收口到 utils/timeFormat 一份 helper 之后，
// 这里禁止这两个文件再把手工格式化写回去（同 T02693/T02716 的裸字面串钉法）。
// T02884 把同一形状的位点继续往上加（棘轮只增不减）。

const SRC_ROOT = resolve(__dirname, '../..')
const CLEANED_FILES = [
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
      const src = read(rel)
      // 模板串里的 `${o.created_at}` 与 JSX 里的 `{o.created_at}` 是同一个病，两种写法都要拦
      for (const m of src.matchAll(/\$\{[\w.]+\.created_at\}/g)) {
        offenders.push(`${rel}: ${m[0]}`)
      }
      for (const m of src.matchAll(/\{\s*[\w.]+\.created_at\s*\}/g)) {
        offenders.push(`${rel}: ${m[0]}`)
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
        // 且必须先经 Intl 落地再切位（TaskDetail 的 runs 轴），不能直接切库里的 ISO 串
        if (/toLocaleString/.test(line)) continue
        offenders.push(`${rel}: ${line.trim()}`)
      }
    }
    expect(offenders, `直接切 ISO 是第四套口径（雷达低分曾这么干）：\n${offenders.join('\n')}`).toEqual([])
  })

  it('禁止裸秒数与「分钟前」两种时长写法（必须走 formatDuration）', () => {
    const offenders: string[] = []
    for (const rel of CLEANED_FILES) {
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
