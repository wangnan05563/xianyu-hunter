// frontend/src/mobile/__tests__/mobileFailureStates.test.tsx
// T02718：其余移动端页面的「接口失败」不能再用空列表 / 0 / 未激活 / IDLE 冒充成功。
// 与 T02701 的 mobileLoadFailed.test.tsx 同口径：真实渲染，断言错误态出现且空态不出现。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp } from 'antd'

const mocks = vi.hoisted(() => ({
  evalList: vi.fn(),
  antiSession: vi.fn(),
  antiHealth: vi.fn(),
  batchStatus: vi.fn(),
  dbTables: vi.fn(),
  dbRows: vi.fn(),
  taskList: vi.fn(),
  linkList: vi.fn(),
}))

vi.mock('../../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api')>()
  return {
    ...actual,
    evalApi: { ...actual.evalApi, list: mocks.evalList },
    anticrawlApi: {
      ...actual.anticrawlApi,
      getSessionStatus: mocks.antiSession,
      checkHealth: mocks.antiHealth,
    },
    batchRefreshApi: { ...actual.batchRefreshApi, getStatus: mocks.batchStatus },
    taskApi: { ...actual.taskApi, list: mocks.taskList },
    taskLinkApi: { ...actual.taskLinkApi, list: mocks.linkList },
  }
})

vi.mock('../../api/dbAdmin', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/dbAdmin')>()
  return {
    ...actual,
    dbAdminApi: {
      ...actual.dbAdminApi,
      listTables: mocks.dbTables,
      listRows: mocks.dbRows,
    },
  }
})

import MobileEvaluations from '../pages/Evaluations'
import MobileAntiCrawl from '../pages/AntiCrawl'
import MobileBatchRefresh from '../pages/BatchRefresh'
import MobileDatabaseAdmin from '../pages/DatabaseAdmin'
import MobileItems from '../pages/Items'

const wrap = (node: React.ReactNode) => render(<AntApp>{node}</AntApp>)

beforeEach(() => {
  Object.values(mocks).forEach((m) => m.mockReset())
})

describe('移动端评估页（T02718）', () => {
  it('接口失败：给错误条，不用「暂无评估记录」冒充', async () => {
    mocks.evalList.mockRejectedValue(new Error('boom'))
    wrap(<MobileEvaluations />)
    await waitFor(() => expect(screen.getByText(/评估列表加载失败/)).toBeInTheDocument())
    expect(screen.queryByText('暂无评估记录')).not.toBeInTheDocument()
  })

  it('接口成功但 0 条：这才是空态，且无错误条', async () => {
    mocks.evalList.mockResolvedValue({ items: [] })
    wrap(<MobileEvaluations />)
    await screen.findByText('暂无评估记录')
    expect(screen.queryByRole('alert')).toBeNull()
  })
})

describe('移动端反爬页（T02718）', () => {
  it('会话接口失败：状态灯显示「状态未知」，不显示「未激活」', async () => {
    mocks.antiSession.mockRejectedValue(new Error('boom'))
    mocks.antiHealth.mockResolvedValue({
      score: 90, cookie_valid: true, api_reachable: true, page_accessible: true, waf_status: 'ok',
    })
    wrap(<MobileAntiCrawl />)
    await waitFor(() => expect(screen.getByText(/会话状态加载失败/)).toBeInTheDocument())
    expect(screen.getByText('状态未知')).toBeInTheDocument()
    expect(screen.queryByText('未激活')).not.toBeInTheDocument()
    // 另一路成功：健康数据照常显示，不该被会话失败带成红叉
    expect(screen.getByText('90')).toBeInTheDocument()
  })

  it('健康接口失败：三项检查不再渲染成 ✗', async () => {
    mocks.antiSession.mockResolvedValue({ active: true, strategy: 'default', cookie_layers: {} })
    mocks.antiHealth.mockRejectedValue(new Error('boom'))
    wrap(<MobileAntiCrawl />)
    await waitFor(() => expect(screen.getByText(/健康报告加载失败/)).toBeInTheDocument())
    expect(screen.getByText('健康数据不可用')).toBeInTheDocument()
    expect(document.body.textContent).not.toContain('API ✗')
    expect(screen.getByText('运行中')).toBeInTheDocument()
  })
})

describe('移动端批量采集页（T02718）', () => {
  it('状态接口失败：不显示 IDLE，保存配置被禁用；重试成功后恢复', async () => {
    mocks.batchStatus
      .mockRejectedValueOnce(new Error('boom'))
      .mockResolvedValue({ status: 'idle', interval_minutes: 30, enabled: false, change_log: [] })
    wrap(<MobileBatchRefresh />)
    await waitFor(() => expect(screen.getByText(/调度状态加载失败/)).toBeInTheDocument())
    expect(screen.queryByText('IDLE')).not.toBeInTheDocument()
    expect(screen.getByText('状态未知')).toBeInTheDocument()
    const save = screen.getByRole('button', { name: /保存配置/ })
    expect(save).toBeDisabled()

    await userEvent.click(screen.getByRole('button', { name: /重\s*试/ }))
    await waitFor(() => expect(screen.getByText('IDLE')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /保存配置/ })).toBeEnabled()
  })
})

describe('移动端数据库维护页（T02718）', () => {
  it('表列表失败：给错误条，空下拉不再等于「没有表」', async () => {
    mocks.dbTables.mockRejectedValue(new Error('boom'))
    wrap(<MobileDatabaseAdmin />)
    await waitFor(() => expect(screen.getByText(/数据表列表加载失败/)).toBeInTheDocument())
  })
})

describe('移动端商品页（T02718）', () => {
  it('任务列表失败：给错误条，不再只打 console.warn', async () => {
    mocks.taskList.mockRejectedValue(new Error('boom'))
    wrap(<MobileItems />)
    await waitFor(() => expect(screen.getByText(/任务列表加载失败/)).toBeInTheDocument())
  })
})
