// T02726：确认框不只要在文案模块里拼好，得证明页面真的用它——
// 并且点「取消」不能把 PUT /api/ai/config 发出去（T02579 立过的规矩）。
import { render, screen, waitFor, within, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Modal } from 'antd'
import { beforeEach, afterEach, describe, it, expect, vi } from 'vitest'
import { aiApi } from '../../../../api'
import AIConfig from '../index'

vi.mock('../../../../api', () => ({
  aiApi: {
    getConfig: vi.fn(async () => ({
      ai_enabled: true,
      base_url: 'https://api.openai.com/v1',
      api_key: '****1234',
      model: 'gpt-4.1-mini',
      vision_model: 'gpt-4o',
      preset_id: 'openai',
    })),
    getUsage: vi.fn(async () => ({
      today: { total_calls: 37, total_tokens: 12800, total_cost_usd: 0, total_cost_cny: 0, by_endpoint: {}, by_model: {} },
      budget: { daily_token_limit: 500000, daily_cost_limit_usd: 5, rate_limit_per_min: 20, token_usage_pct: 0, cost_usage_pct: 0 },
      history: [],
    })),
    putConfig: vi.fn(async () => ({})),
    putBudget: vi.fn(async () => ({})),
    testConnection: vi.fn(async () => ({ ok: true })),
    testEmbedding: vi.fn(async () => ({ ok: true })),
  },
}))

beforeEach(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation(() => ({
      matches: false,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
  vi.mocked(aiApi.putConfig).mockClear()
})

afterEach(() => {
  cleanup()
  // confirmDanger 用的是命令式 Modal.confirm，DOM 挂在 RTL 容器之外
  Modal.destroyAll()
})

/** 命令式 Modal.confirm 的节点在 RTL 容器外，且会跨用例残留，按「新增的那一个」定位 */
async function openDisableConfirm() {
  render(<AIConfig />)
  await screen.findByText('AI 功能总开关')
  const before = document.querySelectorAll('.ant-modal-confirm').length
  await userEvent.click(screen.getByRole('switch'))
  await waitFor(() => {
    expect(document.querySelectorAll('.ant-modal-confirm').length).toBeGreaterThan(before)
  })
  const modals = document.querySelectorAll<HTMLElement>('.ant-modal-confirm')
  return modals[modals.length - 1]
}

describe('AI 总开关关闭确认框', () => {
  it('点开关弹出四要素确认框，数量取自页面真实配置', async () => {
    const modal = await openDisableConfirm()
    const q = within(modal)
    expect(q.getAllByText('确认关闭 AI 功能总开关？').length).toBeGreaterThan(0)
    for (const label of ['动作：', '影响范围：', '数量：', '恢复成本：']) {
      expect(q.getAllByText(label).length, `${label} 未渲染`).toBeGreaterThan(0)
    }
    // 模型名与今日用量来自 getConfig / getUsage，不是写死的数字
    expect(modal.textContent).toContain('文本 gpt-4.1-mini')
    expect(modal.textContent).toContain('视觉 gpt-4o')
    expect(modal.textContent).toContain('今日已调用 37 次')
    // 开关卡片上的说明不得再承诺那句假后果
    expect(document.querySelector('.page-container')?.textContent)
      .not.toContain('所有 AI 功能将降级到规则模式')
  })

  it('点「取消」不得发出关闭请求', async () => {
    const modal = await openDisableConfirm()
    await userEvent.click(within(modal).getByRole('button', { name: /取\s*消/ }))
    expect(aiApi.putConfig).not.toHaveBeenCalled()
  })

  it('点「确认执行」才真正关闭', async () => {
    const modal = await openDisableConfirm()
    await userEvent.click(within(modal).getByRole('button', { name: /确认执行/ }))
    await waitFor(() => {
      expect(aiApi.putConfig).toHaveBeenCalledWith({ ai_enabled: false })
    })
  })
})
