import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import UserMenu from '../UserMenu'
import type { AuthMe } from '../../../api/types'

// UserMenu 依赖 storage/cookieHealth 请求，渲染期即触发，做静默 mock
vi.mock('../../../utils/storage', () => ({
  storage: { getItem: vi.fn(() => null), setItem: vi.fn(), removeItem: vi.fn() },
}))

const renderMenu = (userInfo: AuthMe) =>
  render(
    <MemoryRouter>
      <UserMenu userInfo={userInfo} />
    </MemoryRouter>
  )

describe('UserMenu 顶栏账号名（T01606 现场数据）', () => {
  it('Cookie 有效但昵称为空时展示账号 ID，不再与 Cookie 状态自相矛盾', () => {
    // 修复后 /api/auth/me 的真实返回（隔离实例 8123，用户 2026-10-08 扫码登录数据）
    renderMenu({
      logged_in: true,
      user_id: '135379349',
      nick: '',
      avatar_url: '',
      fetched_at: 0,
      detecting: true,
      local_username: '135379349',
      nickname: '',
      custom_alias: '',
    })
    expect(screen.queryByText('未登录')).toBeNull()
    expect(screen.getAllByText('135379349').length).toBeGreaterThan(0)
  })

  it('真正未登录时仍展示未登录', () => {
    renderMenu({ logged_in: false, user_id: '', nick: '' })
    expect(screen.getAllByText('未登录').length).toBeGreaterThan(0)
  })
})
