// frontend/src/pages/Config/AIConfig/__tests__/aiConfigFailureStates.test.tsx
// T02700：AI 配置页两路数据（getConfig / getUsage）原先各自 catch 成 null，
// 后端故障时表单显示空值、用量显示「今日 0 次」，看起来像「没配模型、没花钱」。
// 钉住：失败要有错误态与重试，开关状态未知时不许盲操作，
// 且没读到配置时不能把内置空值保存回去（覆盖真实配置）。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const { apiMocks } = vi.hoisted(() => ({
  apiMocks: {
    getConfig: vi.fn(),
    getUsage: vi.fn(),
    putConfig: vi.fn(),
    putBudget: vi.fn(),
    testConnection: vi.fn(),
    testEmbedding: vi.fn(),
    listModels: vi.fn(),
  },
}))

vi.mock('../../../../api', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  const a = actual as { aiApi: Record<string, unknown> }
  return { ...actual, aiApi: { ...a.aiApi, ...apiMocks } }
})

import AIConfig from '../index'

const ERR = new Error('500')
const CONFIG = {
  ai_enabled: true,
  base_url: 'https://api.openai.com/v1',
  api_key: 'sk-****',
  model: 'gpt-4o',
  vision_model: 'qwen-vl-max',
  preset_id: 'openai',
}
const USAGE = {
  today: { total_calls: 37, total_tokens: 12800, total_cost_usd: 1.2, total_cost_cny: 8.6, by_endpoint: {}, by_model: {} },
  budget: { daily_token_limit: 500000, daily_cost_limit_usd: 5, rate_limit_per_min: 20, token_usage_pct: 10, cost_usage_pct: 20 },
  history: [],
}

function renderPage() {
  return render(
    <MemoryRouter>
      <AIConfig />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  apiMocks.getConfig.mockReset()
  apiMocks.getUsage.mockReset()
  apiMocks.putConfig.mockReset()
  apiMocks.getConfig.mockResolvedValue(CONFIG)
  apiMocks.getUsage.mockResolvedValue(USAGE)
})

describe('AI 配置页失败态（T02700）', () => {
  it('两路都成功时不出现任何错误态', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('今日调用')).toBeInTheDocument())
    expect(screen.queryByText(/加载失败/)).not.toBeInTheDocument()
    expect(screen.getByText('已开启')).toBeInTheDocument()
  })

  it('配置读取失败：状态显示「未知」而不是拿默认值当现状，开关同时禁用', async () => {
    apiMocks.getConfig.mockRejectedValue(ERR)
    renderPage()
    await waitFor(() => expect(screen.getByText('AI 配置加载失败')).toBeInTheDocument())
    expect(screen.getByText('状态未知')).toBeInTheDocument()
    expect(screen.queryByText('已开启')).not.toBeInTheDocument()
    expect(screen.getByRole('switch')).toBeDisabled()
  })

  it('配置读取失败时点「保存配置」不能把内置空值写回服务端', async () => {
    apiMocks.getConfig.mockRejectedValue(ERR)
    apiMocks.putConfig.mockResolvedValue(CONFIG)
    renderPage()
    await waitFor(() => expect(screen.getByText('AI 配置加载失败')).toBeInTheDocument())
    fireEvent.click(screen.getByText('保存配置'))
    await waitFor(() => expect(screen.getByText(/避免用空值覆盖现有配置/)).toBeInTheDocument())
    expect(apiMocks.putConfig).not.toHaveBeenCalled()
  })

  it('用量读取失败：整块用量与预算不展示，而不是留下「今日 0 次」和默认预算上限', async () => {
    apiMocks.getUsage.mockRejectedValue(ERR)
    renderPage()
    await waitFor(() => expect(screen.getByText('AI 用量加载失败')).toBeInTheDocument())
    expect(screen.queryByText('今日调用')).not.toBeInTheDocument()
    // 默认预算（500000）不能被当成服务端当前配置展示
    expect(screen.queryByText('500000')).not.toBeInTheDocument()
  })

  it('用量区重试成功后错误态消失、真实数字回来', async () => {
    apiMocks.getUsage.mockRejectedValue(ERR)
    renderPage()
    await waitFor(() => expect(screen.getByText('AI 用量加载失败')).toBeInTheDocument())
    apiMocks.getUsage.mockResolvedValue(USAGE)
    fireEvent.click(screen.getAllByRole('button', { name: /重\s*试/ })[0])
    await waitFor(() => expect(screen.getByText('今日调用')).toBeInTheDocument())
    expect(screen.queryByText('AI 用量加载失败')).not.toBeInTheDocument()
  })

  it('连接测试成功后刷新用量，刷新失败要在账上标红而不是静默', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('今日调用')).toBeInTheDocument())
    apiMocks.testConnection.mockResolvedValue({ ok: true, model: 'gpt-4o' })
    apiMocks.getUsage.mockRejectedValue(ERR)
    fireEvent.click(screen.getByRole('button', { name: /测试连接/ }))
    await waitFor(() => expect(screen.getByText('AI 用量加载失败')).toBeInTheDocument())
  })
})
