// T02579（PRD 4.5-3 / 4.5-4 / 4.5-6）反爬登录管理文案与失败态 — 纯函数单测
// 断言的是「说了什么」，与后端真实行为一一对应：
//   · invalidate_cookie_layer 走 manual=True，cookie_checker 自动同步跳过 manual_invalidate 层
//   · _merge_existing_with_incoming：同名覆盖 value、其余保留、新名按 .goofish.com 域写入
import { describe, expect, it } from 'vitest'

import {
  ANTI_CRAWL_SECTION_LABELS,
  COOKIE_MERGE_COPY,
  buildAnticrawlErrorBanner,
  buildImportOverrideCopy,
  buildInvalidateLayerCopy,
  describeAnticrawlError,
  layerLabelCn,
} from '../index'

describe('4.5-4 层名中文化', () => {
  it('英文枚举翻成中文并保留枚举名（审计日志用的就是它）', () => {
    expect(layerLabelCn('identity')).toBe('身份层（identity）')
    expect(layerLabelCn('session')).toBe('会话层（session）')
    expect(layerLabelCn('tracking')).toBe('追踪层（tracking）')
  })

  it('未知层名原样透出，不编造中文', () => {
    expect(layerLabelCn('future_layer')).toBe('future_layer')
  })
})

describe('4.5-4 主动失效确认四要素', () => {
  const c = buildInvalidateLayerCopy('identity', { valid: true, cookie_count: 3 })

  it('标题/动作中文化且带真实条数', () => {
    expect(c.title).toBe('确认失效身份层？')
    expect(c.action).toContain('身份层')
    expect(c.count).toBe('身份层当前记录 3 个 Cookie')
  })

  it('身份层写明会级联会话层，并声明不动 CookieStore 明文', () => {
    expect(c.scope).toContain('会话层')
    expect(c.scope).toContain('级联')
    expect(c.scope).toContain('不删除 CookieStore')
  })

  it('恢复成本按后端真实行为写：自动同步会跳过该层，不会被自愈', () => {
    expect(c.recovery).toContain('跳过')
    expect(c.recovery).toContain('不会被自愈恢复')
    expect(c.recovery).toContain('重新登录')
  })

  it('会话层不声称级联，条数缺省时如实写 0 而不是省略', () => {
    const s = buildInvalidateLayerCopy('session', { valid: true })
    expect(s.scope).not.toContain('级联')
    expect(s.count).toBe('会话层当前记录 0 个 Cookie')
  })
})

describe('4.5-3 加载失败原因可读', () => {
  it('401 给出可执行的下一步，而不是 http error', () => {
    expect(describeAnticrawlError({ response: { status: 401 } }))
      .toContain('请重新登录后重试')
  })

  it('其它状态码/超时/无 message 都有兜底', () => {
    expect(describeAnticrawlError({ response: { status: 503 } })).toBe('接口返回 503')
    expect(describeAnticrawlError({ message: 'timeout of 5000ms exceeded' })).toContain('超时')
    expect(describeAnticrawlError(new Error(''))).toBe('请求失败')
  })

  it('汇总条点名失败的是哪几块，并声明空白不等于没有数据', () => {
    expect(buildAnticrawlErrorBanner({})).toBeNull()
    expect(buildAnticrawlErrorBanner({ session: undefined })).toBeNull()
    const b = buildAnticrawlErrorBanner({
      session: '接口返回 500',
      cookieLayers: '未登录或登录已过期（401），请重新登录后重试',
    })
    expect(b?.failedLabels).toEqual([ANTI_CRAWL_SECTION_LABELS.session, ANTI_CRAWL_SECTION_LABELS.cookieLayers])
    expect(b?.text).toContain('2 项数据未能加载')
    expect(b?.text).toContain('不代表')
  })
})

describe('4.5-6 Cookie 合并语义与导入确认', () => {
  it('说明写清「合并 + 同名覆盖 + 未出现项保留」，不再用无依据的「原子更新」', () => {
    expect(COOKIE_MERGE_COPY).toContain('合并')
    expect(COOKIE_MERGE_COPY).toContain('同名项覆盖其值')
    expect(COOKIE_MERGE_COPY).toContain('未出现的项保持不变')
    expect(COOKIE_MERGE_COPY).toContain('.goofish.com')
    expect(COOKIE_MERGE_COPY).not.toContain('原子')
  })

  it('文本框脏时确认条数为「N 项 → M 项替换」', () => {
    const c = buildImportOverrideCopy(4, 9)
    expect(c.count).toContain('文本框现有 4 项')
    expect(c.count).toContain('9 项替换')
    expect(c.recovery).toContain('尚未写入后端')
  })

  it('文本框为空时不谎称会丢东西', () => {
    const c = buildImportOverrideCopy(0, 9)
    expect(c.count).toContain('文本框为空')
    expect(c.count).not.toContain('替换')
  })
})
