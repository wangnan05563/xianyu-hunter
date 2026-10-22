// frontend/src/pages/Evaluations/__tests__/evaluationsLoginEntry.test.tsx
// 评审 2.4-10：数据不足 Alert 只写「去 Dashboard 重新登录」，用户要自己跳两次。
// 钉住：Alert 内有「前往登录」直达按钮，落到 /login?redirect=/evaluations；
// 文案同时说明重新评估不调 AI、不发通知（T02567 的二次确认口径）。
import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'

const { listMock, distMock, taskListMock } = vi.hoisted(() => ({
  listMock: vi.fn(),
  distMock: vi.fn(),
  taskListMock: vi.fn(),
}))

vi.mock('../../../api', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  const evalApi = (actual as { evalApi: Record<string, unknown> }).evalApi
  const taskApi = (actual as { taskApi: Record<string, unknown> }).taskApi
  return {
    ...actual,
    evalApi: {
      ...evalApi,
      list: listMock,
      distribution: distMock,
      thresholdSuggestion: vi.fn(),
      sellerTrend: vi.fn().mockResolvedValue({ points: [] }),
    },
    taskApi: { ...taskApi, list: taskListMock },
  }
})

vi.mock('../../../components/charts/EChart', () => ({ default: () => null }))

import Evaluations from '../index'

const DIST = {
  buckets: [],
  marginals: { price: [], score: [], result: { pass: 0, auto: 0, fail: 0 } },
  distribution: [],
  suggested_threshold: { score: 70, pass_rate: 0.5 },
  total: 3,
  insufficient_count: 3,
  price_range: [0, 0] as [number, number],
  thresholds: { pass_score: 60, auto_buy_score: 80 },
}

function LoginProbe() {
  const loc = useLocation()
  const redirect = new URLSearchParams(loc.search).get('redirect')
  return <div>{`LOGIN_STUB:${loc.pathname}:${redirect}`}</div>
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/evaluations']}>
      <Routes>
        <Route path="/evaluations" element={<Evaluations />} />
        <Route path="/login" element={<LoginProbe />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeAll(() => {
  Element.prototype.scrollIntoView = () => {}
})

beforeEach(() => {
  localStorage.clear()
  listMock.mockReset()
  distMock.mockReset()
  taskListMock.mockReset()
  listMock.mockResolvedValue({ items: [], count: 0, total: 0 })
  distMock.mockResolvedValue(DIST)
  taskListMock.mockResolvedValue({ items: [], count: 0, total: 0 })
})

describe('评估页数据不足提示的登录直达（评审 2.4-10）', () => {
  it('Alert 内有「前往登录」，点击后带 redirect 落到登录页', async () => {
    renderPage()
    expect(await screen.findByText(/有 3 条评估记录因卖家信息缺失仅基于价格评估/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /前往登录/ }))
    await waitFor(() =>
      expect(screen.getByText('LOGIN_STUB:/login:/evaluations')).toBeInTheDocument(),
    )
  }, 15000)

  it('文案说明重算不调 AI、不发通知，用户知道登录后点重新评估的代价', async () => {
    renderPage()
    expect(await screen.findByText(/不调用 AI、不产生接口费用，也不发送通知/)).toBeInTheDocument()
  })
})
