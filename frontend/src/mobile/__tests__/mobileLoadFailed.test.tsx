// frontend/src/mobile/__tests__/mobileLoadFailed.test.tsx
// T02701 移动端假回执清零：接口失败必须渲染错误态，且不得同时给出「暂无数据」空态。
// 空态（取到 0 条）与错误态（没取到）在 UI 上必须是两种东西 —— 这是本单的核心断言。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp } from 'antd'

const mocks = vi.hoisted(() => ({
  chatGetConfig: vi.fn(),
  chatGetWelcome: vi.fn(),
  chatListFAQ: vi.fn(),
  logSearch: vi.fn(),
}))

vi.mock('../../pages/Chatbot/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../pages/Chatbot/api')>()
  return {
    ...actual,
    chatbotApi: {
      ...actual.chatbotApi,
      getConfig: mocks.chatGetConfig,
      getWelcome: mocks.chatGetWelcome,
      listFAQ: mocks.chatListFAQ,
    },
  }
})

vi.mock('../../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api')>()
  return { ...actual, logApi: { ...actual.logApi, search: mocks.logSearch } }
})

import MobileChatbotConfig from '../pages/ChatbotConfig'
import MobileLogs from '../pages/Logs'

const wrap = (node: React.ReactNode) => render(<AntApp>{node}</AntApp>)

beforeEach(() => {
  mocks.chatGetConfig.mockReset()
  mocks.chatGetWelcome.mockReset()
  mocks.chatListFAQ.mockReset()
  mocks.logSearch.mockReset()
})

describe('移动端客服配置（T02701）', () => {
  it('三路都成功且 FAQ 为空：如实显示空态 (0) / 暂无 FAQ', async () => {
    mocks.chatGetConfig.mockResolvedValue({ enabled: true, welcome_message: 'x' })
    mocks.chatGetWelcome.mockResolvedValue({ message: '你好' })
    mocks.chatListFAQ.mockResolvedValue([])
    wrap(<MobileChatbotConfig />)
    await screen.findByText('你好')
    expect(screen.getByText('FAQ 列表 (0)')).toBeInTheDocument()
    expect(screen.getByText('暂无 FAQ')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('欢迎语接口失败：给错误态 + 重试，不再永久显示「加载中...」或冒充「未配置欢迎语」', async () => {
    mocks.chatGetConfig.mockResolvedValue({ enabled: true })
    mocks.chatGetWelcome.mockRejectedValue(new Error('boom'))
    mocks.chatListFAQ.mockResolvedValue([])
    wrap(<MobileChatbotConfig />)
    const bar = await screen.findByText(/欢迎语加载失败/)
    expect(bar).toBeInTheDocument()
    expect(screen.queryByText('加载中...')).not.toBeInTheDocument()
    expect(screen.queryByText('(未配置欢迎语)')).not.toBeInTheDocument()
  })

  it('FAQ 接口失败：标题写「数量未知」而不是 0，且不渲染「暂无 FAQ」空态', async () => {
    mocks.chatGetConfig.mockResolvedValue({ enabled: true })
    mocks.chatGetWelcome.mockResolvedValue({ message: '你好' })
    mocks.chatListFAQ.mockRejectedValue(new Error('boom'))
    wrap(<MobileChatbotConfig />)
    await waitFor(() => expect(screen.getByText('FAQ 列表 (数量未知)')).toBeInTheDocument())
    expect(screen.getByText(/FAQ 列表加载失败/)).toBeInTheDocument()
    expect(screen.queryByText('暂无 FAQ')).not.toBeInTheDocument()
    // 其它数据源不受影响：欢迎语照常显示
    expect(screen.getByText('你好')).toBeInTheDocument()
  })

  it('配置接口失败：整页给错误态与重试按钮，不再无限转圈', async () => {
    mocks.chatGetConfig.mockRejectedValue(new Error('boom'))
    mocks.chatGetWelcome.mockResolvedValue({ message: '你好' })
    mocks.chatListFAQ.mockResolvedValue([])
    wrap(<MobileChatbotConfig />)
    await waitFor(() => expect(screen.getByText(/智能客服配置加载失败/)).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /重\s*试/ })).toBeInTheDocument()
  })

  it('失败后重试成功：错误条消失，恢复成真实数据', async () => {
    mocks.chatGetConfig.mockResolvedValue({ enabled: true })
    mocks.chatGetWelcome.mockRejectedValueOnce(new Error('boom')).mockResolvedValue({ message: '回来了' })
    mocks.chatListFAQ.mockResolvedValue([])
    wrap(<MobileChatbotConfig />)
    await screen.findByText(/欢迎语加载失败/)
    await userEvent.click(screen.getAllByRole('button', { name: /重\s*试/ })[0])
    await waitFor(() => expect(screen.getByText('回来了')).toBeInTheDocument())
    expect(screen.queryByText(/欢迎语加载失败/)).not.toBeInTheDocument()
  })
})

describe('移动端日志页（T02701）', () => {
  it('列表接口失败：给错误态，不再用「暂无日志」空态冒充', async () => {
    mocks.logSearch.mockRejectedValue(new Error('boom'))
    wrap(<MobileLogs />)
    await waitFor(() => expect(screen.getByText(/日志列表加载失败/)).toBeInTheDocument())
    expect(screen.queryByText('暂无日志')).not.toBeInTheDocument()
    expect(screen.getByRole('alert').textContent).toContain('本次一条都没取到')
  })

  it('接口成功但确实 0 条：这才是空态，不出现错误条', async () => {
    mocks.logSearch.mockResolvedValue({ items: [] })
    wrap(<MobileLogs />)
    await waitFor(() => expect(screen.getByText('暂无日志')).toBeInTheDocument())
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('自动刷新失败：保留旧列表并显式说明可能已过期', async () => {
    mocks.logSearch
      .mockResolvedValueOnce({ items: [{ id: 1, level: 'info', message: '旧数据', created_at: '2026-10-21T00:00:00' }] })
      .mockRejectedValue(new Error('boom'))
    wrap(<MobileLogs />)
    await screen.findByText('旧数据')
    await userEvent.click(screen.getByRole('button', { name: /开启轮询/ }))
    await waitFor(() => expect(screen.getByText(/自动刷新加载失败/)).toBeInTheDocument(), { timeout: 8000 })
    const bar = screen.getByRole('alert')
    expect(bar.textContent).toContain('列表停留在上一次成功拉取的结果')
    // 旧数据仍在列表里，但空态没有被冒充
    expect(screen.queryByText('暂无日志')).not.toBeInTheDocument()
  })
})
