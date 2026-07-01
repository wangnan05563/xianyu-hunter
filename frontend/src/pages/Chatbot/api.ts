import client from '../../api/client'
import type { Session, Message, KBStatus, KBVersion, FAQ, ChatbotConfig, AuditLog, WelcomeInfo } from './types'

const BASE = '/api/chatbot'

// 智能客服 API 客户端
// 非 SSE 请求复用全局 axios client（自动携带 xh_token + 401 跳转），
// SSE 流式请求（chat）必须用 fetch + ReadableStream，axios 不支持流式读取
export const chatbotApi = {
  // ============== 会话管理 ==============
  createSession: (title?: string) =>
    client
      .post<Session>(`${BASE}/sessions`, { title })
      .then((r) => r.data),

  listSessions: (page = 1, pageSize = 20, keyword?: string, favoriteOnly?: boolean) =>
    client
      .get<{ items: Session[]; total: number }>(`${BASE}/sessions`, {
        params: {
          limit: pageSize,
          offset: (page - 1) * pageSize,
          ...(keyword ? { keyword } : {}),
          ...(favoriteOnly ? { favorite_only: true } : {}),
        },
      })
      .then((r) => r.data),

  deleteSession: (id: string) => client.delete(`${BASE}/sessions/${id}`),

  // M2：切换会话收藏状态
  toggleFavorite: (id: string, isFavorite: boolean) =>
    client
      .patch<Session>(`${BASE}/sessions/${id}/favorite`, { is_favorite: isFavorite })
      .then((r) => r.data),

  // M4：撤回用户消息（2 分钟时间窗内）
  recallMessage: (messageId: string) =>
    client
      .post<{ ok: boolean; id: string; is_recalled: boolean }>(`${BASE}/messages/${messageId}/recall`)
      .then((r) => r.data),

  // M5：主动触发转人工
  triggerEscalation: (sessionId: string) =>
    client
      .post<{ ok: boolean; session_id: string; status: string }>(`${BASE}/escalation/trigger`, { session_id: sessionId })
      .then((r) => r.data),

  // ============== 消息 ==============
  listMessages: (sessionId: string, limit = 20, beforeId?: string) =>
    client
      .get<{ items: Message[]; has_more: boolean }>(`${BASE}/sessions/${sessionId}/messages`, {
        params: { limit, ...(beforeId ? { before_id: beforeId } : {}) },
      })
      .then((r) => r.data),

  // ============== 反馈 ==============
  // 后端路由为 POST /messages/{message_id}/feedback，message_id 在路径中
  // body 只含 rating/comment/star_rating/category（FeedbackRequest 定义）
  submitFeedback: (
    messageId: string,
    rating: 'positive' | 'negative',
    comment?: string,
    sessionId?: string,
    starRating?: number,
    category?: string,
  ) =>
    client.post(`${BASE}/messages/${messageId}/feedback`, {
      rating,
      comment,
      star_rating: starRating,
      category,
    }),

  // ============== 知识库 ==============
  getKBStatus: () => client.get<KBStatus>(`${BASE}/kb/status`).then((r) => r.data),

  rebuildKB: (force = false) =>
    client
      .post<{ status: string }>(`${BASE}/kb/rebuild`, null, {
        params: { force },
      })
      .then((r) => r.data),

  // 后端返回 {items, total}，前端只需 items 数组供 Table 渲染
  // 之前误标为 KBVersion[]，实际收到对象会导致 Table dataSource 崩溃
  listKBVersions: () =>
    client
      .get<{ items: KBVersion[]; total: number }>(`${BASE}/kb/versions`)
      .then((r) => r.data.items),

  rollbackKB: (versionId: string) =>
    client.post(`${BASE}/kb/rollback/${versionId}`),

  // ============== 配置 ==============
  getConfig: () => client.get<ChatbotConfig>(`${BASE}/config`).then((r) => r.data),

  updateConfig: (key: string, value: string) =>
    client.put(`${BASE}/config`, { key, value }),

  // ============== FAQ ==============
  listFAQ: () => client.get<FAQ[]>(`${BASE}/faq`).then((r) => r.data),

  upsertFAQ: (faq: FAQ) => client.post(`${BASE}/faq`, faq),

  deleteFAQ: (id: number) => client.delete(`${BASE}/faq/${id}`),

  // ============== 审计日志 ==============
  listAuditLogs: (page = 1, pageSize = 20) =>
    client
      .get<{ items: AuditLog[]; total: number }>(`${BASE}/audit-logs`, {
        params: { page, page_size: pageSize },
      })
      .then((r) => r.data),

  // ============== M1 欢迎语 ==============
  getWelcome: () =>
    client.get<WelcomeInfo>(`${BASE}/welcome`).then((r) => r.data),

  // ============== 转人工导出 ==============
  exportSession: (sessionId: string) =>
    client
      .get<{ content: string }>(`${BASE}/escalation/${sessionId}/export`)
      .then((r) => r.data),
}
