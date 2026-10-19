// frontend/src/__tests__/dangerSummary.test.tsx
// T02573《危险操作文案规范》的可执行断言：四要素必须全部出现，
// 且「数量」在拿不到统计值时必须显式说明未知，而不是省略或退化成 0。
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import DangerSummary, {
  COUNT_UNKNOWN,
  DANGER_FIELD_LABELS,
  missingDangerFields,
} from '../components/DangerSummary'

const BASE = {
  action: '删除 12 个 __pycache__ 目录',
  scope: '仅 Python 字节码缓存；不包含数据库与 ./browser-data 登录态目录',
  count: '12 个目录（3.4 MB）',
  recovery: '不可恢复；字节码会在下次运行时自动重建',
}

describe('DangerSummary 四要素', () => {
  it('四个标签按规范全部渲染', () => {
    render(<DangerSummary {...BASE} />)
    for (const label of DANGER_FIELD_LABELS) {
      expect(screen.getByText(`${label}：`)).toBeTruthy()
    }
  })

  it('每条要素的内容文本都可见', () => {
    render(<DangerSummary {...BASE} />)
    expect(screen.getByText(BASE.action)).toBeTruthy()
    expect(screen.getByText(BASE.scope)).toBeTruthy()
    expect(screen.getByText(BASE.count)).toBeTruthy()
    expect(screen.getByText(BASE.recovery)).toBeTruthy()
  })

  it('数量为 null/空串时显示「未能预先统计」，不能整行消失', () => {
    const { rerender } = render(<DangerSummary {...BASE} count={null} />)
    expect(screen.getByText(COUNT_UNKNOWN)).toBeTruthy()
    rerender(<DangerSummary {...BASE} count="" />)
    expect(screen.getByText(COUNT_UNKNOWN)).toBeTruthy()
    expect(screen.getByText('数量：')).toBeTruthy()
  })

  it('数量真实为 0 时照常显示 0（0 是有效统计值，不等于未知）', () => {
    render(<DangerSummary {...BASE} count={0} />)
    expect(screen.getByText('0')).toBeTruthy()
    expect(screen.queryByText(COUNT_UNKNOWN)).toBeNull()
  })

  it('缺动作/范围/恢复成本时被判定为不合规（数量允许未知）', () => {
    expect(missingDangerFields({ ...BASE, action: '  ' })).toEqual(['动作'])
    expect(missingDangerFields({ ...BASE, scope: '' })).toEqual(['影响范围'])
    expect(missingDangerFields({ ...BASE, recovery: '' })).toEqual(['恢复成本'])
    expect(missingDangerFields({ ...BASE, count: null })).toEqual([])
  })
})
