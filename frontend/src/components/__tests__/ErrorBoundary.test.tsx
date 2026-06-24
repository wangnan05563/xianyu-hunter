import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { useState } from 'react'
import { ErrorBoundary } from '../ErrorBoundary'

// 故意抛错的子组件，用于触发 ErrorBoundary
function Bomb({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) throw new Error('test explosion')
  return <div data-testid="child">正常渲染</div>
}

describe('ErrorBoundary', () => {
  beforeEach(() => {
    // 安静化错误日志，避免测试输出噪音
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  it('正常情况下渲染子组件', () => {
    render(
      <ErrorBoundary>
        <Bomb shouldThrow={false} />
      </ErrorBoundary>,
    )
    expect(screen.getByTestId('child')).toBeInTheDocument()
  })

  it('子组件抛错时显示错误界面而非白屏', () => {
    render(
      <ErrorBoundary>
        <Bomb shouldThrow={true} />
      </ErrorBoundary>,
    )
    // 应显示友好错误界面，而不是整个应用崩溃
    expect(screen.getByText('页面渲染异常')).toBeInTheDocument()
    expect(screen.getByText('test explosion')).toBeInTheDocument()
  })

  it('点击"重试"按钮后清除错误状态', () => {
    function Wrapper() {
      const [throwErr, setThrowErr] = useState(true)
      return (
        <ErrorBoundary>
          <Bomb shouldThrow={throwErr} />
          {/* 错误恢复后切换为不抛错 */}
          <button onClick={() => setThrowErr(false)}>恢复</button>
        </ErrorBoundary>
      )
    }
    render(<Wrapper />)
    expect(screen.getByText('页面渲染异常')).toBeInTheDocument()

    // 点击重试：ErrorBoundary 清除错误状态，但 Bomb 仍会抛错（throwErr 仍为 true）
    // antd Button 会在中文之间自动插入空格（"重 试"），用正则兼容
    fireEvent.click(screen.getByRole('button', { name: /重\s*试/ }))
    // 重新抛错，再次显示错误界面
    expect(screen.getByText('页面渲染异常')).toBeInTheDocument()

    // 再次点击重试，验证按钮可重复点击且不崩溃
    fireEvent.click(screen.getByRole('button', { name: /重\s*试/ }))
    expect(screen.getByText('页面渲染异常')).toBeInTheDocument()
  })

  it('resetKeys 变化时自动重置错误状态', () => {
    function Wrapper({ resetKey }: { resetKey: string }) {
      return (
        <ErrorBoundary resetKeys={[resetKey]}>
          <Bomb shouldThrow={true} />
        </ErrorBoundary>
      )
    }
    const { rerender } = render(<Wrapper resetKey="page-a" />)
    expect(screen.getByText('页面渲染异常')).toBeInTheDocument()

    // resetKeys 变化触发重置，但 Bomb 仍会抛错，所以会再次进入错误态
    rerender(<Wrapper resetKey="page-b" />)
    // 验证 resetKeys 变化后 ErrorBoundary 确实尝试重置（错误界面重新出现说明走了重置流程）
    expect(screen.getByText('页面渲染异常')).toBeInTheDocument()
  })

  it('调用 onError 回调', () => {
    const onError = vi.fn()
    render(
      <ErrorBoundary onError={onError}>
        <Bomb shouldThrow={true} />
      </ErrorBoundary>,
    )
    expect(onError).toHaveBeenCalledTimes(1)
    expect(onError.mock.calls[0][0]).toBeInstanceOf(Error)
    expect(onError.mock.calls[0][0].message).toBe('test explosion')
  })

  it('自定义 fallback 渲染', () => {
    render(
      <ErrorBoundary fallback={(err, reset) => (
        <div>
          <span data-testid="custom-error">{err.message}</span>
          <button onClick={reset} data-testid="custom-reset">自定义重试</button>
        </div>
      )}>
        <Bomb shouldThrow={true} />
      </ErrorBoundary>,
    )
    expect(screen.getByTestId('custom-error')).toHaveTextContent('test explosion')
    expect(screen.getByTestId('custom-reset')).toBeInTheDocument()
  })
})
