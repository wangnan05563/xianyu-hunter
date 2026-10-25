// frontend/src/mobile/__tests__/mobileConfigFailureStates.test.tsx
// T02978：7 个配置/表单页在数据源 reject 时不能永久转圈，也不能拿初值冒充真实配置。
// 与 T02718 的 mobileFailureStates.test.tsx 同口径：真实渲染，断言错误态出现、表单/默认值不出现。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp } from 'antd'

const mocks = vi.hoisted(() => ({
  configGet: vi.fn(),
  aiGetConfig: vi.fn(),
  aiGetUsage: vi.fn(),
  aboutGet: vi.fn(),
}))

vi.mock('../../api/config', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/config')>()
  return { ...actual, configApi: { ...actual.configApi, get: mocks.configGet } }
})

vi.mock('../../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api')>()
  return {
    ...actual,
    aiApi: { ...actual.aiApi, getConfig: mocks.aiGetConfig, getUsage: mocks.aiGetUsage },
    aboutApi: { ...actual.aboutApi, get: mocks.aboutGet },
  }
})

import MobilePriceStrategy from '../pages/PriceStrategy'
import MobileBuyConfig from '../pages/BuyConfig'
import MobileSearchConfig from '../pages/SearchConfig'
import MobileAIConfig from '../pages/AIConfig'
import MobileNotifierChannels from '../pages/NotifierChannels'
import MobileAbout from '../pages/About'

const wrap = (node: React.ReactNode) => render(<AntApp>{node}</AntApp>)

const PRICE_CFG = {
  price_strategy: {
    enabled_max: true, max_price: 500, enabled_min: true, min_price: 10,
    enabled_market_ratio: false, market_ratio: 0.8, enabled_top_n: false, top_n: 5,
  },
}

const AI_CFG = {
  ai_enabled: true, base_url: 'https://api.example.com/v1', api_key: 'sk-test',
  model: 'gpt-4o-mini', vision_model: '', embedding_base_url: '',
  embedding_api_key: '', embedding_model: '',
}

const AI_USAGE = {
  today: { total_calls: 12, total_tokens: 3456, total_cost_cny: 1.23, total_cost_usd: 0.17 },
  budget: { daily_token_limit: 0, token_usage_pct: 0, cost_usage_pct: 0 },
}

beforeEach(() => {
  Object.values(mocks).forEach((m) => m.mockReset())
})

describe('移动端价格策略页（T02978）', () => {
  it('配置失败：给错误条与重试，不渲染表单；重试成功后恢复', async () => {
    mocks.configGet
      .mockRejectedValueOnce(new Error('boom'))
      .mockResolvedValueOnce(PRICE_CFG)
    wrap(<MobilePriceStrategy />)

    await waitFor(() => expect(screen.getByText(/价格策略配置加载失败/)).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: /保存配置/ })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /重\s*试/ }))
    await waitFor(() => expect(screen.getByRole('button', { name: /保存配置/ })).toBeInTheDocument())
    expect(screen.queryByText(/价格策略配置加载失败/)).not.toBeInTheDocument()
  })
})

describe('移动端抢单阈值页（T02978）', () => {
  it('配置失败：错误态，不显示 0 分阈值', async () => {
    mocks.configGet.mockRejectedValue(new Error('boom'))
    wrap(<MobileBuyConfig />)
    await waitFor(() => expect(screen.getByText(/抢单阈值配置加载失败/)).toBeInTheDocument())
    expect(screen.queryByText('/ 100')).not.toBeInTheDocument()
  })
})

describe('移动端搜索参数页（T02978）', () => {
  it('配置失败：错误态，不渲染「每页条数」等输入', async () => {
    mocks.configGet.mockRejectedValue(new Error('boom'))
    wrap(<MobileSearchConfig />)
    await waitFor(() => expect(screen.getByText(/搜索参数配置加载失败/)).toBeInTheDocument())
    expect(screen.queryByText(/每页条数/)).not.toBeInTheDocument()
  })
})

describe('移动端 AI 配置页（T02978）', () => {
  it('用量失败：今日用量卡保留但数字为 —，并给用量错误条', async () => {
    mocks.aiGetConfig.mockResolvedValue(AI_CFG)
    mocks.aiGetUsage.mockRejectedValue(new Error('boom'))
    wrap(<MobileAIConfig />)

    await waitFor(() => expect(screen.getByText(/用量统计加载失败/)).toBeInTheDocument())
    expect(screen.getByText('今日用量')).toBeInTheDocument()
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
    // 配置本身成功：总开关照常可编辑
    expect(screen.getByText('启用 AI 服务')).toBeInTheDocument()
  })

  it('配置失败：整页错误态，不渲染 LLM 输入框', async () => {
    mocks.aiGetConfig.mockRejectedValue(new Error('boom'))
    mocks.aiGetUsage.mockResolvedValue(AI_USAGE)
    wrap(<MobileAIConfig />)

    await waitFor(() => expect(screen.getByText(/AI 配置加载失败/)).toBeInTheDocument())
    expect(screen.queryByText('启用 AI 服务')).not.toBeInTheDocument()
  })
})

describe('移动端通知渠道页（T02978）', () => {
  it('配置失败：不渲染 defaultChannels 的默认渠道与启停态', async () => {
    mocks.configGet.mockRejectedValue(new Error('boom'))
    wrap(<MobileNotifierChannels />)
    await waitFor(() => expect(screen.getByText(/通知渠道配置加载失败/)).toBeInTheDocument())
    expect(screen.queryByText('Server酱')).not.toBeInTheDocument()
  })
})

describe('移动端关于页（T02978）', () => {
  it('系统信息失败：错误态，不显示版本号', async () => {
    mocks.aboutGet.mockRejectedValue(new Error('boom'))
    wrap(<MobileAbout />)
    await waitFor(() => expect(screen.getByText(/系统信息加载失败/)).toBeInTheDocument())
    expect(screen.queryByText(/^v\d/)).not.toBeInTheDocument()
  })
})
