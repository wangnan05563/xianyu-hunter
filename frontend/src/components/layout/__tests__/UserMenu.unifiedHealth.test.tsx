import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import UserMenu from '../UserMenu'
import type { AuthMe } from '../../../api/types'
import type { CookieHealthReport, UnifiedHealthReport } from '../../../api/auth'

// UserMenu 依赖 storage / authApi 请求，渲染期即触发，做静默 mock
vi.mock('../../../utils/storage', () => ({
  storage: { getItem: vi.fn(() => null), setItem: vi.fn(), removeItem: vi.fn() },
}))

// authApi 整体 mock：统一结论 + legacy 明细可控
const unifiedMock: UnifiedHealthReport = {
  ok: true,
  status: 'healthy',
  reasons: [],
  self_healed: false,
  actions: [],
  user_id: 'u1',
  freshest_source: 'cookies_default.json',
  expiry_ts: Date.now() / 1000 + 86400,
  expiry_human: '1 天 0 小时后过期',
  sources: [{
    source: 'cookies_default.json',
    method: 'browser',
    exported_at: Date.now() / 1000 - 60,
    cookie_count: 22,
    identity_valid: ['cookie2', 'sgcookie', 'unb'],
    identity_expired: [],
    identity_missing: [],
    has_valid_m5tk: true,
    fresh: true,
  }],
}

const legacyMock: CookieHealthReport = {
  ok: true,
  is_valid: true,
  reason: 'ok',
  cookie_count: 22,
  key_cookies_found: ['cookie2', 'unb'],
  expiry_ts: Date.now() / 1000 + 86400,
  expiry_human: '1 天 0 小时后过期',
  integrity: 'complete',
  integrity_reason: 'ok',
  layers: { identity: true, session: true, tracking: true },
  security_flags: { has_secure: true, has_httponly: true, is_session_cookie: false },
  exported_at: Date.now() / 1000 - 60,
  method: 'browser',
  elapsed_ms: 10,
}

// authApi 整体 mock：vi.mock 会被提升到文件顶部，mock 对象必须经 vi.hoisted 创建
const { authApiMock } = vi.hoisted(() => ({
  authApiMock: {
    getUnifiedHealth: vi.fn(() => Promise.resolve(null)),
    checkCookieHealth: vi.fn(() => Promise.resolve(null)),
    refreshMe: vi.fn(() => Promise.resolve({ ok: true })),
    logout: vi.fn(() => Promise.resolve({ ok: true })),
    getSavedCookieInfo: vi.fn(() => Promise.resolve({ has_cookies: true, logged_in: true })),
  },
}))

vi.mock('../../../api', () => ({ authApi: authApiMock }))

const userInfo: AuthMe = {
  logged_in: true,
  user_id: '135379349',
  nick: '南屿轻舟',
  avatar_url: '',
  fetched_at: 0,
  local_username: 'dosufo',
  nickname: '南屿轻舟',
  custom_alias: '',
  display_name_source: 'nickname',
  nick_sync_state: 'ok',
} as AuthMe

const renderMenu = () =>
  render(
    <MemoryRouter>
      <UserMenu userInfo={userInfo} />
    </MemoryRouter>
  )

const openPanel = async (expectText: string = '登录态正常') => {
  const trigger = screen.getByLabelText('悬浮查看 Cookie 状态')
  // click 打开受控 Popover（onOpenChange 不一定被 jsdom hover 模拟触发），
  // 再点刷新按钮确定性触发 fetchHealth；withUserInfo 路径含 1.5s 延迟，需放宽超时
  fireEvent.click(trigger)
  const refreshBtn = await screen.findByLabelText('刷新用户信息与健康状态')
  fireEvent.click(refreshBtn)
  await waitFor(() => {
    expect(screen.getByText(expectText)).toBeTruthy()
  }, { timeout: 4000 })
}

beforeEach(() => {
  vi.clearAllMocks()
  authApiMock.getUnifiedHealth.mockImplementation(() => Promise.resolve(unifiedMock))
  authApiMock.checkCookieHealth.mockImplementation(() => Promise.resolve(legacyMock))
})

describe('UserMenu 统一健康结论面板（T01778 / PRD FR-C1-5）', () => {
  it('healthy 时展示统一结论「登录态正常」与健康标签', async () => {
    renderMenu()
    await openPanel()
    expect(screen.getByText('健康')).toBeTruthy()
    // legacy 明细仍在：分层与安全标记（三层均就绪 → 3 行「✓ 已就绪」）
    expect(screen.getAllByText('✓ 已就绪').length).toBe(3)
  })

  it('self_healed=true 时展示「已自动修复」徽标', async () => {
    authApiMock.getUnifiedHealth.mockImplementation(() =>
      Promise.resolve({ ...unifiedMock, self_healed: true }))
    renderMenu()
    await openPanel()
    expect(screen.getByText('已自动修复')).toBeTruthy()
  })

  it('invalid 时展示失效结论、原因列表与修复引导按钮', async () => {
    authApiMock.getUnifiedHealth.mockImplementation(() =>
      Promise.resolve({
        ...unifiedMock,
        status: 'invalid',
        freshest_source: null,
        expiry_human: '未知',
        reasons: [
          { source: 'cookies_default.json', cookie: 'cookie2', issue: 'expired' },
        ],
        actions: ['relogin', 'import_json'],
      }))
    renderMenu()
    await openPanel('登录态失效')
    expect(screen.getByText('登录态失效')).toBeTruthy()
    expect(screen.getByText(/cookie2 已过期/)).toBeTruthy()
    expect(screen.getByText('重新登录')).toBeTruthy()
    expect(screen.getByText('导入登录态')).toBeTruthy()
  })

  it('诊断详情抽屉逐源展示档案评估明细', async () => {
    renderMenu()
    await openPanel()
    fireEvent.click(screen.getByText('诊断详情'))
    await waitFor(() => {
      expect(screen.getByText('登录态诊断详情')).toBeTruthy()
    })
    expect(screen.getByText('cookies_default.json')).toBeTruthy()
    // sources 明细：有效凭证列表与会话令牌状态
    expect(screen.getByText(/✓ 有效：cookie2、sgcookie、unb/)).toBeTruthy()
    expect(screen.getByText(/会话令牌：✓ 有效/)).toBeTruthy()
  })
})
