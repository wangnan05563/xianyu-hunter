import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// T02695：同一份今日告警载荷（TodayAlert）在两个入口曾有三种时间长相——
// 抽屉裸 ISO、抽屉裸秒、雷达「N 分钟前」。收口到 utils/timeFormat 一份 helper 之后，
// 这里禁止这两个文件再把手工格式化写回去（同 T02693/T02716 的裸字面串钉法）。

const SRC_ROOT = resolve(__dirname, '../..')
const CLEANED_FILES = [
  'components/layout/MainLayout.tsx',
  'pages/Dashboard/components/AlertRadar.tsx',
]

function read(rel: string): string {
  return readFileSync(resolve(SRC_ROOT, rel), 'utf-8')
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
      for (const m of read(rel).matchAll(/\$\{[\w.]+\.created_at\}/g)) {
        offenders.push(`${rel}: ${m[0]}`)
      }
    }
    expect(offenders, `裸 ISO 会露出 T 和微秒，与订单表格列两套口径：\n${offenders.join('\n')}`).toEqual([])
  })

  it('禁止手工切 ISO 字符串当时间显示', () => {
    const offenders: string[] = []
    for (const rel of CLEANED_FILES) {
      for (const m of read(rel).matchAll(/\.slice\(\s*5\s*,\s*16\s*\)/g)) {
        offenders.push(`${rel}: ${m[0]}`)
      }
    }
    expect(offenders, `手工切位是第四套口径（雷达低分曾这么干）：\n${offenders.join('\n')}`).toEqual([])
  })

  it('禁止裸秒数与「分钟前」两种时长写法（必须走 formatDuration）', () => {
    const offenders: string[] = []
    for (const rel of CLEANED_FILES) {
      const src = read(rel)
      for (const m of src.matchAll(/\$\{[\w.() |]+\bage_sec[\w.() |]*\}s/g)) offenders.push(`${rel}: ${m[0]}`)
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
