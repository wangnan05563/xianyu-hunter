import { describe, it, expect } from 'vitest'
import { computeDisplayName } from '../UserMenu'
import type { AuthMe } from '../../../api/types'

describe('computeDisplayName', () => {
  it('有昵称时优先展示可辨识名称', () => {
    const info: AuthMe = { logged_in: true, user_id: '135379349', local_username: '南屿轻舟', nick: '南屿轻舟' }
    expect(computeDisplayName(info)).toBe('南屿轻舟')
  })

  it('已登录但昵称抓取失败时展示账号 ID，不再显示未登录', () => {
    // 与同面板"Cookie 状态正常"矛盾的旧行为：名字字段全空 → 直接判"未登录"
    const info: AuthMe = { logged_in: true, user_id: '135379349', local_username: '135379349', nick: '' }
    expect(computeDisplayName(info)).toBe('135379349')
  })

  it('已登录且无 user_id 时展示已登录占位', () => {
    expect(computeDisplayName({ logged_in: true })).toBe('已登录')
  })

  it('后端标记检测中时展示检测中', () => {
    expect(computeDisplayName({ logged_in: false, detecting: true })).toBe('检测中')
  })

  it('未登录时仍展示未登录', () => {
    expect(computeDisplayName({ logged_in: false, user_id: '', nick: '' })).toBe('未登录')
  })
})
