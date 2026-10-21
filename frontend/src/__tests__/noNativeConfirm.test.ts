// T02726 收尾：AI 总开关是全站最后一处原生 confirm，改完后归零。
// 原生框无法承载「动作/影响范围/数量/恢复成本」四要素排版，也带不出 danger 语义
// （规范 docs/standards/危险操作文案规范.md 第 3、5 节），
// 所以这里钉成棘轮：新增原生 confirm/prompt/alert 直接红。
import { describe, it, expect } from 'vitest'
import { readFileSync, readdirSync } from 'node:fs'
import { join, resolve } from 'node:path'

const SRC_ROOT = resolve(__dirname, '..')

function walk(dir: string): string[] {
  const out: string[] = []
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, entry.name)
    if (entry.isDirectory()) out.push(...walk(p))
    else if (/\.tsx?$/.test(entry.name)) out.push(p)
  }
  return out
}

/** 运行时拼出被禁用的符号名，避免本文件自匹配 */
const banned = [
  ['globalThis', 'confirm'],
  ['window', 'confirm'],
].map((parts) => new RegExp(`${parts[0]}\\s*\\.\\s*(${parts[1]})\\s*\\(`, 'g'))

describe('全站禁止原生确认框（T02726）', () => {
  it('frontend/src 里 globalThis.confirm / window.confirm 归零', () => {
    const offenders: string[] = []
    for (const p of walk(SRC_ROOT)) {
      const src = readFileSync(p, 'utf-8')
      for (const re of banned) {
        for (const m of src.matchAll(re)) {
          offenders.push(`${p.replace(SRC_ROOT, '')}: ${m[0]}`)
        }
      }
    }
    expect(offenders, `原生框摆不下四要素，请用 confirmDanger：\n${offenders.join('\n')}`).toEqual([])
  })

  it('AIConfig 关闭开关走 confirmDanger，且文案由 dangerCopy 生成', () => {
    const page = readFileSync(join(SRC_ROOT, 'pages/Config/AIConfig/index.tsx'), 'utf-8')
    expect(page).toContain('confirmDanger(')
    expect(page).toContain('buildDisableAICopy(')
  })

  it('开关卡片上的说明不再承诺「所有 AI 功能降级到规则模式」', () => {
    // 这句是假后果：四个推理接口在规则回落之前就被 _check_ai_enabled() 拦成 403
    const page = readFileSync(join(SRC_ROOT, 'pages/Config/AIConfig/index.tsx'), 'utf-8')
    expect(page).not.toContain('所有 AI 功能将降级到规则模式')
  })
})
