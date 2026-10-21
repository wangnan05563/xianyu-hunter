// frontend/src/pages/Chatbot/__tests__/chatbotConfigFailureStates.test.tsx
// T02700：客服配置页 6 路数据原先统一 safe(p, fallback) 压成 null/[]，
// Promise.all 整体 reject 时页面永远停在「加载中...」，
// 各表格则显示「暂无 FAQ / 暂无重建记录 / 无版本」——把后端故障说成没数据。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const { chatbotMocks } = vi.hoisted(() => ({
  chatbotMocks: {
    getConfig: vi.fn(),
    getKBStatus: vi.fn(),
    listKBVersions: vi.fn(),
    listFAQ: vi.fn(),
    listAuditLogs: vi.fn(),
  },
}))

vi.mock('../api', () => ({ chatbotApi: chatbotMocks }))

import ConfigPage from '../Config'

const ERR = new Error('500')

const CONFIG = {
  enabled: true,
  max_history_turns: 6,
  session_timeout_min: 30,
  welcome_message: '',
  rag: { top_k: 4, similarity_threshold: 0.5, max_context_chars: 3000 },
  llm: { model: 'gpt-4o', temperature: 0.2, max_tokens: 1024, http_timeout_sec: 30, first_token_timeout_sec: 8, vision_model: '' },
  agent: { enable_tools: true, max_tool_rounds: 3, tool_trigger_mode: 'auto' },
  kb: { auto_update_enabled: false, update_interval_hours: 24 },
  escalation: { feedback_threshold: 3, feedback_window_min: 60, contact: '', sanitize_pii: true },
}

const KB_STATUS = { current_version: 'v1', chunk_count: 120, last_build_at: '2026-10-01T00:00:00', building: false, status: 'success' }

function setAllOk() {
  chatbotMocks.getConfig.mockResolvedValue(CONFIG)
  chatbotMocks.getKBStatus.mockResolvedValue(KB_STATUS)
  chatbotMocks.listKBVersions.mockResolvedValue([])
  chatbotMocks.listFAQ.mockResolvedValue([])
  chatbotMocks.listAuditLogs.mockResolvedValue({ items: [], total: 0 })
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ConfigPage />
    </MemoryRouter>,
  )
}

async function openTab(name: string) {
  await waitFor(() => expect(screen.getByRole('tab', { name })).toBeInTheDocument())
  fireEvent.click(screen.getByRole('tab', { name }))
}

beforeEach(() => {
  Object.values(chatbotMocks).forEach((m) => m.mockReset())
  setAllOk()
})

describe('客服配置页失败态（T02700）', () => {
  it('全部成功时没有任何错误态', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('智能客服配置')).toBeInTheDocument())
    expect(screen.queryByText(/加载失败/)).not.toBeInTheDocument()
  })

  it('配置请求失败：给错误态 + 重试，不再永久「加载中...」', async () => {
    chatbotMocks.getConfig.mockRejectedValue(ERR)
    renderPage()
    await waitFor(() => expect(screen.getByText('客服配置加载失败')).toBeInTheDocument(), { timeout: 4000 })
    expect(screen.queryByText('加载中...')).not.toBeInTheDocument()
  })

  it('只有 FAQ 请求失败：错误态与「暂无 FAQ」互斥', async () => {
    chatbotMocks.listFAQ.mockRejectedValue(ERR)
    renderPage()
    await openTab('FAQ 管理')
    await waitFor(() => expect(screen.getByText('FAQ 列表加载失败')).toBeInTheDocument())
    expect(screen.queryByText('暂无 FAQ')).not.toBeInTheDocument()
  })

  it('知识库状态失败 + 版本列表失败：各自区块分别声明，不共用一个空态', async () => {
    chatbotMocks.getKBStatus.mockRejectedValue(ERR)
    chatbotMocks.listKBVersions.mockRejectedValue(ERR)
    renderPage()
    await openTab('知识库管理')
    await waitFor(() => expect(screen.getByText('知识库状态加载失败')).toBeInTheDocument())
    expect(screen.getByText('版本列表加载失败')).toBeInTheDocument()
  })

  it('审计日志失败时重建记录同源失败，两处都不能写「暂无××」', async () => {
    chatbotMocks.listAuditLogs.mockRejectedValue(ERR)
    renderPage()
    await openTab('知识库管理')
    await waitFor(() => expect(screen.getByText('重建记录加载失败')).toBeInTheDocument())
    expect(screen.queryByText('暂无重建记录')).not.toBeInTheDocument()
    await openTab('审计日志')
    await waitFor(() => expect(screen.getByText('审计日志加载失败')).toBeInTheDocument())
    expect(screen.queryByText('暂无审计日志')).not.toBeInTheDocument()
  })

  it('失败后重试成功，错误条消失', async () => {
    chatbotMocks.listFAQ.mockRejectedValue(ERR)
    renderPage()
    await openTab('FAQ 管理')
    await waitFor(() => expect(screen.getByText('FAQ 列表加载失败')).toBeInTheDocument())
    chatbotMocks.listFAQ.mockResolvedValue([{ id: 1, question: '如何退货', answer: '联系客服' }])
    chatbotMocks.getConfig.mockResolvedValue(CONFIG)
    fireEvent.click(screen.getByRole('button', { name: /重\s*试/ }))
    // 整页重载会回到默认 tab，重新进入 FAQ 页签再断言
    await waitFor(() => expect(screen.getByText('基础配置')).toBeInTheDocument(), { timeout: 4000 })
    await openTab('FAQ 管理')
    expect(screen.getByText('如何退货')).toBeInTheDocument()
    expect(screen.queryByText('FAQ 列表加载失败')).not.toBeInTheDocument()
  })
})
