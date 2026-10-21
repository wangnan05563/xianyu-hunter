// T02700：三态二选一的区块组件。
// 钉住的核心是「失败」与「空态」互斥 —— 原写法 list.length === 0 ? Empty : Table 配合
// catch(() => []) 会让接口失败伪装成「暂无××」，只断言错误态出现并不够，必须同时断言空态不出现。
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import DataBlock from '../DataBlock'

describe('DataBlock 错误态/空态/内容三态互斥（T02700）', () => {
  it('失败时只给错误态与重试，绝不落到空态', () => {
    const onRetry = vi.fn()
    render(
      <DataBlock failed source="FAQ 列表" count={0} emptyText="暂无 FAQ" onRetry={onRetry}>
        <div>表格内容</div>
      </DataBlock>,
    )
    expect(screen.getByText('FAQ 列表加载失败')).toBeInTheDocument()
    // 关键断言：空态文案不能与错误态同时出现，否则读者仍会把故障读成「没有数据」
    expect(screen.queryByText('暂无 FAQ')).not.toBeInTheDocument()
    expect(screen.queryByText('表格内容')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /重\s*试/ }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('取到 0 条时才是空态，且不出现错误文案', () => {
    render(
      <DataBlock failed={false} source="FAQ 列表" count={0} emptyText="暂无 FAQ">
        <div>表格内容</div>
      </DataBlock>,
    )
    expect(screen.getByText('暂无 FAQ')).toBeInTheDocument()
    expect(screen.queryByText(/加载失败/)).not.toBeInTheDocument()
  })

  it('有数据时渲染 children，count 未传也按 children 处理', () => {
    render(
      <DataBlock failed={false} source="运行历史" emptyText="暂无运行记录">
        <div>图表</div>
      </DataBlock>,
    )
    expect(screen.getByText('图表')).toBeInTheDocument()
    expect(screen.queryByText('暂无运行记录')).not.toBeInTheDocument()
  })
})
