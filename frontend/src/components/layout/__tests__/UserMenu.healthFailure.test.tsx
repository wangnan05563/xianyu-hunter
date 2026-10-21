// frontend/src/components/layout/__tests__/UserMenu.healthFailure.test.tsx
// T02700：健康面板两路数据（统一结论 + legacy 明细）失败时的口径。
// 原实现 getUnifiedHealth().catch(() => null) / checkCookieHealth().catch(() => null)
// 把后端故障压成「无法获取 Cookie 状态」的 Empty 空态，与抽屉里的「无档案数据」同一个病根：
// 读者分不清是「没有 Cookie」还是「服务没答话」。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { AuthMe } from '../../../api/types'
import type { CookieHealthReport, UnifiedHealthReport } from '../../../api/auth'

vi.mock('../../../utils/storage', () => ({
  storage: { getItem: vi.fn(() => null), setItem: vi.fn(), removeItem: vi.fn() },
}))

const { authApiMock } = vi.hoisted(() => ({
  authApiMock: {
    getUnifiedHealth: vi.fn(),
    checkCookieHealth: vi.fn(),
    refreshMe: vi.fn(() => Promise.resolve({ ok: true })),
    logout: vi.fn(() => Promise.resolve({ ok: true })),
    getSavedCookieInfo: vi.fn(() => Promise.resolve({ has_cookies: true, logged_in: true })),
  },
}))

vi.mock('../../../api', () => ({ authApi: authApiMock }))

import UserMenu from '../UserMenu'

const unified: UnifiedHealthReport = {
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
    cookie_count: 7,
    identity_valid: ['cookie2'],
    identity_expired: [],
    identity_missing: [],
    has_valid_m5tk: true,
    fresh: true,
  }],
}

