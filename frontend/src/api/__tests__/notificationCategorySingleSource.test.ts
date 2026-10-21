import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import {
  NOTIFICATION_CATEGORY_LABEL,
  NOTIFICATION_LEVEL_COLOR,
  NOTIFICATION_LEVEL_LABEL,
} from '../notifications'

// T02619：通知分类的唯一事实源在后端 domain/notification.py。
// 盯盘降价通知写的 category='price' 曾经既不在 API 白名单、也不在前端标签表里，
// 通知中心那条 Tag 取到 undefined 只显示一个空白框；桌面/移动两张表还把 auth
// 分别写成「登录」和「认证」。这里用跨语言源码断言把四处钉成一处（同 T02556 家族）。

const BACKEND_DOMAIN = resolve(
  __dirname,
  '../../../../backend/xianyu_hunter/domain/notification.py',
)
const DESKTOP_PAGE = resolve(__dirname, '../../pages/Notifications/index.tsx')
const MOBILE_PAGE = resolve(__dirname, '../../mobile/pages/Notifications/index.tsx')

/** 从后端 domain 模块抽取 `成员 = "key"` 与 `_CATEGORY_LABELS` 两张表 */
function parseBackendCategories(): Record<string, string> {
  const src = readFileSync(BACKEND_DOMAIN, 'utf-8')
  const enumBlock = /class NotificationCategory[^}]*\}/.exec(src)
  expect(enumBlock, '后端 domain/notification.py 未找到 NotificationCategory').toBeTruthy()
  const keys = [...enumBlock![0].matchAll(/^\s{4}[A-Z_]+\s*=\s*"([a-z_]+)"/gm)].map((m) => m[1])
  // 声明带类型注解：`_CATEGORY_LABELS: dict[NotificationCategory, str] = {`
  const labelBlock = /_CATEGORY_LABELS[^{]*\{([^}]*)\}/.exec(src)
  expect(labelBlock, '后端 domain/notification.py 未找到 _CATEGORY_LABELS').toBeTruthy()
  const labels = Object.fromEntries(
    [...labelBlock![0].matchAll(/NotificationCategory\.([A-Z_]+):\s*"([^"]+)"/g)]
      .map((m) => [m[1], m[2]]),
  )
  // 成员 → key → 标签三方对齐，缺一个都是半截改动
  const out: Record<string, string> = {}
  for (const key of keys) {
    const member = key.toUpperCase()
    expect(labels[member], `分类 ${key} 缺中文标签`).toBeTruthy()
    out[key] = labels[member]
  }
  return out
}

describe('通知分类单一事实源（T02619）', () => {
  it('price 有中文标签，不再是 undefined 空白', () => {
    expect(NOTIFICATION_CATEGORY_LABEL.price).toBe('盯盘')
  })

  it('auth 只有一套文案（登录），移动端不再写「认证」', () => {
    expect(NOTIFICATION_CATEGORY_LABEL.auth).toBe('登录')
  })

  it('前端标签表的 key 与文案逐字等于后端 domain', () => {
    const backend = parseBackendCategories()
    expect(Object.keys(NOTIFICATION_CATEGORY_LABEL).sort()).toEqual(Object.keys(backend).sort())
    for (const [key, label] of Object.entries(backend)) {
      expect(NOTIFICATION_CATEGORY_LABEL[key as keyof typeof NOTIFICATION_CATEGORY_LABEL], `分类 ${key} 文案漂移`)
        .toBe(label)
    }
  })

  it('level 文案与颜色覆盖全部等级', () => {
    expect(Object.keys(NOTIFICATION_LEVEL_LABEL).sort()).toEqual(['err', 'info', 'warn'])
    expect(NOTIFICATION_LEVEL_COLOR.warn).toBe('orange')
  })

  it('桌面与移动两页都消费共享常量，不再各自声明标签表', () => {
    for (const path of [DESKTOP_PAGE, MOBILE_PAGE]) {
      const src = readFileSync(path, 'utf-8')
      expect(src, `${path} 未引用 NOTIFICATION_CATEGORY_LABEL`).toContain('NOTIFICATION_CATEGORY_LABEL')
      expect(src, `${path} 仍自带一张 category 标签表`).not.toContain(
        "Record<NotificationItem['category'], string>",
      )
    }
  })
})
