// frontend/src/mobile/__tests__/mobileDisableAIConfirm.test.tsx
// T02892：移动端「启用 AI 服务」开关原先 onChange 直接改 form，零确认。
// 开关本身不落库，真正写库是页底的「保存配置」，而保存发的是整份 AI 配置
// （base_url / api_key / model / embedding_*）——误点一下开关、随后按保存，
// 就等于把「关闭全部 AI 评估链」连同别的字段一起写下去。
// 这组用例是那条缺陷的行为证明：关开关必须先确认，取消不得改表单。
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, within, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp, Modal } from 'antd'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { aiApi } from '../../api'

const CONFIG_ON = {
  ai_enabled: true,
  base_url: 'https://api.openai.com/v1',
  api_key: '****1234',
  model: 'gpt-4.1-mini',
  vision_model: 'gpt-4o',
  embedding_base_url: '',
  embedding_api_key: '',
  embedding_model: '',
  embedding_dimensions: 0,
}

const USAGE = {
  today: { total_calls: 37, total_tokens: 12800, total_cost_usd: 0, total_cost_cny: 0, by_endpoint: {}, by_model: {} },
  budget: { daily_token_limit: 500000, daily_cost_limit_usd: 5, rate_limit_per_min: 20, token_usage_pct: 0, cost_usage_pct: 0 },
  history: [],
}

vi.mock('../../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api')>()
  return {
    ...actual,
    aiApi: {
      ...actual.aiApi,
      getConfig: vi.fn(async () => ({ ...CONFIG_ON })),
      getUsage: vi.fn(async () => ({ ...USAGE })),
      putConfig: vi.fn(async () => ({})),
      testConnection: vi.fn(async () => ({ ok: true })),
      testEmbedding: vi.fn(async () => ({ ok: true })),
    },
  }
})

import MobileAIConfig from '../pages/AIConfig'

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
  vi.mocked(aiApi.getConfig).mockReset().mockResolvedValue({ ...CONFIG_ON })
  vi.mocked(aiApi.getUsage).mockReset().mockResolvedValue({ ...USAGE })
  vi.mocked(aiApi.putConfig).mockReset().mockResolvedValue({})
})

afterEach(() => {
  cleanup()
  // confirmDanger 用命令式 Modal.confirm，DOM 挂在 RTL 容器之外且会跨用例残留
  Modal.destroyAll()
})

async function renderPage() {
  render(
    <AntApp>
      <MobileAIConfig />
    </AntApp>,
  )
  return screen.findByText('启用 AI 服务')
}

/** 命令式确认框按「最后新增的那一个」定位（会跨用例残留） */
async function openDisableConfirm() {
  await renderPage()
  const before = document.querySelectorAll('.ant-modal-confirm').length
  await userEvent.click(await screen.findByRole('switch'))
  await waitFor(() => {
    expect(document.querySelectorAll('.ant-modal-confirm').length).toBeGreaterThan(before)
  })
  const modals = document.querySelectorAll<HTMLElement>('.ant-modal-confirm')
  return modals[modals.length - 1]
}

describe('移动端 AI 总开关的关闭确认（T02892）', () => {
  it('关开关先弹四要素确认，且说明「点了开关还要保存才生效」', async () => {
    const modal = await openDisableConfirm()
    const q = within(modal)
    expect(q.getAllByText('确认关闭 AI 功能总开关？').length).toBeGreaterThan(0)
    for (const label of ['动作：', '影响范围：', '数量：', '恢复成本：']) {
      expect(q.getAllByText(label).length, `${label} 未渲染`).toBeGreaterThan(0)
    }
    // 移动端与桌面端的差别必须写进文案：开关只改本页表单
    expect(modal.textContent).toContain('再点本页「保存」才会写入')
    expect(modal.textContent).toContain('只切开关而不点保存，后端配置也不会变')
    // 数量取自本页真实加载的模型与用量
    expect(modal.textContent).toContain('文本 gpt-4.1-mini')
    expect(modal.textContent).toContain('今日已调用 37 次')
  })

  it('卡片说明不再手写「所有 AI 评估功能停用」这句假后果', async () => {
    await renderPage()
    const hint = document.body.textContent ?? ''
    expect(hint).not.toContain('关闭后所有 AI 评估功能停用')
    // T02891 裁决 A（全量纳管）之后，对话助手已被纳管：旧口径「不含 AI 对话助手与知识库检索」
    // 是假的，必须消失；不产生的只有本地 Embedding 与本地向量库检索。
    expect(hint).not.toContain('不含AI 对话助手与知识库检索')
    expect(hint).toContain('不含本地 Embedding 后端')
    // 对话的关闭态是降级（FAQ / 检索片段），不是报错
    expect(hint).toContain('对话退成常见问题与检索片段')
  })

  it('取消确认框：表单不变，随后保存仍是 ai_enabled=true', async () => {
    const modal = await openDisableConfirm()
    await userEvent.click(within(modal).getByRole('button', { name: /取\s*消/ }))
    await userEvent.click(screen.getByRole('button', { name: /保存配置/ }))
    await waitFor(() => expect(aiApi.putConfig).toHaveBeenCalled())
    expect(vi.mocked(aiApi.putConfig).mock.calls[0][0]).toMatchObject({ ai_enabled: true })
  })

  it('确认后才改表单；改表单本身不落库，点保存才发请求', async () => {
    const modal = await openDisableConfirm()
    await userEvent.click(within(modal).getByRole('button', { name: /确认执行/ }))
    // 关键差异：移动端确认只改 form，不像桌面端那样立刻 PUT
    await waitFor(() => expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'false'))
    expect(aiApi.putConfig).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: /保存配置/ }))
    await waitFor(() => expect(aiApi.putConfig).toHaveBeenCalled())
    expect(vi.mocked(aiApi.putConfig).mock.calls[0][0]).toMatchObject({ ai_enabled: false })
  })

  it('开→不弹确认，直接开', async () => {
    vi.mocked(aiApi.getConfig).mockResolvedValue({ ...CONFIG_ON, ai_enabled: false })
    await renderPage()
    const before = document.querySelectorAll('.ant-modal-confirm').length
    await userEvent.click(await screen.findByRole('switch'))
    await waitFor(() => expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'true'))
    expect(document.querySelectorAll('.ant-modal-confirm').length).toBe(before)
    expect(aiApi.putConfig).not.toHaveBeenCalled()
  })

  it('用量接口挂掉时不得把「今日 0 次」当统计结果', async () => {
    vi.mocked(aiApi.getUsage).mockRejectedValue(new Error('boom'))
    const modal = await openDisableConfirm()
    expect(modal.textContent).toContain('未能预先统计')
    expect(modal.textContent).not.toContain('今日已调用 0 次')
  })
})

describe('移动端与桌面端共用同一份开关文案模块（T02892）', () => {
  const page = readFileSync(resolve(__dirname, '../pages/AIConfig/index.tsx'), 'utf-8')

  it('移动端不得再手写开关后果，也不得退回原生 confirm', () => {
    expect(page).toContain('buildDisableAICopy(')
    expect(page).toContain('{ deferredSave: true }')
    expect(page).toContain('{GATE_HINT}')
    expect(page).not.toContain('关闭后所有 AI 评估功能停用')
    expect(page).not.toMatch(/window\.confirm|globalThis\.confirm/)
  })
})