const legacy: CookieHealthReport = {
  ok: true,
  is_valid: true,
  reason: 'ok',
  cookie_count: 22,
  key_cookies_found: ['cookie2'],
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

const userInfo = {
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

const ERR = new Error('500')
// 刷新按钮走 withUserInfo 路径，内部有 1.5s 等后端重抓昵称的固定延迟，等待需放宽
const WT = { timeout: 6000 }

function renderMenu() {
  return render(
    <MemoryRouter>
      <UserMenu userInfo={userInfo} />
    </MemoryRouter>,
  )
}

// hover 打开受控 Popover：这条路径不带 1.5s 昵称重抓延迟，用于首屏检查
async function openPanel() {
  fireEvent.mouseEnter(screen.getByLabelText('悬浮查看 Cookie 状态'))
  await waitFor(() => expect(screen.getByLabelText('刷新用户信息与健康状态')).toBeInTheDocument(), WT)
}

// 面板已打开时 hover 不会再触发 onOpenChange，再检查一次改点刷新按钮（含 1.5s 延迟）
function recheck() {
  fireEvent.click(screen.getByLabelText('刷新用户信息与健康状态'))
}

beforeEach(() => {
  vi.clearAllMocks()
  authApiMock.getUnifiedHealth.mockResolvedValue(unified)
  authApiMock.checkCookieHealth.mockResolvedValue(legacy)
})

describe('健康面板失败态（T02700）', { timeout: 20000 }, () => {
  it('两路都失败时给错误态与重试，不留「无法获取 Cookie 状态」的空态', async () => {
    authApiMock.getUnifiedHealth.mockRejectedValue(ERR)
    authApiMock.checkCookieHealth.mockRejectedValue(ERR)
    renderMenu()
    await openPanel()
    await waitFor(() => expect(screen.getByText('登录态健康检查加载失败')).toBeInTheDocument(), WT)
    // 「健康」标签与空态文案都不能出现
    expect(screen.queryByText('登录态正常')).not.toBeInTheDocument()
    expect(screen.queryByText('无法获取 Cookie 状态')).not.toBeInTheDocument()
  })

  it('健康结论属于「现状陈述」：刷新失败时不铺旧结论，只给重试', async () => {
    renderMenu()
    await openPanel()
    await waitFor(() => expect(screen.getByText('登录态正常')).toBeInTheDocument(), WT)
    // 第二次刷新失败：面板不能继续显示上一轮的「登录态正常」
    authApiMock.getUnifiedHealth.mockRejectedValue(ERR)
    recheck()
    await waitFor(() => expect(screen.getByText('登录态健康检查加载失败')).toBeInTheDocument(), WT)
    expect(screen.queryByText('登录态正常')).not.toBeInTheDocument()
  })

  it('重试成功后错误条消失、结论恢复', async () => {
    authApiMock.getUnifiedHealth.mockRejectedValue(ERR)
    renderMenu()
    await openPanel()
    await waitFor(() => expect(screen.getByText('登录态健康检查加载失败')).toBeInTheDocument(), WT)
    authApiMock.getUnifiedHealth.mockResolvedValue(unified)
    fireEvent.click(screen.getByRole('button', { name: /重\s*试/ }))
    await waitFor(() => expect(screen.getByText('登录态正常')).toBeInTheDocument(), WT)
    expect(screen.queryByText('登录态健康检查加载失败')).not.toBeInTheDocument()
  })

  it('只有 legacy 明细失败时结论仍展示，但明细缺失要说明，Cookie 数改用统一结论汇总', async () => {
    authApiMock.checkCookieHealth.mockRejectedValue(ERR)
    renderMenu()
    await openPanel()
    await waitFor(() => expect(screen.getByText('登录态正常')).toBeInTheDocument(), WT)
    expect(screen.getByText('Cookie 明细本次未取到，分层与安全标记无法展示')).toBeInTheDocument()
    expect(screen.queryByText('✓ 已就绪')).not.toBeInTheDocument()
    // 统一结论里 sources 合计 7 个，不能被失败的 legacy 值冒充
    expect(screen.getByText('7 个')).toBeInTheDocument()
    expect(screen.queryByText('22 个')).not.toBeInTheDocument()
  })

  it('刷新时只有 legacy 明细失败：上一轮的分层标记与 Cookie 数都要撤下', async () => {
    renderMenu()
    await openPanel()
    // 首轮两路都成功：legacy 的 22 个与分层标记正常展示
    await waitFor(() => expect(screen.getByText('22 个')).toBeInTheDocument(), WT)
    // 三层（身份/会话/跟踪）全就绪，所以这个文案本来就不止一处
    expect(screen.getAllByText('✓ 已就绪').length).toBeGreaterThan(0)
    // 第二轮只挂 legacy 这一路。Cookie 明细属于「现状陈述」，旧值继续摆着就会被读成「现在还是 22 个」
    authApiMock.checkCookieHealth.mockRejectedValue(ERR)
    recheck()
    await waitFor(
      () => expect(screen.getByText('Cookie 明细本次未取到，分层与安全标记无法展示')).toBeInTheDocument(),
      WT,
    )
    expect(screen.queryAllByText('✓ 已就绪')).toHaveLength(0)
    expect(screen.queryByText('22 个')).not.toBeInTheDocument()
    // 汇总数退回统一结论的 sources 合计
    expect(screen.getByText('7 个')).toBeInTheDocument()
    expect(screen.getByText('登录态正常')).toBeInTheDocument()
  })

  it('诊断抽屉：结论没取到时不展示诊断入口也不给「无档案数据」空态', async () => {
    authApiMock.getUnifiedHealth.mockRejectedValue(ERR)
    renderMenu()
    await openPanel()
    await waitFor(() => expect(screen.getByText('登录态健康检查加载失败')).toBeInTheDocument(), WT)
    expect(screen.queryByText('诊断详情')).not.toBeInTheDocument()
    expect(screen.queryByText('无档案数据')).not.toBeInTheDocument()
  })

  it('诊断抽屉：取到结论但确实没有档案时，才给「无档案数据」空态', async () => {
    authApiMock.getUnifiedHealth.mockResolvedValue({ ...unified, sources: [] })
    renderMenu()
    await openPanel()
    await waitFor(() => expect(screen.getByText('登录态正常')).toBeInTheDocument(), WT)
    fireEvent.click(screen.getByText('诊断详情'))
    await waitFor(() => expect(screen.getByText('登录态诊断详情')).toBeInTheDocument(), WT)
    expect(screen.getByText('无档案数据')).toBeInTheDocument()
    expect(screen.queryByText('登录态健康检查加载失败')).not.toBeInTheDocument()
  })

  it('诊断抽屉开着时刷新失败：旧档案卡片要换成错误态，不能继续冒充本次诊断', async () => {
    renderMenu()
    await openPanel()
    await waitFor(() => expect(screen.getByText('登录态正常')).toBeInTheDocument(), WT)
    fireEvent.click(screen.getByText('诊断详情'))
    await waitFor(() => expect(screen.getAllByText('cookies_default.json').length).toBeGreaterThan(0), WT)
    // 抽屉不受面板错误态影响，会继续用 state 里的旧 unified 渲染 —— 这一条钉住它必须让位给错误态
    authApiMock.getUnifiedHealth.mockRejectedValue(ERR)
    recheck()
    await waitFor(() => expect(screen.getAllByText('登录态健康检查加载失败').length).toBeGreaterThan(0), WT)
    expect(screen.queryByText('cookies_default.json')).not.toBeInTheDocument()
    expect(screen.queryByText('无档案数据')).not.toBeInTheDocument()
  })
})
