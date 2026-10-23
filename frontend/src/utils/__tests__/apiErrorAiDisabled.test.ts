// @vitest-environment node
// T02890：AI 总开关关闭的 403 必须在 API 层「判定一次」，
// 页面不得再各自把任意 403 说成「AI 未开启」，也不得给「稍后重试」这种无效建议。
import { describe, it, expect } from 'vitest'
import {
  AI_DISABLED_CODE, AI_DISABLED_FALLBACK, extractApiError, isAiDisabledError,
} from '../apiError'

const axiosErr = (status: number, data: unknown) => ({ response: { status, data } })

describe('isAiDisabledError：机器码优先，文案兜底', () => {
  it('403 + code=ai_disabled 判定为开关关闭', () => {
    expect(isAiDisabledError(axiosErr(403, { code: AI_DISABLED_CODE, detail: 'AI 功能已关闭，请在「AI 服务」配置页面开启' })))
      .toBe(true)
  })

  it('旧后端没有 code 时按 detail 前缀兜底', () => {
    expect(isAiDisabledError(axiosErr(403, { detail: 'AI 功能已关闭，请在「AI 服务」配置页面开启' }))).toBe(true)
  })

  it('code 分支本身要成立：detail 换成别的语言/留空也认（证明不是只在 grep 中文）', () => {
    expect(isAiDisabledError(axiosErr(403, { code: AI_DISABLED_CODE, detail: 'AI feature is off' }))).toBe(true)
    expect(isAiDisabledError(axiosErr(403, { code: AI_DISABLED_CODE }))).toBe(true)
  })

  it('其它 403（权限类）不得被说成 AI 未开启', () => {
    for (const data of [{ detail: '无权访问该资源' }, { code: 'forbidden', detail: 'nope' }, 'AI 功能已关闭']) {
      expect(isAiDisabledError(axiosErr(403, data)), JSON.stringify(data)).toBe(false)
    }
  })

  it('非 403 与无响应对象一律为 false', () => {
    expect(isAiDisabledError(axiosErr(401, { code: AI_DISABLED_CODE }))).toBe(false)
    expect(isAiDisabledError(new Error('network down'))).toBe(false)
    expect(isAiDisabledError(undefined)).toBe(false)
  })
})

describe('extractApiError：开关关闭时的措辞', () => {
  const off = axiosErr(403, { code: AI_DISABLED_CODE, detail: 'AI 功能已关闭，请在「AI 服务」配置页面开启' })

  it('优先原样转述后端指向开关的 detail', () => {
    expect(extractApiError(off)).toBe('AI 功能已关闭，请在「AI 服务」配置页面开启')
  })

  it('后端没给 detail 时兜底文案指向开关，且不含「稍后重试」', () => {
    const bare = axiosErr(403, { code: AI_DISABLED_CODE })
    expect(extractApiError(bare)).toBe(AI_DISABLED_FALLBACK)
    expect(AI_DISABLED_FALLBACK).toContain('配置-AI 服务')
    expect(AI_DISABLED_FALLBACK).not.toContain('稍后重试')
  })

  it('权限类 403 仍走 detail，不会被改写成 AI 文案', () => {
    expect(extractApiError(axiosErr(403, { detail: '无权访问该资源' }))).toBe('无权访问该资源')
  })
})
