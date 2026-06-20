import client from './client'
import type { AuthMe } from './types'

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
}
