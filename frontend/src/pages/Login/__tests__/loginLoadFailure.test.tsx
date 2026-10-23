// frontend/src/pages/Login/__tests__/loginLoadFailure.test.tsx
// T02939（源自 T02899）：登录页两路数据的失败态原先只有静态/文案级证据。
// 钉住渲染级行为：接口 reject 时必须出现「××加载失败」+ 重试，
// 且不得把「取不到」渲染成「还没保存过 Cookie / 浏览器不存在」这类成功态。
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const { apiMocks } = vi.hoisted(() => ({
  apiMocks: {
    getSavedCookieInfo: vi.fn(),
    getBrowserImportStatus: vi.fn(),
    getMe: vi.fn(),
  },
}))

vi.mock('../../../api', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  const a = actual as Record<string, Record<string, unknown>>
  return {
    ...actual,
    authApi: {
      ...a.authApi,
      getSavedCookieInfo: apiMocks.getSavedCookieInfo,
      getBrowserImportStatus: apiMocks.getBrowserImportStatus,
      getMe: apiMocks.getMe,
    },
  }
})

// 背景是 p5 画布动画，jsdom 没有 canvas 实现
vi.mock('../../../components/TidalForagers', () => ({ default: () => null }))

import LoginPage from '../index'
import { ThemeProvider } from '../../../contexts/ThemeContext'

const ERR = new Error('500')
const OK_COOKIE = { has_cookies: true, cookie_count: 2, method: 'manual' }
const OK_STATUS = {
  edge: { exists: false, has_goofish_cookie: false },
  chrome: { exists: false, has_goofish_cookie: false },
}

let fetchMock: ReturnType<typeof vi.fn>

function renderPage() {
  return render(
    <ThemeProvider>
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    </ThemeProvider>,
  )
}

async function openTab(name: RegExp) {
  await waitFor(() => expect(screen.getByRole('tab', { name })).toBeInTheDocument())
  fireEvent.click(screen.getByRole('tab', { name }))
}

beforeEach(() => {
  vi.clearAllMocks()
  apiMocks.getMe.mockResolvedValue(undefined)
  apiMocks.getSavedCookieInfo.mockResolvedValue(OK_COOKIE)
  apiMocks.getBrowserImportStatus.mockResolvedValue(OK_STATUS)
  fetchMock = vi.fn().mockResolvedValue({ json: async () => ({ ok: true, cookies: {} }) })
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('登录页数据源失败态（T02939）', () => {
  it('已保存 Cookie 取不到：错误条 + 重试，且不冒充「还没保存过」', async () => {
    apiMocks.getSavedCookieInfo.mockRejectedValue(ERR)
    fetchMock.mockRejectedValue(ERR)
    renderPage()
    await openTab(/Cookie 注入/)

    await waitFor(() => {
      expect(screen.getByText('已保存 Cookie 状态加载失败')).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: /重\s*试/ })).toBeInTheDocument()
    // 失败时必须明说「这不是还没保存过 Cookie」
    expect(screen.getByText(/这不是「还没保存过 Cookie」/)).toBeInTheDocument()
    // 也不能出现成功态摘要
    expect(screen.queryByText(/个 Cookie（来源/)).not.toBeInTheDocument()
  })

  it('重试成功后错误条消失并渲染真实摘要', async () => {
    apiMocks.getSavedCookieInfo.mockRejectedValueOnce(ERR)
    fetchMock.mockRejectedValueOnce(ERR)
    renderPage()
    await openTab(/Cookie 注入/)
    await waitFor(() => expect(screen.getByText('已保存 Cookie 状态加载失败')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /重\s*试/ }))

    await waitFor(() => {
      expect(screen.queryByText('已保存 Cookie 状态加载失败')).not.toBeInTheDocument()
    })
    expect(screen.getByText(/个 Cookie（来源: manual）/)).toBeInTheDocument()
    expect(apiMocks.getSavedCookieInfo).toHaveBeenCalledTimes(2)
  })

  it('浏览器状态取不到：错误条 + 重试，且导入按钮不冒充「可以导入」', async () => {
    apiMocks.getBrowserImportStatus.mockRejectedValueOnce(ERR)
    renderPage()
    await openTab(/浏览器导入/)

    await waitFor(() => {
      expect(screen.getByText('浏览器导入状态加载失败')).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: /重\s*试/ })).toBeInTheDocument()
    // 状态未知时不允许点「自动关闭并导入」
    expect(screen.getByRole('button', { name: /自动关闭 Edge 并导入/ })).toBeDisabled()
    expect(screen.getByRole('button', { name: /自动关闭 Chrome 并导入/ })).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: /重\s*试/ }))
    await waitFor(() => {
      expect(screen.queryByText('浏览器导入状态加载失败')).not.toBeInTheDocument()
    })
    expect(apiMocks.getBrowserImportStatus).toHaveBeenCalledTimes(2)
  })

  it('两路都成功时不显示任何错误条（失败账不会常驻）', async () => {
    renderPage()
    await openTab(/Cookie 注入/)
    await waitFor(() => expect(screen.getByText(/个 Cookie（来源: manual）/)).toBeInTheDocument())
    expect(screen.queryByText(/加载失败/)).not.toBeInTheDocument()

    await openTab(/浏览器导入/)
    await waitFor(() => expect(apiMocks.getBrowserImportStatus).toHaveBeenCalled())
    expect(screen.queryByText(/加载失败/)).not.toBeInTheDocument()
  })
})
