import client from './client'
import type { AuthMe } from './types'

// 登录状态轮询响应
export interface LoginStatus {
  method: string | null
  status: 'idle' | 'running' | 'qr_ready' | 'success' | 'cancelled' | 'error' | 'timeout'
  message: string
  elapsed: number
  phase?: 'pending' | 'starting' | 'opening' | 'waiting' | 'already_logged' | 'running'
  child_elapsed?: number
  wait_elapsed?: number
  timings?: Record<string, number>
  qr_png_b64?: string
}

// Cookie 注入响应
export interface CookieInjectResult {
  ok: boolean
  injected?: number
  total_parsed?: number
  method?: string
  message?: string
  error?: string
  hint?: string
}

// 浏览器导入状态
export interface BrowserImportStatus {
  edge: { exists: boolean; has_goofish_cookie: boolean }
  chrome: { exists: boolean; has_goofish_cookie: boolean }
}

// Cookie 摘要信息
export interface SavedCookieInfo {
  has_cookies: boolean
  logged_in: boolean
  cookie_count?: number
  key_cookies_found?: string[]
  exported_at?: number
  method?: string
}

// Cookie 健康检查报告（轻量级，供状态栏悬浮面板使用）
export interface CookieHealthReport {
  ok: boolean
  is_valid: boolean
  reason: string
  cookie_count: number
  key_cookies_found: string[]
  expiry_ts: number | null
  expiry_human: string
  integrity: 'complete' | 'incomplete'
  integrity_reason: string
  layers: {
    identity: boolean
    session: boolean
    tracking: boolean
  }
  security_flags: {
    has_secure: boolean
    has_httponly: boolean
    is_session_cookie: boolean
  }
  exported_at: number
  method: string
  elapsed_ms: number
}

// 认证 API：管理当前登录态与闲鱼会话校验
export const authApi = {
  getMe: () => client.get<AuthMe>('/api/auth/me').then((r) => r.data),

  // 强制后台刷新用户信息（不等完成）
  refreshMe: () =>
    client.post<{ ok: boolean; message: string }>('/api/auth/me/refresh').then((r) => r.data),

  // 实际访问闲鱼页面验证会话有效性（区别于 /me 仅检查 Cookie 文件）
  verifySession: () =>
    client
      .post<{ ok: boolean; logged_in: boolean; message?: string; reason?: string }>(
        '/api/auth/verify-session',
      )
      .then((r) => r.data),

  // ===== 登录相关 =====

  // 启动浏览器窗口登录
  startBrowserLogin: () =>
    client
      .post<{ ok: boolean; method?: string; status?: string; message?: string; error?: string }>(
        '/api/auth/login',
        { method: 'browser' },
      )
      .then((r) => r.data),

  // 启动 QR 扫码登录
  startQrLogin: () =>
    client
      .post<{ ok: boolean; method?: string; status?: string; message?: string; error?: string }>(
        '/api/auth/login',
        { method: 'qr' },
      )
      .then((r) => r.data),

  // 轮询登录状态
  getLoginStatus: () =>
    client.get<LoginStatus>('/api/auth/login/status').then((r) => r.data),

  // 取消登录
  cancelLogin: () =>
    client.post<{ ok: boolean; message?: string }>('/api/auth/login/cancel').then((r) => r.data),

  // ===== Cookie 注入 =====

  // 手动粘贴 Cookie 字符串注入
  injectCookie: (cookieString: string) => {
    const formData = new FormData()
    formData.append('cookie_string', cookieString)
    return client
      .post<CookieInjectResult>('/api/auth/cookie', formData)
      .then((r) => r.data)
  },

  // 上传 Cookie 文件导入
  importCookieFile: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return client
      .post<CookieInjectResult>('/api/auth/cookie/file', formData)
      .then((r) => r.data)
  },

  // 获取已保存的 Cookie 摘要
  getSavedCookieInfo: () =>
    client.get<SavedCookieInfo>('/api/auth/cookie/saved').then((r) => r.data),

  // ===== 浏览器导入 =====

  // 检测可导入的浏览器状态
  getBrowserImportStatus: () =>
    client.get<BrowserImportStatus>('/api/auth/import-from-browser/status').then((r) => r.data),

  // 从指定浏览器导入 Cookie
  // auto_close: 检测到文件锁定时自动关闭浏览器进程后重试
  importFromBrowser: (browser: 'edge' | 'chrome', autoClose: boolean = false) =>
    client
      .post<CookieInjectResult>('/api/auth/import-from-browser', null, {
        params: { browser, auto_close: autoClose },
      })
      .then((r) => r.data),

  // 自动尝试 Edge + Chrome 导入
  autoImportFromBrowser: () =>
    client
      .post<CookieInjectResult>('/api/auth/import-from-browser/auto')
      .then((r) => r.data),

  // 打开系统浏览器到闲鱼
  openBrowserToLogin: () =>
    client
      .post<{ ok: boolean; message?: string; error?: string }>('/api/auth/import-from-browser/open')
      .then((r) => r.data),

  // ===== Cookie 健康检查 & 退出登录 =====

  // 轻量级 Cookie 健康检查（纯文件读取，< 300ms）
  // 供状态栏用户头像悬浮面板调用
  checkCookieHealth: () =>
    client.get<CookieHealthReport>('/api/auth/cookie/health').then((r) => r.data),

  // 退出登录：清除 cookies.json / SQLite Cookie / xh_token 认证 Cookie
  logout: () =>
    client.post<{ ok: boolean; message?: string; cleared?: Record<string, unknown> }>(
      '/api/auth/logout',
    ).then((r) => r.data),
}
