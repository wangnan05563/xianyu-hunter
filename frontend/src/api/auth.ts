import client from './client'
import type { AuthMe } from './types'

// 登录状态轮询响应
// 项目规范：用 type 而非 interface 定义数据结构
export type LoginStatus = {
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
export type CookieInjectResult = {
  ok: boolean
  injected?: number
  total_parsed?: number
  method?: string
  message?: string
  error?: string
  hint?: string
}

// 浏览器导入状态
export type BrowserImportStatus = {
  edge: { exists: boolean; has_goofish_cookie: boolean }
  chrome: { exists: boolean; has_goofish_cookie: boolean }
}

// Cookie 摘要信息
export type SavedCookieInfo = {
  has_cookies: boolean
  logged_in: boolean
  cookie_count?: number
  key_cookies_found?: string[]
  exported_at?: number
  method?: string
}

// Cookie 健康检查报告（轻量级，供状态栏悬浮面板使用）
export type CookieHealthReport = {
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

  // ===== 多账号管理（MU3/MU7）=====
  // 后端契约：/api/auth/* 路径（与 /api/auth/cookie、/api/auth/me 同前缀）
  // session_token 由 cookie 自动携带，字段名 target_user_id 与设计文档对齐

  // 账号列表：返回所有已登录账号，含当前账号标记
  getAccounts: () =>
    client.get<{ accounts: AccountInfo[] }>('/api/auth/accounts').then((r) => r.data.accounts),

  // 切换账号：后端签发新 session_token 并通过 Set-Cookie 写入
  // 切换后前端需刷新菜单 + 任务列表（新 user_id 隔离的数据）
  // body 字段 target_user_id 与设计文档需求规格 L341 严格对齐
  switchAccount: (targetUserId: string) =>
    client.post<{ ok: boolean; user_id?: string; nickname?: string }>('/api/auth/switch', {
      target_user_id: targetUserId,
    }).then((r) => r.data),

  // 退出当前账号（不删除账号数据，仅失效当前 session）
  logoutAccount: () =>
    client.post<{ ok: boolean }>('/api/auth/logout').then((r) => r.data),

  // 会话事件日志：用于账号切换历史审计
  getSessionEvents: (userId?: string, limit: number = 100) =>
    client
      .get<SessionEvent[]>('/api/auth/session-events', {
        params: { user_id: userId, limit },
      })
      .then((r) => r.data),
}

// 已登录账号信息：与后端 api_accounts.py AccountInfo 对齐
export type AccountInfo = {
  user_id: string
  nickname: string
  avatar_url: string
  status: 'active' | 'expired' | 'disabled'
  is_current: boolean
  last_active_at?: string
  custom_alias?: string
}

// 会话事件：login/logout/switch/cookie_expired/session_renewed
export type SessionEvent = {
  id: number
  user_id: string | null
  event_type: string
  detail: string
  created_at: string
}
