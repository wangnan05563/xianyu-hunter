import { describe, expect, it } from 'vitest'
import { classifyLiveSearchError } from '../liveSearchError'

// 构造与 taskLinkApi.live 抛出一致的 axios 兼容错误：{ response: { status, data } }
const httpError = (status: number, data: unknown, code?: string) =>
  Object.assign(new Error(`HTTP ${status}`), {
    response: { status, data },
    ...(code ? { code } : {}),
  })

describe('实时搜索错误分类：结构化 code 优先', () => {
  // 用中性状态码 400 构造：证明分类由 code 驱动，而不是被旧状态码/文案回落掩盖
  it('cookie_expired → 登录态失效', () => {
    const r = classifyLiveSearchError(httpError(400, { detail: '任意新文案', code: 'cookie_expired' }))
    expect(r.kind).toBe('session_expired')
    expect(r.code).toBe('cookie_expired')
  })

  it('cookie_stale → 登录态失效', () => {
    expect(classifyLiveSearchError(httpError(400, { code: 'cookie_stale' })).kind).toBe('session_expired')
  })

  it('cookie_missing → 登录态失效', () => {
    expect(classifyLiveSearchError(httpError(400, { code: 'cookie_missing' })).kind).toBe('session_expired')
  })

  it('cookie_sync_failed → 登录态失效（后端以 503 返回，但分类不应依赖状态码）', () => {
    const r = classifyLiveSearchError(httpError(400, { detail: '同步失败', code: 'cookie_sync_failed' }))
    expect(r.kind).toBe('session_expired')
  })

  it('browser_unavailable → 仅提示，不置登录态失效', () => {
    expect(classifyLiveSearchError(httpError(400, { code: 'browser_unavailable' })).kind).toBe('browser_unavailable')
  })

  it('scheduler_off → 仅提示，不置登录态失效', () => {
    expect(classifyLiveSearchError(httpError(400, { code: 'scheduler_off' })).kind).toBe('browser_unavailable')
  })

  it('code 与中文文案解耦：文案不含旧关键字也照常分支', () => {
    const r = classifyLiveSearchError(httpError(400, { detail: 'please login again', code: 'cookie_expired' }))
    expect(r.kind).toBe('session_expired')
    expect(r.detail).toBe('please login again')
  })

  it('未识别的新 code 回落到状态码/文案口径，不丢提示', () => {
    expect(classifyLiveSearchError(httpError(440, { code: 'future_code' })).kind).toBe('session_expired')
  })
})

describe('实时搜索错误分类：旧后端兼容回落', () => {
  it('无 code 的 440 + 已过期 → 登录态失效', () => {
    expect(classifyLiveSearchError(httpError(440, { detail: 'Cookie 已过期' })).kind).toBe('session_expired')
  })

  it('无 code 的 403 → 登录态失效（保持修复前行为）', () => {
    expect(classifyLiveSearchError(httpError(403, { detail: '搜索令牌临时过期' })).kind).toBe('session_expired')
  })

  it('无 code 的 503 → 浏览器不可用提示', () => {
    const r = classifyLiveSearchError(httpError(503, { detail: '浏览器实例未初始化' }))
    expect(r.kind).toBe('browser_unavailable')
    expect(r.detail).toBe('浏览器实例未初始化')
  })

  it('后台持锁 → browser_lock', () => {
    expect(classifyLiveSearchError(httpError(502, { detail: '系统正在执行后台搜索任务，请稍后重试' })).kind)
      .toBe('browser_lock')
  })

  it('ECONNABORTED / timeout → timeout', () => {
    expect(classifyLiveSearchError(httpError(0, { detail: 'timeout' }, 'ECONNABORTED')).kind).toBe('timeout')
  })

  it('无法识别 → unknown 且保留原文案', () => {
    const r = classifyLiveSearchError(httpError(400, { detail: '任务无关键词' }))
    expect(r.kind).toBe('unknown')
    expect(r.detail).toBe('任务无关键词')
  })
})
