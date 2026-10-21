/**
 * 异常雷达逐条跳转（T02828）
 *
 * 钉住的行为：三类条目都落到「已经按本条告警筛好的子集」，参数口径与顶栏抽屉同源
 * （utils/alertDeepLink.ts）。此前雷达整块跳 `/orders?ref=<id>`，不带状态筛选，
 * 落地还是全量列表；低分评估更是纯文本，点不动。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { TodayAlert } from '../../../api'

const { openSheetMock } = vi.hoisted(() => ({ openSheetMock: vi.fn() }))
vi.mock('../../../components/SheetWorkspace/sheetNotifications', () => ({
  openSheetWithNotification: openSheetMock,
}))

import AlertRadar from '../components/AlertRadar'

const alertData: TodayAlert = {
  today: { orders: 4, events: 12, succeeded: 1, failed: 2 },
  ts: '2026-10-21T06:51:00',
  alerts: {
    counts: { failed: 1, timeout: 1, low_eval: 2 },
    failed_orders: [{ id: '91', item_id: 'itm-1', price: 50, status: 'failed', created_at: '2026-10-21T05:40:07' }],
    timeout_pending: [{ id: '92', item_id: 'itm-2', price: 12.5, status: 'pending_pay', created_at: '2026-10-21T05:40:00', age_sec: 4270 }],
    low_evaluations: [
      { id: 7, message: '商品评分偏低', type: 'eval.scored', created_at: '2026-10-21T05:39:00', score_value: 0.42, item_id: 'itm-3' },
      { id: 8, message: '缺商品 id 的历史事件', type: 'eval.scored', created_at: '2026-10-21T05:38:00', score_value: 0.1 },
    ],
  },
}

function renderRadar(data: TodayAlert = alertData) {
  return render(
    <MemoryRouter>
      <AlertRadar alertData={data} alertOpen onToggle={() => {}} onReload={() => {}} />
    </MemoryRouter>,
  )
}

/** 拆开断言，避免把参数拼接顺序写死成第二条口径 */
function jumpTarget(path: string) {
  const [pathname, query = ''] = path.split('?')
  return { pathname, params: new URLSearchParams(query) }
}

beforeEach(() => {
  openSheetMock.mockClear()
})

describe('异常雷达逐条深链（T02828）', () => {
  it('失败订单带 status=failed，而不只是 ref', () => {
    renderRadar()
    fireEvent.click(screen.getByText(/订单 #91/))
    expect(openSheetMock).toHaveBeenCalledTimes(1)
    const { pathname, params } = jumpTarget(openSheetMock.mock.calls[0][0])
    expect(pathname).toBe('/orders')
    expect(params.get('status')).toBe('failed')
    expect(params.get('ref')).toBe('91')
  })

  it('超时待支付落到「待支付」筛选，而不是全量列表', () => {
    renderRadar()
    fireEvent.click(screen.getByText(/订单 #92/))
    const { pathname, params } = jumpTarget(openSheetMock.mock.calls[0][0])
    expect(pathname).toBe('/orders')
    expect(params.get('status')).toBe('pending_pay')
    expect(params.get('ref')).toBe('92')
  })

  it('低分评估跳评估明细，带 item_id 与换算后的 score_max', () => {
    renderRadar()
    fireEvent.click(screen.getByText(/商品评分偏低/))
    const { pathname, params } = jumpTarget(openSheetMock.mock.calls[0][0])
    expect(pathname).toBe('/evaluations')
    expect(params.get('item_id')).toBe('itm-3')
    // 告警里是 0–1 归一分，评估页的 max_score 是 0–100
    expect(params.get('score_max')).toBe('42')
  })

  it('历史事件没有 item_id 时不给链接：与其把用户丢进全量评估页，不如不跳', () => {
    renderRadar()
    const row = screen.getByText(/缺商品 id 的历史事件/)
    expect(row.closest('button')).toBeNull()
    fireEvent.click(row)
    expect(openSheetMock).not.toHaveBeenCalled()
  })

  // 上面两条订单用例的条目都自带合法 status，会盖掉「本栏兜底值」，
  // 所以把超时栏误接到 failed 口径也能绿——这条专门钉住兜底分支。
  it('条目 status 是脏值时，退回本栏兜底口径（超时栏兜底必须是 pending_pay）', () => {
    const dirty: TodayAlert = {
      ...alertData,
      alerts: {
        ...alertData.alerts,
        timeout_pending: [{ ...alertData.alerts.timeout_pending[0], status: 'WAITING_PAY' }],
      },
    }
    renderRadar(dirty)
    fireEvent.click(screen.getByText(/订单 #92/))
    const { pathname, params } = jumpTarget(openSheetMock.mock.calls[0][0])
    expect(pathname).toBe('/orders')
    // 兜底值与后端超时告警的 WHERE 同源；写成 failed 落地就是空列表
    expect(params.get('status')).toBe('pending_pay')
    expect(params.get('ref')).toBe('92')
  })
})
