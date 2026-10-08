import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import UserMenu from '../UserMenu'
import type { AuthMe } from '../../../api/types'

// UserMenu 依赖 storage / cookieHealth 请求，渲染期即触发，做静默 mock
vi.mock('../../../utils/storage', () => ({
  storage: { getItem: vi.fn(() => null), setItem: vi.fn(), removeItem: vi.fn() },
}))

const renderMenu = (userInfo: AuthMe) =>
  render(
    <MemoryRouter>
      <UserMenu userInfo={userInfo} />
    </MemoryRouter>
  )

// 打开悬浮面板：面板走 antd Popover portal，受控 open + 动画，需等待挂载
const openPanel = async () => {
  const trigger = screen.getByLabelText('悬浮查看 Cookie 状态')
  fireEvent.click(trigger)
  await waitFor(() => {
    expect(screen.getByLabelText('刷新用户信息与健康状态')).toBeTruthy()
  })
}

describe('UserMenu 昵称兜底与未同步提示（T01633 / T01634）', () => {
  it('昵称抓取失败时用 Cookie 账号名兜底，并明确标注为「账号名」而非「闲鱼昵称」', async () => {
    renderMenu({
      logged_in: true,
      user_id: '135379349',
      nick: '',
      avatar_url: '',
      fetched_at: 0,
      local_username: 'dosufo',
      nickname: '',
      custom_alias: '',
      display_name_source: 'cookie_account',
      nick_sync_state: 'failed',
      nick_sync_error: 'auth_helper 退出码 1: ... has been closed',
    })
    await openPanel()
    expect(screen.getAllByText('dosufo').length).toBeGreaterThan(0)
    expect(screen.getByText('账号名：dosufo')).toBeTruthy()
    // 兜底名不得被标成闲鱼昵称
    expect(screen.queryByText('闲鱼昵称：dosufo')).toBeNull()
  })

  it('刷新失败且无真实昵称时显示「昵称未同步」提示，不再静默空值', async () => {
    renderMenu({
      logged_in: true,
      user_id: '135379349',
      nick: '',
      avatar_url: '',
      fetched_at: 0,
      local_username: 'dosufo',
      display_name_source: 'cookie_account',
      nick_sync_state: 'failed',
      nick_sync_error: 'auth_helper 退出码 1',
    })
    await openPanel()
    expect(screen.getByText(/昵称未同步/)).toBeTruthy()
  })

  it('已拿到真实昵称时不显示「昵称未同步」提示', async () => {
    renderMenu({
      logged_in: true,
      user_id: '135379349',
      nick: '南屿轻舟',
      avatar_url: '',
      fetched_at: 1791473387,
      local_username: '南屿轻舟',
      nickname: '南屿轻舟',
      display_name_source: 'userinfo_nick',
      nick_sync_state: 'ok',
    })
    await openPanel()
    expect(screen.queryByText(/昵称未同步/)).toBeNull()
  })
})
