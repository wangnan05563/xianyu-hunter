/**
 * 告警雷达时间口径同源（T02695）
 *
 * 钉住的行为：同一份 TodayAlert 载荷在雷达里必须与顶栏抽屉说同一种话——
 * 绝对时间走 formatDateTime、相对时长走 formatDuration，不再出现裸秒或「N 分钟前」。
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import AlertRadar from '../components/AlertRadar'
import type { TodayAlert } from '../../../api'

const alertData: TodayAlert = {
  today: { orders: 3, events: 10, succeeded: 1, failed: 1 },
  ts: '2026-10-19T06:51:00',
  alerts: {
    counts: { failed: 1, timeout: 1, low_eval: 1 },
    failed_orders: [{ id: '91', item_id: 'itm-1', price: 50, status: 'failed', created_at: '2026-10-19T05:40:07.728251' }],
    timeout_pending: [{ id: '92', item_id: 'itm-2', price: 12.5, status: 'pending_pay', created_at: '2026-10-19T05:40:00', age_sec: 4270 }],
    low_evaluations: [{ id: 7, message: '', type: 'eval.scored', created_at: '2026-10-19T05:39:00', score_value: 0.31 }],
  },
}

function renderRadar() {
  return render(
    <MemoryRouter>
      <AlertRadar alertData={alertData} alertOpen onToggle={() => {}} onReload={() => {}} />
    </MemoryRouter>,
  )
}

describe('AlertRadar 时间/时长展示（T02695）', () => {
  it('超时项说「1 小时 11 分」，页面上找不到裸秒', () => {
    renderRadar()
    expect(screen.getByText(/超时 1 小时 11 分/)).toBeTruthy()
    expect(screen.queryByText(/4270s/)).toBeNull()
    expect(screen.queryByText(/分钟前/)).toBeNull()
  })

  it('低分项时间走本地格式，不切 ISO 子串', () => {
    const { container } = renderRadar()
    const text = container.textContent || ''
    expect(text).not.toContain('T05:39')
    expect(text).toMatch(/2026\/10\/19/)
  })

  it('事件类型显示中文而不是落库原文', () => {
    const { container } = renderRadar()
    const text = container.textContent || ''
    // 低分项的 message 为空时才用类型名兜底，且整行文本跨节点，按整页文本断言
    expect(text).toContain('商品评分')
    expect(text).not.toContain('eval.scored')
  })
})
