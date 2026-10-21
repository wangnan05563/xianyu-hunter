// T02701：窄屏失败条的行为契约 —— 它是错误态，不是空态，且必须可重试
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import LoadFailedBar from '../LoadFailedBar'

describe('LoadFailedBar（移动端单行失败态）', () => {
  it('报出是哪个数据源失败，并声明本区块数字不可信', () => {
    render(<LoadFailedBar source="成交统计" />)
    const alert = screen.getByRole('alert')
    expect(alert.textContent).toContain('成交统计加载失败')
    expect(alert.textContent).toContain('本区块数字不代表真实状态')
  })

  it('有 onRetry 时提供重试入口并回调', async () => {
    const onRetry = vi.fn()
    render(<LoadFailedBar source="分类分布" onRetry={onRetry} />)
    await userEvent.click(screen.getByRole('button', { name: /重\s*试/ }))
    expect(onRetry).toHaveBeenCalledOnce()
  })

  it('无 onRetry 时不渲染重试按钮（离线只读场景）', () => {
    render(<LoadFailedBar source="任务列表" />)
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('note 覆盖默认的「数字不可信」措辞，用于说明数据到底是哪来的', () => {
    render(<LoadFailedBar source="列定义" note="以下选项是内置兜底列表" />)
    const text = screen.getByRole('alert').textContent || ''
    expect(text).toContain('以下选项是内置兜底列表')
    expect(text).not.toContain('本区块数字不代表真实状态')
  })

  it('保持单行结构：不套桌面端 message + description 的两块布局', () => {
    render(<LoadFailedBar source="成交统计" onRetry={() => undefined} />)
    const alert = screen.getByRole('alert')
    // 换成 antd Alert / 加 description 区块后这里会出现嵌套 div，窄屏就要换行
    expect(alert.querySelectorAll('div')).toHaveLength(0)
    expect(alert.children).toHaveLength(3)
  })
})
